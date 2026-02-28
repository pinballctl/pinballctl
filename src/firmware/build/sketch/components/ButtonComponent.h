#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/components/ButtonComponent.h"
#ifndef PINBALLCTL_BUTTON_COMPONENT_H
#define PINBALLCTL_BUTTON_COMPONENT_H

#include "components/Component.h"
#include "components/ComponentInterfaces.h"

class ButtonComponent : public Component, public EventSource {
 public:
  ButtonComponent(const char* comp_id, int pin);
  const char* id() const override;
  void begin() override;
  void service(unsigned long now_ms) override;
  bool readEvent(ComponentEvent* out_event) override;

 private:
  const char* id_;
  int pin_;
  bool last_state_high_;
  bool event_pending_;
  ComponentEvent pending_event_;
};

#endif  // PINBALLCTL_BUTTON_COMPONENT_H
