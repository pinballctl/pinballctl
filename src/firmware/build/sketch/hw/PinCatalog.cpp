#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/hw/PinCatalog.cpp"
// PinCatalog: profile-backed pin metadata table.

#include "hw/PinCatalog.h"
#include "../profiles/ProfileRegistry.h"

size_t PinCatalog::count() {
  return activePinProfile().pin_count;
}

const PinEntry& PinCatalog::at(size_t index) {
  return activePinProfile().pins[index];
}

const char* PinCatalog::profileId() {
  return activePinProfile().id;
}
