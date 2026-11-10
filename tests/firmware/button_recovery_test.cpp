#include <cassert>
#include "drivers/Button/Default.h"
int button_level=HIGH;
int button_mode=0;
namespace coil_safety { bool claimPeripheral(int) { return true; } }
int main() {
  for (int idle : {LOW, HIGH}) {
    ButtonDefault::Instance explicit_button;
    explicit_button.bindPin(10);
    explicit_button.setIdleLevel(idle);
    std::vector<ButtonDefault::Event> events;
    button_level = idle;
    explicit_button.service(0, &events);
    assert(button_mode == (idle == LOW ? INPUT_PULLDOWN : INPUT_PULLUP));
    assert(events.empty());
    button_level = !idle;
    explicit_button.service(1, &events);
    explicit_button.service(10, &events);
    assert(events.size() == 1 && events[0].type == ButtonDefault::EventType::PRESSED);
    assert(explicit_button.active());
  }
  button_level = HIGH;
  ButtonDefault::Instance button;
  ButtonDefault::Config config;
  config.enable_double_click=true;
  config.held_thresholds_ms={50}; config.repeat_intervals_ms={20};
  button.bindPin(1); button.configure(config);
  std::vector<ButtonDefault::Event> events;
  button.service(0,&events);
  button_level=0; button.service(1,&events); button.service(10,&events);
  assert(button.active()); assert(events.size()==1);
  button.cancelGestures(); events.clear();
  button.service(1000,&events); assert(events.empty());
  button_level=HIGH; button.service(1001,&events); button.service(1010,&events);
  assert(events.size()==1 && events[0].type==ButtonDefault::EventType::RELEASED);
  events.clear(); button.service(2000,&events); assert(events.empty());
  // A new press works normally; the electrical idle level was preserved.
  button_level=0; button.service(2001,&events); button.service(2010,&events);
  assert(events.size()==1 && events[0].type==ButtonDefault::EventType::PRESSED);
  events.clear(); button.service(2070,&events); assert(!events.empty());
  // Pending delayed clicks are also cancelled.
  button_level=HIGH; button.service(2080,&events); button.service(2090,&events);
  button_level=0; button.service(2100,&events); button.service(2110,&events);
  button_level=HIGH; button.service(2111,&events); button.service(2120,&events);
  button.cancelGestures(); events.clear(); button.service(3000,&events); assert(events.empty());
}
