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
      const String& color_hex,
      float brightness,
      String* error = nullptr);
};

#endif  // PINBALLCTL_RGB_STRIP_DEFAULT_H
