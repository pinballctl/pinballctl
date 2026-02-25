#ifndef PINBALLCTL_COMPONENT_H
#define PINBALLCTL_COMPONENT_H

#include <Arduino.h>

class Component {
 public:
  virtual ~Component() = default;
  virtual const char* id() const = 0;
  virtual void begin() = 0;
  virtual void service(unsigned long now_ms) = 0;
};

#endif  // PINBALLCTL_COMPONENT_H
