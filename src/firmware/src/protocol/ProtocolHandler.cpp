// ProtocolHandler: handles text commands and emits framed responses.

#include "protocol/ProtocolHandler.h"
#include "version.h"
#include <sys/time.h>
#include <functional>
#include <LittleFS.h>
#include <vector>
#include "hw/MappingBlob.h"
#include "hw/RulesBlob.h"

static bool _enqueueWithRetry(FramedSerial& serial, const String& payload, uint32_t timeout_ms = 250) {
  const unsigned long started = millis();
  while ((millis() - started) < timeout_ms) {
    if (serial.enqueue(payload)) return true;
    serial.pump();
    delay(1);
  }
  // Last immediate attempt at timeout boundary.
  if (serial.enqueue(payload)) return true;
  return false;
}

static void _emitBlobDebug(
    FramedSerial& serial,
    const String& stage,
    const String& req_id,
    size_t received,
    size_t expected,
    const String& note = String()) {
  String msg = "{\"t\":\"BLOB_DEBUG\",\"stage\":\"";
  msg += stage;
  msg += "\"";
  if (req_id.length()) {
    msg += ",\"reqId\":\"";
    msg += req_id;
    msg += "\"";
  }
  msg += ",\"received\":";
  msg += static_cast<uint32_t>(received);
  msg += ",\"expected\":";
  msg += static_cast<uint32_t>(expected);
  if (note.length()) {
    msg += ",\"note\":\"";
    msg += note;
    msg += "\"";
  }
  msg += "}";
  _enqueueWithRetry(serial, msg, 10);
}

ProtocolHandler::ProtocolHandler(FramedSerial& serial, HardwareStreamer& streamer)
    : serial_(serial),
      streamer_(streamer),
      fs_mounted_(false),
      blob_active_(false),
      blob_expected_(0),
      blob_received_(0),
      blob_crc_expected_(0),
      blob_crc_running_(0),
      blob_expect_end_(false),
      blob_complete_(false),
      last_cmd_typed_(false),
      blob_req_id_(""),
      blob_path_(""),
      blob_type_(""),
      evt_stream_active_(false),
      evt_stream_target_count_(0),
      evt_stream_sent_count_(0),
      evt_stream_drop_count_(0),
      evt_stream_rate_hz_(200),
      evt_stream_interval_us_(5000),
      evt_stream_last_emit_us_(0),
      evt_stream_name_("esp.stub.event"),
      evt_stream_source_("esp.stub"),
      evt_stream_req_id_(""),
      evt_in_total_(0),
      evt_in_ack_count_(0),
      evt_in_fire_count_(0),
      evt_in_last_seq_(0),
      evt_in_last_ms_(0),
      evt_in_last_name_(""),
      evt_in_last_source_("") {}

static bool extract_json_string(const String& json, const char* key, String* out) {
  if (!out) return false;
  String needle = String("\"") + key + "\":";
  int idx = json.indexOf(needle);
  if (idx < 0) return false;
  int pos = idx + needle.length();
  while (pos < json.length() && (json[pos] == ' ')) pos++;
  if (pos >= json.length() || json[pos] != '"') return false;
  pos++;
  String value;
  while (pos < json.length()) {
    char c = json[pos++];
    if (c == '"') break;
    if (c == '\\' && pos < json.length()) {
      char next = json[pos++];
      value += next;
    } else {
      value += c;
    }
  }
  *out = value;
  return true;
}

static bool extract_json_uint(const String& json, const char* key, uint32_t* out) {
  if (!out) return false;
  String needle = String("\"") + key + "\":";
  int idx = json.indexOf(needle);
  if (idx < 0) return false;
  int pos = idx + needle.length();
  while (pos < json.length() && (json[pos] == ' ')) pos++;
  uint32_t value = 0;
  bool found = false;
  while (pos < json.length()) {
    char c = json[pos];
    if (c < '0' || c > '9') break;
    found = true;
    value = value * 10 + (c - '0');
    pos++;
  }
  if (!found) return false;
  *out = value;
  return true;
}

static String append_req_id(const String& payload, const String& req_id) {
  if (!req_id.length()) return payload;
  int idx = payload.lastIndexOf('}');
  if (idx <= 0) return payload;
  String out = payload.substring(0, idx);
  out += ",\"reqId\":\"";
  out += req_id;
  out += "\"}";
  return out;
}

struct ManifestEntry {
  String name;
  String sha256;
  uint32_t size = 0;
  uint32_t uploaded_at = 0;
};

static String manifest_path() {
  return "/cfg/manifest.json";
}

static bool parse_manifest_entries(const String& content, std::vector<ManifestEntry>& entries) {
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
    extract_json_string(obj, "sha256", &entry.sha256);
    extract_json_uint(obj, "size", &entry.size);
    extract_json_uint(obj, "uploadedAt", &entry.uploaded_at);
    entries.push_back(entry);
    pos = end_brace + 1;
  }
  return true;
}

static bool load_manifest(std::vector<ManifestEntry>& entries) {
  entries.clear();
  if (!LittleFS.exists(manifest_path())) {
    return true;
  }
  fs::File file = LittleFS.open(manifest_path(), "r");
  if (!file) {
    return false;
  }
  String content = file.readString();
  return parse_manifest_entries(content, entries);
}

static String manifest_to_json(const std::vector<ManifestEntry>& entries) {
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

static bool update_manifest_entry(const String& path, const String& sha256, uint32_t size, uint32_t uploaded_at) {
  std::vector<ManifestEntry> entries;
  load_manifest(entries);
  String name = path;
  int slash = name.lastIndexOf('/');
  if (slash >= 0 && slash + 1 < name.length()) {
    name = name.substring(slash + 1);
  }
  bool found = false;
  for (auto& entry : entries) {
    if (entry.name == name) {
      entry.sha256 = sha256;
      entry.size = size;
      entry.uploaded_at = uploaded_at;
      found = true;
      break;
    }
  }
  if (!found) {
    ManifestEntry entry;
    entry.name = name;
    entry.sha256 = sha256;
    entry.size = size;
    entry.uploaded_at = uploaded_at;
    entries.push_back(entry);
  }
  String payload = manifest_to_json(entries);
  String temp_path = String(manifest_path()) + ".tmp";
  fs::File tmp = LittleFS.open(temp_path, "w");
  if (!tmp) return false;
  tmp.print(payload);
  tmp.close();
  LittleFS.remove(manifest_path());
  return LittleFS.rename(temp_path, manifest_path());
}

static String build_fs_status_payload(bool mounted) {
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

void ProtocolHandler::setFsMounted(bool mounted) {
  fs_mounted_ = mounted;
}

void ProtocolHandler::sendInfo(const String& req_id) {
  const char* ver = FW_VERSION;
  if (!ver || !*ver) ver = "v0.0.0";
  String payload = "{\"t\":\"INFO\",\"fw\":\"";
  payload += ver;
  payload += "\",\"chip\":\"esp32s3\",\"proto\":2}";
  _enqueueWithRetry(serial_, append_req_id(payload, req_id));
}

void ProtocolHandler::handleLine(const String& line) {
  String req_id;
  String cmd;
  extract_json_string(line, "reqId", &req_id);
  extract_json_string(line, "cmd", &cmd);
  auto is_cmd = [&](const char* name) -> bool {
    if (cmd.length()) return cmd == name;
    return line.indexOf(name) >= 0;
  };

  if (is_cmd("GET_INFO") || is_cmd("HELLO")) {
    sendInfo(req_id);
    return;
  }
  if (is_cmd("GET_FS_STATUS")) {
    String payload = build_fs_status_payload(fs_mounted_);
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("FS_MANIFEST_GET")) {
    if (!fs_mounted_) {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"MANIFEST\",\"ok\":false,\"error\":\"fs_not_mounted\"}", req_id));
      return;
    }
    std::vector<ManifestEntry> entries;
    load_manifest(entries);
    String data = manifest_to_json(entries);
    String payload = "{\"t\":\"MANIFEST\",\"ok\":true,\"data\":";
    payload += data;
    payload += "}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("FS_MANIFEST_UPDATE")) {
    if (!fs_mounted_) {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"fs_not_mounted\"}", req_id));
      return;
    }
    String name;
    String sha256;
    uint32_t size = 0;
    uint32_t uploaded_at = 0;
    extract_json_string(line, "name", &name);
    extract_json_string(line, "sha256", &sha256);
    extract_json_uint(line, "size", &size);
    extract_json_uint(line, "uploadedAt", &uploaded_at);
    if (!name.length() || !sha256.length() || size == 0) {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"bad_args\"}", req_id));
      return;
    }
    bool ok = update_manifest_entry(name, sha256, size, uploaded_at);
    if (ok) {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"MANIFEST_UPDATE\",\"ok\":true}", req_id));
    } else {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"MANIFEST_UPDATE\",\"ok\":false,\"error\":\"write_failed\"}", req_id));
    }
    return;
  }
  if (is_cmd("FS_LIST")) {
    String path;
    if (!extract_json_string(line, "path", &path)) {
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
              if (child && child.isDirectory()) {
                walk(child, name);
              }
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
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("MOUNT_FS")) {
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
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("GET_FLASH_INFO")) {
    String payload = "{\"t\":\"FLASH_INFO\",\"chip_size\":";
    payload += ESP.getFlashChipSize();
    payload += ",\"sketch_size\":";
    payload += ESP.getSketchSize();
    payload += ",\"free_sketch\":";
    payload += ESP.getFreeSketchSpace();
    payload += "}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("ECHO")) {
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"ECHO\",\"ok\":true}", req_id));
    return;
  }
  if (is_cmd("SET_RULES")) {
    rules_payload_ = line;
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"RULES_STATUS\",\"status\":\"ok\"}", req_id));
    return;
  }
  if (is_cmd("EVENT")) {
    String evt_name;
    if (!extract_json_string(line, "name", &evt_name) || !evt_name.length()) {
      evt_name = "pi.stub.event";
    }
    uint32_t seq = 0;
    extract_json_uint(line, "seq", &seq);
    String source;
    extract_json_string(line, "source", &source);
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
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("EVENT_FIRE")) {
    String evt_name;
    if (!extract_json_string(line, "name", &evt_name) || !evt_name.length()) {
      evt_name = "pi.stub.fire";
    }
    String source;
    extract_json_string(line, "source", &source);
    uint32_t seq = 0;
    extract_json_uint(line, "seq", &seq);
    evt_in_total_++;
    evt_in_fire_count_++;
    evt_in_last_seq_ = seq;
    evt_in_last_ms_ = millis();
    evt_in_last_name_ = evt_name;
    if (source.length()) evt_in_last_source_ = source;
    return;
  }
  if (is_cmd("EVENT_STATS_RESET")) {
    evt_in_total_ = 0;
    evt_in_ack_count_ = 0;
    evt_in_fire_count_ = 0;
    evt_in_last_seq_ = 0;
    evt_in_last_ms_ = 0;
    evt_in_last_name_ = "";
    evt_in_last_source_ = "";
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"EVENT_STATS\",\"ok\":true,\"status\":\"reset\"}", req_id));
    return;
  }
  if (is_cmd("EVENT_STATS")) {
    String payload = "{\"t\":\"EVENT_STATS\",\"ok\":true,\"in_total\":";
    payload += evt_in_total_;
    payload += ",\"in_ack\":";
    payload += evt_in_ack_count_;
    payload += ",\"in_fire\":";
    payload += evt_in_fire_count_;
    payload += ",\"last_seq\":";
    payload += evt_in_last_seq_;
    payload += ",\"last_ms\":";
    payload += evt_in_last_ms_;
    payload += ",\"last_name\":\"";
    payload += evt_in_last_name_;
    payload += "\",\"last_source\":\"";
    payload += evt_in_last_source_;
    payload += "\"}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("LIGHT_SCENE_PLAY")) {
    String scene_id;
    extract_json_string(line, "sceneId", &scene_id);
    if (!scene_id.length()) {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":false,\"reason\":\"missing_scene\"}", req_id));
      return;
    }
    // Runtime integration hook: lighting scene engine apply/start.
    String payload = "{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":true,\"status\":\"playing\",\"sceneId\":\"";
    payload += scene_id;
    payload += "\"}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("LIGHT_SCENE_STOP")) {
    String scene_id;
    extract_json_string(line, "sceneId", &scene_id);
    if (!scene_id.length()) scene_id = "*";
    // Runtime integration hook: lighting scene engine stop.
    String payload = "{\"t\":\"LIGHT_SCENE_STATUS\",\"ok\":true,\"status\":\"stopped\",\"sceneId\":\"";
    payload += scene_id;
    payload += "\"}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("EVT_STREAM_START")) {
    uint32_t count = 0;
    uint32_t rate_hz = 0;
    String name;
    String source;
    String done_req_id;
    extract_json_uint(line, "count", &count);
    extract_json_uint(line, "rateHz", &rate_hz);
    extract_json_string(line, "name", &name);
    extract_json_string(line, "source", &source);
    extract_json_string(line, "doneReqId", &done_req_id);
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
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("EVT_STREAM_STOP")) {
    bool active = evt_stream_active_;
    evt_stream_active_ = false;
    String payload = "{\"t\":\"EVT_STREAM_STATUS\",\"status\":\"stopped\",\"active\":";
    payload += (active ? "true" : "false");
    payload += ",\"sent\":";
    payload += evt_stream_sent_count_;
    payload += ",\"dropped\":";
    payload += evt_stream_drop_count_;
    payload += "}";
    _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    return;
  }
  if (is_cmd("BLOB_END")) {
    uint32_t sent = 0;
    extract_json_uint(line, "sent", &sent);
    _emitBlobDebug(serial_, "end_cmd", req_id, blob_received_, blob_expected_);
    if (!blob_active_) {
      _emitBlobDebug(serial_, "end_no_blob", req_id, blob_received_, blob_expected_);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"no_blob\"}", req_id));
      return;
    }
    if (req_id.length() && blob_req_id_.length() && req_id != blob_req_id_) {
      _emitBlobDebug(serial_, "end_req_mismatch", req_id, blob_received_, blob_expected_);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"req_mismatch\"}", req_id));
      resetBlobState();
      return;
    }
    if (blob_received_ < blob_expected_) {
      _emitBlobDebug(serial_, "end_incomplete", req_id, blob_received_, blob_expected_);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"incomplete\"}", req_id));
      resetBlobState();
      return;
    }
    if (sent && sent != blob_received_) {
      _emitBlobDebug(serial_, "end_size_mismatch", req_id, blob_received_, blob_expected_);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"size_mismatch\"}", req_id));
      resetBlobState();
      return;
    }
    _emitBlobDebug(serial_, "end_finalize", req_id, blob_received_, blob_expected_);
    finalizeBlobResult();
    return;
  }
  if (is_cmd("BLOB_BEGIN")) {
    if (!fs_mounted_) {
      _emitBlobDebug(serial_, "begin_fs_unmounted", req_id, 0, 0);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"fs_not_mounted\"}", req_id));
      return;
    }
    if (blob_active_) {
      _emitBlobDebug(serial_, "begin_busy", req_id, blob_received_, blob_expected_);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"busy\"}", req_id));
      return;
    }
    String path;
    String blob_type;
    uint32_t size = 0;
    uint32_t crc32 = 0;
    uint32_t ver = 0;
    extract_json_string(line, "path", &path);
    extract_json_string(line, "blobType", &blob_type);
    extract_json_uint(line, "size", &size);
    extract_json_uint(line, "crc32", &crc32);
    extract_json_uint(line, "ver", &ver);
    if (!path.length() || !path.startsWith("/cfg/")) {
      _emitBlobDebug(serial_, "begin_bad_path", req_id, 0, size);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"bad_path\"}", req_id));
      return;
    }
    if (size == 0) {
      _emitBlobDebug(serial_, "begin_bad_size", req_id, 0, size);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"bad_size\"}", req_id));
      return;
    }
    if (!LittleFS.exists("/cfg")) {
      LittleFS.mkdir("/cfg");
    }
    blob_file_ = LittleFS.open(path, "w");
    if (!blob_file_) {
      _emitBlobDebug(serial_, "begin_open_failed", req_id, 0, size);
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"open_failed\"}", req_id));
      return;
    }
    blob_active_ = true;
    blob_expected_ = size;
    blob_received_ = 0;
    blob_crc_expected_ = crc32;
    blob_crc_running_ = 0;
    blob_expect_end_ = last_cmd_typed_;
    blob_complete_ = false;
    blob_req_id_ = req_id;
    blob_path_ = path;
    blob_type_ = blob_type;
    _emitBlobDebug(serial_, "begin_ok", req_id, 0, blob_expected_, blob_type);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_READY\",\"ok\":true}", req_id));
    return;
  }
  if (is_cmd("GET_HW")) {
    streamer_.start();
    return;
  }
  if (is_cmd("SYNC_TIME") || line.startsWith("SYNC_TIME")) {
    long epoch = 0;
    uint32_t ts = 0;
    if (extract_json_uint(line, "ts", &ts) && ts > 0) {
      epoch = static_cast<long>(ts);
    }
    int sep = line.indexOf(' ');
    if (epoch <= 0 && sep >= 0) epoch = line.substring(sep + 1).toInt();

    if (epoch > 0) {
      struct timeval tv;
      tv.tv_sec = epoch;
      tv.tv_usec = 0;
      settimeofday(&tv, nullptr);

      String payload = "{\"t\":\"TIME\",\"status\":\"ok\",\"ts\":";
      payload += epoch;
      payload += "}";
      _enqueueWithRetry(serial_, append_req_id(payload, req_id));
    } else {
      _enqueueWithRetry(serial_, append_req_id("{\"t\":\"TIME\",\"status\":\"error\",\"reason\":\"bad epoch\"}", req_id));
    }
  }
}

void ProtocolHandler::service(unsigned long now_ms) {
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
    // Under heavy TX load, DONE can fail to enqueue on first attempt.
    // Keep stream active until DONE is accepted so host waiters always complete.
    if (_enqueueWithRetry(serial_, append_req_id(payload, evt_stream_req_id_), 500)) {
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
  if (_enqueueWithRetry(serial_, payload, 5)) {
    evt_stream_sent_count_++;
  } else {
    evt_stream_drop_count_++;
  }
}

void ProtocolHandler::handleFrame(const uint8_t* data, size_t len, uint8_t frame_type, bool typed) {
  if (!data || len == 0) return;
  bool treat_blob = (frame_type == 2) || (blob_active_ && !typed);
  if (!treat_blob) {
    last_cmd_typed_ = typed;
    String payload(reinterpret_cast<const char*>(data), len);
    handleLine(payload);
    return;
  }
  if (!blob_active_) {
    return;
  }
  if (!blob_file_) {
    _emitBlobDebug(serial_, "rx_file_closed", blob_req_id_, blob_received_, blob_expected_);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"file_closed\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  if (blob_received_ + len > blob_expected_) {
    _emitBlobDebug(serial_, "rx_size_overrun", blob_req_id_, blob_received_, blob_expected_);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"size_overrun\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  if (blob_file_.write(data, len) != len) {
    _emitBlobDebug(serial_, "rx_write_failed", blob_req_id_, blob_received_, blob_expected_);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"write_failed\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  blob_crc_running_ = crc32_update(blob_crc_running_, data, len);
  blob_received_ += len;
  if (blob_received_ == len || blob_received_ == blob_expected_ || (blob_received_ % 2048) == 0) {
    _emitBlobDebug(serial_, "rx_progress", blob_req_id_, blob_received_, blob_expected_);
  }
  if (blob_received_ < blob_expected_) return;
  if (blob_expect_end_) {
    blob_complete_ = true;
    _emitBlobDebug(serial_, "rx_wait_end", blob_req_id_, blob_received_, blob_expected_);
    return;
  }
  _emitBlobDebug(serial_, "rx_auto_finalize", blob_req_id_, blob_received_, blob_expected_);
  finalizeBlobResult();
}

void ProtocolHandler::resetBlobState() {
  if (blob_file_) {
    blob_file_.close();
  }
  blob_active_ = false;
  blob_expected_ = 0;
  blob_received_ = 0;
  blob_crc_expected_ = 0;
  blob_crc_running_ = 0;
  blob_expect_end_ = false;
  blob_complete_ = false;
  blob_req_id_ = "";
  blob_path_ = "";
  blob_type_ = "";
}

void ProtocolHandler::finalizeBlobResult() {
  String blob_type = blob_type_;
  String blob_path = blob_path_;
  String req_id = blob_req_id_;
  _emitBlobDebug(serial_, "finalize_start", req_id, blob_received_, blob_expected_, blob_type);

  if (!blob_file_) {
    _emitBlobDebug(serial_, "finalize_file_closed", req_id, blob_received_, blob_expected_);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"file_closed\"}", req_id));
    resetBlobState();
    return;
  }

  blob_file_.close();
  blob_active_ = false;

  if (blob_crc_expected_ && blob_crc_running_ != blob_crc_expected_) {
    _emitBlobDebug(serial_, "finalize_crc_mismatch", req_id, blob_received_, blob_expected_);
    _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"crc_mismatch\"}", req_id));
    resetBlobState();
    return;
  }

  if (blob_type == "hardware") {
    uint16_t count = 0;
    String error;
    bool valid = validateMappingBlob(blob_path.c_str(), &count, &error);
    if (!valid) {
      _emitBlobDebug(serial_, "finalize_hardware_invalid", req_id, blob_received_, blob_expected_, error);
      String msg = "{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"";
      msg += error;
      msg += "\"}";
      _enqueueWithRetry(serial_, append_req_id(msg, req_id));
      resetBlobState();
      return;
    }
  } else if (blob_type == "rules") {
    String error;
    bool valid = validateRulesBlob(blob_path.c_str(), &error);
    if (!valid) {
      _emitBlobDebug(serial_, "finalize_rules_invalid", req_id, blob_received_, blob_expected_, error);
      String msg = "{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"";
      msg += error;
      msg += "\"}";
      _enqueueWithRetry(serial_, append_req_id(msg, req_id));
      resetBlobState();
      return;
    }
  }

  _emitBlobDebug(serial_, "finalize_ok", req_id, blob_received_, blob_expected_, blob_type);
  _enqueueWithRetry(serial_, append_req_id("{\"t\":\"BLOB_RESULT\",\"ok\":true}", req_id));
  resetBlobState();

  if (blob_type == "hardware") {
    String apply_err;
    uint16_t applied = 0;
    if (applyMappingBlob(blob_path.c_str(), &applied, &apply_err)) {
      String msg = "{\"t\":\"MAP_APPLY\",\"status\":\"ok\",\"count\":";
      msg += applied;
      msg += "}";
      _enqueueWithRetry(serial_, msg);
    } else {
      String msg = "{\"t\":\"MAP_APPLY\",\"status\":\"error\",\"reason\":\"";
      msg += apply_err;
      msg += "\"}";
      _enqueueWithRetry(serial_, msg);
    }
  }
}
