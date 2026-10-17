#include "safety/CoilSafety.h"
#define COIL_IRAM IRAM_ATTR
#include "safety/CoilSafetyCore.h"
#include <ArduinoJson.h>
#include <LittleFS.h>
#include "hal/gpio_ll.h"
#include "soc/gpio_struct.h"
#include "hardware/PinCatalog.h"

namespace coil_safety {
namespace {
portMUX_TYPE mux = portMUX_INITIALIZER_UNLOCKED;
void IRAM_ATTR level(int pin, bool high) { gpio_ll_set_level(&GPIO, pin, high); }
Core core(level);
bool peripheral[kPins] = {};
bool ready = false;
volatile uint32_t last_tick = 0;
volatile bool tick_seen = false;
uint32_t challenge = 1;
hw_timer_t* timer = nullptr;
constexpr const char* path = "/cfg/coils.json";
void IRAM_ATTR onTimer() {
  portENTER_CRITICAL_ISR(&mux);
  last_tick = millis();
  tick_seen = true;
  core.tick(last_tick);
  core.pwmTick(micros());
  portEXIT_CRITICAL_ISR(&mux);
}
const char* faultName(Fault f) {
  switch(f) {
    case Fault::None: return "none";
    case Fault::MaxOn: return "max_on_exceeded";
    case Fault::HostLost: return "host_watchdog";
    case Fault::LoopStalled: return "firmware_watchdog";
    case Fault::MaxHold: return "max_hold_exceeded";
    case Fault::InvalidRequest: return "invalid_pulse_request";
    case Fault::Cooldown: return "cooldown_violation";
    default: return "configuration";
  }
}
bool allowedPin(int pin) {
  for (size_t i=0;i<PinCatalog::count();++i) {
    const auto& p=PinCatalog::at(i);
    // Exclude board-dependent, boot, USB and flash pins.
    if (p.gpio==pin && String(p.reported)=="GPIO_FREE") return true;
  }
  return false;
}
const char* modeName(Mode mode) {
  switch(mode) {
    case Mode::Pulse: return "pulse";
    case Mode::Pwm: return "pwm";
    case Mode::Dual: return "dual";
    case Mode::Continuous: return "continuous";
    default: return "hold";
  }
}
bool configure(JsonVariantConst configs, bool persist, String* error) {
  disable();
  Limit next[kPins];
  if (!configs.is<JsonArrayConst>() || configs.size() > kPins) { *error="invalid_coils"; return false; }
  for (JsonObjectConst row : configs.as<JsonArrayConst>()) {
    if (!row["pin"].is<int>() || !row["max_on_ms"].is<uint32_t>() ||
        !row["min_off_ms"].is<uint32_t>() || !row["off_high"].is<bool>() || !row["enabled"].is<bool>()) {
      *error="explicit_limits_and_polarity_required"; return false;
    }
    int pin=row["pin"];
    uint32_t maxon=row["max_on_ms"], minoff=row["min_off_ms"];
    if (pin<0 || pin>=kPins || !allowedPin(pin) || peripheral[pin] || next[pin].max_on_ms ||
        maxon<1 || maxon>1000 || minoff<maxon || minoff>60000) {
      *error="invalid_limits_or_pin_conflict"; return false;
    }
    next[pin] = {maxon,minoff,row["off_high"].as<bool>(),row["enabled"].as<bool>()};
    auto& limit=next[pin];
    String mode=row["mode"] | "pulse";
    if (mode=="pulse") limit.mode=Mode::Pulse;
    else if(mode=="pwm") limit.mode=Mode::Pwm;
    else if(mode=="dual") limit.mode=Mode::Dual;
    else if(mode=="continuous") limit.mode=Mode::Continuous;
    else if(mode=="hold") limit.mode=Mode::Hold;
    else { *error="unsupported_mode"; return false; }
    const char* integers[]={"pulse_ms","max_hold_ms","hold_duty","pwm_hz"};
    for (const auto* key:integers) if (!row[key].isNull() && !row[key].is<uint32_t>()) {
      *error="invalid_mode_limits"; return false;
    }
    if (!row["hold_pin"].isNull() && !row["hold_pin"].is<int>()) { *error="invalid_hold_pin"; return false; }
    limit.pulse_ms=row["pulse_ms"] | 10U;
    limit.max_hold_ms=row["max_hold_ms"] | 1000U;
    limit.hold_duty=row["hold_duty"] | 0U;
    limit.pwm_hz=row["pwm_hz"] | 100U;
    limit.hold_pin=row["hold_pin"] | -1;
    bool frequency=limit.pwm_hz==50 || limit.pwm_hz==100 || limit.pwm_hz==250 || limit.pwm_hz==500;
    if (!limit.pulse_ms || limit.pulse_ms>1000 ||
        ((limit.mode==Mode::Pulse || limit.mode==Mode::Pwm || limit.mode==Mode::Dual) && limit.pulse_ms>limit.max_on_ms) || !limit.max_hold_ms || limit.max_hold_ms>60000 ||
        limit.hold_duty>95 || limit.hold_duty%5 || !frequency ||
        (limit.mode==Mode::Pwm && limit.enabled && !limit.hold_duty) ||
        (limit.mode!=Mode::Dual && limit.hold_pin!=-1)) { *error="invalid_mode_limits"; return false; }

  }
  bool owned[kPins]={};
  for (int i=0;i<kPins;++i) if(next[i].max_on_ms && next[i].mode==Mode::Dual) {
    int h=next[i].hold_pin;
    if(h<0 || h>=kPins || h==i || owned[h] || !next[h].max_on_ms || next[h].mode!=Mode::Hold ||
       (next[i].enabled && !next[h].enabled) || next[i].max_hold_ms>next[h].max_hold_ms) {
      *error="invalid_hold_pair"; return false;
    }
    owned[h]=true;
  }
  for (int i=0;i<kPins;++i) if(next[i].max_on_ms && next[i].mode==Mode::Hold && next[i].enabled && !owned[i]) {
    *error="unpaired_hold_winding"; return false;
  }
  // Reservations and polarity cannot change in a live boot: peripherals may
  // retain GPIO ownership internally. Never release a coil to another driver.
  for (int i=0;i<kPins;++i) if (core.configured(i) &&
      (!next[i].max_on_ms || next[i].off_high != core.pins[i].limit.off_high)) {
    *error="cannot_remove_or_reverse_live_coil"; return false;
  }
  if (persist) {
    auto f=LittleFS.open("/cfg/coils.tmp","w");
    if (!f) { *error="storage_unavailable"; return false; }
    size_t expected=measureJson(configs);
    size_t written=serializeJson(configs,f); f.flush(); f.close();
    if (written!=expected || !LittleFS.rename("/cfg/coils.tmp",path)) { *error="save_failed"; return false; }
  }
  for (int i=0;i<kPins;++i) if (next[i].max_on_ms) {
    // Set the latch before enabling output to avoid an active-low glitch.
    level(i,next[i].off_high);
    pinMode(i,OUTPUT);
  }
  portENTER_CRITICAL(&mux);
  if (core.fault==Fault::Configuration) core.fault=Fault::None;
  for (int i=0;i<kPins;++i) if (next[i].max_on_ms) {
    core.pins[i].limit=next[i];
    core.pins[i].active=false;
    core.pins[i].off_since=millis();
  }
  portEXIT_CRITICAL(&mux);
  return true;
}
}
void begin() {
  challenge=esp_random() | 1U;
  core.generation=esp_random() | 1U;
  timer=timerBegin(1000000);
  if (!timer) return;
  timerAttachInterrupt(timer,onTimer);
  timerAlarm(timer,100,true,0);
  ready=true;
}
void load() {
  if (!LittleFS.exists(path)) return;
  auto f=LittleFS.open(path,"r");
  JsonDocument doc;
  String error;
  bool ok=f && f.size()<=8192 && !deserializeJson(doc,f) && configure(doc.as<JsonVariantConst>(),false,&error);
  if (f) f.close();
  if (!ok) { portENTER_CRITICAL(&mux); core.trip(Fault::Configuration,millis()); portEXIT_CRITICAL(&mux); }
}
void loopAlive() { portENTER_CRITICAL(&mux); core.loop_at=millis(); portEXIT_CRITICAL(&mux); }
void disable() { portENTER_CRITICAL(&mux); core.disable(millis()); portEXIT_CRITICAL(&mux); }
bool reserved(int pin) { return core.configured(pin); }
bool claimPeripheral(int pin) {
  if (pin<0 || pin>=kPins || reserved(pin) || core.fault==Fault::Configuration) return false;
  peripheral[pin]=true;
  return true;
}
bool write(int pin,bool on) {
  portENTER_CRITICAL(&mux);
  bool ok=ready && core.write(pin,on,millis());
  portEXIT_CRITICAL(&mux);
  return ok;
}
bool pulse(int pin,uint32_t duration) {
  portENTER_CRITICAL(&mux);
  bool ok=ready && core.pulse(pin,duration,millis());
  portEXIT_CRITICAL(&mux);
  return ok;
}
bool mappingSafe(int pin,bool high) {
  if (core.fault==Fault::Configuration) return true;
  if (!reserved(pin)) return false;
  // Mapping cannot override the independently configured electrical OFF level.
  write(pin,false);
  return true;
}
String command(const String& line) {
  JsonDocument request;
  if (deserializeJson(request,line)) return "";
  String cmd=request["cmd"] | "";
  if (!cmd.startsWith("COIL_") && cmd!="ENABLE" && cmd!="DISABLE") return "";
  bool ok=true;
  String error;
  if (cmd=="COIL_CONFIG") ok=configure(request["coils"],true,&error);
  else {
    portENTER_CRITICAL(&mux);
    uint32_t now=millis();
    core.tick(now);
    if (cmd=="COIL_HEARTBEAT") {
      ok=request["challenge"].is<uint32_t>() && request["challenge"].as<uint32_t>()==challenge;
      if (ok) { core.host_seen=true; core.host_at=now; ++challenge; }
    } else if (cmd=="ENABLE") {
      ok=ready && tick_seen && uint32_t(now-last_tick)<10 && request["generation"].is<uint32_t>() && core.enable(request["generation"],now);
    } else if (cmd=="DISABLE") core.disable(now);
    else if (cmd=="COIL_RESET") {
      ok=!core.armed && ready && core.fault!=Fault::Configuration;
      if(ok) { core.fault=Fault::None; ++core.generation; }
    } else if(cmd!="COIL_STATUS") ok=false;
    portEXIT_CRITICAL(&mux);
  }
  JsonDocument response;
  response["t"]="COIL_STATUS";
  response["ok"]=ok;
  if(request["reqId"].is<const char*>()) response["reqId"]=request["reqId"].as<String>();
  if(error.length()) response["error"]=error;
  // Copy mutable interrupt state under the lock, allocate JSON only afterwards.
  portENTER_CRITICAL(&mux);
  bool armed=core.armed;
  Fault fault=core.fault;
  uint32_t gen=core.generation;
  portEXIT_CRITICAL(&mux);
  response["armed"]=armed; response["fault"]=faultName(fault);
  response["generation"]=gen; response["challenge"]=challenge; response["ready"]=ready;
  auto rows=response["coils"].to<JsonArray>();
  for(int i=0;i<kPins;++i) if(core.configured(i)) {
    auto row=rows.add<JsonObject>(); row["pin"]=i;
    row["max_on_ms"]=core.pins[i].limit.max_on_ms;
    row["min_off_ms"]=core.pins[i].limit.min_off_ms;
    row["off_high"]=core.pins[i].limit.off_high;
    row["enabled"]=core.pins[i].limit.enabled;
    row["mode"]=modeName(core.pins[i].limit.mode);
    row["pulse_ms"]=core.pins[i].limit.pulse_ms;
    row["max_hold_ms"]=core.pins[i].limit.max_hold_ms;
    row["hold_duty"]=core.pins[i].limit.hold_duty;
    row["pwm_hz"]=core.pins[i].limit.pwm_hz;
    row["hold_pin"]=core.pins[i].limit.hold_pin;
  }
  String result; serializeJson(response,result); return result;
}
}
