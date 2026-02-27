#ifndef PINBALLCTL_HARDWARE_STREAMER_H
#define PINBALLCTL_HARDWARE_STREAMER_H

// HardwareStreamer: streams pin catalog as HW_BEGIN/HW_PIN/HW_END frames.

#include <Arduino.h>
#include "core/FramedSerial.h"
#include "hw/PinCatalog.h"

class HardwareStreamer {
 public:
  explicit HardwareStreamer(FramedSerial& serial);

  void setControllerId(const char* controller_id);
  void start();
  void service(unsigned long now_ms);
  bool isStreaming() const;

 private:
  FramedSerial& serial_;
  const char* controller_id_;
  bool streaming_;
  size_t index_;
  unsigned long last_tick_ms_;
  unsigned long start_ms_;
  bool begin_sent_;

  static const unsigned long kStreamTimeoutMs = 8000;
  static const bool kAllowGpioProbe = true;

  bool shouldProbePin(const PinEntry& p) const;
  void restoreMappedSafeStates();
  void appendJsonEscaped(String& out, const char* s) const;
  void appendPinJson(String& out, const PinEntry& p, bool include_state, int state) const;
};

#endif  // PINBALLCTL_HARDWARE_STREAMER_H
