#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <ArduinoJson.h>
#include <LittleFS.h>
#include <stdlib.h>

#include "drivers/Accelerometer/MMA8452.h"

namespace {
constexpr const char* kAccelRuntimePath = "/cfg/accelerometer.runtime.json";

bool parseIntValue(JsonVariantConst v, int* out) {
  if (!out) return false;
  if (v.is<int>()) {
    *out = v.as<int>();
    return true;
  }
  if (v.is<unsigned int>()) {
    *out = static_cast<int>(v.as<unsigned int>());
    return true;
  }
  if (v.is<const char*>()) {
    String s = String(v.as<const char*>());
    s.trim();
    if (!s.length()) return false;
    char* end_ptr = nullptr;
    long parsed = strtol(s.c_str(), &end_ptr, 0);
    if (!end_ptr || *end_ptr != '\0') return false;
    *out = static_cast<int>(parsed);
    return true;
  }
  return false;
}

bool parseFloatValue(JsonVariantConst v, float* out) {
  if (!out) return false;
  if (v.is<float>()) {
    *out = v.as<float>();
    return true;
  }
  if (v.is<double>()) {
    *out = static_cast<float>(v.as<double>());
    return true;
  }
  if (v.is<int>()) {
    *out = static_cast<float>(v.as<int>());
    return true;
  }
  if (v.is<const char*>()) {
    String s = String(v.as<const char*>());
    s.trim();
    if (!s.length()) return false;
    char* end_ptr = nullptr;
    const double parsed = strtod(s.c_str(), &end_ptr);
    if (!end_ptr || *end_ptr != '\0') return false;
    *out = static_cast<float>(parsed);
    return true;
  }
  return false;
}

bool parseAccelConfigs(const String& line, std::vector<AccelerometerMMA8452::Config>* out, String* error) {
  if (!out) {
    if (error) *error = "out_required";
    return false;
  }
  out->clear();
  DynamicJsonDocument doc(8192);
  DeserializationError e = deserializeJson(doc, line);
  if (e) {
    if (error) *error = "invalid_json";
    return false;
  }
  JsonArray configs = doc["configs"].as<JsonArray>();
  if (configs.isNull()) {
    if (error) *error = "configs_required";
    return false;
  }
  for (JsonVariantConst v : configs) {
    if (!v.is<JsonObjectConst>()) continue;
    JsonObjectConst o = v.as<JsonObjectConst>();
    AccelerometerMMA8452::Config cfg;
    cfg.source = String(o["source"] | "");
    cfg.source.trim();
    if (!cfg.source.length()) {
      if (error) *error = "source_required";
      return false;
    }
    int sda = -1;
    int scl = -1;
    if (!parseIntValue(o["sdaPin"], &sda) || !parseIntValue(o["sclPin"], &scl)) {
      if (error) *error = "pins_required";
      return false;
    }
    cfg.sda_pin = sda;
    cfg.scl_pin = scl;

    int addr = 0x1C;
    if (parseIntValue(o["i2cAddress"], &addr) || parseIntValue(o["address"], &addr)) {
      // Parsed.
    }
    if (addr < 0x03 || addr > 0x77) addr = 0x1C;
    cfg.i2c_addr = static_cast<uint8_t>(addr);

    int sens_mg = 350;
    if (parseIntValue(o["tiltSensitivityMg"], &sens_mg)) {
      if (sens_mg < 50) sens_mg = 50;
      if (sens_mg > 4000) sens_mg = 4000;
    }
    cfg.tilt_sensitivity_g = static_cast<float>(sens_mg) / 1000.0f;

    int lift_deg = 20;
    if (parseIntValue(o["liftAngleDeg"], &lift_deg)) {
      if (lift_deg < 5) lift_deg = 5;
      if (lift_deg > 89) lift_deg = 89;
    }
    cfg.lift_angle_deg = static_cast<float>(lift_deg);

    int hyst_deg = 5;
    if (parseIntValue(o["liftHysteresisDeg"], &hyst_deg)) {
      if (hyst_deg < 1) hyst_deg = 1;
      if (hyst_deg > 30) hyst_deg = 30;
    }
    cfg.lift_hysteresis_deg = static_cast<float>(hyst_deg);

    int sample_ms = 25;
    if (parseIntValue(o["sampleMs"], &sample_ms)) {
      if (sample_ms < 10) sample_ms = 10;
      if (sample_ms > 1000) sample_ms = 1000;
    }
    cfg.sample_ms = static_cast<uint16_t>(sample_ms);

    int cooldown_ms = 150;
    if (parseIntValue(o["tiltCooldownMs"], &cooldown_ms)) {
      if (cooldown_ms < 20) cooldown_ms = 20;
      if (cooldown_ms > 5000) cooldown_ms = 5000;
    }
    cfg.tilt_cooldown_ms = static_cast<uint16_t>(cooldown_ms);

    String mount = String(o["mountDirection"] | "Normal");
    mount.trim();
    cfg.inverted = mount.equalsIgnoreCase("Inverted");

    float bx = 0.0f;
    float by = 0.0f;
    float bz = 1.0f;
    bool has_baseline =
        parseFloatValue(o["baselineX"], &bx) &&
        parseFloatValue(o["baselineY"], &by) &&
        parseFloatValue(o["baselineZ"], &bz);
    if (!has_baseline) {
      JsonObjectConst baseline = o["baseline"].as<JsonObjectConst>();
      if (!baseline.isNull()) {
        has_baseline =
            parseFloatValue(baseline["x"], &bx) &&
            parseFloatValue(baseline["y"], &by) &&
            parseFloatValue(baseline["z"], &bz);
      }
    }
    if (has_baseline) {
      const float mag = sqrtf((bx * bx) + (by * by) + (bz * bz));
      if (mag > 0.001f) {
        cfg.has_calibration = true;
        cfg.baseline_x = bx / mag;
        cfg.baseline_y = by / mag;
        cfg.baseline_z = bz / mag;
      }
    }
    out->push_back(cfg);
  }
  return true;
}
}  // namespace

bool ProtocolHandler::handleHardwareCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "GET_HW")) {
    streamer_.start();
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "SET_ACCEL_CONFIG")) {
    std::vector<AccelerometerMMA8452::Config> configs;
    String err;
    if (!parseAccelConfigs(line, &configs, &err)) {
      String payload = "{\"t\":\"ACCEL_CONFIG\",\"ok\":false,\"reason\":\"";
      payload += (err.length() ? err : "parse_failed");
      payload += "\"}";
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
      return true;
    }
    if (!AccelerometerMMA8452::setConfigs(configs, &err)) {
      String payload = "{\"t\":\"ACCEL_CONFIG\",\"ok\":false,\"reason\":\"";
      payload += (err.length() ? err : "apply_failed");
      payload += "\"}";
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
      return true;
    }
    if (fs_mounted_) {
      fs::File f = LittleFS.open(kAccelRuntimePath, "w");
      if (f) {
        f.print(line);
        f.close();
      }
    }
    String payload = "{\"t\":\"ACCEL_CONFIG\",\"ok\":true,\"count\":";
    payload += static_cast<uint32_t>(configs.size());
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "ACCEL_STATUS_QUERY")) {
    protocol_support::enqueueWithRetry(
        serial_,
        AccelerometerMMA8452::buildStatusPayload(req_id));
    return true;
  }

  return false;
}

bool ProtocolHandler::handleTimeCommands(const String& line, const String& req_id, const String& cmd) {
  if (!(protocol_support::isCmd(line, cmd, "SYNC_TIME") || line.startsWith("SYNC_TIME"))) return false;

  long epoch = 0;
  uint32_t ts = 0;
  if (protocol_support::extractJsonUint(line, "ts", &ts) && ts > 0) {
    epoch = static_cast<long>(ts);
  }
  int sep = line.indexOf(' ');
  if (epoch <= 0 && sep >= 0) epoch = line.substring(sep + 1).toInt();

  if (system_runtime_.syncTimeEpoch(epoch)) {
    String payload = "{\"t\":\"TIME\",\"status\":\"ok\",\"ts\":";
    payload += epoch;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
  } else {
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"TIME\",\"status\":\"error\",\"reason\":\"bad epoch\"}", req_id));
  }
  return true;
}

void ProtocolHandler::loadAccelerometerFromFsOnBoot() {
  if (!fs_mounted_) return;
  if (!LittleFS.exists(kAccelRuntimePath)) return;
  fs::File f = LittleFS.open(kAccelRuntimePath, "r");
  if (!f) {
    protocol_support::enqueueWithRetry(
        serial_, "{\"t\":\"ACCEL_BOOT\",\"status\":\"error\",\"reason\":\"open_failed\"}");
    return;
  }
  String payload = f.readString();
  f.close();
  std::vector<AccelerometerMMA8452::Config> configs;
  String err;
  if (!parseAccelConfigs(payload, &configs, &err)) {
    String msg = "{\"t\":\"ACCEL_BOOT\",\"status\":\"error\",\"reason\":\"";
    msg += (err.length() ? err : "parse_failed");
    msg += "\"}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  if (!AccelerometerMMA8452::setConfigs(configs, &err)) {
    String msg = "{\"t\":\"ACCEL_BOOT\",\"status\":\"error\",\"reason\":\"";
    msg += (err.length() ? err : "apply_failed");
    msg += "\"}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  String msg = "{\"t\":\"ACCEL_BOOT\",\"status\":\"ok\",\"count\":";
  msg += static_cast<uint32_t>(configs.size());
  msg += "}";
  protocol_support::enqueueWithRetry(serial_, msg);
}
