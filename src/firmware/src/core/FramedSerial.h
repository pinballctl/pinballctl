#ifndef PINBALLCTL_FRAMED_SERIAL_H
#define PINBALLCTL_FRAMED_SERIAL_H

// FramedSerial: non-blocking length-prefixed JSON frame queue over Serial.

#include <Arduino.h>

class FramedSerial {
 public:
  static const size_t kQueueMax = 8;
  static const size_t kFrameMax = 8192;

  FramedSerial();

  void pump();
  bool enqueue(const String& payload);
  bool enqueueText(const String& payload);
  bool enqueueTyped(uint8_t type, const uint8_t* data, size_t len);
  bool enqueueTyped(uint8_t type, const String& payload);
  size_t queueFree() const;

 private:
  uint8_t queue_[kQueueMax][kFrameMax];
  size_t len_[kQueueMax];
  size_t off_[kQueueMax];
  size_t head_;
  size_t tail_;
  size_t count_;
};

#endif  // PINBALLCTL_FRAMED_SERIAL_H
