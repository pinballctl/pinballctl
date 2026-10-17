#include "safety/CoilSafety.h"
#include "drivers/Coil/Default.h"

bool CoilDefault::writePin(int pin, bool high) {
  return coil_safety::write(pin, high);
}
