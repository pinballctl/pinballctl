#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

void ProtocolHandler::handleLine(const String& line) {
  String req_id;
  String cmd;
  protocol_support::extractJsonString(line, "reqId", &req_id);
  protocol_support::extractJsonString(line, "cmd", &cmd);

  if (handleSystemCommands(line, req_id, cmd)) return;
  if (handleFsCommands(line, req_id, cmd)) return;
  if (handleEventCommands(line, req_id, cmd)) return;
  if (handleLightingCommands(line, req_id, cmd)) return;
  if (handleBlobCommands(line, req_id, cmd)) return;
  if (handleHardwareCommands(line, req_id, cmd)) return;
  if (handleTimeCommands(line, req_id, cmd)) return;
  if (handleDisplayCommands(line, req_id, cmd)) return;
}
