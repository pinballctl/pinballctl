#ifndef PINBALLCTL_SYSTEM_H
#define PINBALLCTL_SYSTEM_H

// System: top-level firmware orchestrator for serial, protocol, and hardware streaming.

#include <Arduino.h>
#include "core/FramedSerial.h"
#include "hardware/HardwareStreamer.h"
#include "protocol/ProtocolHandler.h"

class System {
 public:
  System();

  void setup();
  void loop();

 private:
  FramedSerial serial_;
  HardwareStreamer streamer_;
  ProtocolHandler protocol_;
  unsigned long last_heartbeat_ms_;
  char controller_id_[24];
  bool rx_have_header_;
  uint32_t rx_expected_len_;
  size_t rx_received_;
  uint8_t rx_buf_[FramedSerial::kFrameMax + 1];
  uint8_t rx_header_buf_[4];
  size_t rx_header_len_;
  unsigned long rx_last_progress_ms_;
  void resetRxParser();
  void updateControllerId();
  void sendPing(unsigned long now_ms);
};

#endif  // PINBALLCTL_SYSTEM_H
