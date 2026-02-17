// app.cpp: minimal entry points delegating to System.

#include "System.h"

static System SYS;

void appSetup() {
  SYS.setup();
}

void appLoop() {
  SYS.loop();
}
