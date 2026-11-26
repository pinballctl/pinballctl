#ifndef PINBALLCTL_COIL_SAFETY_H
#define PINBALLCTL_COIL_SAFETY_H
#include <Arduino.h>
namespace coil_safety {
void begin();
void load();
void loopAlive();
void serviceArming(bool runtime_ready);
bool takeHostTimeout();
void disable();
bool reserved(int pin);
bool active(int pin);
bool claimPeripheral(int pin);
bool write(int pin, bool on);
bool testPulse(int pin);
bool pulse(int pin, uint32_t duration);
bool mappingSafe(int pin);
void setMappingCoils(const int8_t* off_levels, size_t count);
}
#endif
