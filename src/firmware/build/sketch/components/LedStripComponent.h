#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/components/LedStripComponent.h"
#ifndef PINBALLCTL_LED_STRIP_COMPONENT_H
#define PINBALLCTL_LED_STRIP_COMPONENT_H

#include "components/Component.h"
#include "components/ComponentInterfaces.h"

class LedStripComponent : public Component, public Actuator {
 public:
  LedStripComponent(const char* comp_id, int pin);
  const char* id() const override;
  void begin() override;
  void service(unsigned long now_ms) override;
  bool setOutput(bool high) override;
  bool pulseOutput(uint32_t duration_ms) override;

 private:
  const char* id_;
  int pin_;
};

#endif  // PINBALLCTL_LED_STRIP_COMPONENT_H
