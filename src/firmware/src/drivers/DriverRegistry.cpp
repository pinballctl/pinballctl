#include "drivers/DriverRegistry.h"

#include "drivers/Coil/Default.h"
#include "drivers/LED/Default.h"
#include "drivers/LcdDisplay/LCD1602I2C.h"
#include "drivers/RgbStrip/Default.h"
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
    String* out_impl_name) {
  if (out_function_name) *out_function_name = default_function_name;
  if (out_driver_name) *out_driver_name = normalizeDriverName(default_function_name, requested_driver);
  if (out_impl_name) *out_impl_name = implementationName(default_function_name, requested_driver);

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
    bool clear_first) {
  String d = canonicalDisplayDriver(driver_name);
  if (!d.equalsIgnoreCase("LCD1602I2C")) return false;
  return LcdDisplayLCD1602I2C::writeText(sda_pin, scl_pin, addr, line1, line2, cols, rows, clear_first);
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
  resolveDriverForTarget(mapping_path, target, requested_driver, "LCD Display", &fn, &dn, &impl);
  if (out_function_name) *out_function_name = fn;
  if (out_driver_name) *out_driver_name = dn;
  if (out_impl_name) *out_impl_name = impl;
  return writeDisplayTextByDriver(dn, sda_pin, scl_pin, addr, line1, line2, cols, rows, clear_first);
}

bool writeOutputByDriver(
    const String& function_name,
    const String& driver_name,
    int pin,
    bool high) {
  const String fn = normalizeFunctionName(function_name);
  const String dn = normalizeDriverName(function_name, driver_name);

  if (fn.equalsIgnoreCase("Coil") && dn.equalsIgnoreCase("Default")) {
    return CoilDefault::writePin(pin, high);
  }
  if (fn.equalsIgnoreCase("Led") && dn.equalsIgnoreCase("Default")) {
    return LedDefault::writePin(pin, high);
  }

  // Generic GPIO fallback for any output-capable driver binding.
  if (pin < 0) return false;
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
}

void endRgbBatch() {
  RgbStripDefault::endBatch();
}

void service(unsigned long now_ms) {
  RgbStripDefault::service(now_ms);
}

}  // namespace driver_registry
