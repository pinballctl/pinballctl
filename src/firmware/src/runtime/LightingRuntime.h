#ifndef PINBALLCTL_LIGHTING_RUNTIME_H
#define PINBALLCTL_LIGHTING_RUNTIME_H

#include <Arduino.h>

class LightingRuntime {
 public:
  bool loadFromLightingBlob(const char* path, String* error);
  bool playScene(const String& scene_id, String* reason = nullptr);
  bool stopScene(const String& scene_id);
 void clear();

 private:
  bool loaded_ = false;
};

#endif  // PINBALLCTL_LIGHTING_RUNTIME_H
