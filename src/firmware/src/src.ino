#include <Arduino.h>

// Entry points implemented in app.cpp
void appSetup();
void appLoop();

void setup() {
  appSetup();
}

void loop() {
  appLoop();
}
