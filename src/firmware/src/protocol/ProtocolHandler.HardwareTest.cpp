#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"
#include "safety/CoilSafety.h"
#include "hardware/PinCatalog.h"

namespace {
constexpr unsigned long kHardwareTestTimeoutMs = 1600;
constexpr const char* kHardwareTestMapping = "/cfg/mapping.pb";

bool testableGpio(int pin) {
  if (pin < 0) return false;
  for (size_t i = 0; i < PinCatalog::count(); ++i) {
    const auto& entry = PinCatalog::at(i);
    if (entry.gpio == pin && entry.safe) return true;
  }
  return false;
}
}  // namespace

void ProtocolHandler::stopHardwareTest() {
  if (!hardware_test_session_.length()) return;
  coil_safety::disable();
  for (auto& device : hardware_test_devices_) {
    driver_registry::stopTestDevice(device);
    if (device.kind == driver_registry::TestKind::Lamp) {
      gpio_set_direction(static_cast<gpio_num_t>(device.pin), GPIO_MODE_OUTPUT);
    }
  }
  hardware_test_devices_.clear();
  hardware_test_session_ = "";
  rules_runtime_.resumeAfterRecovery();
}

void ProtocolHandler::serviceHardwareTest(unsigned long now) {
  if (!hardware_test_session_.length()) return;
  if (now - hardware_test_last_poll_ >= kHardwareTestTimeoutMs) {
    stopHardwareTest();
    return;
  }
  for (auto& device : hardware_test_devices_) driver_registry::sampleTestDevice(device, now);
}

void ProtocolHandler::handleHardwareTest(const String& req_id, JsonObject request) {
  const String op = request["op"] | "";
  const String session = request["session"] | "";
  const unsigned long now = millis();
  serviceHardwareTest(now);

  JsonDocument reply;
  reply["t"] = "HARDWARE_TEST_STATUS";
  reply["reqId"] = req_id;
  const char* error = nullptr;
  if (session.length() != 32) {
    error = "invalid_session";
  } else if (op == "start") {
    if (hardware_test_session_.length() && session != hardware_test_session_) {
      error = "test_in_use";
    } else if (!hardware_test_session_.length()) {
      std::vector<MappingDriverBindingEntry> bindings;
      std::vector<MappingSafeStateEntry> safe_states;
      String mapping_error;
      if (!fs_mounted_ || blob_active_ || streamer_.isStreaming() || rules_runtime_.recoveryPaused()) {
        error = "controller_busy";
      } else if (!loadMappingDriverBindings(kHardwareTestMapping, &bindings, &mapping_error) ||
                 !loadMappingSafeStates(kHardwareTestMapping, &safe_states, &mapping_error) || bindings.empty()) {
        error = "mapping_required";
      } else {
        coil_safety::disable();
        rules_runtime_.pauseForRecovery();
        hardware_test_session_ = session;
        hardware_test_devices_.reserve(bindings.size());
        for (const auto& binding : bindings) {
          driver_registry::TestDevice device;
          device.binding = binding;
          device.pin = mappingBindingPin(binding);
          device.kind = driver_registry::testKind(binding);
          using driver_registry::TestKind;
          if (device.kind == TestKind::Input || device.kind == TestKind::Lamp ||
              device.kind == TestKind::Coil || device.kind == TestKind::Strip) {
            if (!testableGpio(device.pin)) device.kind = TestKind::Unsupported;
          }
          if (device.kind == TestKind::Input) {
            device.idle_high = binding.button_idle_level == kAutoButtonIdle
                ? digitalRead(device.pin) == HIGH : binding.button_idle_level == HIGH;
          }
          if (device.kind == TestKind::Lamp || device.kind == TestKind::Coil) {
            bool found = false;
            for (const auto& state : safe_states) {
              if (state.pin != device.pin) continue;
              device.idle_high = state.safe_high;
              found = true;
              break;
            }
            if (!found) device.kind = TestKind::Unsupported;
          }
          if (device.kind == TestKind::Lamp &&
              (coil_safety::reserved(device.pin) ||
               gpio_input_enable(static_cast<gpio_num_t>(device.pin)) != ESP_OK)) {
            device.kind = TestKind::Unsupported;
          }
          if (device.kind == TestKind::Strip) {
            device.pixel_count = constrain(lighting_runtime_.mappedPixelCount(binding.target_id), 1, 2048);
          }
          if (device.kind == TestKind::Display &&
              (!testableGpio(binding.lcd_sda_pin) || !testableGpio(binding.lcd_scl_pin))) {
            device.kind = TestKind::Unsupported;
          }
          driver_registry::sampleTestDevice(device, now);
          hardware_test_devices_.push_back(std::move(device));
        }
      }
    }
    if (!error) {
      hardware_test_last_poll_ = now;
      auto rows = reply["devices"].to<JsonArray>();
      for (const auto& device : hardware_test_devices_) {
        auto row = rows.add<JsonObject>();
        driver_registry::describeTestDevice(device, row);
        driver_registry::reportTestDevice(device, row);
      }
    }
  } else if (session != hardware_test_session_) {
    if (op != "stop") error = "test_ended";
  } else if (op == "stop") {
    stopHardwareTest();
  } else if (op == "poll") {
    hardware_test_last_poll_ = now;
    const String held = request["held"] | "";
    auto rows = reply["state"].to<JsonArray>();
    for (auto& device : hardware_test_devices_) {
      if (device.kind == driver_registry::TestKind::Lamp && device.duration_ms) {
        if (held == device.binding.target_id) device.started_ms = now;
        else driver_registry::stopTestDevice(device);
      }
      driver_registry::reportTestDevice(device, rows.add<JsonObject>());
    }
  } else if (op == "action") {
    const String target = request["target"] | "";
    const String action = request["action"] | "";
    error = "action_blocked";
    for (auto& device : hardware_test_devices_) {
      if (device.binding.target_id != target) continue;
      if (driver_registry::runTestAction(device, action, now)) error = nullptr;
      break;
    }
  } else {
    error = "invalid_operation";
  }
  reply["ok"] = error == nullptr;
  if (error) reply["error"] = error;
  String payload;
  serializeJson(reply, payload);
  if (payload.length() + 5 > FramedSerial::kFrameMax) {
    reply.clear();
    reply["t"] = "HARDWARE_TEST_STATUS";
    reply["reqId"] = req_id;
    reply["ok"] = false;
    reply["error"] = "mapping_too_large";
    payload = "";
    serializeJson(reply, payload);
    stopHardwareTest();
  }
  protocol_support::enqueueWithRetry(serial_, payload);
}
