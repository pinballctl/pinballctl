#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/hw/PinCatalog.h"
#ifndef PINBALLCTL_PIN_CATALOG_H
#define PINBALLCTL_PIN_CATALOG_H

// PinCatalog: static pin metadata table for ESP32-S3.

#include <Arduino.h>

struct PinEntry {
  const char* board;
  const char* type;
  const char* chan;
  const char* reported;
  const char* notes;
  int gpio;
  bool safe;
};

class PinCatalog {
 public:
  static size_t count();
  static const PinEntry& at(size_t index);
  static const char* profileId();
};

#endif  // PINBALLCTL_PIN_CATALOG_H
