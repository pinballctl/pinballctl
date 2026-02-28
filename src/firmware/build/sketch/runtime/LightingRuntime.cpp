#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/runtime/LightingRuntime.cpp"
#include "runtime/LightingRuntime.h"

#include <LittleFS.h>

namespace {
constexpr size_t kBlobHeaderSize = 44;

uint16_t readU16Le(const uint8_t* buf) {
  return static_cast<uint16_t>(buf[0]) | (static_cast<uint16_t>(buf[1]) << 8);
}

uint32_t readU32Le(const uint8_t* buf) {
  return static_cast<uint32_t>(buf[0]) |
         (static_cast<uint32_t>(buf[1]) << 8) |
         (static_cast<uint32_t>(buf[2]) << 16) |
         (static_cast<uint32_t>(buf[3]) << 24);
}
}  // namespace

bool LightingRuntime::loadFromLightingBlob(const char* path, String* error) {
  if (!path || !path[0]) {
    if (error) *error = "bad_path";
    loaded_ = false;
    return false;
  }
  fs::File file = LittleFS.open(path, "r");
  if (!file) {
    if (error) *error = "open_failed";
    loaded_ = false;
    return false;
  }
  size_t size = file.size();
  if (size < kBlobHeaderSize) {
    if (error) *error = "bad_size";
    loaded_ = false;
    return false;
  }
  uint8_t header[kBlobHeaderSize];
  if (file.read(header, kBlobHeaderSize) != static_cast<int>(kBlobHeaderSize)) {
    if (error) *error = "read_failed";
    loaded_ = false;
    return false;
  }
  if (memcmp(header, "PLT1", 4) != 0) {
    if (error) *error = "bad_magic";
    loaded_ = false;
    return false;
  }
  uint16_t version = readU16Le(header + 4);
  if (version != 1) {
    if (error) *error = "bad_version";
    loaded_ = false;
    return false;
  }
  uint32_t payload_len = readU32Le(header + 8);
  if (size != kBlobHeaderSize + payload_len) {
    if (error) *error = "size_mismatch";
    loaded_ = false;
    return false;
  }

  loaded_ = true;
  return true;
}

bool LightingRuntime::playScene(const String& scene_id, String* reason) {
  if (!loaded_) {
    if (reason) *reason = "not_loaded";
    return false;
  }
  if (!scene_id.length()) {
    if (reason) *reason = "missing_scene";
    return false;
  }
  return true;
}

bool LightingRuntime::stopScene(const String& scene_id) {
  (void)scene_id;
  return true;
}

void LightingRuntime::clear() {
  loaded_ = false;
}
