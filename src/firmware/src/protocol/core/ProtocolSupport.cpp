#include "protocol/core/ProtocolSupport.h"

#include <LittleFS.h>

namespace protocol_support {

namespace {
uint8_t readBootGuard(const char* path) {
  if (!path || !path[0]) return 0;
  fs::File f = LittleFS.open(path, "r");
  if (!f) return 0;
  String s = f.readString();
  f.close();
  s.trim();
  if (!s.length()) return 0;
  int n = s.toInt();
  if (n < 0) return 0;
  if (n > 255) return 255;
  return static_cast<uint8_t>(n);
}

void writeBootGuard(const char* path, uint8_t count) {
  if (!path || !path[0]) return;
  fs::File f = LittleFS.open(path, "w");
  if (!f) return;
  f.print(static_cast<unsigned int>(count));
  f.close();
}
}  // namespace

bool enqueueWithRetry(FramedSerial& serial, const String& payload, uint32_t timeout_ms) {
  const unsigned long started = millis();
  while ((millis() - started) < timeout_ms) {
    if (serial.enqueue(payload)) return true;
    serial.pump();
    delay(1);
  }
  return serial.enqueue(payload);
}

void emitBlobDebug(
    FramedSerial& serial,
    const String& stage,
    const String& req_id,
    size_t received,
    size_t expected,
    const String& note) {
  static const bool kBlobDebugEnabled = false;
  if (!kBlobDebugEnabled) return;
  String msg = "{\"t\":\"BLOB_DEBUG\",\"stage\":\"";
  msg += stage;
  msg += "\"";
  if (req_id.length()) {
    msg += ",\"reqId\":\"";
    msg += req_id;
    msg += "\"";
  }
  msg += ",\"received\":";
  msg += static_cast<uint32_t>(received);
  msg += ",\"expected\":";
  msg += static_cast<uint32_t>(expected);
  if (note.length()) {
    msg += ",\"note\":\"";
    msg += note;
    msg += "\"";
  }
  msg += "}";
  serial.enqueue(msg);
}

bool extractJsonString(const String& json, const char* key, String* out) {
  if (!out) return false;
  String needle = String("\"") + key + "\":";
  int idx = json.indexOf(needle);
  if (idx < 0) return false;
  int pos = idx + needle.length();
  while (pos < json.length() && (json[pos] == ' ')) pos++;
  if (pos >= json.length() || json[pos] != '"') return false;
  pos++;
  String value;
  while (pos < json.length()) {
    char c = json[pos++];
    if (c == '"') break;
    if (c == '\\' && pos < json.length()) {
      char next = json[pos++];
      value += next;
    } else {
      value += c;
    }
  }
  *out = value;
  return true;
}

bool extractJsonUint(const String& json, const char* key, uint32_t* out) {
  if (!out) return false;
  String needle = String("\"") + key + "\":";
  int idx = json.indexOf(needle);
  if (idx < 0) return false;
  int pos = idx + needle.length();
  while (pos < json.length() && (json[pos] == ' ')) pos++;
  uint32_t value = 0;
  bool found = false;
  while (pos < json.length()) {
    char c = json[pos];
    if (c < '0' || c > '9') break;
    found = true;
    value = value * 10 + (c - '0');
    pos++;
  }
  if (!found) return false;
  *out = value;
  return true;
}

String appendReqId(const String& payload, const String& req_id) {
  if (!req_id.length()) return payload;
  int idx = payload.lastIndexOf('}');
  if (idx <= 0) return payload;
  String out = payload.substring(0, idx);
  out += ",\"reqId\":\"";
  out += req_id;
  out += "\"}";
  return out;
}

bool isCmd(const String& line, const String& cmd, const char* name) {
  if (cmd.length()) return cmd == name;
  return line.indexOf(name) >= 0;
}

BootGuardResult runBootGuardedLoad(
    const char* guard_path,
    uint8_t max_failures,
    const std::function<bool(String* error)>& loader) {
  BootGuardResult out;
  if (!loader) {
    out.ok = false;
    out.reason = "no_loader";
    return out;
  }

  uint8_t fail_count = readBootGuard(guard_path);
  if (fail_count >= max_failures) {
    out.ok = false;
    out.skipped = true;
    out.failures = fail_count;
    out.reason = "guarded";
    return out;
  }

  uint8_t next_fail = static_cast<uint8_t>(fail_count + 1);
  writeBootGuard(guard_path, next_fail);
  out.failures = next_fail;

  String err;
  if (!loader(&err)) {
    out.ok = false;
    out.reason = err.length() ? err : "load_failed";
    return out;
  }

  writeBootGuard(guard_path, 0);
  out.ok = true;
  out.failures = 0;
  out.reason = "";
  return out;
}

void clearBootGuard(const char* guard_path) {
  writeBootGuard(guard_path, 0);
}

}  // namespace protocol_support
