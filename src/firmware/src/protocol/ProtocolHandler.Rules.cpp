#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

bool ProtocolHandler::handleRulesCommands(const String& line, const String& req_id, const String& cmd) {
  if (!protocol_support::isCmd(line, cmd, "SET_RULES")) return false;
  protocol_support::enqueueWithRetry(
      serial_,
      protocol_support::appendReqId(
          "{\"t\":\"RULES_STATUS\",\"status\":\"error\",\"reason\":\"deprecated_use_rules_blob_sync\"}",
          req_id));
  return true;
}
