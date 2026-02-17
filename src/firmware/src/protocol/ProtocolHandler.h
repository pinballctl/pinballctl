#ifndef PINBALLCTL_PROTOCOL_HANDLER_H
#define PINBALLCTL_PROTOCOL_HANDLER_H

// ProtocolHandler: handles text commands and emits framed responses.

#include <Arduino.h>
#include <FS.h>
#include "core/FramedSerial.h"
#include "hw/HardwareStreamer.h"

class ProtocolHandler {
 public:
  ProtocolHandler(FramedSerial& serial, HardwareStreamer& streamer);

  void sendInfo(const String& req_id = String());
  void handleLine(const String& line);
  void handleFrame(const uint8_t* data, size_t len, uint8_t frame_type, bool typed);
  void service(unsigned long now_ms);
  void setFsMounted(bool mounted);

 private:
  void finalizeBlobResult();
  void resetBlobState();
  FramedSerial& serial_;
  HardwareStreamer& streamer_;
  String rules_payload_;
  bool fs_mounted_;
  bool blob_active_;
  size_t blob_expected_;
  size_t blob_received_;
  uint32_t blob_crc_expected_;
  uint32_t blob_crc_running_;
  bool blob_expect_end_;
  bool blob_complete_;
  bool last_cmd_typed_;
  String blob_req_id_;
  String blob_path_;
  String blob_type_;
  fs::File blob_file_;

  bool evt_stream_active_;
  uint32_t evt_stream_target_count_;
  uint32_t evt_stream_sent_count_;
  uint32_t evt_stream_drop_count_;
  uint32_t evt_stream_rate_hz_;
  uint32_t evt_stream_interval_us_;
  uint32_t evt_stream_last_emit_us_;
  String evt_stream_name_;
  String evt_stream_source_;
  String evt_stream_req_id_;
  uint32_t evt_in_total_;
  uint32_t evt_in_ack_count_;
  uint32_t evt_in_fire_count_;
  uint32_t evt_in_last_seq_;
  unsigned long evt_in_last_ms_;
  String evt_in_last_name_;
  String evt_in_last_source_;

};

#endif  // PINBALLCTL_PROTOCOL_HANDLER_H
