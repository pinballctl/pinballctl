#ifndef PINBALLCTL_COMPONENT_DRIVER_REGISTRY_H
#define PINBALLCTL_COMPONENT_DRIVER_REGISTRY_H

#include <Arduino.h>

namespace component_driver_registry {

String normalizeFunctionName(const String& raw_function);
String normalizeDriverName(const String& function_name, const String& raw_driver);
String resolveDriverForTarget(
    const char* mapping_path,
    const String& function_name,
    const String& target,
    const String& requested_driver);
String implementationName(const String& function_name, const String& driver_name);

bool writeDisplayTextByDriver(
    const String& driver_name,
    int sda_pin,
    int scl_pin,
    uint8_t addr,
    const String& line1,
    const String& line2,
    uint8_t cols,
    uint8_t rows,
    bool clear_first);

}  // namespace component_driver_registry

#endif  // PINBALLCTL_COMPONENT_DRIVER_REGISTRY_H
