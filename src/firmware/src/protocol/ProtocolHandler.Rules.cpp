#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <LittleFS.h>

namespace {
constexpr const char* kRulesBootGuardPathSetRules = "/cfg/rules.boot_fail";
constexpr const char* kRulesRuntimePath = "/cfg/rules.runtime.json";
}

bool ProtocolHandler::handleRulesCommands(const String& line, const String& req_id, const String& cmd) {
  if (!protocol_support::isCmd(line, cmd, "SET_RULES")) return false;
  rules_payload_ = line;
  String err;
  bool ok = rules_runtime_.loadFromSetRulesCommand(line, &err);
  if (!ok) {
    rules_runtime_.clear();
    String payload = "{\"t\":\"RULES_STATUS\",\"status\":\"error\",\"reason\":\"";
    payload += (err.length() ? err : "rules_load_failed");
    payload += "\"}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (fs_mounted_) {
    fs::File f = LittleFS.open(kRulesRuntimePath, "w");
    if (f) {
      f.print(line);
      f.close();
    }
    protocol_support::clearBootGuard(kRulesBootGuardPathSetRules);
  }
  protocol_support::enqueueWithRetry(
      serial_, protocol_support::appendReqId("{\"t\":\"RULES_STATUS\",\"status\":\"ok\"}", req_id));
  return true;
}
