#include "components/ComponentDriverRegistry.h"

#include "components/Lcd1602I2C.h"
#include "hw/MappingBlob.h"

namespace {

String canonicalDisplayDriver(const String& raw_driver) {
  String d = raw_driver;
  d.trim();
  if (!d.length() || d.equalsIgnoreCase("Default")) return String("LCD1602I2C");
  if (d.equalsIgnoreCase("LEDDisplay1602")) return String("LCD1602I2C");
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

}  // namespace

namespace component_driver_registry {

String normalizeFunctionName(const String& raw_function) {
  String fn = raw_function;
  fn.trim();
  if (fn.equalsIgnoreCase("LCD Display") || fn.equalsIgnoreCase("LCD1602")) return String("LedDisplay");
  if (fn.equalsIgnoreCase("Button")) return String("Button");
  if (fn.equalsIgnoreCase("LED")) return String("Led");
  if (fn.equalsIgnoreCase("Coil")) return String("Coil");
  return compactToken(fn);
}

String normalizeDriverName(const String& function_name, const String& raw_driver) {
  String fn = normalizeFunctionName(function_name);
  if (fn.equalsIgnoreCase("LedDisplay")) return canonicalDisplayDriver(raw_driver);

  String d = raw_driver;
  d.trim();
  if (!d.length()) return String("Default");
  return d;
}

String resolveDriverForTarget(
    const char* mapping_path,
    const String& function_name,
    const String& target,
    const String& requested_driver) {
  String requested = requested_driver;
  requested.trim();
  const bool has_explicit_driver = requested.length() && !requested.equalsIgnoreCase("Default");
  if (has_explicit_driver || !target.length()) {
    return normalizeDriverName(function_name, requested);
  }

  String mapped;
  String err;
  if (loadMappingComponentDriverForTarget(mapping_path, target, &mapped, &err) && mapped.length()) {
    return normalizeDriverName(function_name, mapped);
  }
  return normalizeDriverName(function_name, requested);
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
  return Lcd1602I2C::writeText(sda_pin, scl_pin, addr, line1, line2, cols, rows, clear_first);
}

}  // namespace component_driver_registry
