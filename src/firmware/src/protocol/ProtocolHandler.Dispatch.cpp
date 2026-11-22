#include "safety/CoilSafety.h"
#include "safety/CoilSafetyCommand.h"
#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

void ProtocolHandler::handleLine(const String& line) {
  String req_id;
  String cmd;
  protocol_support::extractJsonString(line, "reqId", &req_id);
  protocol_support::extractJsonString(line, "cmd", &cmd);

  const bool recovery_pause = cmd == "EVENT_PAUSE";
  const bool recovery_resume = cmd == "EVENT_RESUME";
  if (recovery_pause) {
    coil_safety::disable();
    rules_runtime_.pauseForRecovery();
  }

  JsonDocument request;
  bool valid_request = !deserializeJson(request, line);
  if (recovery_pause || recovery_resume) {
    if (recovery_resume && !rules_runtime_.recoveryPaused()) {
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(
        "{\"t\":\"COIL_STATUS\",\"ok\":false,\"error\":\"not_paused\"}", req_id));
      return;
    }
    if (recovery_resume && (!valid_request || request["cmd"] != cmd ||
        !request["generation"].is<uint32_t>())) {
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(
        "{\"t\":\"COIL_STATUS\",\"ok\":false,\"error\":\"invalid_resume\"}", req_id));
      return;
    }
    if (!valid_request) request.clear();
    request["cmd"] = "COIL_STATUS";
    if (req_id.length()) request["reqId"] = req_id;
    valid_request = true;
  }

  JsonDocument response;
  if (valid_request && coil_safety::command(request.as<JsonVariantConst>(), response)) {
    if (recovery_resume) {
      if (response["fault"] == "none" &&
          request["generation"].as<uint32_t>() == response["generation"].as<uint32_t>()) {
        rules_runtime_.resumeAfterRecovery();
      } else {
        response["ok"] = false;
        response["error"] = "resume_blocked";
      }
    }
    request.clear();
    response["recoverySupported"] = true;
    response["runtimePaused"] = rules_runtime_.recoveryPaused();
    response["recoveryQuietMs"] = rules_runtime_.recoveryQuietMs();
    String safety_response;
    serializeJson(response, safety_response);
    protocol_support::enqueueWithRetry(serial_, safety_response);
    return;
  }
  // Any deployment or maintenance transition revokes arming before doing work.
  if (cmd == "HELLO" || cmd == "BLOB_BEGIN" || cmd == "SET_RULES" ||
      cmd == "FS_MANIFEST_UPDATE" || cmd == "MOUNT_FS" ||
      cmd == "SET_ACCEL_CONFIG" || cmd == "GET_HW") coil_safety::disable();
  // Other handlers retain their own parsing and do not need this document.
  if (!valid_request || (cmd != "RULE_ACTIONS" &&
      !protocol_support::isCmd(line, cmd, "LIGHT_PIXELS_SET") &&
      !protocol_support::isCmd(line, cmd, "LCD_SET"))) request.clear();
  JsonObject request_object = request.as<JsonObject>();
  if (handleSystemCommands(line, req_id, cmd)) return;
  if (handleFsCommands(line, req_id, cmd)) return;
  if (handleEventCommands(line, req_id, cmd, request_object)) return;
  if (handleLightingCommands(line, req_id, cmd, request_object)) return;
  if (handleBlobCommands(line, req_id, cmd)) return;
  if (handleHardwareCommands(line, req_id, cmd)) return;
  if (handleTimeCommands(line, req_id, cmd)) return;
  if (handleDisplayCommands(line, req_id, cmd, request_object)) return;
}
