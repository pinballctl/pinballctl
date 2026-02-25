#include "components/GyroComponent.h"

GyroComponent::GyroComponent(const char* comp_id) : id_(comp_id) {}

const char* GyroComponent::id() const {
  return id_;
}

void GyroComponent::begin() {}

void GyroComponent::service(unsigned long now_ms) {
  (void)now_ms;
}

bool GyroComponent::readEvent(ComponentEvent* out_event) {
  (void)out_event;
  return false;
}
