#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <ArduinoJson.h>
#include <vector>

#include "drivers/DriverRegistry.h"

namespace {
constexpr const char* kLightingMappingBlobPath = "/cfg/mapping.pb";

bool parseTargetGpio(const String& target, int* pin_out) {
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
}  // namespace

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

  if (protocol_support::isCmd(line, cmd, "LIGHT_PIXELS_SET")) {
    DynamicJsonDocument doc(3072);
    auto err = deserializeJson(doc, line);
    if (err || !doc.is<JsonObject>()) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"LIGHT_PIXELS_STATUS\",\"ok\":false,\"error\":\"bad_json\"}", req_id));
      return true;
    }
    JsonObject obj = doc.as<JsonObject>();
    String target = obj["target"].is<const char*>() ? String(obj["target"].as<const char*>()) : String("");
    target.trim();
    if (!target.length()) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"LIGHT_PIXELS_STATUS\",\"ok\":false,\"error\":\"target_required\"}", req_id));
      return true;
    }
    int pin = -1;
    if (!parseTargetGpio(target, &pin)) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"LIGHT_PIXELS_STATUS\",\"ok\":false,\"error\":\"bad_target\"}", req_id));
      return true;
    }

    int pixel_count = 1;
    if (obj["pixelCount"].is<int>()) pixel_count = obj["pixelCount"].as<int>();
    if (pixel_count < 1) pixel_count = 1;
    if (pixel_count > 2048) pixel_count = 2048;

    std::vector<uint16_t> indexes;
    JsonVariant pixels_var = obj["pixelIndexes"];
    if (pixels_var.is<JsonArray>()) {
      for (JsonVariant v : pixels_var.as<JsonArray>()) {
        if (!v.is<int>()) continue;
        int idx = v.as<int>();
        if (idx < 0 || idx >= pixel_count) continue;
        indexes.push_back(static_cast<uint16_t>(idx));
      }
    }
    if (indexes.empty()) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"LIGHT_PIXELS_STATUS\",\"ok\":false,\"error\":\"no_pixels\"}", req_id));
      return true;
    }

    String color = obj["color"].is<const char*>() ? String(obj["color"].as<const char*>()) : String("#ffffff");
    color.trim();
    if (!color.length()) color = "#ffffff";
    float brightness = 1.0f;
    if (obj["brightness"].is<float>()) brightness = obj["brightness"].as<float>();
    else if (obj["brightness"].is<int>()) brightness = static_cast<float>(obj["brightness"].as<int>());
    if (brightness < 0.0f) brightness = 0.0f;
    if (brightness > 1.0f) brightness = 1.0f;
    String driver = obj["driver"].is<const char*>() ? String(obj["driver"].as<const char*>()) : String("");

    String resolved_fn;
    String resolved_driver;
    String impl;
    String write_error;
    bool ok = driver_registry::writeRgbPixelsForTarget(
        kLightingMappingBlobPath,
        target,
        driver,
        pin,
        pixel_count,
        indexes,
        color,
        brightness,
        &resolved_fn,
        &resolved_driver,
        &impl,
        &write_error);
    String payload = "{\"t\":\"LIGHT_PIXELS_STATUS\",\"ok\":";
    payload += (ok ? "true" : "false");
    payload += ",\"target\":\"";
    payload += target;
    payload += "\",\"pin\":";
    payload += pin;
    payload += ",\"pixelCount\":";
    payload += pixel_count;
    payload += ",\"pixels\":";
    payload += static_cast<unsigned int>(indexes.size());
    payload += ",\"color\":\"";
    payload += color;
    payload += "\",\"brightness\":";
    payload += String(brightness, 3);
    payload += ",\"function\":\"";
    payload += resolved_fn;
    payload += "\",\"driver\":\"";
    payload += resolved_driver;
    payload += "\",\"impl\":\"";
    payload += impl;
    payload += "\"";
    if (!ok && write_error.length()) {
      payload += ",\"error\":\"";
      payload += write_error;
      payload += "\"";
    }
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }

  return false;
}
