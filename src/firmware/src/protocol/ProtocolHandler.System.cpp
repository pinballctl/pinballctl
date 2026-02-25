#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <LittleFS.h>

bool ProtocolHandler::handleSystemCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "GET_INFO") || protocol_support::isCmd(line, cmd, "HELLO")) {
    sendInfo(req_id);
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "GET_FLASH_INFO")) {
    String payload = "{\"t\":\"FLASH_INFO\",\"chip_size\":";
    payload += ESP.getFlashChipSize();
    payload += ",\"sketch_size\":";
    payload += ESP.getSketchSize();
    payload += ",\"free_sketch\":";
    payload += ESP.getFreeSketchSpace();
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "ECHO")) {
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"ECHO\",\"ok\":true}", req_id));
    return true;
  }
  return false;
}
