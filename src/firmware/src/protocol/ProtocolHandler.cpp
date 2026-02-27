// ProtocolHandler core lifecycle wiring.

#include "protocol/ProtocolHandler.h"
#include "protocol/core/ProtocolSupport.h"
#include "version.h"

ProtocolHandler::ProtocolHandler(FramedSerial& serial, HardwareStreamer& streamer)
    : serial_(serial),
      streamer_(streamer),
      system_runtime_(),
      lighting_runtime_(),
      rules_runtime_(),
      rules_payload_(""),
      fs_mounted_(false),
      blob_active_(false),
      blob_expected_(0),
      blob_received_(0),
      blob_crc_expected_(0),
      blob_crc_running_(0),
      blob_ack_step_(1024),
      blob_next_ack_at_(0),
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
      evt_in_stale_drop_count_(0),
      evt_in_last_seq_(0),
      evt_in_last_ms_(0),
      evt_in_last_name_(""),
      evt_in_last_source_("") {}

void ProtocolHandler::setFsMounted(bool mounted) {
  fs_mounted_ = mounted;
  if (!fs_mounted_) {
    rules_runtime_.clear();
    lighting_runtime_.clear();
  }
}

void ProtocolHandler::sendInfo(const String& req_id) {
  const char* ver = FW_VERSION;
  if (!ver || !*ver) ver = "v0.0.0";
  String payload = "{\"t\":\"INFO\",\"fw\":\"";
  payload += ver;
  payload += "\",\"chip\":\"esp32s3\",\"proto\":2}";
  protocol_support::enqueueWithRetry(serial_, protocol_support::appendReqId(payload, req_id));
}
