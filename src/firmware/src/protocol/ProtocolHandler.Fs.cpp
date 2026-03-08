#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <LittleFS.h>
#include <functional>
#include <vector>

#include "drivers/DriverRegistry.h"
#include "hardware/MappingBlob.h"

namespace protocol_fs_internal {

constexpr const char* kMappingBlobPath = "/cfg/mapping.pb";
constexpr const char* kMappingBootGuardPath = "/cfg/mapping.boot_fail";
constexpr const char* kRulesBlobPath = "/cfg/rules.pd";
constexpr const char* kRulesBootGuardPath = "/cfg/rules.boot_fail";
constexpr const char* kLightingBlobPath = "/cfg/lighting.pd";
constexpr const char* kLightingBootGuardPath = "/cfg/lighting.boot_fail";
constexpr uint8_t kBootFailMax = 3;

struct ManifestEntry {
  String name;
  String sha256;
  uint32_t size = 0;
  uint32_t uploaded_at = 0;
};

String manifestPath() {
  return "/cfg/manifest.json";
}

bool parseManifestEntries(const String& content, std::vector<ManifestEntry>& entries) {
  int pos = 0;
  while (pos < content.length()) {
    int key_start = content.indexOf('"', pos);
    if (key_start < 0) break;
    int key_end = content.indexOf('"', key_start + 1);
    if (key_end < 0) break;
    String key = content.substring(key_start + 1, key_end);
    int colon = content.indexOf(':', key_end + 1);
    if (colon < 0) break;
    int brace = content.indexOf('{', colon);
    if (brace < 0) {
      pos = key_end + 1;
      continue;
    }
    int end_brace = content.indexOf('}', brace);
    if (end_brace < 0) break;
    String obj = content.substring(brace, end_brace + 1);
    ManifestEntry entry;
    entry.name = key;
    protocol_support::extractJsonString(obj, "sha256", &entry.sha256);
    protocol_support::extractJsonUint(obj, "size", &entry.size);
    protocol_support::extractJsonUint(obj, "uploadedAt", &entry.uploaded_at);
    entries.push_back(entry);
    pos = end_brace + 1;
  }
  return true;
}

bool loadManifest(std::vector<ManifestEntry>& entries) {
  entries.clear();
  if (!LittleFS.exists(manifestPath())) return true;
  fs::File file = LittleFS.open(manifestPath(), "r");
  if (!file) return false;
  String content = file.readString();
  return parseManifestEntries(content, entries);
}

String manifestToJson(const std::vector<ManifestEntry>& entries) {
  String out = "{";
  for (size_t i = 0; i < entries.size(); i++) {
    const auto& entry = entries[i];
    if (i > 0) out += ",";
    out += "\"";
    out += entry.name;
    out += "\":{";
    out += "\"sha256\":\"";
    out += entry.sha256;
    out += "\",\"size\":";
    out += entry.size;
    out += ",\"uploadedAt\":";
    out += entry.uploaded_at;
    out += "}";
  }
  out += "}";
  return out;
}

bool updateManifestEntry(const String& path, const String& sha256, uint32_t size, uint32_t uploaded_at) {
  std::vector<ManifestEntry> entries;
  loadManifest(entries);
  String name = path;
  int slash = name.lastIndexOf('/');
  if (slash >= 0 && slash + 1 < name.length()) name = name.substring(slash + 1);
  bool found = false;
  for (auto& entry : entries) {
    if (entry.name != name) continue;
    entry.sha256 = sha256;
    entry.size = size;
    entry.uploaded_at = uploaded_at;
    found = true;
    break;
  }
  if (!found) {
    ManifestEntry entry;
    entry.name = name;
    entry.sha256 = sha256;
    entry.size = size;
    entry.uploaded_at = uploaded_at;
    entries.push_back(entry);
  }
  String payload = manifestToJson(entries);
  String temp_path = String(manifestPath()) + ".tmp";
  fs::File tmp = LittleFS.open(temp_path, "w");
  if (!tmp) return false;
  tmp.print(payload);
  tmp.close();
  LittleFS.remove(manifestPath());
  return LittleFS.rename(temp_path, manifestPath());
}

String buildFsStatusPayload(bool mounted) {
  if (!mounted) {
    return String("{\"t\":\"FS_STATUS\",\"fs\":\"littlefs\",\"mounted\":false,\"error\":\"not_mounted\"}");
  }
  bool rules_ok = LittleFS.exists("/rules");
  String fs = "{\"t\":\"FS_STATUS\",\"fs\":\"littlefs\",\"mounted\":true";
  fs += ",\"rules_dir\":";
  fs += (rules_ok ? "true" : "false");
  fs += ",\"total\":";
  size_t total = LittleFS.totalBytes();
  size_t used = LittleFS.usedBytes();
  fs += total;
  fs += ",\"free\":";
  fs += (total > used ? (total - used) : 0);
  fs += "}";
  return fs;
}

String buildDriverWiringPayload(const char* mapping_path) {
  std::vector<MappingDriverBindingEntry> bindings;
  String err;
  if (!loadMappingDriverBindings(mapping_path, &bindings, &err)) {
    String out = "{\"t\":\"DRIVER_WIRING\",\"ok\":false,\"error\":\"";
    out += (err.length() ? err : "load_failed");
    out += "\"}";
    return out;
  }
  String out = "{\"t\":\"DRIVER_WIRING\",\"ok\":true,\"count\":";
  out += static_cast<unsigned int>(bindings.size());
  out += ",\"bindings\":[";
  for (size_t i = 0; i < bindings.size(); ++i) {
    if (i > 0) out += ",";
    const auto& row = bindings[i];
    String function_name = row.function_name;
    if (!function_name.length()) function_name = "Coil";
    String driver_name = row.driver;
    if (!driver_name.length()) driver_name = "Default";
    out += "{\"target\":\"";
    out += row.target_id;
    out += "\",\"function\":\"";
    out += function_name;
    out += "\",\"driver\":\"";
    out += driver_name;
    out += "\",\"impl\":\"";
    out += driver_registry::implementationName(function_name, driver_name);
    out += "\"}";
  }
  out += "]}";
  return out;
}

}  // namespace protocol_fs_internal

void ProtocolHandler::loadMappingFromFsOnBoot() {
  if (!fs_mounted_) return;
  if (!LittleFS.exists(protocol_fs_internal::kMappingBlobPath)) {
    protocol_support::enqueueWithRetry(serial_, "{\"t\":\"MAP_BOOT\",\"status\":\"missing\"}");
    return;
  }
  auto outcome = protocol_support::runBootGuardedLoad(
      protocol_fs_internal::kMappingBootGuardPath,
      protocol_fs_internal::kBootFailMax,
      [&](String* error) {
        uint16_t ignored = 0;
        return applyMappingBlob(protocol_fs_internal::kMappingBlobPath, &ignored, error);
      });
  if (outcome.skipped) {
    String msg = "{\"t\":\"MAP_BOOT\",\"status\":\"skipped\",\"reason\":\"guarded\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  if (!outcome.ok) {
    String msg = "{\"t\":\"MAP_BOOT\",\"status\":\"error\",\"reason\":\"";
    msg += (outcome.reason.length() ? outcome.reason : "load_failed");
    msg += "\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  protocol_support::enqueueWithRetry(serial_, "{\"t\":\"MAP_BOOT\",\"status\":\"ok\",\"source\":\"/cfg/mapping.pb\"}");
  protocol_support::enqueueWithRetry(
      serial_,
      protocol_fs_internal::buildDriverWiringPayload(protocol_fs_internal::kMappingBlobPath));
}

void ProtocolHandler::loadRulesFromFsOnBoot() {
  if (!fs_mounted_) return;
  if (!LittleFS.exists(protocol_fs_internal::kRulesBlobPath)) {
    protocol_support::enqueueWithRetry(serial_, "{\"t\":\"RULES_BOOT\",\"status\":\"missing\",\"reason\":\"blob_missing\"}");
    return;
  }
  auto outcome = protocol_support::runBootGuardedLoad(
      protocol_fs_internal::kRulesBootGuardPath,
      protocol_fs_internal::kBootFailMax,
      [&](String* error) {
        return rules_runtime_.loadFromRulesBlob(protocol_fs_internal::kRulesBlobPath, error);
      });
  if (outcome.skipped) {
    String msg = "{\"t\":\"RULES_BOOT\",\"status\":\"skipped\",\"reason\":\"guarded\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  if (!outcome.ok) {
    rules_runtime_.clear();
    String msg = "{\"t\":\"RULES_BOOT\",\"status\":\"error\",\"reason\":\"";
    msg += (outcome.reason.length() ? outcome.reason : "load_failed");
    msg += "\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  protocol_support::enqueueWithRetry(serial_, "{\"t\":\"RULES_BOOT\",\"status\":\"ok\",\"source\":\"/cfg/rules.pd\"}");
}

void ProtocolHandler::loadLightingFromFsOnBoot() {
  if (!fs_mounted_) return;
  if (!LittleFS.exists(protocol_fs_internal::kLightingBlobPath)) {
    protocol_support::enqueueWithRetry(serial_, "{\"t\":\"LIGHTING_BOOT\",\"status\":\"missing\",\"reason\":\"blob_missing\"}");
    return;
  }
  auto outcome = protocol_support::runBootGuardedLoad(
      protocol_fs_internal::kLightingBootGuardPath,
      protocol_fs_internal::kBootFailMax,
      [&](String* error) {
        return lighting_runtime_.loadFromLightingBlob(protocol_fs_internal::kLightingBlobPath, error);
      });
  if (outcome.skipped) {
    String msg = "{\"t\":\"LIGHTING_BOOT\",\"status\":\"skipped\",\"reason\":\"guarded\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  if (!outcome.ok) {
    lighting_runtime_.clear();
    String msg = "{\"t\":\"LIGHTING_BOOT\",\"status\":\"error\",\"reason\":\"";
    msg += (outcome.reason.length() ? outcome.reason : "load_failed");
    msg += "\",\"failures\":";
    msg += static_cast<unsigned int>(outcome.failures);
    msg += "}";
    protocol_support::enqueueWithRetry(serial_, msg);
    return;
  }
  protocol_support::enqueueWithRetry(serial_, "{\"t\":\"LIGHTING_BOOT\",\"status\":\"ok\",\"source\":\"/cfg/lighting.pd\"}");
}

bool ProtocolHandler::handleFsCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "GET_FS_STATUS")) {
    String payload = protocol_fs_internal::buildFsStatusPayload(fs_mounted_);
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "FS_MANIFEST_GET")) {
    if (!fs_mounted_) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"MANIFEST\",\"ok\":false,\"error\":\"fs_not_mounted\"}", req_id));
      return true;
    }
    std::vector<protocol_fs_internal::ManifestEntry> entries;
    protocol_fs_internal::loadManifest(entries);
    String data = protocol_fs_internal::manifestToJson(entries);
    String payload = "{\"t\":\"MANIFEST\",\"ok\":true,\"data\":";
    payload += data;
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "FS_MANIFEST_UPDATE")) {
    if (!fs_mounted_) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"fs_not_mounted\"}", req_id));
      return true;
    }
    String name;
    String sha256;
    uint32_t size = 0;
    uint32_t uploaded_at = 0;
    protocol_support::extractJsonString(line, "name", &name);
    protocol_support::extractJsonString(line, "sha256", &sha256);
    protocol_support::extractJsonUint(line, "size", &size);
    protocol_support::extractJsonUint(line, "uploadedAt", &uploaded_at);
    if (!name.length() || !sha256.length() || size == 0) {
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"bad_args\"}", req_id));
      return true;
    }
    bool ok = protocol_fs_internal::updateManifestEntry(name, sha256, size, uploaded_at);
    protocol_support::enqueueWithRetry(
        serial_,
        protocol_support::appendReqId(
            ok ? "{\"t\":\"MANIFEST_UPDATE\",\"ok\":true}"
               : "{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"write_failed\"}",
            req_id));
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "FS_LIST")) {
    String path;
    if (!protocol_support::extractJsonString(line, "path", &path)) {
      int idx = line.indexOf("FS_LIST");
      int sp = line.indexOf(' ', idx >= 0 ? idx : 0);
      if (sp >= 0) {
        path = line.substring(sp + 1);
        path.trim();
      }
    }
    if (!path.length()) path = "/";
    String payload = "{\"t\":\"FS_LIST\",\"path\":\"";
    payload += path;
    payload += "\",\"files\":[";
    uint32_t count = 0;
    bool first = true;
    if (fs_mounted_) {
      fs::File root = LittleFS.open(path, "r");
      if (root && root.isDirectory()) {
        std::function<void(fs::File&, String)> walk = [&](fs::File& dir, String base) {
          fs::File file = dir.openNextFile();
          while (file) {
            String name = file.name();
            if (!name.startsWith("/")) name = base + (base.endsWith("/") ? "" : "/") + name;
            if (file.isDirectory()) {
              fs::File child = LittleFS.open(name, "r");
              if (child && child.isDirectory()) walk(child, name);
            } else {
              if (!first) payload += ",";
              first = false;
              payload += "{\"name\":\"";
              payload += name;
              payload += "\",\"size\":";
              payload += String(file.size());
              uint32_t mtime = file.getLastWrite();
              if (mtime > 0) {
                payload += ",\"mtime\":";
                payload += String(mtime);
              }
              payload += "}";
              count++;
            }
            file = dir.openNextFile();
          }
        };
        walk(root, path);
      }
    }
    payload += "],\"count\":";
    payload += String(count);
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  if (protocol_support::isCmd(line, cmd, "MOUNT_FS")) {
    bool ok = LittleFS.begin(true);
    fs_mounted_ = ok;
    bool rules_ok = false;
    if (ok) {
      if (!LittleFS.exists("/rules")) {
        rules_ok = LittleFS.mkdir("/rules");
      } else {
        rules_ok = true;
      }
    }
    String payload = "{\"t\":\"FS_MOUNT\",\"mounted\":";
    payload += (ok ? "true" : "false");
    if (ok) {
      payload += ",\"rules_dir\":";
      payload += (rules_ok ? "true" : "false");
      payload += ",\"total\":";
      size_t total = LittleFS.totalBytes();
      size_t used = LittleFS.usedBytes();
      payload += total;
      payload += ",\"used\":";
      payload += used;
      payload += ",\"free\":";
      payload += (total > used ? (total - used) : 0);
    } else {
      payload += ",\"error\":\"begin_failed\"";
    }
    payload += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
    return true;
  }
  return false;
}
