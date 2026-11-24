#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"
#include "drivers/Accelerometer/MMA8452.h"
#include "safety/CoilSafety.h"

bool ProtocolHandler::handleEventCommands(const String& line, const String& req_id, const String& cmd, JsonObject request) {
  if (cmd == "GET_RUNTIME_CLOCK") {
    JsonDocument response;
    response["t"] = "RUNTIME_CLOCK";
    response["tsMs"] = millis();
    response["reqId"] = req_id;
    String payload; serializeJson(response, payload);
    protocol_support::enqueueWithRetry(serial_, payload);
    return true;
  }
  if (cmd == "GET_INPUT_LEVELS") {
    JsonDocument inputs_request;
    JsonDocument response;
    response["t"] = "INPUT_LEVELS";
    response["reqId"] = req_id;
    JsonObject levels = response["levels"].to<JsonObject>();
    if (!deserializeJson(inputs_request, line)) {
      JsonArrayConst sources = inputs_request["sources"].as<JsonArrayConst>();
      if (sources.size() <= 16) {
        for (JsonVariantConst item : sources) {
          const char* source = item.as<const char*>();
          if (!source || strlen(source) > 128) continue;
          int level = rules_runtime_.watchedInputLevel(source);
          if (level >= 0) levels[source] = bool(level);
        }
      }
    }
    String payload;
    serializeJson(response, payload);
    protocol_support::enqueueWithRetry(serial_, payload);
    return true;
  }
  if (cmd == "RULE_ACTIONS") {
    bool accepted = rules_runtime_.applyHostActions(request);
    JsonDocument response;
    response["t"] = "RULE_ACTIONS_STATUS";
    response["accepted"] = accepted;
    response["reqId"] = req_id;
    String payload; serializeJson(response, payload);
    protocol_support::enqueueWithRetry(serial_, payload);
    return true;
  }
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
    if (evt_name.equalsIgnoreCase("ACCEL_STATUS_REQUEST") || evt_name.equalsIgnoreCase("ACCEL_QUERY")) {
      String payload = AccelerometerMMA8452::buildMetricsEventPayload(millis(), evt_name);
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
      return true;
    }
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
      payload += ",\"tsMs\":";
      payload += millis();
      payload += ",\"rulesVersion\":";
      payload += rules_runtime_.activeRulesVersion();
      payload += ",\"observedDevices\":";
      payload += rules_runtime_.deviceStatesJSON();
      payload += "}";
      protocol_support::enqueueWithRetry(serial_, payload);
    } else {
      String payload = "{\"t\":\"EVT\",\"synthetic\":true,\"rulesApplied\":true,\"name\":\"";
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
      payload += ",\"rulesVersion\":";
      payload += rules_runtime_.activeRulesVersion();
      payload += ",\"observedDevices\":";
      payload += rules_runtime_.deviceStatesJSON();
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
  if (coil_safety::takeHostTimeout() && !rules_runtime_.recoveryPaused()) {
    // Discard pre-timeout gestures while allowing the ESP to track new switch edges.
    rules_runtime_.pauseForRecovery();
    rules_runtime_.resumeAfterRecovery();
  }
  rules_runtime_.service(now_ms);
  coil_safety::serviceArming(fs_mounted_ && rules_ready_ && !blob_active_ && !rules_runtime_.recoveryPaused());
  lighting_runtime_.service(now_ms);
  while (const auto* event = rules_runtime_.nextEmittedEvent()) {
    // Reserve a transmit slot for control replies, including safety status.
    if (serial_.queueFree() <= 1) break;
    if (!serial_.enqueueTyped(compact_event::kFrameType, event->data(), event->size())) break;
    rules_runtime_.consumeEmittedEvent();
  }
  const uint32_t dropped = rules_runtime_.droppedInputEvents();
  if (reported_input_drops_ != dropped) {
    String loss = "{\"t\":\"EVENT_INPUT_LOSS\",\"dropped\":";
    loss += static_cast<uint32_t>(dropped - reported_input_drops_);
    loss += "}";
    if (serial_.enqueue(loss)) reported_input_drops_ = dropped;
  }
  LightingRuntime::EmittedEvent light_evt;
  while (serial_.queueFree() > 1 && lighting_runtime_.popEmittedEvent(&light_evt)) {
    String payload = "{\"t\":\"EVT\",\"name\":\"";
    payload += light_evt.event_name;
    payload += "\",\"source\":\"";
    payload += light_evt.source;
    payload += "\",\"eventType\":\"";
    payload += light_evt.event_type;
    payload += "\",\"tsMs\":";
    payload += light_evt.ts_ms;
    payload += ",\"rulesVersion\":";
    payload += rules_runtime_.activeRulesVersion();
    payload += ",\"observedDevices\":";
    payload += rules_runtime_.deviceStatesJSON();
    payload += "}";
    if (!protocol_support::enqueueWithRetry(serial_, payload, 5)) {
      break;
    }
  }
  AccelerometerMMA8452::Event accel_evt;
  while (serial_.queueFree() > 1 && AccelerometerMMA8452::popEvent(&accel_evt)) {
    String payload = "{\"t\":\"EVT\",\"name\":\"";
    payload += accel_evt.source;
    payload += "_";
    payload += accel_evt.event_type;
    payload += "\",\"source\":\"";
    payload += accel_evt.source;
    payload += "\",\"eventType\":\"";
    payload += accel_evt.event_type;
    payload += "\",\"angleDeg\":";
    payload += String(accel_evt.angle_deg, 2);
    payload += ",\"joltG\":";
    payload += String(accel_evt.jolt_g, 3);
    payload += ",\"tsMs\":";
    payload += accel_evt.ts_ms;
    payload += ",\"rulesVersion\":";
    payload += rules_runtime_.activeRulesVersion();
    payload += ",\"observedDevices\":";
    payload += rules_runtime_.deviceStatesJSON();
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
  const compact_event::Encoder event(evt_stream_name_.c_str(), evt_stream_source_.c_str(), "",
                                     seq, now_ms, 0, 0, false, -1);
  if (serial_.queueFree() > 1 &&
      serial_.enqueueTyped(compact_event::kFrameType, event.bytes.data(), event.bytes.size())) {
    evt_stream_sent_count_++;
  } else {
    evt_stream_drop_count_++;
  }
}
