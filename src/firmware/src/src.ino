#include <Arduino.h>
#include "conf.h"

// Forward declarations implemented in ../main.cpp
void appSetup();
void appLoop();

void setup() {
  appSetup();
}

void loop() {
  appLoop();
}
