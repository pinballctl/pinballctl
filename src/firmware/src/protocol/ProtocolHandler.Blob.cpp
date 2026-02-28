#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"

#include <LittleFS.h>

#include "hardware/MappingBlob.h"
#include "hardware/RulesBlob.h"

namespace {
constexpr const char* kMappingBootGuardPath = "/cfg/mapping.boot_fail";
constexpr const char* kRulesBootGuardPath = "/cfg/rules.boot_fail";
constexpr const char* kLightingBootGuardPath = "/cfg/lighting.boot_fail";
}

bool ProtocolHandler::handleBlobCommands(const String& line, const String& req_id, const String& cmd) {
  if (protocol_support::isCmd(line, cmd, "BLOB_END")) {
    uint32_t sent = 0;
    protocol_support::extractJsonUint(line, "sent", &sent);
    protocol_support::emitBlobDebug(serial_, "end_cmd", req_id, blob_received_, blob_expected_);
    if (!blob_active_) {
      protocol_support::emitBlobDebug(serial_, "end_no_blob", req_id, blob_received_, blob_expected_);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"no_blob\"}", req_id));
      return true;
    }
    if (req_id.length() && blob_req_id_.length() && req_id != blob_req_id_) {
      protocol_support::emitBlobDebug(serial_, "end_req_mismatch", req_id, blob_received_, blob_expected_);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"req_mismatch\"}", req_id));
      resetBlobState();
      return true;
    }
    if (blob_received_ < blob_expected_) {
      protocol_support::emitBlobDebug(serial_, "end_incomplete", req_id, blob_received_, blob_expected_);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"incomplete\"}", req_id));
      resetBlobState();
      return true;
    }
    if (sent && sent != blob_received_) {
      protocol_support::emitBlobDebug(serial_, "end_size_mismatch", req_id, blob_received_, blob_expected_);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"size_mismatch\"}", req_id));
      resetBlobState();
      return true;
    }
    protocol_support::emitBlobDebug(serial_, "end_finalize", req_id, blob_received_, blob_expected_);
    finalizeBlobResult();
    return true;
  }

  if (protocol_support::isCmd(line, cmd, "BLOB_BEGIN")) {
    if (!fs_mounted_) {
      protocol_support::emitBlobDebug(serial_, "begin_fs_unmounted", req_id, 0, 0);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"fs_not_mounted\"}", req_id));
      return true;
    }
    if (blob_active_) {
      protocol_support::emitBlobDebug(serial_, "begin_busy", req_id, blob_received_, blob_expected_);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"busy\"}", req_id));
      return true;
    }

    String path;
    String blob_type;
    uint32_t size = 0;
    uint32_t crc32 = 0;
    uint32_t ver = 0;
    protocol_support::extractJsonString(line, "path", &path);
    protocol_support::extractJsonString(line, "blobType", &blob_type);
    protocol_support::extractJsonUint(line, "size", &size);
    protocol_support::extractJsonUint(line, "crc32", &crc32);
    protocol_support::extractJsonUint(line, "ver", &ver);
    (void)ver;

    if (!path.length() || !path.startsWith("/cfg/")) {
      protocol_support::emitBlobDebug(serial_, "begin_bad_path", req_id, 0, size);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"bad_path\"}", req_id));
      return true;
    }
    if (size == 0) {
      protocol_support::emitBlobDebug(serial_, "begin_bad_size", req_id, 0, size);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"bad_size\"}", req_id));
      return true;
    }
    if (!LittleFS.exists("/cfg")) {
      LittleFS.mkdir("/cfg");
    }

    blob_file_ = LittleFS.open(path, "w");
    if (!blob_file_) {
      protocol_support::emitBlobDebug(serial_, "begin_open_failed", req_id, 0, size);
      protocol_support::enqueueWithRetry(
          serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":false,\"reason\":\"open_failed\"}", req_id));
      return true;
    }

    blob_active_ = true;
    blob_expected_ = size;
    blob_received_ = 0;
    blob_crc_expected_ = crc32;
    blob_crc_running_ = 0;
    blob_next_ack_at_ = (blob_ack_step_ > 0) ? blob_ack_step_ : 1024;
    if (blob_next_ack_at_ > blob_expected_) blob_next_ack_at_ = blob_expected_;
    blob_expect_end_ = last_cmd_typed_;
    blob_complete_ = false;
    blob_req_id_ = req_id;
    blob_path_ = path;
    blob_type_ = blob_type;
    protocol_support::emitBlobDebug(serial_, "begin_ok", req_id, 0, blob_expected_, blob_type);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_READY\",\"ok\":true}", req_id));
    return true;
  }

  return false;
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
  if (!blob_active_) return;
  if (!blob_file_) {
    protocol_support::emitBlobDebug(serial_, "rx_file_closed", blob_req_id_, blob_received_, blob_expected_);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"file_closed\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  if (blob_received_ + len > blob_expected_) {
    protocol_support::emitBlobDebug(serial_, "rx_size_overrun", blob_req_id_, blob_received_, blob_expected_);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"size_overrun\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  if (blob_file_.write(data, len) != len) {
    protocol_support::emitBlobDebug(serial_, "rx_write_failed", blob_req_id_, blob_received_, blob_expected_);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"write_failed\"}", blob_req_id_));
    resetBlobState();
    return;
  }
  blob_crc_running_ = crc32_update(blob_crc_running_, data, len);
  blob_received_ += len;
  if (blob_received_ == len || blob_received_ == blob_expected_ || (blob_received_ % 2048) == 0) {
    protocol_support::emitBlobDebug(serial_, "rx_progress", blob_req_id_, blob_received_, blob_expected_);
  }
  while (blob_next_ack_at_ > 0 && blob_received_ >= blob_next_ack_at_) {
    String ack = "{\"t\":\"BLOB_ACK\",\"received\":";
    ack += static_cast<uint32_t>(blob_received_);
    ack += "}";
    protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(ack, blob_req_id_));
    if (blob_next_ack_at_ >= blob_expected_) {
      blob_next_ack_at_ = 0;
      break;
    }
    blob_next_ack_at_ += blob_ack_step_;
    if (blob_next_ack_at_ > blob_expected_) blob_next_ack_at_ = blob_expected_;
  }
  if (blob_received_ < blob_expected_) return;
  if (blob_expect_end_) {
    blob_complete_ = true;
    protocol_support::emitBlobDebug(serial_, "rx_wait_end", blob_req_id_, blob_received_, blob_expected_);
    return;
  }
  protocol_support::emitBlobDebug(serial_, "rx_auto_finalize", blob_req_id_, blob_received_, blob_expected_);
  finalizeBlobResult();
}

void ProtocolHandler::resetBlobState() {
  if (blob_file_) blob_file_.close();
  blob_active_ = false;
  blob_expected_ = 0;
  blob_received_ = 0;
  blob_crc_expected_ = 0;
  blob_crc_running_ = 0;
  blob_next_ack_at_ = 0;
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
  protocol_support::emitBlobDebug(serial_, "finalize_start", req_id, blob_received_, blob_expected_, blob_type);

  if (!blob_file_) {
    protocol_support::emitBlobDebug(serial_, "finalize_file_closed", req_id, blob_received_, blob_expected_);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"file_closed\"}", req_id));
    resetBlobState();
    return;
  }

  blob_file_.close();
  blob_active_ = false;

  if (blob_crc_expected_ && blob_crc_running_ != blob_crc_expected_) {
    protocol_support::emitBlobDebug(serial_, "finalize_crc_mismatch", req_id, blob_received_, blob_expected_);
    protocol_support::enqueueWithRetry(
        serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"crc_mismatch\"}", req_id));
    resetBlobState();
    return;
  }

  if (blob_type == "hardware") {
    uint16_t count = 0;
    String error;
    if (!validateMappingBlob(blob_path.c_str(), &count, &error)) {
      protocol_support::emitBlobDebug(serial_, "finalize_hardware_invalid", req_id, blob_received_, blob_expected_, error);
      String msg = "{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"";
      msg += error;
      msg += "\"}";
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(msg, req_id));
      resetBlobState();
      return;
    }
  } else if (blob_type == "rules") {
    String error;
    if (!validateRulesBlob(blob_path.c_str(), &error)) {
      protocol_support::emitBlobDebug(serial_, "finalize_rules_invalid", req_id, blob_received_, blob_expected_, error);
      String msg = "{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"";
      msg += error;
      msg += "\"}";
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(msg, req_id));
      resetBlobState();
      return;
    }
  } else if (blob_type == "lighting") {
    String error;
    if (!lighting_runtime_.loadFromLightingBlob(blob_path.c_str(), &error)) {
      protocol_support::emitBlobDebug(serial_, "finalize_lighting_invalid", req_id, blob_received_, blob_expected_, error);
      String msg = "{\"t\":\"BLOB_RESULT\",\"ok\":false,\"reason\":\"";
      msg += error;
      msg += "\"}";
      protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(msg, req_id));
      resetBlobState();
      return;
    }
  }

  protocol_support::emitBlobDebug(serial_, "finalize_ok", req_id, blob_received_, blob_expected_, blob_type);
  protocol_support::enqueueWithRetry(
      serial_, protocol_support::appendReqId("{\"t\":\"BLOB_RESULT\",\"ok\":true}", req_id));
  resetBlobState();

  if (blob_type == "hardware") {
    String apply_err;
    uint16_t applied = 0;
    if (applyMappingBlob(blob_path.c_str(), &applied, &apply_err)) {
      protocol_support::clearBootGuard(kMappingBootGuardPath);
      String msg = "{\"t\":\"MAP_APPLY\",\"status\":\"ok\",\"count\":";
      msg += applied;
      msg += "}";
      protocol_support::enqueueWithRetry(serial_, msg);
    } else {
      String msg = "{\"t\":\"MAP_APPLY\",\"status\":\"error\",\"reason\":\"";
      msg += apply_err;
      msg += "\"}";
      protocol_support::enqueueWithRetry(serial_, msg);
    }
  } else if (blob_type == "rules") {
    // Keep rules blob transport-only for now.
    // Runtime rules continue to come from SET_RULES to avoid parser instability.
    protocol_support::clearBootGuard(kRulesBootGuardPath);
  } else if (blob_type == "lighting") {
    protocol_support::clearBootGuard(kLightingBootGuardPath);
    protocol_support::enqueueWithRetry(serial_, "{\"t\":\"LIGHTING_APPLY\",\"status\":\"ok\"}");
  }
}
