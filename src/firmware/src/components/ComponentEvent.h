#ifndef PINBALLCTL_COMPONENT_EVENT_H
#define PINBALLCTL_COMPONENT_EVENT_H

#include <Arduino.h>

struct ComponentEvent {
  String source;
  String type;
  unsigned long ts_ms = 0;
  String data;
};

#endif  // PINBALLCTL_COMPONENT_EVENT_H
