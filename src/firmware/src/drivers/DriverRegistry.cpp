#include "safety/CoilSafety.h"
#include "drivers/DriverRegistry.h"

#include "drivers/Coil/Default.h"
#include "drivers/LED/Default.h"
#include "drivers/Accelerometer/MMA8452.h"
#include "drivers/LcdDisplay/LCD1602I2C.h"
#include "drivers/RgbStrip/Default.h"
#include "drivers/RgbStrip/NeoPixel.h"
#include "hardware/MappingBlob.h"

namespace {

String canonicalDisplayDriver(const String& raw_driver) {
  String d = raw_driver;
  d.trim();
  if (!d.length() || d.equalsIgnoreCase("Default")) return String("LCD1602I2C");
  return d;
}

String compactToken(const String& raw) {
  String out;
  out.reserve(raw.length());
  for (size_t i = 0; i < raw.length(); ++i) {
    char c = raw[i];
    if ((c >= 'a' && c <= 'z') ||
        (c >= 'A' && c <= 'Z') ||
        (c >= '0' && c <= '9')) {
      out += c;
    }
  }
  return out;
}

struct BindingCacheState {
  String mapping_path;
  bool loaded = false;
  std::vector<MappingDriverBindingEntry> entries;
};

BindingCacheState g_binding_cache;

void normalizeTargetId(String* target) {
  if (!target) return;
  target->trim();
  int sep = target->indexOf("::");
  if (sep >= 0) *target = target->substring(sep + 2);
  target->trim();
}

bool loadBindingsCached(const char* mapping_path, String* error) {
  String path = mapping_path ? String(mapping_path) : String("");
  if (!path.length()) path = "/cfg/mapping.pb";
  if (g_binding_cache.loaded && g_binding_cache.mapping_path == path) {
    return true;
  }
  std::vector<MappingDriverBindingEntry> rows;
  String load_err;
  if (!loadMappingDriverBindings(path.c_str(), &rows, &load_err)) {
    if (error) *error = load_err;
    g_binding_cache.entries.clear();
    g_binding_cache.mapping_path = path;
    g_binding_cache.loaded = false;
    return false;
  }
  g_binding_cache.entries.swap(rows);
  g_binding_cache.mapping_path = path;
  g_binding_cache.loaded = true;
  return true;
}

bool loadBindingForTargetCached(
    const char* mapping_path,
    const String& target,
    MappingDriverBindingEntry* out_entry,
    String* error) {
  if (out_entry) *out_entry = MappingDriverBindingEntry{};
  String normalized = target;
  normalizeTargetId(&normalized);
  if (!normalized.length()) {
    if (error) *error = "target_required";
    return false;
  }
  if (!loadBindingsCached(mapping_path, error)) return false;
  for (const auto& row : g_binding_cache.entries) {
    if (row.target_id != normalized) continue;
    if (out_entry) *out_entry = row;
    return true;
  }
  if (error) *error = "not_found";
  return false;
}

}  // namespace

namespace driver_registry {

void invalidateBindingCache() {
  g_binding_cache.entries.clear();
  g_binding_cache.mapping_path = "";
  g_binding_cache.loaded = false;
}

String normalizeFunctionName(const String& raw_function) {
  String fn = raw_function;
  fn.trim();
  if (fn.equalsIgnoreCase("LCD Display")) return String("LcdDisplay");
  if (fn.equalsIgnoreCase("Button")) return String("Button");
  if (fn.equalsIgnoreCase("LED")) return String("Led");
  if (fn.equalsIgnoreCase("RGB Strip")) return String("RgbStrip");
  if (fn.equalsIgnoreCase("Accelerometer")) return String("Accelerometer");
  if (fn.equalsIgnoreCase("Coil")) return String("Coil");
  return compactToken(fn);
}

String normalizeDriverName(const String& function_name, const String& raw_driver) {
  String fn = normalizeFunctionName(function_name);
  if (fn.equalsIgnoreCase("LcdDisplay")) return canonicalDisplayDriver(raw_driver);

  String d = raw_driver;
  d.trim();
  if (!d.length()) return String("Default");
  return d;
}

bool resolveDriverForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    const String& default_function_name,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name,
    uint16_t* out_lcd_auto_off_sec) {
  if (out_function_name) *out_function_name = default_function_name;
  if (out_driver_name) *out_driver_name = normalizeDriverName(default_function_name, requested_driver);
  if (out_impl_name) *out_impl_name = implementationName(default_function_name, requested_driver);
  if (out_lcd_auto_off_sec) *out_lcd_auto_off_sec = 60;

  MappingDriverBindingEntry entry;
  String err;
  const bool found = target.length() && loadBindingForTargetCached(mapping_path, target, &entry, &err);
  String resolved_function = default_function_name;
  if (found && entry.function_name.length()) resolved_function = entry.function_name;

  String driver = requested_driver;
  driver.trim();
  const bool explicit_driver = driver.length() && !driver.equalsIgnoreCase("Default");
  if (!explicit_driver && found && entry.driver.length()) driver = entry.driver;
  if (!driver.length()) driver = "Default";
  driver = normalizeDriverName(resolved_function, driver);

  if (out_function_name) *out_function_name = resolved_function;
  if (out_driver_name) *out_driver_name = driver;
  if (out_impl_name) *out_impl_name = implementationName(resolved_function, driver);
  if (out_lcd_auto_off_sec && normalizeFunctionName(resolved_function).equalsIgnoreCase("LcdDisplay")) {
    if (found) {
      *out_lcd_auto_off_sec = entry.lcd_auto_off_sec;
    } else {
      *out_lcd_auto_off_sec = 60;
    }
  }
  return found;
}

String implementationName(const String& function_name, const String& driver_name) {
  const String fn = normalizeFunctionName(function_name);
  const String dn = normalizeDriverName(function_name, driver_name);
  return fn + compactToken(dn);
}

bool writeDisplayTextByDriver(
    const String& driver_name,
    int sda_pin,
    int scl_pin,
    uint8_t addr,
    const String& line1,
    const String& line2,
    uint8_t cols,
    uint8_t rows,
    bool clear_first,
    uint16_t auto_off_seconds) {
  String d = canonicalDisplayDriver(driver_name);
  if (!d.equalsIgnoreCase("LCD1602I2C")) return false;
  return LcdDisplayLCD1602I2C::writeText(
      sda_pin, scl_pin, addr, line1, line2, cols, rows, clear_first, auto_off_seconds);
}

bool writeDisplayTextForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    int sda_pin,
    int scl_pin,
    uint8_t addr,
    const String& line1,
    const String& line2,
    uint8_t cols,
    uint8_t rows,
    bool clear_first,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name) {
  String fn;
  String dn;
  String impl;
  uint16_t lcd_auto_off_sec = 60;
  resolveDriverForTarget(
      mapping_path, target, requested_driver, "LCD Display", &fn, &dn, &impl, &lcd_auto_off_sec);
  if (out_function_name) *out_function_name = fn;
  if (out_driver_name) *out_driver_name = dn;
  if (out_impl_name) *out_impl_name = impl;
  return writeDisplayTextByDriver(
      dn, sda_pin, scl_pin, addr, line1, line2, cols, rows, clear_first, lcd_auto_off_sec);
}

bool writeOutputByDriver(
    const String& function_name,
    const String& driver_name,
    int pin,
    bool high) {
  const String fn = normalizeFunctionName(function_name);
  const String dn = normalizeDriverName(function_name, driver_name);

  if (fn.equalsIgnoreCase("Coil")) {
    return dn.equalsIgnoreCase("Default") && CoilDefault::writePin(pin, high);
  }
  if (fn.equalsIgnoreCase("Led") && dn.equalsIgnoreCase("Default")) {
    return LedDefault::writePin(pin, high);
  }

  // Generic GPIO fallback for any output-capable driver binding.
  if (!coil_safety::claimPeripheral(pin)) return false;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, high ? HIGH : LOW);
  return true;
}

bool writeOutputForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    int pin,
    bool high,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name) {
  String fn;
  String dn;
  String impl;
  resolveDriverForTarget(mapping_path, target, requested_driver, "Coil", &fn, &dn, &impl);
  if (out_function_name) *out_function_name = fn;
  if (out_driver_name) *out_driver_name = dn;
  if (out_impl_name) *out_impl_name = impl;
  return writeOutputByDriver(fn, dn, pin, high);
}

bool writeRgbPixelsByDriver(
    const String& function_name,
    const String& driver_name,
    int pin,
    int pixel_count,
    const std::vector<uint16_t>& pixel_indexes,
    const String& mode,
    const String& color_hex,
    float brightness,
    uint16_t blink_count,
    uint32_t blink_interval_ms,
    String* error) {
  const String fn = normalizeFunctionName(function_name);
  const String dn = normalizeDriverName(function_name, driver_name);
  if (fn.equalsIgnoreCase("RgbStrip") && dn.equalsIgnoreCase("Default")) {
    return RgbStripDefault::writePixels(
        pin, pixel_count, pixel_indexes, mode, color_hex, brightness, blink_count, blink_interval_ms, error);
  }
  if (fn.equalsIgnoreCase("RgbStrip") && dn.equalsIgnoreCase("NeoPixel")) {
    return RgbStripNeoPixel::writePixels(
        pin, pixel_count, pixel_indexes, mode, color_hex, brightness, blink_count, blink_interval_ms, error);
  }
  if (error) *error = "unsupported_driver";
  return false;
}

bool writeRgbPixelsForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    int pin,
    int pixel_count,
    const std::vector<uint16_t>& pixel_indexes,
    const String& mode,
    const String& color_hex,
    float brightness,
    uint16_t blink_count,
    uint32_t blink_interval_ms,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name,
    String* out_error) {
  String fn;
  String dn;
  String impl;
  resolveDriverForTarget(mapping_path, target, requested_driver, "RGB Strip", &fn, &dn, &impl);
  if (out_function_name) *out_function_name = fn;
  if (out_driver_name) *out_driver_name = dn;
  if (out_impl_name) *out_impl_name = impl;
  return writeRgbPixelsByDriver(
      fn, dn, pin, pixel_count, pixel_indexes, mode, color_hex, brightness, blink_count, blink_interval_ms, out_error);
}

void beginRgbBatch() {
  RgbStripDefault::beginBatch();
  RgbStripNeoPixel::beginBatch();
}

void endRgbBatch() {
  RgbStripDefault::endBatch();
  RgbStripNeoPixel::endBatch();
}

void clearAllRgb() {
  RgbStripDefault::clearAll();
  RgbStripNeoPixel::clearAll();
}

void service(unsigned long now_ms) {
  RgbStripDefault::service(now_ms);
  RgbStripNeoPixel::service(now_ms);
  AccelerometerMMA8452::service(now_ms);
  LcdDisplayLCD1602I2C::service(now_ms);
}

}  // namespace driver_registry

namespace driver_registry {
TestKind testKind(const MappingDriverBindingEntry& binding) {
  const String fn = normalizeFunctionName(binding.function_name);
  const String driver = normalizeDriverName(fn, binding.driver);
  const bool is_default = driver.equalsIgnoreCase("Default");
  if ((fn == "Button" || fn == "Switch") && is_default) return TestKind::Input;
  if (fn == "Led" && is_default) return TestKind::Lamp;
  if (fn == "Coil" && is_default) return TestKind::Coil;
  if (fn == "RgbStrip" && (is_default || driver.equalsIgnoreCase("NeoPixel"))) return TestKind::Strip;
  if (fn == "LcdDisplay" && driver.equalsIgnoreCase("LCD1602I2C")) return TestKind::Display;
  if (fn == "Accelerometer" && (is_default || driver.equalsIgnoreCase("MMA8452"))) return TestKind::Accelerometer;
  return TestKind::Unsupported;
}

void describeTestDevice(const TestDevice& device, JsonObject row) {
  row["id"] = device.binding.target_id;
  row["function"] = device.binding.function_name;
  row["driver"] = device.binding.driver;
  if (device.pin >= 0) row["pin"] = device.pin;
  auto actions = row["actions"].to<JsonArray>();
  switch (device.kind) {
    case TestKind::Lamp:
      actions.add("on");
      actions.add("off");
      actions.add("hold");
      break;
    case TestKind::Strip: actions.add("flash"); break;
    case TestKind::Coil: actions.add("pulse"); break;
    case TestKind::Display: actions.add("text"); break;
    default: break;
  }
}

void reportTestDevice(const TestDevice& device, JsonObject row) {
  row["activity"] = device.activity;
  switch (device.kind) {
    case TestKind::Input:
    case TestKind::Lamp:
    case TestKind::Coil:
      if (device.level >= 0) row["high"] = device.level != 0;
      break;
    case TestKind::Strip:
    case TestKind::Display:
      row["testing"] = device.engaged;
      break;
    case TestKind::Accelerometer:
      AccelerometerMMA8452::reportTest(device.binding.target_id, device.pin, row);
      break;
    default: break;
  }
}

static bool writeStripTest(const TestDevice& device, const char* mode) {
  std::vector<uint16_t> pixels;
  pixels.reserve(device.pixel_count);
  for (int i = 0; i < device.pixel_count; ++i) pixels.push_back(i);
  return writeRgbPixelsByDriver("RgbStrip", device.binding.driver, device.pin,
                                device.pixel_count, pixels, mode, "#ffffff", 0.1f, 2, 150);
}

static bool writeDisplayTest(const TestDevice& device, const char* message) {
  const auto& binding = device.binding;
  return writeDisplayTextByDriver(binding.driver, binding.lcd_sda_pin, binding.lcd_scl_pin,
                                  binding.lcd_i2c_addr, message, "", binding.lcd_cols,
                                  binding.lcd_rows, false, 2);
}

void stopTestDevice(TestDevice& device) {
  if (!device.wrote_output) return;
  switch (device.kind) {
    case TestKind::Lamp:
      if (LedDefault::writePin(device.pin, device.idle_high)) {
        gpio_input_enable(static_cast<gpio_num_t>(device.pin));
      }
      break;
    case TestKind::Coil: CoilDefault::writePin(device.pin, false); break;
    case TestKind::Strip: writeStripTest(device, "off_force"); break;
    case TestKind::Display: writeDisplayTest(device, ""); break;
    default: break;
  }
  device.engaged = false;
  device.wrote_output = false;
  device.duration_ms = 0;
}

void sampleTestDevice(TestDevice& device, unsigned long now) {
  if (device.duration_ms && now - device.started_ms >= device.duration_ms) stopTestDevice(device);
  if (device.kind == TestKind::Input && device.pin >= 0 && !coil_safety::reserved(device.pin)) {
    const int level = digitalRead(device.pin) == HIGH;
    // Count a short observed pulse even when it ends before the browser refresh.
    if (device.level >= 0 && device.level != level && level != device.idle_high &&
        (!device.activity || now - device.last_hit_ms >= 8)) {
      ++device.activity;
      device.last_hit_ms = now;
    }
    device.level = level;
  }
  if (device.kind == TestKind::Lamp && device.pin >= 0 && !coil_safety::reserved(device.pin)) {
    device.level = digitalRead(device.pin) == HIGH;
  }
  if (device.kind == TestKind::Coil && coil_safety::reserved(device.pin)) {
    device.level = device.idle_high != coil_safety::active(device.pin);
  }
}

bool runTestAction(TestDevice& device, const String& action, unsigned long now) {
  if (device.kind == TestKind::Lamp && device.pin >= 0) {
    if (action != "on" && action != "off" && action != "hold" && action != "release") return false;
    const bool on = action == "on" || action == "hold";
    if (action == "release" && !device.duration_ms) return true;
    if (!LedDefault::writePin(device.pin, device.idle_high != on)) return false;
    gpio_input_enable(static_cast<gpio_num_t>(device.pin));
    device.wrote_output = on;
    device.duration_ms = action == "hold" ? 700 : 0;
  } else if (device.kind == TestKind::Coil && action == "pulse") {
    if (!coil_safety::testPulse(device.pin)) return false;
    device.wrote_output = true;
    ++device.activity;
  } else if (device.kind == TestKind::Strip && action == "flash") {
    if (device.pin < 0 || !writeStripTest(device, "blink")) return false;
    device.wrote_output = device.engaged = true;
    device.duration_ms = 600;
  } else if (device.kind == TestKind::Display && action == "text") {
    if (!writeDisplayTest(device, "Hardware test")) return false;
    device.wrote_output = device.engaged = true;
    device.duration_ms = 1800;
  } else {
    return false;
  }
  device.started_ms = now;
  return true;
}
}  // namespace driver_registry
