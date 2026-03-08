#ifndef PINBALLCTL_DRIVER_REGISTRY_H
#define PINBALLCTL_DRIVER_REGISTRY_H

#include <Arduino.h>
#include <vector>

namespace driver_registry {

String normalizeFunctionName(const String& raw_function);
String normalizeDriverName(const String& function_name, const String& raw_driver);
void invalidateBindingCache();
bool resolveDriverForTarget(
    const char* mapping_path,
    const String& target,
    const String& requested_driver,
    const String& default_function_name,
    String* out_function_name,
    String* out_driver_name,
    String* out_impl_name,
    uint16_t* out_lcd_auto_off_sec = nullptr);
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
    bool clear_first,
    uint16_t auto_off_seconds = 60);
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
    String* error = nullptr);
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
    String* out_function_name = nullptr,
    String* out_driver_name = nullptr,
    String* out_impl_name = nullptr,
    String* out_error = nullptr);
void beginRgbBatch();
void endRgbBatch();
void clearAllRgb();

void service(unsigned long now_ms);

}  // namespace driver_registry

#endif  // PINBALLCTL_DRIVER_REGISTRY_H
