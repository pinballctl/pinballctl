#include "drivers/Accelerometer/MMA8452.h"

#include <Wire.h>
#include <math.h>

namespace {
constexpr float kRadToDeg = 57.2957795f;
constexpr uint8_t kRegOutXMsb = 0x01;
constexpr uint8_t kRegWhoAmI = 0x0D;
constexpr uint8_t kRegXyzDataCfg = 0x0E;
constexpr uint8_t kRegCtrl1 = 0x2A;
constexpr uint8_t kWhoAmIMma8452 = 0x2A;

struct InstanceState {
  AccelerometerMMA8452::Config cfg;
  bool online = false;
  String last_error;
  unsigned long last_sample_ms = 0;
  unsigned long last_tilt_event_ms = 0;
  float ax_g = 0.0f;
  float ay_g = 0.0f;
  float az_g = 0.0f;
  float prev_ax_g = 0.0f;
  float prev_ay_g = 0.0f;
  float prev_az_g = 0.0f;
  bool has_prev_axes = false;
  float prev_mag_g = 0.0f;
  bool has_prev_mag = false;
  float baseline_x = 0.0f;
  float baseline_y = 0.0f;
  float baseline_z = 1.0f;
  bool has_baseline = false;
  float angle_deg = 0.0f;
  float last_jolt_g = 0.0f;
  bool lifted = false;
  unsigned long lift_candidate_ms = 0;
  uint32_t tilt_count = 0;
  uint32_t lift_count = 0;
};

std::vector<InstanceState> g_instances;
std::vector<AccelerometerMMA8452::Event> g_events;
int g_wire_sda = -1;
int g_wire_scl = -1;

float clampUnit(float v) {
  if (v < -1.0f) return -1.0f;
  if (v > 1.0f) return 1.0f;
  return v;
}

bool ensureWirePins(int sda, int scl, bool force_reinit = false) {
  if (sda < 0 || scl < 0 || sda == scl) return false;
  if (!force_reinit && sda == g_wire_sda && scl == g_wire_scl) return true;
  if (g_wire_sda >= 0 && g_wire_scl >= 0) {
    Wire.end();
    delay(2);
  }
  Wire.begin(sda, scl);
  g_wire_sda = sda;
  g_wire_scl = scl;
  return true;
}

bool writeReg8(uint8_t addr, uint8_t reg, uint8_t value) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

bool readReg8(uint8_t addr, uint8_t reg, uint8_t* out) {
  if (!out) return false;
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(static_cast<int>(addr), 1) != 1) return false;
  *out = Wire.read();
  return true;
}

bool readAxes(uint8_t addr, float* ax_g, float* ay_g, float* az_g) {
  if (!ax_g || !ay_g || !az_g) return false;
  Wire.beginTransmission(addr);
  Wire.write(kRegOutXMsb);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom(static_cast<int>(addr), 6) != 6) return false;
  uint8_t b[6];
  for (uint8_t i = 0; i < 6; ++i) b[i] = Wire.read();

  auto decode12 = [](uint8_t msb, uint8_t lsb) -> int16_t {
    int16_t raw = static_cast<int16_t>((static_cast<uint16_t>(msb) << 8) | static_cast<uint16_t>(lsb));
    raw >>= 4;
    if (raw & 0x0800) raw |= 0xF000;
    return raw;
  };

  const int16_t x = decode12(b[0], b[1]);
  const int16_t y = decode12(b[2], b[3]);
  const int16_t z = decode12(b[4], b[5]);
  // 2g full scale => 1024 counts per g in 12-bit mode.
  *ax_g = static_cast<float>(x) / 1024.0f;
  *ay_g = static_cast<float>(y) / 1024.0f;
  *az_g = static_cast<float>(z) / 1024.0f;
  return true;
}

bool initSensor(InstanceState* state) {
  if (!state) return false;
  // Force I2C re-init on each sensor init attempt so runtime config re-apply
  // can recover from transient bus state without requiring reboot.
  if (!ensureWirePins(state->cfg.sda_pin, state->cfg.scl_pin, true)) {
    state->online = false;
    state->last_error = "invalid_pins";
    return false;
  }
  uint8_t who = 0;
  if (!readReg8(state->cfg.i2c_addr, kRegWhoAmI, &who)) {
    g_wire_sda = -1;
    g_wire_scl = -1;
    state->online = false;
    state->last_error = "whoami_read_failed";
    return false;
  }
  if (who != kWhoAmIMma8452) {
    state->online = false;
    state->last_error = "whoami_mismatch";
    return false;
  }
  if (!writeReg8(state->cfg.i2c_addr, kRegCtrl1, 0x00)) {
    state->online = false;
    state->last_error = "standby_failed";
    return false;
  }
  // 2g range.
  if (!writeReg8(state->cfg.i2c_addr, kRegXyzDataCfg, 0x00)) {
    state->online = false;
    state->last_error = "range_failed";
    return false;
  }
  // Active mode, 800Hz ODR.
  if (!writeReg8(state->cfg.i2c_addr, kRegCtrl1, 0x01)) {
    state->online = false;
    state->last_error = "active_failed";
    return false;
  }
  state->online = true;
  state->last_error = "";
  state->has_prev_mag = false;
  state->has_prev_axes = false;
  state->has_baseline = state->cfg.has_calibration;
  if (state->cfg.has_calibration) {
    state->baseline_x = state->cfg.baseline_x;
    state->baseline_y = state->cfg.baseline_y;
    state->baseline_z = state->cfg.baseline_z;
  }
  state->lifted = false;
  return true;
}

void pushEvent(
    const String& source,
    const String& event_type,
    unsigned long ts_ms,
    float angle_deg,
    float jolt_g) {
  if (!source.length() || !event_type.length()) return;
  if (g_events.size() >= 64) g_events.erase(g_events.begin());
  AccelerometerMMA8452::Event evt;
  evt.source = source;
  evt.event_type = event_type;
  evt.ts_ms = ts_ms;
  evt.angle_deg = angle_deg;
  evt.jolt_g = jolt_g;
  g_events.push_back(evt);
}

}  // namespace

bool AccelerometerMMA8452::setConfigs(const std::vector<Config>& configs, String* error) {
  std::vector<InstanceState> next;
  next.reserve(configs.size());
  for (const auto& cfg : configs) {
    if (!cfg.source.length()) {
      if (error) *error = "source_required";
      return false;
    }
    if (cfg.sda_pin < 0 || cfg.scl_pin < 0 || cfg.sda_pin == cfg.scl_pin) {
      if (error) *error = "invalid_pins";
      return false;
    }
    if (cfg.i2c_addr < 0x03 || cfg.i2c_addr > 0x77) {
      if (error) *error = "invalid_i2c_address";
      return false;
    }
    InstanceState s;
    s.cfg = cfg;
    s.has_baseline = cfg.has_calibration;
    if (cfg.has_calibration) {
      s.baseline_x = cfg.baseline_x;
      s.baseline_y = cfg.baseline_y;
      s.baseline_z = cfg.baseline_z;
    }
    next.push_back(s);
  }
  g_instances.swap(next);
  g_events.clear();
  return true;
}

void AccelerometerMMA8452::clearConfigs() {
  g_instances.clear();
  g_events.clear();
}

void AccelerometerMMA8452::service(unsigned long now_ms) {
  constexpr unsigned long kLiftConfirmMs = 120;
  for (auto& st : g_instances) {
    const uint16_t sample_ms = st.cfg.sample_ms < 5 ? 5 : st.cfg.sample_ms;
    if (st.last_sample_ms > 0 && (now_ms - st.last_sample_ms) < sample_ms) continue;
    st.last_sample_ms = now_ms;

    if (!st.online && !initSensor(&st)) {
      continue;
    }

    float x = 0.0f;
    float y = 0.0f;
    float z = 0.0f;
    if (!readAxes(st.cfg.i2c_addr, &x, &y, &z)) {
      st.online = false;
      st.last_error = "read_failed";
      continue;
    }
    if (st.cfg.inverted) {
      x = -x;
      y = -y;
      z = -z;
    }

    st.ax_g = x;
    st.ay_g = y;
    st.az_g = z;
    const float mag = sqrtf((x * x) + (y * y) + (z * z));

    float jolt = 0.0f;
    bool has_jolt = false;
    // Directional impacts can keep |g| near 1.0 while still being a strong nudge.
    // Use both magnitude delta and axis-vector delta, then take the larger impulse.
    float mag_delta = 0.0f;
    if (st.has_prev_mag) {
      mag_delta = fabsf(mag - st.prev_mag_g);
      has_jolt = true;
    }

    float vec_delta = 0.0f;
    if (st.has_prev_axes) {
      const float dx = x - st.prev_ax_g;
      const float dy = y - st.prev_ay_g;
      const float dz = z - st.prev_az_g;
      vec_delta = sqrtf((dx * dx) + (dy * dy) + (dz * dz));
      has_jolt = true;
    }

    jolt = fmaxf(mag_delta, vec_delta);
    st.last_jolt_g = jolt;

    st.prev_ax_g = x;
    st.prev_ay_g = y;
    st.prev_az_g = z;
    st.has_prev_axes = true;
    st.prev_mag_g = mag;
    st.has_prev_mag = true;

    const float norm = mag;
    if (norm < 0.001f) continue;
    const float nx = x / norm;
    const float ny = y / norm;
    const float nz = z / norm;
    if (!st.has_baseline) {
      st.baseline_x = nx;
      st.baseline_y = ny;
      st.baseline_z = nz;
      st.has_baseline = true;
      st.angle_deg = 0.0f;
      continue;
    }
    const float dot = clampUnit((nx * st.baseline_x) + (ny * st.baseline_y) + (nz * st.baseline_z));
    st.angle_deg = acosf(dot) * kRadToDeg;

    const bool lifted_now = st.angle_deg >= st.cfg.lift_angle_deg;
    if (lifted_now && !st.lifted) {
      if (st.lift_candidate_ms == 0) {
        st.lift_candidate_ms = now_ms;
      } else if ((now_ms - st.lift_candidate_ms) >= kLiftConfirmMs) {
        st.lifted = true;
        st.lift_candidate_ms = 0;
        st.lift_count++;
        pushEvent(st.cfg.source, "TILT_LIFTED", now_ms, st.angle_deg, st.last_jolt_g);
      }
    } else if (!lifted_now) {
      st.lift_candidate_ms = 0;
      if (st.lifted) {
      const float release_threshold = st.cfg.lift_angle_deg - st.cfg.lift_hysteresis_deg;
      if (st.angle_deg <= release_threshold) {
        st.lifted = false;
      }
      }
    }

    // Keep nudge and lift distinct: suppress nudges while lifted or near lift threshold.
    const float nudge_block_angle = st.cfg.lift_angle_deg - (st.cfg.lift_hysteresis_deg * 0.5f);
    const bool nudge_blocked = st.lifted || lifted_now || (st.angle_deg >= nudge_block_angle);
    if (has_jolt &&
        !nudge_blocked &&
        jolt >= st.cfg.tilt_sensitivity_g &&
        (now_ms - st.last_tilt_event_ms) >= st.cfg.tilt_cooldown_ms) {
      st.last_tilt_event_ms = now_ms;
      st.tilt_count++;
      pushEvent(st.cfg.source, "TILT_NUDGE", now_ms, st.angle_deg, jolt);
    }
  }
}

bool AccelerometerMMA8452::popEvent(Event* out_event) {
  if (!out_event || g_events.empty()) return false;
  *out_event = g_events.front();
  g_events.erase(g_events.begin());
  return true;
}

String AccelerometerMMA8452::buildStatusPayload(const String& req_id) {
  String payload = "{\"t\":\"ACCEL_STATUS\",\"ok\":true,\"configured\":";
  payload += static_cast<uint32_t>(g_instances.size());
  payload += ",\"sensors\":[";
  for (size_t i = 0; i < g_instances.size(); ++i) {
    const auto& st = g_instances[i];
    if (i > 0) payload += ",";
    payload += "{\"source\":\"";
    payload += st.cfg.source;
    payload += "\",\"online\":";
    payload += (st.online ? "true" : "false");
    payload += ",\"sdaPin\":";
    payload += st.cfg.sda_pin;
    payload += ",\"sclPin\":";
    payload += st.cfg.scl_pin;
    payload += ",\"i2cAddress\":\"0x";
    char addr_hex[3];
    snprintf(addr_hex, sizeof(addr_hex), "%02x", st.cfg.i2c_addr);
    payload += addr_hex;
    payload += "\",\"inverted\":";
    payload += (st.cfg.inverted ? "true" : "false");
    payload += ",\"tiltSensitivityG\":";
    payload += String(st.cfg.tilt_sensitivity_g, 3);
    payload += ",\"liftAngleDeg\":";
    payload += String(st.cfg.lift_angle_deg, 2);
    payload += ",\"liftHysteresisDeg\":";
    payload += String(st.cfg.lift_hysteresis_deg, 2);
    payload += ",\"sampleMs\":";
    payload += st.cfg.sample_ms;
    payload += ",\"tiltCooldownMs\":";
    payload += st.cfg.tilt_cooldown_ms;
    payload += ",\"ax\":";
    payload += String(st.ax_g, 3);
    payload += ",\"ay\":";
    payload += String(st.ay_g, 3);
    payload += ",\"az\":";
    payload += String(st.az_g, 3);
    payload += ",\"angleDeg\":";
    payload += String(st.angle_deg, 2);
    payload += ",\"baselineX\":";
    payload += String(st.baseline_x, 4);
    payload += ",\"baselineY\":";
    payload += String(st.baseline_y, 4);
    payload += ",\"baselineZ\":";
    payload += String(st.baseline_z, 4);
    payload += ",\"calibrated\":";
    payload += (st.has_baseline ? "true" : "false");
    payload += ",\"lastJoltG\":";
    payload += String(st.last_jolt_g, 3);
    payload += ",\"lifted\":";
    payload += (st.lifted ? "true" : "false");
    payload += ",\"tiltCount\":";
    payload += st.tilt_count;
    payload += ",\"liftCount\":";
    payload += st.lift_count;
    payload += ",\"lastSampleMs\":";
    payload += st.last_sample_ms;
    if (st.last_error.length()) {
      payload += ",\"error\":\"";
      payload += st.last_error;
      payload += "\"";
    }
    payload += "}";
  }
  payload += "]";
  if (req_id.length()) {
    payload += ",\"reqId\":\"";
    payload += req_id;
    payload += "\"";
  }
  payload += "}";
  return payload;
}

String AccelerometerMMA8452::buildMetricsEventPayload(unsigned long ts_ms, const String& request_name) {
  String payload = "{\"t\":\"EVT\",\"name\":\"ACCEL_STATUS_METRICS\",\"source\":\"accelerometer.mma8452\",\"eventType\":\"STATUS\",\"tsMs\":";
  payload += ts_ms;
  if (request_name.length()) {
    payload += ",\"request\":\"";
    payload += request_name;
    payload += "\"";
  }
  payload += ",\"metrics\":";
  payload += buildStatusPayload(String());
  payload += "}";
  return payload;
}
