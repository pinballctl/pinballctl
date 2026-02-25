#include "components/ButtonComponent.h"

ButtonComponent::ButtonComponent(const char* comp_id, int pin)
    : id_(comp_id), pin_(pin), last_state_high_(false), event_pending_(false), pending_event_() {}

const char* ButtonComponent::id() const {
  return id_;
}

void ButtonComponent::begin() {
  pinMode(pin_, INPUT_PULLUP);
  last_state_high_ = (digitalRead(pin_) == HIGH);
}

void ButtonComponent::service(unsigned long now_ms) {
  bool current_high = (digitalRead(pin_) == HIGH);
  if (current_high == last_state_high_) return;
  last_state_high_ = current_high;
  pending_event_.source = String(id_);
  pending_event_.type = current_high ? "RELEASED" : "PRESSED";
  pending_event_.ts_ms = now_ms;
  pending_event_.data = "";
  event_pending_ = true;
}

bool ButtonComponent::readEvent(ComponentEvent* out_event) {
  if (!out_event || !event_pending_) return false;
  *out_event = pending_event_;
  event_pending_ = false;
  return true;
}
