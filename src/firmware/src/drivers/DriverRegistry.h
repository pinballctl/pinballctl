#ifndef PINBALLCTL_DRIVER_REGISTRY_H
#define PINBALLCTL_DRIVER_REGISTRY_H

#include <Arduino.h>

namespace driver_registry {

String normalizeFunctionName(const String& raw_function);
String normalizeDriverName(const String& function_name, const String& raw_driver);
bool resolveDriverForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    const String& default_function_name,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name);
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
    String* out_function_name = nullptr,
    String* out_driver_name = nullptr,
    String* out_impl_name = nullptr);

bool writeOutputByDriver(
    const String& function_name,
    const String& driver_name,
    int pin,
    bool high);
bool writeOutputForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    int pin,
    bool high,
    String* out_function_name = nullptr,
    String* out_driver_name = nullptr,
    String* out_impl_name = nullptr);

}  // namespace driver_registry

#endif  // PINBALLCTL_DRIVER_REGISTRY_H
