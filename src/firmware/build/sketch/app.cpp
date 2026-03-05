#line 1 "/Users/andy/Repositories/other/pinballctl/src/firmware/src/app.cpp"
// app.cpp: minimal entry points delegating to System.

#include "System.h"

static System SYS;

void appSetup() {
  SYS.setup();
}

void appLoop() {
  SYS.loop();
}
