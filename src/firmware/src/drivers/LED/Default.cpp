#include "safety/CoilSafety.h"
#include "drivers/LED/Default.h"

bool LedDefault::writePin(int pin, bool high) {
  if (!coil_safety::claimPeripheral(pin)) return false;
  pinMode(pin, OUTPUT);
  digitalWrite(pin, high ? HIGH : LOW);
  return true;
}
