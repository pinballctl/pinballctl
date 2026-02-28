#include "drivers/LED/Default.h"

bool LedDefault::writePin(int pin, bool high) {
  if (pin < 0) return false;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, high ? HIGH : LOW);
  return true;
}
