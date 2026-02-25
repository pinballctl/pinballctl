#include "components/CoilComponent.h"

CoilComponent::CoilComponent(const char* comp_id, int pin, bool safe_high)
    : id_(comp_id), pin_(pin), safe_high_(safe_high), pulse_active_(false), pulse_end_ms_(0) {}

const char* CoilComponent::id() const {
  return id_;
}

void CoilComponent::begin() {
  pinMode(pin_, OUTPUT);
  digitalWrite(pin_, safe_high_ ? HIGH : LOW);
}

void CoilComponent::service(unsigned long now_ms) {
  if (!pulse_active_) return;
  if (now_ms < pulse_end_ms_) return;
  pulse_active_ = false;
  digitalWrite(pin_, safe_high_ ? HIGH : LOW);
}

bool CoilComponent::setOutput(bool high) {
  pulse_active_ = false;
  digitalWrite(pin_, high ? HIGH : LOW);
  return true;
}

bool CoilComponent::pulseOutput(uint32_t duration_ms) {
  if (duration_ms == 0) duration_ms = 20;
  digitalWrite(pin_, HIGH);
  pulse_active_ = true;
  pulse_end_ms_ = millis() + duration_ms;
  return true;
}
