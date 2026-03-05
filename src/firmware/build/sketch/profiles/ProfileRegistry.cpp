#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/profiles/ProfileRegistry.cpp"
#include "ProfileRegistry.h"

#include "esp32s3_profile.h"

namespace {
String normalizeChipKey(const String& raw_chip_model) {
  String out = raw_chip_model;
  out.toLowerCase();
  out.replace("-", "");
  out.replace(" ", "");
  if (!out.length()) out = "esp32";
  return out;
}

const PinCatalogProfile& resolveProfile() {
  const PinCatalogProfile& s3 = esp32s3Profile();
  String chip_key = normalizeChipKey(ESP.getChipModel());
  if (chip_key == s3.chip_key) return s3;
  // Conservative default while additional profiles are added.
  return s3;
}
}  // namespace

const PinCatalogProfile& activePinProfile() {
  static const PinCatalogProfile* selected = nullptr;
  if (!selected) {
    selected = &resolveProfile();
  }
  return *selected;
}
