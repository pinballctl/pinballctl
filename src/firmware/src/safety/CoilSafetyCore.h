#ifndef PINBALLCTL_COIL_SAFETY_CORE_H
#define PINBALLCTL_COIL_SAFETY_CORE_H
#include <stdint.h>
#ifndef COIL_IRAM
#define COIL_IRAM
#endif

// Allocation-free policy shared by interrupt code and native regression tests.
// The platform adapter serializes every call. ON/OFF is logical, not electrical.
namespace coil_safety {
constexpr int kPins = 49;
enum class Mode { Pulse, Pwm, Dual, Continuous, Hold };
struct Limit {
  uint32_t max_on_ms = 0, min_off_ms = 0;
  bool off_high = false, enabled = false;
  Mode mode = Mode::Pulse;
  uint32_t pulse_ms = 10, max_hold_ms = 1000;
  uint32_t hold_duty = 0, pwm_hz = 100;
  int hold_pin = -1;
};
struct Channel {
  Limit limit;
  bool active = false, holding = false, pulse_only = false;
  uint32_t since = 0, off_since = 0, pulse_ms = 0;
};
enum class Fault { None, MaxOn, HostLost, LoopStalled, Cooldown, Configuration, MaxHold, InvalidRequest };
class Core {
 public:
  Channel pins[kPins];
  bool armed = false;
  Fault fault = Fault::None;
  uint32_t host_at = 0, loop_at = 0, generation = 1;
  bool host_seen = false;
  using Write = void (*)(int, bool);
  explicit Core(Write write) : write_(write) {}
  COIL_IRAM bool configured(int pin) const { return pin >= 0 && pin < kPins && pins[pin].limit.max_on_ms; }
  COIL_IRAM void offChannel(int pin, uint32_t now) {
    auto& c = pins[pin];
    write_(pin, c.limit.off_high);
    if (c.active) { c.active = false; c.off_since = now; }
    c.holding = false;
  }
  COIL_IRAM void disable(uint32_t now) {
    armed = false;
    ++generation;
    for (int i = 0; i < kPins; ++i) if (configured(i)) offChannel(i, now);
  }
  COIL_IRAM void trip(Fault reason, uint32_t now) {
    if (fault == Fault::None) fault = reason;
    disable(now);
  }
  COIL_IRAM int owner(int pin) const {
    for (int i=0; i<kPins; ++i)
      if (configured(i) && pins[i].limit.mode==Mode::Dual && pins[i].limit.hold_pin==pin) return i;
    return pin;
  }
  COIL_IRAM void off(int pin, uint32_t now) {
    pin = owner(pin);
    offChannel(pin, now);
    const auto& limit = pins[pin].limit;
    if (limit.mode==Mode::Dual && configured(limit.hold_pin)) offChannel(limit.hold_pin, now);
  }
  COIL_IRAM void tick(uint32_t now) {
    if (!armed) return;
    if (!host_seen || uint32_t(now-host_at)>=1000) { trip(Fault::HostLost,now); return; }
    if (uint32_t(now-loop_at)>=500) { trip(Fault::LoopStalled,now); return; }
    for (int i=0; i<kPins; ++i) {
      auto& c=pins[i];
      if (!c.active || c.limit.mode==Mode::Hold) continue;
      uint32_t elapsed=uint32_t(now-c.since);
      if (c.pulse_only) {
        // Normal pulse expiry is not a fault. Invalid requests never energize.
        if (elapsed>c.limit.max_on_ms) { trip(Fault::MaxOn,now); return; }
        if (elapsed>=c.pulse_ms) off(i,now);
        continue;
      }
      if (c.limit.mode==Mode::Continuous) {
        if (elapsed>=c.limit.max_hold_ms) { trip(Fault::MaxHold,now); return; }
        continue;
      }
      if (elapsed>=c.pulse_ms+c.limit.max_hold_ms) { trip(Fault::MaxHold,now); return; }
      if (!c.holding) {
        if (elapsed>c.limit.max_on_ms) { trip(Fault::MaxOn,now); return; }
        if (elapsed>=c.pulse_ms) {
          write_(i,c.limit.off_high);
          c.holding=true;
          if (c.limit.mode==Mode::Dual) {
            int h=c.limit.hold_pin;
            write_(h,!pins[h].limit.off_high);
            pins[h].holding=true;
          }
        } else if (elapsed>=c.limit.max_on_ms) { trip(Fault::MaxOn,now); return; }
      }
    }
  }
  // 100 us interrupt cadence; frequencies and duty steps are validated so all
  // supported waveforms have integral tick periods. No PWM state in the main loop.
  COIL_IRAM void pwmTick(uint32_t now_us) {
    if (!armed) return;
    for (int i=0; i<kPins; ++i) {
      const auto& c=pins[i];
      if (!c.active || !c.holding || c.limit.mode!=Mode::Pwm) continue;
      uint32_t period=1000000U/c.limit.pwm_hz;
      bool on=(now_us % period)<(period*c.limit.hold_duty/100U);
      write_(i,on ? !c.limit.off_high : c.limit.off_high);
    }
  }
  bool enable(uint32_t token, uint32_t now) {
    tick(now);
    if (armed) return token==generation;
    if (token!=generation || fault!=Fault::None || !host_seen || uint32_t(now-host_at)>=500) return false;
    bool any=false;
    for (int i=0; i<kPins; ++i) if (configured(i) && pins[i].limit.enabled) {
      any |= pins[i].limit.mode!=Mode::Hold;
      if (uint32_t(now-pins[i].off_since)<pins[i].limit.min_off_ms) return false;
    }
    if (!any) return false;
    loop_at=now; armed=true; return true;
  }
  bool start(int pin, uint32_t duration, bool pulse_only, uint32_t now) {
    tick(now);
    if (!configured(pin) || !armed || fault!=Fault::None) return false;
    auto& c=pins[pin];
    if (!c.limit.enabled || c.limit.mode==Mode::Hold) return false;
    if (!duration || ((pulse_only || c.limit.mode!=Mode::Continuous) && duration>c.limit.max_on_ms)) { trip(Fault::InvalidRequest,now); return false; }
    if (c.active) return true; // Repeated activation never restarts any deadline.
    int h=c.limit.mode==Mode::Dual ? c.limit.hold_pin : -1;
    if (h>=0 && (!configured(h) || !pins[h].limit.enabled || pins[h].limit.mode!=Mode::Hold)) {
      trip(Fault::Configuration,now); return false;
    }
    if (uint32_t(now-c.off_since)<c.limit.min_off_ms ||
        (h>=0 && uint32_t(now-pins[h].off_since)<pins[h].limit.min_off_ms)) {
      trip(Fault::Cooldown,now); return false;
    }
    c.since=now; c.pulse_ms=duration; c.pulse_only=pulse_only; c.holding=false; c.active=true;
    if (h>=0) { pins[h].active=true; pins[h].since=now; write_(h,pins[h].limit.off_high); }
    write_(pin,!c.limit.off_high);
    return true;
  }
  bool pulse(int pin,uint32_t duration,uint32_t now) { return start(pin,duration,true,now); }
  bool write(int pin, bool on, uint32_t now) {
    tick(now);
    if (!configured(pin)) return false;
    if (!on) { off(pin,now); return true; }
    return start(pin,pins[pin].limit.pulse_ms,pins[pin].limit.mode==Mode::Pulse,now);
  }
 private:
  Write write_;
};
}
#endif
