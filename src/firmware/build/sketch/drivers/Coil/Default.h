#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/drivers/Coil/Default.h"
#ifndef PINBALLCTL_COIL_DEFAULT_H
#define PINBALLCTL_COIL_DEFAULT_H

#include <Arduino.h>

class CoilDefault {
 public:
  static constexpr const char* kFunction = "Coil";
  static constexpr const char* kDriver = "Default";
  static bool writePin(int pin, bool high);
};

#endif  // PINBALLCTL_COIL_DEFAULT_H
