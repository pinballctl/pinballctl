#pragma once

// --- Pin + timing configuration for the heartbeat sketch ---
#ifndef LED_PIN
#define LED_PIN 32          // Onboard LED on most ESP32-S3 dev boards (GPIO 2)
#endif

#ifndef BLINK_MS
#define BLINK_MS 100       // Duration of each quick blink (ms)
#endif

#ifndef GAP_MS
#define GAP_MS 5000        // Pause after two blinks (ms)
#endif
