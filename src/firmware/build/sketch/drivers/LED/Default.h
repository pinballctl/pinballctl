#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/drivers/LED/Default.h"
#ifndef PINBALLCTL_LED_DEFAULT_H
#define PINBALLCTL_LED_DEFAULT_H

#include <Arduino.h>

class LedDefault {
 public:
  static constexpr const char* kFunction = "LED";
  static constexpr const char* kDriver = "Default";
  static bool writePin(int pin, bool high);
};

#endif  // PINBALLCTL_LED_DEFAULT_H
