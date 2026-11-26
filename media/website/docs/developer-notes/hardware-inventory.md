# Hardware inventory

This is a snapshot of the project machine's saved hardware mapping on **10 November 2026**, from `src/instance/hardware/mapping.json`. It records configured assignments, not a live hardware discovery or verification of physical wiring. These GPIO assignments are specific to this machine, not a recommended pinout for other builds.

## Mapped components

| Component | ESP GPIO | Type | What it does |
|---|---|---|---|
| Drain Switch | 1 | Switch input | Detects a ball entering the drain. |
| Launch Button LED | 2 | LED output | Illuminates the launch button. |
| LCD Display | 3 SCL, 8 SDA | 16×2 I²C display | Shows text and status; address `0x27`, backlight timeout 30 seconds. |
| Shooter Lane Switch | 4 | Switch input | Detects a ball in the shooter lane. |
| Status RGB | 5 | 6-pixel RGB strip | Provides coloured status indications. |
| Left Flipper Coil | 6 | Coil output | Assigned to the left flipper; disabled, configured for pulse-only operation. |
| Right Flipper Coil | 7 | Coil output | Assigned to the right flipper; disabled, configured for pulse-only operation. |
| On Table Lights | 9 | 12-pixel RGB strip | Provides addressable lighting on the table. |
| Playfield Entry Switch | 10 | Switch input | Detects the ball entering the playfield. |
| Lock Switch | 11 | Switch input | Detects a ball at the lock position. |
| Left Playfield RGB | 12 | 120-pixel RGB strip | Provides addressable lighting along the left playfield. |
| Left Ramp Switch | 13 | Switch input | Detects a ball passing the left ramp switch. |
| Start Button LED | 14 | LED output | Illuminates the start button. |
| Right Orbit Switch | 15 | Switch input | Detects a ball passing the right orbit switch. |
| Standup Target | 16 | Switch input | Registers a standup target hit. |
| Pop Bumper 1 | 17 | Switch input | Registers a bumper hit; repurposes the former Jackpot Target input. |
| Skill Shot Target | 21 | Switch input | Registers a hit on the designated skill-shot target. |
| Left Flipper Button | 37 | Button input | Receives the player's left-flipper input. |
| Right Flipper Button | 38 | Button input | Receives the player's right-flipper input. |
| Launch Button | 39 | Button input | Receives the player's launch request. |
| Accelerometer | 40 SDA, 41 SCL | MMA8452 / GY-45 | Detects nudges and table lifting; address `0x1c`, configured for inverted mounting. |
| Start Button | 42 | Button input | Receives the player's start-game request. |
| Pop Bumper 2 | 47 | Switch input | Registers a hit on the second pop bumper. |
| Pop Bumper 3 | 48 | Switch input | Registers a hit on the third pop bumper. |

**Total: 24 mapped components** — 15 buttons/switches, 2 individual LEDs, 3 RGB strips containing 138 pixels, 2 coils, 1 LCD and 1 accelerometer. Each paired I²C device is counted once. Unassigned and reserved pins are excluded.

## Configuration notes

- Updated on 10 November 2026 to replace Jackpot Target with Pop Bumper 1 and bind Pop Bumpers 2 and 3 to previously unassigned GPIO 47 and 48. These assignments use the saved discovery metadata; actual board wiring must match. The local mapping blob was rebuilt but not deployed. Older scoring/jackpot rules referencing a previous controller ID were preserved and require separate reconciliation.

- All button/switch inputs use **LOW idle / HIGH active**, except the Drain Switch, which uses **AUTO**.
- Both coils are disabled in this snapshot. Their configured pulse is 10 ms, hard pulse limit 20 ms, minimum off-time 1,000 ms, and safe output level LOW. These settings are a record, not validated recommendations for the physical coils.
- Status RGB uses the Default (FastLED) driver. On Table Lights and Left Playfield RGB use NeoPixel.
- Scoring, launch actions and lighting effects depend on the configured rules and scenes; the descriptions above reflect the assigned component names.
- This page is maintained manually. Update the snapshot date, table and totals when the machine's mapping changes. Saving this inventory does not change or deploy the hardware configuration.

See [Hardware](../user-guide/hardware.md) for mapping, deployment and safety guidance.

## Hardware Test design

The Hardware module separates the configured default from live wiring checks. The Test tab uses driver capabilities declared by the ESP and resolves commands against the applied mapping. A browser event can simulate a gameplay input, but only an ESP measurement can verify a physical switch changed level. Output tests call the mapped driver directly and use the same firmware limits as normal operation.

The ESP samples mapped inputs while the test session is active and counts observed edges before sending a browser status update. This keeps short hits visible after a switch returns to idle. While the tab is visible, the browser requests live status every 200 ms and retries an unavailable session after two seconds. The session expires after 1.6 seconds without a status request, and holds have a shorter lease. The test path adds no GPIO sampling after the session ends.

ESP32-S3 compilation and browser checks with a simulated controller verify the software paths. Physical switch capture, installed-driver behaviour and timing still need bench validation with the real controller and wiring.
