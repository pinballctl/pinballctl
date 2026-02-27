// HardwareStreamer: streams pin catalog as HW_BEGIN/HW_PIN/HW_END frames.

#include "hw/HardwareStreamer.h"
#include "hw/MappingBlob.h"

namespace {
constexpr const char* kMappingBlobPath = "/cfg/mapping.pb";
}

HardwareStreamer::HardwareStreamer(FramedSerial& serial)
    : serial_(serial),
      controller_id_("ESP32S3"),
      streaming_(false),
      index_(0),
      last_tick_ms_(0),
      start_ms_(0),
      begin_sent_(false) {}

void HardwareStreamer::setControllerId(const char* controller_id) {
  controller_id_ = controller_id ? controller_id : "ESP32S3";
}

bool HardwareStreamer::isStreaming() const {
  return streaming_;
}

void HardwareStreamer::start() {
  streaming_ = true;
  index_ = 0;
  last_tick_ms_ = millis();
  start_ms_ = last_tick_ms_;
  begin_sent_ = false;
}

bool HardwareStreamer::shouldProbePin(const PinEntry& p) const {
  return kAllowGpioProbe && p.safe && p.gpio >= 0;
}

void HardwareStreamer::restoreMappedSafeStates() {
  uint16_t restored = 0;
  String error;
  if (applyMappingBlob(kMappingBlobPath, &restored, &error)) {
    String msg = "{\"t\":\"HW_STATUS\",\"stage\":\"map_restore\",\"status\":\"ok\",\"count\":";
    msg += restored;
    msg += "}";
    serial_.enqueue(msg);
    return;
  }

  String msg = "{\"t\":\"HW_STATUS\",\"stage\":\"map_restore\",\"status\":\"skipped\",\"reason\":\"";
  msg += error.length() ? error : "unknown";
  msg += "\"}";
  serial_.enqueue(msg);
}

void HardwareStreamer::appendJsonEscaped(String& out, const char* s) const {
  if (!s) return;
  for (const char* p = s; *p; ++p) {
    char c = *p;
    switch (c) {
      case '\\': out += "\\\\"; break;
      case '"':  out += "\\\""; break;
      case '\n': out += "\\n";  break;
      case '\r': out += "\\r";  break;
      case '\t': out += "\\t";  break;
      default:
        if ((unsigned char)c < 0x20) break;
        out += c;
        break;
    }
  }
}

void HardwareStreamer::appendPinJson(String& out, const PinEntry& p, bool include_state, int state) const {
  char uid[96];
  snprintf(uid, sizeof(uid), "%s__%s__%s__%s", controller_id_, p.board, p.type, p.chan);

  out += "{\"uid\":\""; out += uid;
  out += "\",\"board\":\""; out += p.board;
  out += "\",\"type\":\""; out += p.type;
  out += "\",\"chan\":\""; out += p.chan;

  out += "\",\"safe\":"; out += (p.safe ? "true" : "false");

  out += ",\"reported\":\"";
  appendJsonEscaped(out, p.reported);
  out += "\"";

  if (p.notes && *p.notes) {
    out += ",\"notes\":\"";
    appendJsonEscaped(out, p.notes);
    out += "\"";
  }

  if (include_state) {
    out += ",\"state\":"; out += state;
  }

  out += "}";
}

void HardwareStreamer::service(unsigned long now_ms) {
  if (!streaming_) return;

  if (now_ms - last_tick_ms_ < 5) return;
  last_tick_ms_ = now_ms;

  const size_t gcount = PinCatalog::count();

  if (!begin_sent_) {
    if (!serial_.enqueue("{\"t\":\"HW_STATUS\",\"stage\":\"begin\"}")) return;

    String msg = "{\"t\":\"HW_BEGIN\",\"controller\":\"";
    msg += controller_id_;
    msg += "\"}";
    if (!serial_.enqueue(msg)) return;

    begin_sent_ = true;
  }

  if (start_ms_ > 0 && (now_ms - start_ms_) > kStreamTimeoutMs) {
    String end_msg = "{\"t\":\"HW_END\",\"controller\":\"";
    end_msg += controller_id_;
    end_msg += "\"}";
    if (serial_.enqueue(end_msg) &&
        serial_.enqueue("{\"t\":\"HW_STATUS\",\"stage\":\"forced_end\"}")) {
      restoreMappedSafeStates();
      streaming_ = false;
      start_ms_ = 0;
      index_ = 0;
    }
    return;
  }

  if (index_ < gcount) {
    const PinEntry& p = PinCatalog::at(index_);
    const bool do_probe = shouldProbePin(p);
    size_t needed = do_probe ? 2 : 1;
    if (serial_.queueFree() < needed) return;

    int state = 0;

    if (do_probe) {
      String probe = "{\"t\":\"HW_PROBE\",\"controller\":\"";
      probe += controller_id_;
      probe += "\",\"gpio\":";
      probe += p.gpio;
      probe += ",\"uid\":\"";
      probe += controller_id_;
      probe += "__";
      probe += p.board;
      probe += "__";
      probe += p.type;
      probe += "__";
      probe += p.chan;
      probe += "\"}";
      if (!serial_.enqueue(probe)) return;

      pinMode(p.gpio, INPUT);
      state = digitalRead(p.gpio) ? 1 : 0;
    }

    String msg = "{\"t\":\"HW_PIN\",\"controller\":\"";
    msg += controller_id_;
    msg += "\",\"pin\":";
    appendPinJson(msg, p, do_probe, state);
    msg += "}";

    if (serial_.enqueue(msg)) {
      index_++;
    }
    return;
  }

  String end_msg = "{\"t\":\"HW_END\",\"controller\":\"";
  end_msg += controller_id_;
  end_msg += "\"}";

  if (serial_.enqueue(end_msg) &&
      serial_.enqueue("{\"t\":\"HW_STATUS\",\"stage\":\"end\"}")) {
    restoreMappedSafeStates();
    streaming_ = false;
    start_ms_ = 0;
    index_ = 0;
  }
}
