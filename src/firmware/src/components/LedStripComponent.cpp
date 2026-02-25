#include "components/LedStripComponent.h"

LedStripComponent::LedStripComponent(const char* comp_id, int pin) : id_(comp_id), pin_(pin) {}

const char* LedStripComponent::id() const {
  return id_;
}

void LedStripComponent::begin() {
  pinMode(pin_, OUTPUT);
  digitalWrite(pin_, LOW);
}

void LedStripComponent::service(unsigned long now_ms) {
  (void)now_ms;
}

bool LedStripComponent::setOutput(bool high) {
  digitalWrite(pin_, high ? HIGH : LOW);
  return true;
}

bool LedStripComponent::pulseOutput(uint32_t duration_ms) {
  (void)duration_ms;
  return setOutput(true);
}
