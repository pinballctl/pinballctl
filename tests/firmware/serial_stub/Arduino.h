#pragma once
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
using String = std::string;
struct FakeSerial {
  int space = 0;
  size_t write_limit = 8192;
  std::vector<uint8_t> bytes;
  int availableForWrite() { return space; }
  size_t write(const uint8_t* data, size_t length) {
    size_t size = std::min({length, static_cast<size_t>(space), write_limit});
    bytes.insert(bytes.end(), data, data + size);
    space -= static_cast<int>(size);
    return size;
  }
};
extern FakeSerial Serial;
