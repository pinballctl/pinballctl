#include "safety/CoilSafety.h"
#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

void ProtocolHandler::handleLine(const String& line) {
  String req_id;
  String cmd;
  protocol_support::extractJsonString(line, "reqId", &req_id);
  protocol_support::extractJsonString(line, "cmd", &cmd);

  bool recovery_resume = cmd == "EVENT_RESUME";
  String safety_line = line;
  if (cmd == "EVENT_PAUSE") {
    coil_safety::disable();
    rules_runtime_.pauseForRecovery();
    JsonDocument request;
    deserializeJson(request, line);
    request["cmd"] = "COIL_STATUS";
    safety_line = ""; serializeJson(request, safety_line);
  } else if (recovery_resume) {
    JsonDocument request;
    deserializeJson(request, line);
    // Recovery is only valid from the explicit paused state.
    if (!rules_runtime_.recoveryPaused()) {
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(
        "{\"t\":\"COIL_STATUS\",\"ok\":false,\"error\":\"not_paused\"}", req_id));
      return;
    }
    request["cmd"] = (request["arm"] | false) ? "ENABLE" : "COIL_STATUS";
    safety_line = ""; serializeJson(request, safety_line);
  } else if (cmd == "ENABLE" && rules_runtime_.recoveryPaused()) {
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(
      "{\"t\":\"COIL_STATUS\",\"ok\":false,\"armed\":false,\"error\":\"runtime_paused\"}", req_id));
    return;
  }
  String safety_response = coil_safety::command(safety_line);
  if (safety_response.length()) {
    JsonDocument response;
    deserializeJson(response, safety_response);
    if (recovery_resume && response["ok"] == true && response["fault"] == "none") rules_runtime_.resumeAfterRecovery();
    response["recoverySupported"] = true;
    response["runtimePaused"] = rules_runtime_.recoveryPaused();
    response["recoveryQuietMs"] = rules_runtime_.recoveryQuietMs();
    safety_response = ""; serializeJson(response, safety_response);
    protocol_support::enqueueWithRetry(serial_, safety_response);
    return;
  }
  // Any deployment or maintenance transition revokes arming before doing work.
  if (cmd == "HELLO" || cmd == "BLOB_BEGIN" || cmd == "SET_RULES" ||
      cmd == "FS_MANIFEST_UPDATE" || cmd == "MOUNT_FS" ||
      cmd == "SET_ACCEL_CONFIG" || cmd == "GET_HW") coil_safety::disable();
  if (handleSystemCommands(line, req_id, cmd)) return;
  if (handleFsCommands(line, req_id, cmd)) return;
  if (handleEventCommands(line, req_id, cmd)) return;
  if (handleLightingCommands(line, req_id, cmd)) return;
  if (handleBlobCommands(line, req_id, cmd)) return;
  if (handleHardwareCommands(line, req_id, cmd)) return;
  if (handleTimeCommands(line, req_id, cmd)) return;
  if (handleDisplayCommands(line, req_id, cmd)) return;
}
