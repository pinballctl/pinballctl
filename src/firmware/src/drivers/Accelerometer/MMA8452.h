#ifndef PINBALLCTL_ACCELEROMETER_MMA8452_H
#define PINBALLCTL_ACCELEROMETER_MMA8452_H

#include <Arduino.h>
#include <vector>

class AccelerometerMMA8452 {
 public:
  static constexpr const char* kFunction = "Accelerometer";
  static constexpr const char* kDriver = "MMA8452";

  struct Config {
    String source;
    int sda_pin = -1;
    int scl_pin = -1;
    uint8_t i2c_addr = 0x1C;
    float tilt_sensitivity_g = 0.35f;
    float lift_angle_deg = 20.0f;
    float lift_hysteresis_deg = 5.0f;
    bool inverted = false;
    uint16_t sample_ms = 25;
    uint16_t tilt_cooldown_ms = 150;
    bool has_calibration = false;
    float baseline_x = 0.0f;
    float baseline_y = 0.0f;
    float baseline_z = 1.0f;
  };

  struct Event {
    String source;
    String event_type;
    unsigned long ts_ms = 0;
    float angle_deg = 0.0f;
    float jolt_g = 0.0f;
  };

  static bool setConfigs(const std::vector<Config>& configs, String* error = nullptr);
  static void clearConfigs();
  static void service(unsigned long now_ms);
  static bool popEvent(Event* out_event);
  static String buildStatusPayload(const String& req_id = String());
  static String buildMetricsEventPayload(unsigned long ts_ms, const String& request_name = String());
};

#endif  // PINBALLCTL_ACCELEROMETER_MMA8452_H
