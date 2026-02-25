#include "runtime/SystemRuntime.h"

#include <sys/time.h>

bool SystemRuntime::syncTimeEpoch(long epoch) {
  if (epoch <= 0) return false;
  struct timeval tv;
  tv.tv_sec = epoch;
  tv.tv_usec = 0;
  settimeofday(&tv, nullptr);
  return true;
}
