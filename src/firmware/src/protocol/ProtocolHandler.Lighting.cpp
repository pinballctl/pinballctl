#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

bool ProtocolHandler::handleLightingCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "LIGHT_SCENE_PLAY")) {
    String scene_id;
    protocol_support::extractJsonString(line, "sceneId", &scene_id);
    String reason;
    bool ok = lighting_runtime_.playScene(scene_id, &reason);
    if (!ok) {
      if (!reason.length()) reason = "play_failed";
      String payload = "{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":false,\"reason\":\"";
      payload += reason;
      payload += "\"}";
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId(payload, req_id));
      return true;
    }
    String payload = "{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":true,\"status\":\"playing\",\"sceneId\":\"";
    payload += scene_id;
    payload += "\"}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "LIGHT_SCENE_STOP")) {
    String scene_id;
    protocol_support::extractJsonString(line, "sceneId", &scene_id);
    if (!scene_id.length()) scene_id = "*";
    lighting_runtime_.stopScene(scene_id);
    String payload = "{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":true,\"status\":\"stopped\",\"sceneId\":\"";
    payload += scene_id;
    payload += "\"}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  return false;
}
