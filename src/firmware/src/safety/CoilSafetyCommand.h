#ifndef PINBALLCTL_COIL_SAFETY_COMMAND_H
#define PINBALLCTL_COIL_SAFETY_COMMAND_H

#include <Arduino.h>
#include <ArduinoJson.h>

namespace coil_safety {

// Populate a fresh response document when the parsed request is a coil command.
bool command(JsonVariantConst request, JsonDocument& response);

}  // namespace coil_safety

#endif  // PINBALLCTL_COIL_SAFETY_COMMAND_H
