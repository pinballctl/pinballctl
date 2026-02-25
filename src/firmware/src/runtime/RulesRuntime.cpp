#include "runtime/RulesRuntime.h"

#include <LittleFS.h>
#include <miniz.h>
#include <stdlib.h>
#include <vector>

namespace rules_runtime_internal {
constexpr size_t kRulesBlobHeaderSizeRr = 44;

uint16_t rr_read_u16_le(const uint8_t* buf) {
  return static_cast<uint16_t>(buf[0]) | (static_cast<uint16_t>(buf[1]) << 8);
}

uint32_t rr_read_u32_le(const uint8_t* buf) {
  return static_cast<uint32_t>(buf[0]) |
         (static_cast<uint32_t>(buf[1]) << 8) |
         (static_cast<uint32_t>(buf[2]) << 16) |
         (static_cast<uint32_t>(buf[3]) << 24);
}

bool looksLikeJsonText(const std::vector<uint8_t>& bytes) {
  if (bytes.empty()) return false;
  size_t idx = 0;
  while (idx < bytes.size()) {
    uint8_t c = bytes[idx];
    if (c == ' ' || c == '\t' || c == '\r' || c == '\n') {
      idx++;
      continue;
    }
    break;
  }
  if (idx >= bytes.size()) return false;
  if (bytes[idx] != '{' && bytes[idx] != '[') return false;
  for (size_t i = 0; i < bytes.size(); ++i) {
    uint8_t c = bytes[i];
    if (c == '\t' || c == '\r' || c == '\n') continue;
    if (c < 0x20 || c > 0x7E) return false;
  }
  return true;
}
}  // namespace rules_runtime_internal

RulesRuntime::RulesRuntime() = default;

String RulesRuntime::upper(const String& s) {
  String out = s;
  out.toUpperCase();
  return out;
}

bool RulesRuntime::parseTargetGpio(const String& target, int* pin_out) {
  if (!pin_out) return false;
  int idx = target.lastIndexOf("__GPIO__");
  if (idx < 0) return false;
  String tail = target.substring(idx + 8);
  tail.trim();
  if (!tail.length()) return false;
  for (size_t i = 0; i < tail.length(); ++i) {
    char c = tail[i];
    if (c < '0' || c > '9') return false;
  }
  int pin = tail.toInt();
  if (pin < 0) return false;
  *pin_out = pin;
  return true;
}

bool RulesRuntime::parseOutputValue(const String& action_type, const String& value, bool* out_high) {
  if (!out_high) return false;
  String t = upper(action_type);
  String v = upper(value);
  v.trim();
  if (t == "PULSE" || t == "PULSE_COIL") {
    *out_high = true;
    return true;
  }
  if (v == "PULSE") {
    *out_high = true;
    return true;
  }
  if (v == "HIGH" || v == "ON" || v == "TRUE" || v == "1") {
    *out_high = true;
    return true;
  }
  if (v == "LOW" || v == "OFF" || v == "FALSE" || v == "0") {
    *out_high = false;
    return true;
  }
  return false;
}

bool parseDurationMsField(JsonObject params, const char* key, uint32_t* out_ms) {
  if (!out_ms) return false;
  JsonVariant v = params[key];
  if (v.is<uint32_t>()) {
    uint32_t n = v.as<uint32_t>();
    if (n > 0) {
      *out_ms = n;
      return true;
    }
    return false;
  }
  if (v.is<int>()) {
    int n = v.as<int>();
    if (n > 0) {
      *out_ms = static_cast<uint32_t>(n);
      return true;
    }
    return false;
  }
  if (v.is<const char*>()) {
    String s = String(v.as<const char*>());
    s.trim();
    if (!s.length()) return false;
    char* end_ptr = nullptr;
    long parsed = strtol(s.c_str(), &end_ptr, 10);
    if (!end_ptr || *end_ptr != '\0') return false;
    if (parsed <= 0) return false;
    *out_ms = static_cast<uint32_t>(parsed);
    return true;
  }
  return false;
}

bool RulesRuntime::extractGzipDeflatePayload(
    const std::vector<uint8_t>& in, const uint8_t** deflate_ptr, size_t* deflate_len) {
  if (!deflate_ptr || !deflate_len) return false;
  if (in.size() < 18) return false;
  if (in[0] != 0x1F || in[1] != 0x8B || in[2] != 0x08) return false;

  uint8_t flg = in[3];
  size_t pos = 10;
  const size_t n = in.size();
  if ((flg & 0x04) != 0) {  // FEXTRA
    if (pos + 2 > n) return false;
    uint16_t xlen = rules_runtime_internal::rr_read_u16_le(&in[pos]);
    pos += 2;
    if (pos + xlen > n) return false;
    pos += xlen;
  }
  if ((flg & 0x08) != 0) {  // FNAME
    while (pos < n && in[pos] != 0) pos++;
    if (pos >= n) return false;
    pos++;
  }
  if ((flg & 0x10) != 0) {  // FCOMMENT
    while (pos < n && in[pos] != 0) pos++;
    if (pos >= n) return false;
    pos++;
  }
  if ((flg & 0x02) != 0) {  // FHCRC
    if (pos + 2 > n) return false;
    pos += 2;
  }

  if (pos + 8 > n) return false;
  *deflate_ptr = &in[pos];
  *deflate_len = n - pos - 8;  // strip trailer crc32+isize
  return true;
}

bool RulesRuntime::parseRuleActions(JsonObject rule, std::vector<RuleAction>* actions_out) {
  if (!actions_out) return false;
  actions_out->clear();
  JsonVariant actions_var = rule["actions"];
  if (!actions_var.is<JsonArray>()) return true;

  for (JsonVariant action_var : actions_var.as<JsonArray>()) {
    if (!action_var.is<JsonObject>()) continue;
    JsonObject action = action_var.as<JsonObject>();
    String action_type = action["type"].is<const char*>() ? String(action["type"].as<const char*>()) : String("");
    action_type.trim();
    String action_type_upper = upper(action_type);
    if (action_type_upper != "SET_OUTPUT" && action_type_upper != "PULSE" && action_type_upper != "PULSE_COIL") {
      continue;
    }

    String target = action["target"].is<const char*>() ? String(action["target"].as<const char*>()) : String("");
    int pin = -1;
    if (!parseTargetGpio(target, &pin)) continue;

    String raw_value = "";
    JsonVariant params = action["params"];
    if (params.is<JsonObject>()) {
      JsonObject p = params.as<JsonObject>();
      if (p["value"].is<const char*>()) {
        raw_value = String(p["value"].as<const char*>());
      } else if (p["value"].is<bool>()) {
        raw_value = p["value"].as<bool>() ? "HIGH" : "LOW";
      } else if (p["value"].is<int>()) {
        raw_value = p["value"].as<int>() ? "HIGH" : "LOW";
      } else if (p["state"].is<const char*>()) {
        raw_value = String(p["state"].as<const char*>());
      } else if (p["state"].is<bool>()) {
        raw_value = p["state"].as<bool>() ? "HIGH" : "LOW";
      }
    }

    bool value_high = false;
    if (!parseOutputValue(action_type_upper, raw_value, &value_high)) continue;
    RuleAction a;
    bool value_is_pulse = (upper(raw_value) == "PULSE");
    a.kind = (action_type_upper == "SET_OUTPUT" && !value_is_pulse) ? RuleAction::SET_OUTPUT : RuleAction::PULSE;
    a.pin = pin;
    a.value_high = value_high;
    if (a.kind == RuleAction::PULSE) {
      uint32_t dur = 0;
      if (params.is<JsonObject>()) {
        JsonObject p = params.as<JsonObject>();
        parseDurationMsField(p, "durationMs", &dur);
        if (dur == 0) parseDurationMsField(p, "ms", &dur);
        if (dur == 0) parseDurationMsField(p, "pulseMs", &dur);
      }
      if (dur == 0) dur = 30;
      if (dur > 10000) dur = 10000;
      a.duration_ms = dur;
    }
    actions_out->push_back(a);
  }
  return true;
}

void RulesRuntime::appendTriggers(
    JsonObject rule, const std::vector<RuleAction>& actions, std::vector<EventRule>* out_rules) {
  if (!out_rules) return;
  auto append_trigger = [&](JsonObject trigger_obj) {
    String event_name = trigger_obj["event"].is<const char*>() ? String(trigger_obj["event"].as<const char*>()) : String("");
    event_name.trim();
    if (!event_name.length()) return;
    String source = trigger_obj["source"].is<const char*>() ? String(trigger_obj["source"].as<const char*>()) : String("");
    source.trim();
    String fn = trigger_obj["fn"].is<const char*>() ? String(trigger_obj["fn"].as<const char*>()) : String("");
    fn.trim();
    EventRule rt;
    rt.event_name = event_name;
    rt.source = source;
    rt.event_type = upper(fn);
    rt.actions = actions;
    out_rules->push_back(rt);
  };

  bool added_from_groups = false;
  JsonVariant trigger_groups_var = rule["triggerGroups"];
  if (trigger_groups_var.is<JsonObject>()) {
    JsonObject trigger_groups = trigger_groups_var.as<JsonObject>();
    JsonVariant groups_var = trigger_groups["groups"];
    if (groups_var.is<JsonArray>()) {
      for (JsonVariant group_var : groups_var.as<JsonArray>()) {
        if (!group_var.is<JsonObject>()) continue;
        JsonObject group = group_var.as<JsonObject>();
        JsonVariant items_var = group["items"];
        if (!items_var.is<JsonArray>()) continue;
        for (JsonVariant item_var : items_var.as<JsonArray>()) {
          if (!item_var.is<JsonObject>()) continue;
          append_trigger(item_var.as<JsonObject>());
          added_from_groups = true;
        }
      }
    }
  }
  if (!added_from_groups) {
    JsonVariant legacy_triggers_var = rule["triggers"];
    if (legacy_triggers_var.is<JsonArray>()) {
      for (JsonVariant item_var : legacy_triggers_var.as<JsonArray>()) {
        if (!item_var.is<JsonObject>()) continue;
        append_trigger(item_var.as<JsonObject>());
      }
    }
  }
}

bool RulesRuntime::compileFromRulesArray(JsonVariant rules_var, String* error) {
  if (!rules_var.is<JsonArray>()) {
    if (error) *error = "rules_missing";
    return false;
  }
  std::vector<EventRule> compiled;
  for (JsonVariant rule_var : rules_var.as<JsonArray>()) {
    if (!rule_var.is<JsonObject>()) continue;
    JsonObject rule = rule_var.as<JsonObject>();
    bool enabled = rule["enabled"].is<bool>() ? rule["enabled"].as<bool>() : true;
    if (!enabled) continue;
    std::vector<RuleAction> actions;
    if (!parseRuleActions(rule, &actions)) continue;
    if (actions.empty()) continue;
    appendTriggers(rule, actions, &compiled);
  }
  rules_.swap(compiled);
  return true;
}

bool RulesRuntime::loadFromSetRulesCommand(const String& payload_line, String* error) {
  size_t cap = static_cast<size_t>(payload_line.length()) * 3 + 4096;
  if (cap < 8192) cap = 8192;
  if (cap > 262144) cap = 262144;
  DynamicJsonDocument doc(cap);
  DeserializationError jerr = deserializeJson(doc, payload_line);
  if (jerr) {
    if (error) *error = "rules_json_invalid";
    return false;
  }
  return compileFromRulesArray(doc["rules"], error);
}

bool RulesRuntime::loadFromRulesBlob(const char* path, String* error) {
  if (!path || !path[0]) {
    if (error) *error = "bad_path";
    return false;
  }
  fs::File f = LittleFS.open(path, "r");
  if (!f) {
    if (error) *error = "open_failed";
    return false;
  }
  size_t size = f.size();
  if (size < rules_runtime_internal::kRulesBlobHeaderSizeRr) {
    if (error) *error = "bad_size";
    return false;
  }

  std::vector<uint8_t> blob(size);
  if (f.read(blob.data(), size) != static_cast<int>(size)) {
    if (error) *error = "read_failed";
    return false;
  }
  if (memcmp(blob.data(), "PDR1", 4) != 0) {
    if (error) *error = "bad_magic";
    return false;
  }

  uint16_t version = rules_runtime_internal::rr_read_u16_le(blob.data() + 4);
  uint16_t flags = rules_runtime_internal::rr_read_u16_le(blob.data() + 6);
  uint32_t payload_len = rules_runtime_internal::rr_read_u32_le(blob.data() + 8);
  if (version != 1) {
    if (error) *error = "bad_version";
    return false;
  }
  if (size != rules_runtime_internal::kRulesBlobHeaderSizeRr + payload_len) {
    if (error) *error = "size_mismatch";
    return false;
  }

  std::vector<uint8_t> payload(blob.begin() + rules_runtime_internal::kRulesBlobHeaderSizeRr, blob.end());
  std::vector<uint8_t> json_bytes;
  if (flags & 0x1) {
    // Gzip trailer stores original uncompressed size modulo 2^32 (ISIZE).
    if (payload.size() < 8) {
      if (error) *error = "gzip_short";
      return false;
    }
    const size_t payload_n = payload.size();
    uint32_t expected_isize = rules_runtime_internal::rr_read_u32_le(payload.data() + payload_n - 4);
    if (expected_isize == 0 || expected_isize > 512000) {
      if (error) *error = "gzip_size_invalid";
      return false;
    }
    const uint8_t* deflate_ptr = nullptr;
    size_t deflate_len = 0;
    if (!extractGzipDeflatePayload(payload, &deflate_ptr, &deflate_len)) {
      if (error) *error = "gzip_header_invalid";
      return false;
    }
    json_bytes.resize(expected_isize);
    size_t out_len = tinfl_decompress_mem_to_mem(
        json_bytes.data(),
        json_bytes.size(),
        deflate_ptr,
        deflate_len,
        TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF);
    if (out_len == static_cast<size_t>(-1) || out_len == 0 || out_len > json_bytes.size()) {
      if (error) *error = "gzip_decompress_failed";
      return false;
    }
    json_bytes.resize(out_len);
  } else {
    json_bytes = payload;
  }

  if (json_bytes.empty()) {
    if (error) *error = "payload_empty";
    return false;
  }
  if (json_bytes.size() > 131072) {
    if (error) *error = "payload_too_large";
    return false;
  }
  if (!rules_runtime_internal::looksLikeJsonText(json_bytes)) {
    if (error) *error = "payload_not_json_text";
    return false;
  }
  DynamicJsonDocument doc(json_bytes.size() + 8192);
  DeserializationError jerr = deserializeJson(doc, json_bytes.data(), json_bytes.size());
  if (jerr) {
    if (error) *error = "payload_json_invalid";
    return false;
  }
  JsonVariant rules_var = doc.as<JsonVariant>();
  if (rules_var.is<JsonObject>()) {
    rules_var = rules_var["rules"];
  }
  return compileFromRulesArray(rules_var, error);
}

void RulesRuntime::applyEvent(const String& event_name, const String& source, const String& event_type, unsigned long now_ms) {
  if (!event_name.length()) return;
  String event_type_upper = upper(event_type);
  for (const auto& rule : rules_) {
    if (rule.event_name != event_name) continue;
    if (rule.source.length() && rule.source != source) continue;
    if (rule.event_type.length() && rule.event_type != event_type_upper) continue;
    for (const auto& action : rule.actions) {
      if (action.pin < 0) continue;
      stopPulseForPin(action.pin);
      pinMode(action.pin, OUTPUT);
      if (action.kind == RuleAction::SET_OUTPUT) {
        digitalWrite(action.pin, action.value_high ? HIGH : LOW);
      } else {
        digitalWrite(action.pin, HIGH);
        ActivePulse pulse;
        pulse.pin = action.pin;
        pulse.end_ms = now_ms + action.duration_ms;
        active_pulses_.push_back(pulse);
      }
    }
  }
}

void RulesRuntime::service(unsigned long now_ms) {
  if (active_pulses_.empty()) return;
  for (size_t i = 0; i < active_pulses_.size();) {
    const ActivePulse pulse = active_pulses_[i];
    if (static_cast<long>(now_ms - pulse.end_ms) < 0) {
      ++i;
      continue;
    }
    pinMode(pulse.pin, OUTPUT);
    digitalWrite(pulse.pin, LOW);
    active_pulses_.erase(active_pulses_.begin() + i);
  }
}

void RulesRuntime::stopPulseForPin(int pin) {
  if (pin < 0 || active_pulses_.empty()) return;
  for (size_t i = 0; i < active_pulses_.size();) {
    if (active_pulses_[i].pin != pin) {
      ++i;
      continue;
    }
    active_pulses_.erase(active_pulses_.begin() + i);
  }
}

void RulesRuntime::clear() {
  rules_.clear();
  active_pulses_.clear();
}
