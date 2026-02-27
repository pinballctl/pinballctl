#ifndef PINBALLCTL_PROFILE_REGISTRY_H
#define PINBALLCTL_PROFILE_REGISTRY_H

#include <Arduino.h>

#include "../hw/PinCatalog.h"

struct PinCatalogProfile {
  const char* id;
  const char* chip_key;
  const PinEntry* pins;
  size_t pin_count;
};

const PinCatalogProfile& activePinProfile();

#endif  // PINBALLCTL_PROFILE_REGISTRY_H
