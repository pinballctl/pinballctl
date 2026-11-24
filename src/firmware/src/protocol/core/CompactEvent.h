#ifndef PINBALLCTL_COMPACT_EVENT_H
#define PINBALLCTL_COMPACT_EVENT_H

#include <cstdint>
#include <string_view>
#include <vector>

namespace compact_event {
constexpr uint8_t kFrameType = 4;
enum State : uint8_t { Unknown, Closed, Open, High, Low, Active, Inactive };
constexpr const char* kStateNames[] = {"", "CLOSED", "OPEN", "HIGH", "LOW", "ACTIVE", "INACTIVE"};

// Each frame is independent. Device keys share a prefix with the event source.
class Encoder {
 public:
  Encoder(std::string_view name, std::string_view source, std::string_view type,
          uint32_t seq, uint32_t timestamp, uint32_t detail, uint8_t rules_version,
          bool physical, int input_level, size_t observations = 0) {
    bytes.reserve(48 + name.size() + source.size() + observations * 6);
    uint8_t flags = physical ? 0x20 : 0;
    if (input_level >= 0) flags |= input_level ? 2 : 1;
    if (detail) flags |= 0x10;
    if (name == type) flags |= 4;
    else if (name == source) flags |= 12;
    else if (name.size() == source.size() + 1 + type.size() &&
             name.substr(0, source.size()) == source && name[source.size()] == '_' &&
             name.substr(source.size() + 1) == type) flags |= 8;
    bytes.push_back(flags);
    bytes.push_back(rules_version);
    put32(seq);
    put32(timestamp);
    if (detail) put32(detail);
    putText(source);
    putText(type);
    if (!(flags & 12)) putText(name);
  }

  void addState(std::string_view source, std::string_view key, State state) {
    size_t prefix = 0;
    while (prefix < 255 && prefix < source.size() && prefix < key.size() &&
           source[prefix] == key[prefix]) ++prefix;
    bytes.push_back(static_cast<uint8_t>(prefix));
    bytes.push_back(state);
    putText(key.substr(prefix));
  }

  std::vector<uint8_t> bytes;

 private:
  void put32(uint32_t value) {
    for (int shift = 24; shift >= 0; shift -= 8)
      bytes.push_back(static_cast<uint8_t>(value >> shift));
  }

  void putText(std::string_view value) {
    bytes.push_back(static_cast<uint8_t>(value.size() >> 8));
    bytes.push_back(static_cast<uint8_t>(value.size()));
    bytes.insert(bytes.end(), value.begin(), value.end());
  }
};
}  // namespace compact_event
#endif
