#ifndef PINBALLCTL_RGB_STRIP_DEFAULT_H
#define PINBALLCTL_RGB_STRIP_DEFAULT_H

#include <Arduino.h>
#include <vector>

class RgbStripDefault {
 public:
  static constexpr const char* kFunction = "RGB Strip";
  static constexpr const char* kDriver = "Default";
  static bool writePixels(
      int pin,
      int pixel_count,
      const std::vector<uint16_t>& pixel_indexes,
      const String& mode,
      const String& color_hex,
      float brightness,
      uint16_t blink_count,
      uint32_t blink_interval_ms,
      String* error = nullptr);
  static void beginBatch();
  static void endBatch();
  static void service(unsigned long now_ms);
};

#endif  // PINBALLCTL_RGB_STRIP_DEFAULT_H
