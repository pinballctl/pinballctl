#ifndef PINBALLCTL_COMPONENT_INTERFACES_H
#define PINBALLCTL_COMPONENT_INTERFACES_H

#include <Arduino.h>
#include "components/ComponentEvent.h"

class EventSource {
 public:
  virtual ~EventSource() = default;
  virtual bool readEvent(ComponentEvent* out_event) = 0;
};

class Actuator {
 public:
  virtual ~Actuator() = default;
  virtual bool setOutput(bool high) = 0;
  virtual bool pulseOutput(uint32_t duration_ms) = 0;
};

#endif  // PINBALLCTL_COMPONENT_INTERFACES_H
