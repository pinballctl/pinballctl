#ifndef PINBALLCTL_COIL_SAFETY_H
#define PINBALLCTL_COIL_SAFETY_H
#include <Arduino.h>
namespace coil_safety {
void begin();
void load();
void loopAlive();
void disable();
bool reserved(int pin);
bool active(int pin);
bool claimPeripheral(int pin);
bool write(int pin, bool on);
bool pulse(int pin, uint32_t duration);
bool mappingSafe(int pin, bool high);
String command(const String& line);
}
#endif
