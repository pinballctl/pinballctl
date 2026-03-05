#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/protocol/ProtocolHandler.HardwareTime.cpp"
#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

bool ProtocolHandler::handleHardwareCommands(const String& line, const String& req_id, const String& cmd) {
  (void)req_id;
  if (!protocol_support::isCmd(line, cmd, "GET_HW")) return false;
  streamer_.start();
  return true;
}

bool ProtocolHandler::handleTimeCommands(const String& line, const String& req_id, const String& cmd) {
  if (!(protocol_support::isCmd(line, cmd, "SYNC_TIME") || line.startsWith("SYNC_TIME"))) return false;

  long epoch = 0;
  uint32_t ts = 0;
  if (protocol_support::extractJsonUint(line, "ts", &ts) && ts > 0) {
    epoch = static_cast<long>(ts);
  }
  int sep = line.indexOf(' ');
  if (epoch <= 0 && sep >= 0) epoch = line.substring(sep + 1).toInt();

  if (system_runtime_.syncTimeEpoch(epoch)) {
    String payload = "{\"t\":\"TIME\",\"status\":\"ok\",\"ts\":";
    payload += epoch;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
  } else {
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"TIME\",\"status\":\"error\",\"reason\":\"bad epoch\"}", req_id));
  }
  return true;
}
