// System: top-level firmware orchestrator for serial, protocol, and hardware streaming.

#include "System.h"
#include <LittleFS.h>
#include "drivers/LcdDisplay/LCD1602I2C.h"

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

System::System()
    : serial_(),
      streamer_(serial_),
      protocol_(serial_, streamer_),
      last_heartbeat_ms_(0),
      rx_have_header_(false),
      rx_expected_len_(0),
      rx_received_(0),
      rx_header_len_(0),
      rx_last_progress_ms_(0) {
  strncpy(controller_id_, "ESP32", sizeof(controller_id_));
  controller_id_[sizeof(controller_id_) - 1] = '\0';
}

void System::resetRxParser() {
  rx_have_header_ = false;
  rx_expected_len_ = 0;
  rx_received_ = 0;
  rx_header_len_ = 0;
  rx_last_progress_ms_ = millis();
}

void System::updateControllerId() {
  String chip_model = ESP.getChipModel();
  chip_model.replace(" ", "");
  if (!chip_model.length()) chip_model = "ESP32";
  uint64_t mac = ESP.getEfuseMac();
  uint32_t low = (uint32_t)(mac & 0xFFFFFFFF);
  snprintf(controller_id_, sizeof(controller_id_), "%s-%08X", chip_model.c_str(), low);
  streamer_.setControllerId(controller_id_);
}

void System::setup() {
  Serial.begin(460800);

  unsigned long start = millis();
  while (!Serial && millis() - start < 3000) {
    delay(10);
  }

  updateControllerId();
  delay(300);
  bool mounted = LittleFS.begin(true);
  if (mounted) {
    if (!LittleFS.exists("/rules")) {
      LittleFS.mkdir("/rules");
    }
    if (!LittleFS.exists("/cfg")) {
      LittleFS.mkdir("/cfg");
    }
  }
  protocol_.setFsMounted(mounted);
  if (mounted) {
    _enqueueWithRetry(serial_, "{\"t\":\"FS_STATUS\",\"boot\":true,\"fs\":\"littlefs\",\"mounted\":true}");
  } else {
    _enqueueWithRetry(serial_, "{\"t\":\"FS_STATUS\",\"boot\":true,\"fs\":\"littlefs\",\"mounted\":false,\"error\":\"begin_failed\"}");
  }
  if (mounted) {
    protocol_.loadMappingFromFsOnBoot();
    protocol_.loadRulesFromFsOnBoot();
    protocol_.loadLightingFromFsOnBoot();
  }
  protocol_.sendInfo();
}

void System::sendPing(unsigned long now_ms) {
  if (now_ms - last_heartbeat_ms_ < 10000) return;
  last_heartbeat_ms_ = now_ms;
  if (streamer_.isStreaming()) return;
  // Keep queue headroom for command responses.
  if (serial_.queueFree() <= 2) return;
  String hb = "{\"t\":\"PING\",\"uptime\":";
  hb += now_ms;
  hb += "}";
  _enqueueWithRetry(serial_, hb, 10);
}

void System::loop() {
  static const unsigned long kRxStallTimeoutMs = 2000;
  serial_.pump();

  const unsigned long now = millis();
  protocol_.service(now);
  LcdDisplayLCD1602I2C::service(now);
  sendPing(now);

  // If an inbound frame stalls mid-header/body, reset parser to avoid permanent lockup.
  // Keep this conservative to avoid dropping valid commands during brief USB jitter.
  bool stalled = (rx_header_len_ > 0) || rx_have_header_;
  if (stalled && (now - rx_last_progress_ms_ > kRxStallTimeoutMs)) {
    resetRxParser();
  }

  streamer_.service(now);
  while (Serial.available()) {
    if (!rx_have_header_) {
      while (Serial.available() > 0 && rx_header_len_ < 4) {
        int b = Serial.read();
        if (b < 0) break;
        rx_header_buf_[rx_header_len_++] = (uint8_t)b;
        rx_last_progress_ms_ = millis();
      }
      if (rx_header_len_ < 4) break;
      uint8_t* hdr = rx_header_buf_;
      rx_header_len_ = 0;
      rx_expected_len_ = ((uint32_t)hdr[0] << 24) | ((uint32_t)hdr[1] << 16) | ((uint32_t)hdr[2] << 8) | hdr[3];
      if (rx_expected_len_ == 0 || rx_expected_len_ > FramedSerial::kFrameMax) {
        // Shift header by one byte for resync without discarding extra input.
        rx_header_buf_[0] = hdr[1];
        rx_header_buf_[1] = hdr[2];
        rx_header_buf_[2] = hdr[3];
        rx_header_len_ = 3;
        rx_have_header_ = false;
        rx_expected_len_ = 0;
        rx_received_ = 0;
        rx_last_progress_ms_ = millis();
        continue;
      }
      rx_have_header_ = true;
      rx_received_ = 0;
      rx_last_progress_ms_ = millis();
    }

    while (rx_have_header_ && Serial.available() > 0 && rx_received_ < rx_expected_len_) {
      int b = Serial.read();
      if (b < 0) break;
      rx_buf_[rx_received_++] = (uint8_t)b;
      rx_last_progress_ms_ = millis();
    }

    if (rx_have_header_ && rx_received_ >= rx_expected_len_) {
      bool typed = false;
      uint8_t frame_type = 1;
      const uint8_t* data = rx_buf_;
      size_t len = rx_expected_len_;
      if (rx_expected_len_ > 0) {
        uint8_t first = rx_buf_[0];
        if (first == 2) {
          // Typed binary frame.
          typed = true;
          frame_type = first;
          data = rx_buf_ + 1;
          len = rx_expected_len_ > 0 ? (rx_expected_len_ - 1) : 0;
        } else if (first == 1 || first == 3) {
          // Only treat type=1/3 as typed when payload appears JSON-like.
          // This avoids misclassifying untyped blob payload chunks whose first byte
          // happens to equal 0x01/0x03, which would otherwise drop/corrupt tail bytes.
          if (rx_expected_len_ > 1 && rx_buf_[1] == '{') {
            typed = true;
            frame_type = first;
            data = rx_buf_ + 1;
            len = rx_expected_len_ > 0 ? (rx_expected_len_ - 1) : 0;
          }
        }
      }
      if (len > 0) {
        protocol_.handleFrame(data, len, frame_type, typed);
      }
      resetRxParser();
    }
  }
}
