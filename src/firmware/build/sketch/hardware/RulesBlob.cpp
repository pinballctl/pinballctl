#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/hardware/RulesBlob.cpp"
#include "hardware/RulesBlob.h"

#include <LittleFS.h>

namespace {
constexpr uint32_t kRulesBlobHeaderSize = 44;

uint16_t read_u16_le(const uint8_t *buf) {
  return static_cast<uint16_t>(buf[0]) | (static_cast<uint16_t>(buf[1]) << 8);
}

uint32_t read_u32_le(const uint8_t *buf) {
  return static_cast<uint32_t>(buf[0]) |
         (static_cast<uint32_t>(buf[1]) << 8) |
         (static_cast<uint32_t>(buf[2]) << 16) |
         (static_cast<uint32_t>(buf[3]) << 24);
}
}  // namespace

bool validateRulesBlob(const char *path, String *error) {
  if (!path || !path[0]) {
    if (error) *error = "bad_path";
    return false;
  }
  fs::File file = LittleFS.open(path, "r");
  if (!file) {
    if (error) *error = "open_failed";
    return false;
  }
  size_t size = file.size();
  if (size < kRulesBlobHeaderSize) {
    if (error) *error = "bad_size";
    return false;
  }
  uint8_t header[kRulesBlobHeaderSize];
  if (file.read(header, kRulesBlobHeaderSize) != kRulesBlobHeaderSize) {
    if (error) *error = "read_failed";
    return false;
  }
  if (memcmp(header, "PDR1", 4) != 0) {
    if (error) *error = "bad_magic";
    return false;
  }
  uint16_t version = read_u16_le(header + 4);
  if (version != 1) {
    if (error) *error = "bad_version";
    return false;
  }
  uint32_t payload_len = read_u32_le(header + 8);
  if (size != kRulesBlobHeaderSize + payload_len) {
    if (error) *error = "bad_size";
    return false;
  }
  return true;
}
