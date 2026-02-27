#ifndef PINBALLCTL_MAPPING_BLOB_H
#define PINBALLCTL_MAPPING_BLOB_H

#include <Arduino.h>
#include <LittleFS.h>
#include <vector>

struct MappingSafeStateEntry {
  uint16_t pin = 0;
  bool safe_high = false;
};

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len);
bool validateMappingBlob(const char* path, uint16_t* out_count, String* error);
bool applyMappingBlob(const char* path, uint16_t* out_count, String* error);
bool loadMappingSafeStates(const char* path, std::vector<MappingSafeStateEntry>* out_entries, String* error);

#endif  // PINBALLCTL_MAPPING_BLOB_H
