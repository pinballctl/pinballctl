#ifndef PINBALLCTL_GYRO_COMPONENT_H
#define PINBALLCTL_GYRO_COMPONENT_H

#include "components/Component.h"
#include "components/ComponentInterfaces.h"

class GyroComponent : public Component, public EventSource {
 public:
  explicit GyroComponent(const char* comp_id);
  const char* id() const override;
  void begin() override;
  void service(unsigned long now_ms) override;
  bool readEvent(ComponentEvent* out_event) override;

 private:
  const char* id_;
};

#endif  // PINBALLCTL_GYRO_COMPONENT_H
