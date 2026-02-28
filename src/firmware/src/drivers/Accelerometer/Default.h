#ifndef PINBALLCTL_ACCELEROMETER_DEFAULT_H
#define PINBALLCTL_ACCELEROMETER_DEFAULT_H

#include <Arduino.h>

class AccelerometerDefault {
 public:
  static constexpr const char* kFunction = "Accelerometer";
  static constexpr const char* kDriver = "Default";
};

#endif  // PINBALLCTL_ACCELEROMETER_DEFAULT_H
