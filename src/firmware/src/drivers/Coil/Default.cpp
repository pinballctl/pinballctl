#include "drivers/Coil/Default.h"

bool CoilDefault::writePin(int pin, bool high) {
  if (pin < 0) return false;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, high ? HIGH : LOW);
  return true;
}
