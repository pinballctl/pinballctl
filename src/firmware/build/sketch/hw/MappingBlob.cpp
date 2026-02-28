#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/hw/MappingBlob.cpp"
// MappingBlob: validation + apply for mapping.pb blobs stored on LittleFS.

#include "hw/MappingBlob.h"

namespace {
constexpr size_t kHeaderLen = 12;

struct MappingHeader {
  uint8_t version;
  uint8_t type;
  uint32_t payload_len;
  uint32_t payload_crc;
};

uint32_t crc_table[256];
bool crc_table_init = false;

void init_crc_table() {
  for (uint32_t i = 0; i < 256; ++i) {
    uint32_t c = i;
    for (int j = 0; j < 8; ++j) {
      if (c & 1) {
        c = 0xEDB88320UL ^ (c >> 1);
      } else {
        c >>= 1;
      }
    }
    crc_table[i] = c;
  }
  crc_table_init = true;
}

uint16_t read_le16(const uint8_t* b) {
  return static_cast<uint16_t>(b[0]) | (static_cast<uint16_t>(b[1]) << 8);
}

uint32_t read_le32(const uint8_t* b) {
  return static_cast<uint32_t>(b[0]) |
         (static_cast<uint32_t>(b[1]) << 8) |
         (static_cast<uint32_t>(b[2]) << 16) |
         (static_cast<uint32_t>(b[3]) << 24);
}

bool read_exact(fs::File& f, uint8_t* buf, size_t len) {
  return f.read(buf, len) == static_cast<int>(len);
}

bool read_header(fs::File& f, MappingHeader* out, String* error) {
  uint8_t hdr[kHeaderLen];
  if (!read_exact(f, hdr, sizeof(hdr))) {
    if (error) *error = "header_short";
    return false;
  }
  if (hdr[0] != 'P' || hdr[1] != 'B') {
    if (error) *error = "bad_magic";
    return false;
  }
  out->version = hdr[2];
  out->type = hdr[3];
  out->payload_len = read_le32(hdr + 4);
  out->payload_crc = read_le32(hdr + 8);
  if (out->version != 1 || out->type != 1) {
    if (error) *error = "unsupported_version";
    return false;
  }
  return true;
}

bool check_payload_crc(fs::File& f, const MappingHeader& hdr, String* error) {
  if (!crc_table_init) init_crc_table();
  if (!f.seek(kHeaderLen)) {
    if (error) *error = "seek_failed";
    return false;
  }
  uint32_t crc = 0;
  uint32_t remaining = hdr.payload_len;
  uint8_t buf[128];
  while (remaining > 0) {
    size_t to_read = remaining > sizeof(buf) ? sizeof(buf) : remaining;
    if (!read_exact(f, buf, to_read)) {
      if (error) *error = "payload_short";
      return false;
    }
    crc = crc32_update(crc, buf, to_read);
    remaining -= to_read;
  }
  if (crc != hdr.payload_crc) {
    if (error) *error = "crc_mismatch";
    return false;
  }
  return true;
}

}  // namespace

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len) {
  if (!crc_table_init) init_crc_table();
  crc = ~crc;
  for (size_t i = 0; i < len; ++i) {
    crc = crc_table[(crc ^ data[i]) & 0xFF] ^ (crc >> 8);
  }
  return ~crc;
}

bool validateMappingBlob(const char* path, uint16_t* out_count, String* error) {
  fs::File f = LittleFS.open(path, "r");
  if (!f) {
    if (error) *error = "open_failed";
    return false;
  }
  MappingHeader hdr{};
  if (!read_header(f, &hdr, error)) {
    return false;
  }
  size_t total_size = f.size();
  if (total_size != (kHeaderLen + hdr.payload_len)) {
    if (error) *error = "size_mismatch";
    return false;
  }
  if (!check_payload_crc(f, hdr, error)) {
    return false;
  }
  if (!f.seek(kHeaderLen)) {
    if (error) *error = "seek_failed";
    return false;
  }
  uint8_t count_buf[2];
  if (!read_exact(f, count_buf, sizeof(count_buf))) {
    if (error) *error = "count_short";
    return false;
  }
  uint16_t count = read_le16(count_buf);
  if (hdr.payload_len < (2 + (count * 3))) {
    if (error) *error = "length_mismatch";
    return false;
  }
  if (out_count) *out_count = count;
  return true;
}

bool applyMappingBlob(const char* path, uint16_t* out_count, String* error) {
  uint16_t count = 0;
  if (!validateMappingBlob(path, &count, error)) {
    return false;
  }
  fs::File f = LittleFS.open(path, "r");
  if (!f) {
    if (error) *error = "open_failed";
    return false;
  }
  if (!f.seek(kHeaderLen + 2)) {
    if (error) *error = "seek_failed";
    return false;
  }
  for (uint16_t i = 0; i < count; ++i) {
    uint8_t entry[3];
    if (!read_exact(f, entry, sizeof(entry))) {
      if (error) *error = "entry_short";
      return false;
    }
    uint16_t pin = read_le16(entry);
    uint8_t safe = entry[2];
    if (safe > 1) {
      if (error) *error = "invalid_safe";
      return false;
    }
    pinMode(pin, OUTPUT);
    digitalWrite(pin, safe ? HIGH : LOW);
  }
  if (out_count) *out_count = count;
  return true;
}

bool loadMappingSafeStates(const char* path, std::vector<MappingSafeStateEntry>* out_entries, String* error) {
  if (!out_entries) {
    if (error) *error = "out_entries_required";
    return false;
  }
  out_entries->clear();

  uint16_t count = 0;
  if (!validateMappingBlob(path, &count, error)) {
    return false;
  }
  fs::File f = LittleFS.open(path, "r");
  if (!f) {
    if (error) *error = "open_failed";
    return false;
  }
  if (!f.seek(kHeaderLen + 2)) {
    if (error) *error = "seek_failed";
    return false;
  }
  out_entries->reserve(count);
  for (uint16_t i = 0; i < count; ++i) {
    uint8_t entry[3];
    if (!read_exact(f, entry, sizeof(entry))) {
      if (error) *error = "entry_short";
      out_entries->clear();
      return false;
    }
    uint16_t pin = read_le16(entry);
    uint8_t safe = entry[2];
    if (safe > 1) {
      if (error) *error = "invalid_safe";
      out_entries->clear();
      return false;
    }
    MappingSafeStateEntry item;
    item.pin = pin;
    item.safe_high = (safe != 0);
    out_entries->push_back(item);
  }
  return true;
}
