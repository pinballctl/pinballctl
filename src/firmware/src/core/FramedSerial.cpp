// FramedSerial: non-blocking length-prefixed JSON frame queue over Serial.

#include "core/FramedSerial.h"

FramedSerial::FramedSerial()
    : head_(0), tail_(0), count_(0) {
  for (size_t i = 0; i < kQueueMax; i++) {
    len_[i] = 0;
    off_[i] = 0;
  }
}

void FramedSerial::pump() {
  if (count_ == 0) return;
  int avail = Serial.availableForWrite();
  if (avail <= 0) return;

  size_t idx = head_;
  size_t remaining = len_[idx] - off_[idx];

  if (remaining == 0) {
    off_[idx] = 0;
    len_[idx] = 0;
    head_ = (head_ + 1) % kQueueMax;
    count_--;
    return;
  }

  if (remaining > (size_t)avail) remaining = (size_t)avail;
  size_t wrote = Serial.write(queue_[idx] + off_[idx], remaining);
  off_[idx] += wrote;

  if (off_[idx] >= len_[idx]) {
    off_[idx] = 0;
    len_[idx] = 0;
    head_ = (head_ + 1) % kQueueMax;
    count_--;
  }
}

size_t FramedSerial::queueFree() const {
  return (count_ >= kQueueMax) ? 0 : (kQueueMax - count_);
}

bool FramedSerial::enqueue(const String& payload) {
  return enqueueTyped(1, payload);
}

bool FramedSerial::enqueueText(const String& payload) {
  return enqueueTyped(3, payload);
}

bool FramedSerial::enqueueTyped(uint8_t type, const String& payload) {
  return enqueueTyped(type, reinterpret_cast<const uint8_t*>(payload.c_str()), payload.length());
}

bool FramedSerial::enqueueTyped(uint8_t type, const uint8_t* data, size_t len) {
  if (!data && len > 0) return false;
  uint32_t frame_len = (uint32_t)len + 1;
  if (frame_len + 4 > kFrameMax) return false;
  if (count_ >= kQueueMax) return false;

  size_t idx = tail_;
  uint8_t hdr[4] = {
    (uint8_t)((frame_len >> 24) & 0xFF),
    (uint8_t)((frame_len >> 16) & 0xFF),
    (uint8_t)((frame_len >> 8) & 0xFF),
    (uint8_t)(frame_len & 0xFF)
  };

  memcpy(queue_[idx], hdr, 4);
  queue_[idx][4] = type;
  if (len > 0) {
    memcpy(queue_[idx] + 5, data, len);
  }

  len_[idx] = frame_len + 4;
  off_[idx] = 0;

  tail_ = (tail_ + 1) % kQueueMax;
  count_++;
  return true;
}
