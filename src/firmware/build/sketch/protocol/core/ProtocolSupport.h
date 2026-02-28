#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/protocol/core/ProtocolSupport.h"
#ifndef PINBALLCTL_PROTOCOL_SUPPORT_H
#define PINBALLCTL_PROTOCOL_SUPPORT_H

#include <Arduino.h>
#include <functional>
#include "core/FramedSerial.h"

namespace protocol_support {

struct BootGuardResult {
  bool ok = false;
  bool skipped = false;
  uint8_t failures = 0;
  String reason;
};

bool enqueueWithRetry(FramedSerial& serial, const String& payload, uint32_t timeout_ms = 250);
void emitBlobDebug(
    FramedSerial& serial,
    const String& stage,
    const String& req_id,
    size_t received,
    size_t expected,
    const String& note = String());
bool extractJsonString(const String& json, const char* key, String* out);
bool extractJsonUint(const String& json, const char* key, uint32_t* out);
String appendReqId(const String& payload, const String& req_id);
bool isCmd(const String& line, const String& cmd, const char* name);
BootGuardResult runBootGuardedLoad(
    const char* guard_path,
    uint8_t max_failures,
    const std::function<bool(String* error)>& loader);
void clearBootGuard(const char* guard_path);

}  // namespace protocol_support

#endif  // PINBALLCTL_PROTOCOL_SUPPORT_H
