#ifndef PINBALLCTL_RULE_ACTION_GUARD_H
#define PINBALLCTL_RULE_ACTION_GUARD_H
#include <stdint.h>

namespace rule_action_guard {
// Decisions from the Pi expire; unsigned subtraction is safe over millis wrap.
inline bool accept(uint32_t now, uint32_t triggered, bool has_timestamp,
                   bool paused, bool blocked, bool needs_fresh_input,
                   bool requires_active_input, bool input_active) {
  return has_timestamp && uint32_t(now - triggered) <= 250 && !paused &&
         !blocked && !needs_fresh_input && (!requires_active_input || input_active);
}
}
#endif
