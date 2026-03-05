#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/runtime/RulesRuntime.cpp"
#include "runtime/RulesRuntime.h"

#include <LittleFS.h>
#include <miniz.h>
#include <stdlib.h>
#include <vector>

#include "drivers/DriverRegistry.h"
#include "hardware/MappingBlob.h"

namespace rules_runtime_internal {
constexpr size_t kRulesBlobHeaderSizeRr = 44;
constexpr const char* kMappingBlobPath = "/cfg/mapping.pb";
constexpr uint32_t kNonCoilAutoReleaseMs = 350;

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
  if (t == "PULSE") {
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

bool parsePositiveMsFromVariant(JsonVariant v, uint32_t* out_ms) {
  if (!out_ms) return false;
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

bool parseIntFromVariant(JsonVariant v, int* out_value) {
  if (!out_value) return false;
  if (v.is<int>()) {
    *out_value = v.as<int>();
    return true;
  }
  if (v.is<uint32_t>()) {
    *out_value = static_cast<int>(v.as<uint32_t>());
    return true;
  }
  if (v.is<const char*>()) {
    String s = String(v.as<const char*>());
    s.trim();
    if (!s.length()) return false;
    char* end_ptr = nullptr;
    long parsed = strtol(s.c_str(), &end_ptr, 0);
    if (!end_ptr || *end_ptr != '\0') return false;
    *out_value = static_cast<int>(parsed);
    return true;
  }
  return false;
}

bool parseBoolFromVariant(JsonVariant v, bool* out_value) {
  if (!out_value) return false;
  if (v.is<bool>()) {
    *out_value = v.as<bool>();
    return true;
  }
  if (v.is<int>()) {
    *out_value = (v.as<int>() != 0);
    return true;
  }
  if (v.is<const char*>()) {
    String s = String(v.as<const char*>());
    s.trim();
    s.toLowerCase();
    if (s == "1" || s == "true" || s == "yes" || s == "on") {
      *out_value = true;
      return true;
    }
    if (s == "0" || s == "false" || s == "no" || s == "off") {
      *out_value = false;
      return true;
    }
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
    JsonVariant params = action["params"];
    if (action_type_upper == "SET_LCD_TEXT") {
      if (!params.is<JsonObject>()) continue;
      JsonObject p = params.as<JsonObject>();
      int sda_pin = -1;
      int scl_pin = -1;
      if (!parseIntFromVariant(p["sdaPin"], &sda_pin)) continue;
      if (!parseIntFromVariant(p["sclPin"], &scl_pin)) continue;
      if (sda_pin < 0 || scl_pin < 0 || sda_pin == scl_pin) continue;
      int address_val = 0x27;
      parseIntFromVariant(p["address"], &address_val);
      if (address_val < 0x03 || address_val > 0x77) address_val = 0x27;
      int cols = 16;
      int rows = 2;
      parseIntFromVariant(p["cols"], &cols);
      parseIntFromVariant(p["rows"], &rows);
      if (cols < 8) cols = 8;
      if (cols > 40) cols = 40;
      if (rows < 1) rows = 1;
      if (rows > 4) rows = 4;
      bool clear_first = false;
      parseBoolFromVariant(p["clearFirst"], &clear_first);
      String target = action["target"].is<const char*>() ? String(action["target"].as<const char*>()) : String("");
      String driver = p["driver"].is<const char*>() ? String(p["driver"].as<const char*>()) : String("");
      String line1 = p["line1"].is<const char*>() ? String(p["line1"].as<const char*>()) : String("");
      String line2 = p["line2"].is<const char*>() ? String(p["line2"].as<const char*>()) : String("");
      if (line1.length() > static_cast<unsigned int>(cols)) line1 = line1.substring(0, cols);
      if (line2.length() > static_cast<unsigned int>(cols)) line2 = line2.substring(0, cols);

      RuleAction a;
      a.kind = RuleAction::LCD_TEXT;
      a.sda_pin = sda_pin;
      a.scl_pin = scl_pin;
      a.lcd_addr = static_cast<uint8_t>(address_val);
      a.lcd_cols = static_cast<uint8_t>(cols);
      a.lcd_rows = static_cast<uint8_t>(rows);
      a.lcd_clear_first = clear_first;
      a.lcd_target = target;
      driver.trim();
      a.lcd_driver = driver.length() ? driver : String("Default");
      a.lcd_line1 = line1;
      a.lcd_line2 = line2;
      actions_out->push_back(a);
      continue;
    }
    if (action_type_upper == "SET_LIGHTING_PIXELS") {
      if (!params.is<JsonObject>()) continue;
      JsonObject p = params.as<JsonObject>();
      String target = action["target"].is<const char*>() ? String(action["target"].as<const char*>()) : String("");
      if (!target.length() && p["fixtureId"].is<const char*>()) {
        target = String(p["fixtureId"].as<const char*>());
      }
      target.trim();
      int pin = -1;
      if (!parseTargetGpio(target, &pin)) continue;

      int pixel_count = 1;
      parseIntFromVariant(p["pixelCount"], &pixel_count);
      if (pixel_count < 1) pixel_count = 1;
      if (pixel_count > 2048) pixel_count = 2048;

      JsonVariant idx_var = p["pixelIndexes"];
      if (!idx_var.is<JsonArray>()) continue;
      std::vector<uint16_t> indexes;
      for (JsonVariant v : idx_var.as<JsonArray>()) {
        int idx = -1;
        if (!parseIntFromVariant(v, &idx)) continue;
        if (idx < 0 || idx >= pixel_count) continue;
        indexes.push_back(static_cast<uint16_t>(idx));
      }
      if (indexes.empty()) continue;

      String mode = p["mode"].is<const char*>() ? String(p["mode"].as<const char*>()) : String("on");
      mode.trim();
      mode.toLowerCase();
      if (mode != "on" && mode != "off" && mode != "blink") mode = "on";

      String color = p["color"].is<const char*>() ? String(p["color"].as<const char*>()) : String("#ffffff");
      color.trim();
      if (!color.length()) color = "#ffffff";
      if (!color.startsWith("#")) color = String("#") + color;
      color.toLowerCase();
      if (color.length() != 7) color = "#ffffff";

      float brightness = 1.0f;
      if (p["brightness"].is<float>()) brightness = p["brightness"].as<float>();
      else if (p["brightness"].is<int>()) brightness = static_cast<float>(p["brightness"].as<int>());
      if (brightness < 0.0f) brightness = 0.0f;
      if (brightness > 1.0f) brightness = 1.0f;

      int blink_count = 2;
      parseIntFromVariant(p["blinkCount"], &blink_count);
      if (blink_count < 1) blink_count = 1;
      if (blink_count > 1000) blink_count = 1000;

      uint32_t blink_interval_ms = 150;
      parseDurationMsField(p, "blinkIntervalMs", &blink_interval_ms);
      if (blink_interval_ms < 50) blink_interval_ms = 50;
      if (blink_interval_ms > 60000) blink_interval_ms = 60000;

      String driver = p["driver"].is<const char*>() ? String(p["driver"].as<const char*>()) : String("");
      driver.trim();
      if (!driver.length()) driver = "Default";

      RuleAction a;
      a.kind = RuleAction::LIGHT_PIXELS;
      a.pin = pin;
      a.target = target;
      a.driver = driver;
      a.pixel_indexes = indexes;
      a.pixel_count = static_cast<uint16_t>(pixel_count);
      a.pixels_mode = mode;
      a.pixels_color = color;
      a.pixels_brightness = brightness;
      a.pixels_blink_count = static_cast<uint16_t>(blink_count);
      a.pixels_blink_interval_ms = blink_interval_ms;
      actions_out->push_back(a);
      continue;
    }
    if (action_type_upper != "SET_OUTPUT" && action_type_upper != "PULSE") {
      continue;
    }

    String target = action["target"].is<const char*>() ? String(action["target"].as<const char*>()) : String("");
    int pin = -1;
    if (!parseTargetGpio(target, &pin)) continue;
    String driver = "";
    if (params.is<JsonObject>()) {
      JsonObject p = params.as<JsonObject>();
      if (p["driver"].is<const char*>()) {
        driver = String(p["driver"].as<const char*>());
        driver.trim();
      }
    }

    String raw_value = "";
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
    a.target = target;
    a.driver = driver;
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
  auto append_trigger = [&](JsonObject trigger_obj, uint32_t group_window_ms) {
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
    rt.min_ms = 0;
    rt.repeat_ms = 0;
    rt.window_ms = 0;
    JsonVariant params_var = trigger_obj["params"];
    if (params_var.is<JsonObject>()) {
      JsonObject params = params_var.as<JsonObject>();
      parseDurationMsField(params, "minMs", &rt.min_ms);
      parseDurationMsField(params, "repeatMs", &rt.repeat_ms);
      parseDurationMsField(params, "windowMs", &rt.window_ms);
    }
    if (rt.event_type == "DOUBLE_CLICKED" && rt.window_ms == 0) {
      rt.window_ms = group_window_ms > 0 ? group_window_ms : 280;
    }
    if (rt.event_type == "HELD" && rt.min_ms == 0) {
      rt.min_ms = 450;
    }
    if (rt.event_type == "REPEAT_WHILE_HELD" && rt.repeat_ms == 0) {
      rt.repeat_ms = 120;
    }
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
        uint32_t group_window_ms = 0;
        parsePositiveMsFromVariant(group["windowMs"], &group_window_ms);
        if (group_window_ms == 0) group_window_ms = 750;
        JsonVariant items_var = group["items"];
        if (!items_var.is<JsonArray>()) continue;
        for (JsonVariant item_var : items_var.as<JsonArray>()) {
          if (!item_var.is<JsonObject>()) continue;
          append_trigger(item_var.as<JsonObject>(), group_window_ms);
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
        append_trigger(item_var.as<JsonObject>(), 0);
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
  std::vector<ReleasePair> release_pairs;
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
  for (const auto& rule : compiled) {
    if (rule.source.isEmpty()) continue;
    if (rule.event_type != "RELEASED") continue;
    for (const auto& action : rule.actions) {
      if (action.kind != RuleAction::SET_OUTPUT) continue;
      if (action.value_high) continue;
      if (action.pin < 0) continue;
      bool exists = false;
      for (const auto& pair : release_pairs) {
        if (pair.pin == action.pin && pair.source == rule.source) {
          exists = true;
          break;
        }
      }
      if (exists) continue;
      ReleasePair pair;
      pair.source = rule.source;
      pair.pin = action.pin;
      pair.target = action.target;
      pair.driver = action.driver;
      release_pairs.push_back(pair);
    }
  }
  rules_.swap(compiled);
  release_pairs_.swap(release_pairs);
  held_outputs_.clear();
  rebuildSourceWatches(rules_);
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

bool RulesRuntime::applyEvent(
    const String& event_name,
    const String& source,
    const String& event_type,
    uint32_t seq,
    unsigned long now_ms,
    uint32_t detail_ms) {
  if (!event_name.length()) return false;
  String event_type_upper = upper(event_type);
  if (!acceptEventSeq(event_name, source, seq)) {
    // Never drop RELEASED as stale; dropping release edges can leave outputs latched.
    if (event_type_upper != "RELEASED") {
      restoreSafeStateForStaleEvent(source);
      return false;
    }
  }
  if (event_type_upper == "RELEASED" && source.length()) {
    forceReleasePairsForSource(source);
    clearHeldOutputsForSource(source);
  }
  for (const auto& rule : rules_) {
    if (rule.event_name != event_name) continue;
    if (rule.source.length() && rule.source != source) continue;
    if (rule.event_type.length() && rule.event_type != event_type_upper) continue;
    if (event_type_upper == "HELD" && rule.min_ms > 0 && detail_ms > 0 && detail_ms != rule.min_ms) continue;
    if (event_type_upper == "REPEAT_WHILE_HELD" && rule.repeat_ms > 0 && detail_ms > 0 && detail_ms != rule.repeat_ms) continue;
    if (event_type_upper == "DOUBLE_CLICKED" && rule.window_ms > 0 && detail_ms > 0 && detail_ms > rule.window_ms) continue;
    for (const auto& action : rule.actions) {
      if (action.kind == RuleAction::LCD_TEXT) {
        driver_registry::writeDisplayTextForTarget(
            rules_runtime_internal::kMappingBlobPath,
            action.lcd_target,
            action.lcd_driver,
            action.sda_pin,
            action.scl_pin,
            action.lcd_addr,
            action.lcd_line1,
            action.lcd_line2,
            action.lcd_cols,
            action.lcd_rows,
            action.lcd_clear_first);
        continue;
      }
      if (action.kind == RuleAction::LIGHT_PIXELS) {
        if (action.pin < 0 || action.pixel_indexes.empty()) continue;
        String resolved_fn;
        String resolved_driver;
        String impl;
        String write_error;
        driver_registry::writeRgbPixelsForTarget(
            rules_runtime_internal::kMappingBlobPath,
            action.target,
            action.driver,
            action.pin,
            action.pixel_count,
            action.pixel_indexes,
            action.pixels_mode,
            action.pixels_color,
            action.pixels_brightness,
            action.pixels_blink_count,
            action.pixels_blink_interval_ms,
            &resolved_fn,
            &resolved_driver,
            &impl,
            &write_error);
        continue;
      }
      if (action.pin < 0) continue;
      stopPulseForPin(action.pin);
      if (action.kind == RuleAction::SET_OUTPUT) {
        driveOutputTarget(action.target, action.driver, action.pin, action.value_high);
        if (!source.length()) continue;
        if (event_type_upper == "PRESSED" && action.value_high && hasReleasePair(source, action.pin)) {
          markHeldOutput(source, action.pin, action.target, action.driver);
        } else if (event_type_upper == "RELEASED" || !action.value_high) {
          clearHeldOutput(source, action.pin);
        }
      } else {
        driveOutputTarget(action.target, action.driver, action.pin, true);
        ActivePulse pulse;
        pulse.pin = action.pin;
        pulse.end_ms = now_ms + action.duration_ms;
        pulse.target = action.target;
        pulse.driver = action.driver;
        active_pulses_.push_back(pulse);
      }
    }
  }
  return true;
}

void RulesRuntime::service(unsigned long now_ms) {
  serviceInputWatches(now_ms);
  for (size_t i = 0; i < active_pulses_.size();) {
    const ActivePulse pulse = active_pulses_[i];
    if (static_cast<long>(now_ms - pulse.end_ms) < 0) {
      ++i;
      continue;
    }
    driveOutputTarget(pulse.target, pulse.driver, pulse.pin, false);
    active_pulses_.erase(active_pulses_.begin() + i);
  }
  for (size_t i = 0; i < held_outputs_.size();) {
    const HeldOutput& held = held_outputs_[i];
    if (held.auto_release_at_ms == 0 || static_cast<long>(now_ms - held.auto_release_at_ms) < 0) {
      ++i;
      continue;
    }
    if (held.pin >= 0) {
      driveOutputTarget(held.target, held.driver, held.pin, false);
    }
    held_outputs_.erase(held_outputs_.begin() + i);
  }
}

bool RulesRuntime::popEmittedEvent(EmittedEvent* out_event) {
  if (!out_event || emitted_events_.empty()) return false;
  *out_event = emitted_events_.front();
  emitted_events_.erase(emitted_events_.begin());
  return true;
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

bool RulesRuntime::driveOutputTarget(const String& target, const String& driver, int pin, bool high) {
  return driver_registry::writeOutputForTarget(
      rules_runtime_internal::kMappingBlobPath,
      target,
      driver,
      pin,
      high);
}

void RulesRuntime::clear() {
  rules_.clear();
  active_pulses_.clear();
  release_pairs_.clear();
  held_outputs_.clear();
  event_seq_state_.clear();
  source_watches_.clear();
  emitted_events_.clear();
}

void RulesRuntime::rebuildSourceWatches(const std::vector<EventRule>& compiled_rules) {
  source_watches_.clear();
  for (const auto& rule : compiled_rules) {
    if (!rule.source.length()) continue;
    int pin = -1;
    if (!parseTargetGpio(rule.source, &pin)) continue;
    SourceWatch* watch = findOrCreateWatch(rule.source, pin);
    if (!watch) continue;
    appendWatchEventNameUnique(watch, rule.event_name);
    if (rule.event_type == "DOUBLE_CLICKED") {
      watch->button_cfg.enable_double_click = true;
      uint32_t w = rule.window_ms > 0 ? rule.window_ms : 280;
      if (w > watch->button_cfg.double_click_window_ms) watch->button_cfg.double_click_window_ms = w;
    } else if (rule.event_type == "HELD") {
      uint32_t threshold_ms = rule.min_ms > 0 ? rule.min_ms : 450;
      watch->button_cfg.held_thresholds_ms.push_back(threshold_ms);
    } else if (rule.event_type == "REPEAT_WHILE_HELD") {
      uint32_t interval_ms = rule.repeat_ms > 0 ? rule.repeat_ms : 120;
      watch->button_cfg.repeat_intervals_ms.push_back(interval_ms);
    }
  }
  for (auto& watch : source_watches_) {
    watch.button.bindPin(watch.pin);
    watch.button.configure(watch.button_cfg);
  }
}

RulesRuntime::SourceWatch* RulesRuntime::findOrCreateWatch(const String& source, int pin) {
  for (auto& watch : source_watches_) {
    if (watch.source != source) continue;
    if (watch.pin != pin) {
      watch.pin = pin;
      watch.event_names.clear();
      watch.button_cfg = ButtonDefault::Config();
      watch.button.bindPin(pin);
      watch.button.reset();
    }
    return &watch;
  }
  SourceWatch watch;
  watch.source = source;
  watch.pin = pin;
  watch.button_cfg = ButtonDefault::Config();
  watch.button.bindPin(pin);
  source_watches_.push_back(watch);
  return &source_watches_.back();
}

void RulesRuntime::appendWatchEventNameUnique(SourceWatch* watch, const String& event_name) {
  if (!watch || !event_name.length()) return;
  for (const auto& existing : watch->event_names) {
    if (existing == event_name) return;
  }
  watch->event_names.push_back(event_name);
}

void RulesRuntime::enqueueEmittedEvent(
    const String& event_name,
    const String& source,
    const String& event_type,
    unsigned long ts_ms,
    uint32_t detail_ms) {
  if (!event_name.length() || !source.length() || !event_type.length()) return;
  if (emitted_events_.size() >= 64) {
    emitted_events_.erase(emitted_events_.begin());
  }
  EmittedEvent evt;
  evt.event_name = event_name;
  evt.source = source;
  evt.event_type = event_type;
  evt.seq = ++emitted_event_seq_;
  evt.ts_ms = ts_ms;
  evt.detail_ms = detail_ms;
  emitted_events_.push_back(evt);
}

void RulesRuntime::dispatchWatchEvent(SourceWatch& watch, const String& event_type, unsigned long now_ms, uint32_t detail_ms) {
  if (!watch.source.length() || !event_type.length()) return;
  for (const auto& event_name : watch.event_names) {
    if (!event_name.length()) continue;
    applyEvent(event_name, watch.source, event_type, 0, now_ms, detail_ms);
    enqueueEmittedEvent(event_name, watch.source, event_type, now_ms, detail_ms);
  }
}

void RulesRuntime::serviceInputWatches(unsigned long now_ms) {
  for (auto& watch : source_watches_) {
    std::vector<ButtonDefault::Event> events;
    watch.button.service(now_ms, &events);
    for (const auto& evt : events) {
      const char* event_type = nullptr;
      switch (evt.type) {
        case ButtonDefault::EventType::PRESSED:
          event_type = "PRESSED";
          break;
        case ButtonDefault::EventType::RELEASED:
          event_type = "RELEASED";
          break;
        case ButtonDefault::EventType::CLICKED:
          event_type = "CLICKED";
          break;
        case ButtonDefault::EventType::DOUBLE_CLICKED:
          event_type = "DOUBLE_CLICKED";
          break;
        case ButtonDefault::EventType::HELD:
          event_type = "HELD";
          break;
        case ButtonDefault::EventType::REPEAT_WHILE_HELD:
          event_type = "REPEAT_WHILE_HELD";
          break;
      }
      if (event_type) {
        dispatchWatchEvent(watch, String(event_type), now_ms, evt.detail_ms);
      }
    }
  }
}

bool RulesRuntime::loadMappingSafeStatesCached(std::vector<PinSafeState>* out_states) {
  if (!out_states) return false;
  out_states->clear();
  std::vector<MappingSafeStateEntry> entries;
  String error;
  if (!loadMappingSafeStates(rules_runtime_internal::kMappingBlobPath, &entries, &error)) {
    return false;
  }
  out_states->reserve(entries.size());
  for (const auto& item : entries) {
    PinSafeState s;
    s.pin = static_cast<int>(item.pin);
    s.safe_high = item.safe_high;
    out_states->push_back(s);
  }
  return true;
}

bool RulesRuntime::lookupSafeStateForPin(const std::vector<PinSafeState>& safe_states, int pin, bool* safe_high_out) {
  if (!safe_high_out || pin < 0) return false;
  for (const auto& state : safe_states) {
    if (state.pin != pin) continue;
    *safe_high_out = state.safe_high;
    return true;
  }
  return false;
}

void RulesRuntime::drivePinToMappedSafe(const String& target, const String& driver, int pin, const std::vector<PinSafeState>& safe_states) {
  if (pin < 0) return;
  stopPulseForPin(pin);
  bool safe_high = false;
  bool found = lookupSafeStateForPin(safe_states, pin, &safe_high);
  if (target.length()) {
    driveOutputTarget(target, driver, pin, (found && safe_high));
    return;
  }
  driver_registry::writeOutputByDriver("Coil", "Default", pin, (found && safe_high));
}

void RulesRuntime::restoreSafeStateForStaleEvent(const String& source) {
  std::vector<PinSafeState> safe_states;
  loadMappingSafeStatesCached(&safe_states);

  if (!source.length()) {
    for (const auto& pair : release_pairs_) {
      drivePinToMappedSafe(pair.target, pair.driver, pair.pin, safe_states);
    }
    for (const auto& held : held_outputs_) {
      drivePinToMappedSafe(held.target, held.driver, held.pin, safe_states);
    }
    held_outputs_.clear();
    return;
  }

  for (const auto& pair : release_pairs_) {
    if (pair.source != source) continue;
    drivePinToMappedSafe(pair.target, pair.driver, pair.pin, safe_states);
    clearHeldOutput(source, pair.pin);
  }
  for (size_t i = 0; i < held_outputs_.size();) {
    if (held_outputs_[i].source != source) {
      ++i;
      continue;
    }
    drivePinToMappedSafe(held_outputs_[i].target, held_outputs_[i].driver, held_outputs_[i].pin, safe_states);
    held_outputs_.erase(held_outputs_.begin() + i);
  }
}

bool RulesRuntime::acceptEventSeq(const String& event_name, const String& source, uint32_t seq) {
  if (seq == 0) return true;
  for (auto& s : event_seq_state_) {
    if (s.event_name != event_name) continue;
    if (s.source != source) continue;
    if (seq <= s.last_seq) return false;
    s.last_seq = seq;
    return true;
  }
  EventSeqState fresh;
  fresh.event_name = event_name;
  fresh.source = source;
  fresh.last_seq = seq;
  event_seq_state_.push_back(fresh);
  return true;
}

bool RulesRuntime::hasReleasePair(const String& source, int pin) const {
  if (pin < 0 || !source.length()) return false;
  for (const auto& pair : release_pairs_) {
    if (pair.pin == pin && pair.source == source) return true;
  }
  return false;
}

unsigned long RulesRuntime::computeHeldAutoReleaseAt(
    const String& target, const String& driver, int pin, unsigned long now_ms) const {
  if (pin < 0) return 0;
  String fn;
  String dn;
  String impl;
  driver_registry::resolveDriverForTarget(
      rules_runtime_internal::kMappingBlobPath,
      target,
      driver,
      "Coil",
      &fn,
      &dn,
      &impl);
  if (driver_registry::normalizeFunctionName(fn).equalsIgnoreCase("Coil")) {
    return 0;
  }
  return now_ms + rules_runtime_internal::kNonCoilAutoReleaseMs;
}

void RulesRuntime::markHeldOutput(const String& source, int pin, const String& target, const String& driver) {
  if (pin < 0 || !source.length()) return;
  const unsigned long now_ms = millis();
  const unsigned long auto_release_at = computeHeldAutoReleaseAt(target, driver, pin, now_ms);
  for (auto& held : held_outputs_) {
    if (held.pin == pin && held.source == source) {
      if (target.length()) held.target = target;
      if (driver.length()) held.driver = driver;
      held.auto_release_at_ms = auto_release_at;
      return;
    }
  }
  HeldOutput held;
  held.source = source;
  held.pin = pin;
  held.target = target;
  held.driver = driver;
  held.auto_release_at_ms = auto_release_at;
  held_outputs_.push_back(held);
}

void RulesRuntime::clearHeldOutput(const String& source, int pin) {
  if (pin < 0 || held_outputs_.empty() || !source.length()) return;
  for (size_t i = 0; i < held_outputs_.size();) {
    if (held_outputs_[i].pin == pin && held_outputs_[i].source == source) {
      held_outputs_.erase(held_outputs_.begin() + i);
      continue;
    }
    ++i;
  }
}

void RulesRuntime::clearHeldOutputsForSource(const String& source) {
  if (!source.length() || held_outputs_.empty()) return;
  for (size_t i = 0; i < held_outputs_.size();) {
    if (held_outputs_[i].source != source) {
      ++i;
      continue;
    }
    if (held_outputs_[i].pin >= 0) {
      driveOutputTarget(held_outputs_[i].target, held_outputs_[i].driver, held_outputs_[i].pin, false);
    }
    held_outputs_.erase(held_outputs_.begin() + i);
  }
}

void RulesRuntime::forceReleasePairsForSource(const String& source) {
  if (!source.length() || release_pairs_.empty()) return;
  for (const auto& pair : release_pairs_) {
    if (pair.source != source) continue;
    if (pair.pin < 0) continue;
    stopPulseForPin(pair.pin);
    driveOutputTarget(pair.target, pair.driver, pair.pin, false);
    clearHeldOutput(source, pair.pin);
  }
}
