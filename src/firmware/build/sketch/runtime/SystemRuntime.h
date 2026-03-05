#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/runtime/SystemRuntime.h"
#ifndef PINBALLCTL_SYSTEM_RUNTIME_H
#define PINBALLCTL_SYSTEM_RUNTIME_H

#include <Arduino.h>

class SystemRuntime {
 public:
  bool syncTimeEpoch(long epoch);
};

#endif  // PINBALLCTL_SYSTEM_RUNTIME_H
