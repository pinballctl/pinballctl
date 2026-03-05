#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

bool ProtocolHandler::handleEventCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "EVENT")) {
    String evt_name;
    if (!protocol_support::extractJsonString(line, "name", &evt_name) || !evt_name.length()) evt_name = "pi.stub.event";
    uint32_t seq = 0;
    protocol_support::extractJsonUint(line, "seq", &seq);
    String source;
    protocol_support::extractJsonString(line, "source", &source);
    evt_in_total_++;
    evt_in_ack_count_++;
    evt_in_last_seq_ = seq;
    evt_in_last_ms_ = millis();
    evt_in_last_name_ = evt_name;
    if (source.length()) evt_in_last_source_ = source;
    String payload = "{\"t\":\"EVENT_ACK\",\"ok\":true,\"name\":\"";
    payload += evt_name;
    payload += "\",\"seq\":";
    payload += seq;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "EVENT_FIRE")) {
    String evt_name;
    if (!protocol_support::extractJsonString(line, "name", &evt_name) || !evt_name.length()) evt_name = "pi.stub.fire";
    String source;
    protocol_support::extractJsonString(line, "source", &source);
    uint32_t seq = 0;
    protocol_support::extractJsonUint(line, "seq", &seq);
    uint32_t detail_ms = 0;
    protocol_support::extractJsonUint(line, "detailMs", &detail_ms);
    String event_type;
    protocol_support::extractJsonString(line, "eventType", &event_type);
    evt_in_total_++;
    evt_in_fire_count_++;
    evt_in_last_seq_ = seq;
    evt_in_last_ms_ = millis();
    evt_in_last_name_ = evt_name;
    if (source.length()) evt_in_last_source_ = source;
    bool applied = rules_runtime_.applyEvent(evt_name, source, event_type, seq, millis(), detail_ms);
    if (!applied) {
      evt_in_stale_drop_count_++;
      String payload = "{\"t\":\"EVENT_DROP\",\"reason\":\"stale_seq\",\"name\":\"";
      payload += evt_name;
      payload += "\",\"source\":\"";
      payload += source;
      payload += "\",\"seq\":";
      payload += seq;
      payload += "}";
      protocol_support::enqueueWithRetry(serial_, payload);
    } else {
      String payload = "{\"t\":\"EVT\",\"name\":\"";
      payload += evt_name;
      payload += "\",\"source\":\"";
      payload += source;
      payload += "\",\"eventType\":\"";
      payload += event_type;
      payload += "\",\"seq\":";
      payload += seq;
      if (detail_ms > 0) {
        payload += ",\"detailMs\":";
        payload += detail_ms;
      }
      payload += ",\"tsMs\":";
      payload += millis();
      payload += "}";
      protocol_support::enqueueWithRetry(serial_, payload);
    }
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "EVENT_STATS_RESET")) {
    evt_in_total_ = 0;
    evt_in_ack_count_ = 0;
    evt_in_fire_count_ = 0;
    evt_in_stale_drop_count_ = 0;
    evt_in_last_seq_ = 0;
    evt_in_last_ms_ = 0;
    evt_in_last_name_ = "";
    evt_in_last_source_ = "";
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"EVENT_STATS\",\"ok\":true,\"status\":\"reset\"}", req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "EVENT_STATS")) {
    String payload = "{\"t\":\"EVENT_STATS\",\"ok\":true,\"in_total\":";
    payload += evt_in_total_;
    payload += ",\"in_ack\":";
    payload += evt_in_ack_count_;
    payload += ",\"in_fire\":";
    payload += evt_in_fire_count_;
    payload += ",\"in_stale_drop\":";
    payload += evt_in_stale_drop_count_;
    payload += ",\"last_seq\":";
    payload += evt_in_last_seq_;
    payload += ",\"last_ms\":";
    payload += evt_in_last_ms_;
    payload += ",\"last_name\":\"";
    payload += evt_in_last_name_;
    payload += "\",\"last_source\":\"";
    payload += evt_in_last_source_;
    payload += "\"}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "EVT_STREAM_START")) {
    uint32_t count = 0;
    uint32_t rate_hz = 0;
    String name;
    String source;
    String done_req_id;
    protocol_support::extractJsonUint(line, "count", &count);
    protocol_support::extractJsonUint(line, "rateHz", &rate_hz);
    protocol_support::extractJsonString(line, "name", &name);
    protocol_support::extractJsonString(line, "source", &source);
    protocol_support::extractJsonString(line, "doneReqId", &done_req_id);
    if (count == 0) count = 1000;
    if (rate_hz == 0) rate_hz = 200;
    if (rate_hz > 2000) rate_hz = 2000;
    if (!name.length()) name = "esp.stub.event";
    if (!source.length()) source = "esp.stub";
    evt_stream_active_ = true;
    evt_stream_target_count_ = count;
    evt_stream_sent_count_ = 0;
    evt_stream_drop_count_ = 0;
    evt_stream_rate_hz_ = rate_hz;
    evt_stream_interval_us_ = (1000000U / rate_hz);
    if (evt_stream_interval_us_ == 0) evt_stream_interval_us_ = 1;
    evt_stream_last_emit_us_ = 0;
    evt_stream_name_ = name;
    evt_stream_source_ = source;
    evt_stream_req_id_ = done_req_id.length() ? done_req_id : req_id;
    String payload = "{\"t\":\"EVT_STREAM_STATUS\",\"status\":\"started\",\"count\":";
    payload += evt_stream_target_count_;
    payload += ",\"rateHz\":";
    payload += evt_stream_rate_hz_;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "EVT_STREAM_STOP")) {
    bool active = evt_stream_active_;
    evt_stream_active_ = false;
    String payload = "{\"t\":\"EVT_STREAM_STATUS\",\"status\":\"stopped\",\"active\":";
    payload += (active ? "true" : "false");
    payload += ",\"sent\":";
    payload += evt_stream_sent_count_;
    payload += ",\"dropped\":";
    payload += evt_stream_drop_count_;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  return false;
}

void ProtocolHandler::service(unsigned long now_ms) {
  rules_runtime_.service(now_ms);
  lighting_runtime_.service(now_ms);
  RulesRuntime::EmittedEvent hw_evt;
  while (rules_runtime_.popEmittedEvent(&hw_evt)) {
    String payload = "{\"t\":\"EVT\",\"name\":\"";
    payload += hw_evt.event_name;
    payload += "\",\"source\":\"";
    payload += hw_evt.source;
    payload += "\",\"eventType\":\"";
    payload += hw_evt.event_type;
    payload += "\",\"seq\":";
    payload += hw_evt.seq;
    if (hw_evt.detail_ms > 0) {
      payload += ",\"detailMs\":";
      payload += hw_evt.detail_ms;
    }
    payload += ",\"tsMs\":";
    payload += hw_evt.ts_ms;
    payload += "}";
    if (!protocol_support::enqueueWithRetry(serial_, payload, 5)) {
      break;
    }
  }
  LightingRuntime::EmittedEvent light_evt;
  while (lighting_runtime_.popEmittedEvent(&light_evt)) {
    String payload = "{\"t\":\"EVT\",\"name\":\"";
    payload += light_evt.event_name;
    payload += "\",\"source\":\"";
    payload += light_evt.source;
    payload += "\",\"eventType\":\"";
    payload += light_evt.event_type;
    payload += "\",\"tsMs\":";
    payload += light_evt.ts_ms;
    payload += "}";
    if (!protocol_support::enqueueWithRetry(serial_, payload, 5)) {
      break;
    }
  }
  if (!evt_stream_active_) return;
  uint32_t attempted = evt_stream_sent_count_ + evt_stream_drop_count_;
  if (attempted >= evt_stream_target_count_) {
    String payload = "{\"t\":\"EVT_STREAM_DONE\",\"sent\":";
    payload += evt_stream_sent_count_;
    payload += ",\"dropped\":";
    payload += evt_stream_drop_count_;
    payload += ",\"attempted\":";
    payload += attempted;
    payload += ",\"count\":";
    payload += evt_stream_target_count_;
    payload += "}";
    if (protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, evt_stream_req_id_), 500)) {
      evt_stream_active_ = false;
    }
    return;
  }
  const uint32_t now_us = micros();
  if (evt_stream_last_emit_us_ != 0 && static_cast<uint32_t>(now_us - evt_stream_last_emit_us_) < evt_stream_interval_us_) {
    return;
  }
  evt_stream_last_emit_us_ = now_us;
  uint32_t seq = evt_stream_sent_count_ + evt_stream_drop_count_ + 1;
  String payload = "{\"t\":\"EVT\",\"name\":\"";
  payload += evt_stream_name_;
  payload += "\",\"source\":\"";
  payload += evt_stream_source_;
  payload += "\",\"seq\":";
  payload += seq;
  payload += ",\"tsMs\":";
  payload += now_ms;
  payload += "}";
  if (protocol_support::enqueueWithRetry(serial_, payload, 5)) {
    evt_stream_sent_count_++;
  } else {
    evt_stream_drop_count_++;
  }
}
