#ifndef PINBALLCTL_LCD1602_I2C_H
#define PINBALLCTL_LCD1602_I2C_H

#include <Arduino.h>

class Lcd1602I2C {
 public:
  static constexpr unsigned long kAutoBacklightOffMs = 60000UL;

  static bool writeText(
      int sda_pin,
      int scl_pin,
      uint8_t i2c_addr,
      const String& line1,
      const String& line2,
      uint8_t cols = 16,
      uint8_t rows = 2,
      bool clear_first = false);

  static void service(unsigned long now_ms);
};

#endif  // PINBALLCTL_LCD1602_I2C_H
