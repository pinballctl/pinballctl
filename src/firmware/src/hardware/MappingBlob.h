#ifndef PINBALLCTL_MAPPING_BLOB_H
#define PINBALLCTL_MAPPING_BLOB_H

#include <Arduino.h>
#include <LittleFS.h>
#include <vector>

struct MappingSafeStateEntry {
  uint16_t pin = 0;
  bool safe_high = false;
};

struct MappingDriverBindingEntry {
  String target_id;
  String function_name;
  String driver;
  uint16_t lcd_auto_off_sec = 0;
  uint16_t lcd_sda_pin = 0xFFFF;
  uint16_t lcd_scl_pin = 0xFFFF;
  uint8_t lcd_i2c_addr = 0x27;
  uint8_t lcd_cols = 16;
  uint8_t lcd_rows = 2;
};

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len);
bool validateMappingBlob(const char* path, uint16_t* out_count, String* error);
bool applyMappingBlob(const char* path, uint16_t* out_count, String* error);
bool loadMappingSafeStates(const char* path, std::vector<MappingSafeStateEntry>* out_entries, String* error);
bool loadMappingDriverBindings(const char* path, std::vector<MappingDriverBindingEntry>* out_entries, String* error);
bool loadMappingDriverBindingForTarget(
    const char* path,
    const String& target,
    MappingDriverBindingEntry* out_entry,
    String* error);

#endif  // PINBALLCTL_MAPPING_BLOB_H
