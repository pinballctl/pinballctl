#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/components/CoilComponent.h"
#ifndef PINBALLCTL_COIL_COMPONENT_H
#define PINBALLCTL_COIL_COMPONENT_H

#include "components/Component.h"
#include "components/ComponentInterfaces.h"

class CoilComponent : public Component, public Actuator {
 public:
  CoilComponent(const char* comp_id, int pin, bool safe_high);
  const char* id() const override;
  void begin() override;
  void service(unsigned long now_ms) override;
  bool setOutput(bool high) override;
  bool pulseOutput(uint32_t duration_ms) override;

 private:
  const char* id_;
  int pin_;
  bool safe_high_;
  bool pulse_active_;
  unsigned long pulse_end_ms_;
};

#endif  // PINBALLCTL_COIL_COMPONENT_H
