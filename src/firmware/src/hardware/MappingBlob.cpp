// MappingBlob: validation + apply for mapping.pb blobs stored on LittleFS.

#include "hardware/MappingBlob.h"

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
  if ((out->version != 3 && out->version != 4 && out->version != 5) || out->type != 1) {
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
  const uint32_t safe_bytes = static_cast<uint32_t>(2 + (count * 3));
  if (hdr.payload_len < (safe_bytes + 2)) {
    if (error) *error = "length_mismatch";
    return false;
  }
  uint32_t consumed = safe_bytes;
  if (!f.seek(kHeaderLen + consumed)) {
    if (error) *error = "seek_failed";
    return false;
  }
  uint8_t binding_count_buf[2];
  if (!read_exact(f, binding_count_buf, sizeof(binding_count_buf))) {
    if (error) *error = "binding_count_short";
    return false;
  }
  consumed += 2;
  uint16_t binding_count = read_le16(binding_count_buf);
  for (uint16_t i = 0; i < binding_count; ++i) {
    uint8_t len_buf[1];
    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += 1;
    uint8_t comp_len = len_buf[0];
    if (consumed + static_cast<uint32_t>(comp_len) + 1 > hdr.payload_len) {
      if (error) *error = "binding_entry_overflow";
      return false;
    }
    if (comp_len > 0 && !f.seek(f.position() + comp_len)) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += comp_len;
    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += 1;
    uint8_t fn_len = len_buf[0];
    if (consumed + static_cast<uint32_t>(fn_len) + 1 > hdr.payload_len) {
      if (error) *error = "binding_entry_overflow";
      return false;
    }
    if (fn_len > 0 && !f.seek(f.position() + fn_len)) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += fn_len;
    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += 1;
    uint8_t drv_len = len_buf[0];
    if (consumed + static_cast<uint32_t>(drv_len) > hdr.payload_len) {
      if (error) *error = "binding_entry_overflow";
      return false;
    }
    if (drv_len > 0 && !f.seek(f.position() + drv_len)) {
      if (error) *error = "binding_entry_short";
      return false;
    }
    consumed += drv_len;
    if (hdr.version >= 4) {
      if (consumed + 2 > hdr.payload_len) {
        if (error) *error = "binding_entry_overflow";
        return false;
      }
      if (!f.seek(f.position() + 2)) {
        if (error) *error = "binding_entry_short";
        return false;
      }
      consumed += 2;
    }
    if (hdr.version >= 5) {
      if (consumed + 7 > hdr.payload_len) {
        if (error) *error = "binding_entry_overflow";
        return false;
      }
      if (!f.seek(f.position() + 7)) {
        if (error) *error = "binding_entry_short";
        return false;
      }
      consumed += 7;
    }
  }
  if (consumed != hdr.payload_len) {
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

bool loadMappingDriverBindings(const char* path, std::vector<MappingDriverBindingEntry>* out_entries, String* error) {
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
  MappingHeader hdr{};
  if (!read_header(f, &hdr, error)) {
    return false;
  }
  const uint32_t safe_bytes = static_cast<uint32_t>(2 + (count * 3));
  if (!f.seek(kHeaderLen + safe_bytes)) {
    if (error) *error = "seek_failed";
    return false;
  }
  uint8_t binding_count_buf[2];
  if (!read_exact(f, binding_count_buf, sizeof(binding_count_buf))) {
    if (error) *error = "binding_count_short";
    return false;
  }
  uint16_t binding_count = read_le16(binding_count_buf);
  out_entries->reserve(binding_count);
  for (uint16_t i = 0; i < binding_count; ++i) {
    uint8_t len_buf[1];
    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      out_entries->clear();
      return false;
    }
    uint8_t comp_len = len_buf[0];
    String target_id;
    if (comp_len > 0) {
      std::vector<uint8_t> comp_bytes(comp_len);
      if (!read_exact(f, comp_bytes.data(), comp_len)) {
        if (error) *error = "binding_entry_short";
        out_entries->clear();
        return false;
      }
      target_id.reserve(comp_len);
      for (uint8_t b : comp_bytes) target_id += static_cast<char>(b);
    }

    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      out_entries->clear();
      return false;
    }
    uint8_t fn_len = len_buf[0];

    String function_name;
    if (fn_len > 0) {
      std::vector<uint8_t> fn_bytes(fn_len);
      if (!read_exact(f, fn_bytes.data(), fn_len)) {
        if (error) *error = "binding_entry_short";
        out_entries->clear();
        return false;
      }
      function_name.reserve(fn_len);
      for (uint8_t b : fn_bytes) function_name += static_cast<char>(b);
    }

    if (!read_exact(f, len_buf, sizeof(len_buf))) {
      if (error) *error = "binding_entry_short";
      out_entries->clear();
      return false;
    }
    uint8_t drv_len = len_buf[0];

    String driver;
    if (drv_len > 0) {
      std::vector<uint8_t> drv_bytes(drv_len);
      if (!read_exact(f, drv_bytes.data(), drv_len)) {
        if (error) *error = "binding_entry_short";
        out_entries->clear();
        return false;
      }
      driver.reserve(drv_len);
      for (uint8_t b : drv_bytes) driver += static_cast<char>(b);
    }
    uint16_t auto_off_sec = 0;
    if (hdr.version >= 4) {
      uint8_t auto_off_buf[2];
      if (!read_exact(f, auto_off_buf, sizeof(auto_off_buf))) {
        if (error) *error = "binding_entry_short";
        out_entries->clear();
        return false;
      }
      auto_off_sec = read_le16(auto_off_buf);
    }
    uint16_t lcd_sda_pin = 0xFFFF;
    uint16_t lcd_scl_pin = 0xFFFF;
    uint8_t lcd_i2c_addr = 0x27;
    uint8_t lcd_cols = 16;
    uint8_t lcd_rows = 2;
    if (hdr.version >= 5) {
      uint8_t lcd_cfg[7];
      if (!read_exact(f, lcd_cfg, sizeof(lcd_cfg))) {
        if (error) *error = "binding_entry_short";
        out_entries->clear();
        return false;
      }
      lcd_sda_pin = read_le16(lcd_cfg + 0);
      lcd_scl_pin = read_le16(lcd_cfg + 2);
      lcd_i2c_addr = lcd_cfg[4];
      lcd_cols = lcd_cfg[5];
      lcd_rows = lcd_cfg[6];
    }

    if (!target_id.length()) continue;
    if (!driver.length()) driver = "Default";
    MappingDriverBindingEntry row;
    row.target_id = target_id;
    row.function_name = function_name;
    row.driver = driver;
    if (row.function_name.equalsIgnoreCase("LCD Display") ||
        row.function_name.equalsIgnoreCase("LCD1602")) {
      row.lcd_auto_off_sec = hdr.version >= 4 ? auto_off_sec : 60;
      row.lcd_sda_pin = hdr.version >= 5 ? lcd_sda_pin : 0xFFFF;
      row.lcd_scl_pin = hdr.version >= 5 ? lcd_scl_pin : 0xFFFF;
      row.lcd_i2c_addr = hdr.version >= 5 ? lcd_i2c_addr : 0x27;
      row.lcd_cols = hdr.version >= 5 ? lcd_cols : 16;
      row.lcd_rows = hdr.version >= 5 ? lcd_rows : 2;
    } else {
      row.lcd_auto_off_sec = 0;
      row.lcd_sda_pin = 0xFFFF;
      row.lcd_scl_pin = 0xFFFF;
      row.lcd_i2c_addr = 0x27;
      row.lcd_cols = 16;
      row.lcd_rows = 2;
    }
    out_entries->push_back(row);
  }
  return true;
}

bool loadMappingDriverBindingForTarget(
    const char* path,
    const String& target,
    MappingDriverBindingEntry* out_entry,
    String* error) {
  if (out_entry) *out_entry = MappingDriverBindingEntry{};
  String normalized = target;
  normalized.trim();
  if (!normalized.length()) {
    if (error) *error = "target_required";
    return false;
  }
  int sep = normalized.indexOf("::");
  if (sep >= 0) normalized = normalized.substring(sep + 2);
  normalized.trim();
  if (!normalized.length()) {
    if (error) *error = "target_required";
    return false;
  }

  std::vector<MappingDriverBindingEntry> entries;
  if (!loadMappingDriverBindings(path, &entries, error)) {
    return false;
  }
  for (const auto& row : entries) {
    if (row.target_id != normalized) continue;
    if (out_entry) *out_entry = row;
    return true;
  }
  if (error) *error = "not_found";
  return false;
}
