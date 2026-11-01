# ESPLink

Check the connection between your Pi and the controller handling real-time I/O. Confirm identity and live communication before deploying configuration or applying firmware.

## Before you start

Have the Pi application running, an ESP32-S3 and a USB data cable. Keep output power disconnected for connection, reboot and firmware work.

## Try it step by step

1. Connect the controller and open **ESPLink**. Refresh/select the intended device where available. **Expected:** a live connected device and serial port, not cached identity alone.

2. Inspect firmware/chip information and bridge status. **Expected:** the intended controller is identified; investigate missing or mismatched information before sync.

3. Use **Echo Test** for a communication check, or **FS Status** / **List Files** to inspect supported filesystem results. **Expected:** a result or explicit error; timeout is not success.

4. If the bridge is stopped, use its Start control and recheck status. Restart only during maintenance. **Expected:** live status resumes after the controller reconnects.

5. For a firmware change, download the intended image through Firmware, then follow local apply and watch the console. **Expected:** completion followed by reconnected version/identity checks.

<img src="./media/screenshot-feature-esplink.webp" data-source='{"url":"/login","next_url":"/esplink","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="ESPLink feature overview" style="width: 100%;height: auto;">

**Screen guide:** 1. Connection state establishes live access. 2. Port/chip/version identify the device. 3. Utility results and upload console provide evidence of each operation.

## Helpful checks

Distinguish the bridge process being Running from the ESP actually being Connected. The UI can retain last-known metadata after disconnect.

**Safety:** Reboot, restart and flashing interrupt runtime. Stop gameplay/playback and remove load power first; do not use reconnects to bypass a latched fault or re-enable requirement.

## If the result is different

If no device appears, check data cable, port, permissions and bridge logs. If a utility times out, preserve its error and inspect the connection. If flash fails, use the hardware-specific recovery process rather than repeatedly applying an unknown image.

## Continue your build

Next: [Firmware](12-firmware.md), [Hardware](7-hardware.md), [Logs](14-logs.md).

## Detailed reference

The sections below explain the controls and behaviour used in this workflow.

## What This Feature Does

ESPLink provides the operational control layer between authored configuration and live ESP runtime.

Key responsibilities:

- device selection
- bridge lifecycle control
- status/identity visibility
- utility actions (FS, echo, reboot)
- applying downloaded firmware to connected ESP

## Header Controls

- device dropdown (`Select device…`)
- connection status dot/text
- firmware readout
- `Refresh`
- `Reboot`
- `Sync Time`

Button availability depends on selected/connected device state.

## No-Device State

When no ESP devices are available, a dedicated card explains that USB connection is required.

## Overview Card

Displays:

- Port
- Chip
- IP
- RSSI

Bridge section displays:

- Bridge Status
- Bridge Port
- Bridge Firmware
- Bridge Chip

Bridge actions:

- `Start`
- `Stop`
- `Restart`

## Actions Card

Operational tools:

- `FS Status`
- `List Files`
- `Reboot ESP`
- `Echo Test`

Each action opens a result modal.

Available result modals:

- FS Status modal
- File List modal
- Echo Test modal
- Reboot ESP modal

<img src="./media/screenshot-feature-esplink-file-list-modal.webp" data-source='{"url":"/login","next_url":"/esplink","dark_mode":true,"settle_ms":1100,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"wait","selector":"#esp-device:has(option:not([value=\"\"]):checked)","timeout_ms":15000},{"action":"click","selector":"#esp-fs-list","wait_for":"#esp-fs-list-modal.show"},{"action":"wait","selector":"#esp-fs-list-modal.show","timeout_ms":2000}],"target":"#esplink-root"}' alt="ESPLink file list modal open" style="width: 100%;height: auto;">

## Firmware Card (Local Apply)

Purpose: apply locally downloaded firmware to connected ESP.

List behaviour:

- shows locally available versions
- displays `Latest` and `Current` badges where relevant
- apply action per version
- upload console with progress/log output

## Compatibility and Confidence Checks

ESPLink helps ensure safe rollout by exposing:

- bridge running state
- device presence
- live firmware/chip info
- clear checks that Pi and ESP are on matching versions and manifest data before deployment

## Typical Workflow

1. Select target ESP device.
2. Confirm status dot and overview data.
3. Start/restart bridge if needed.
4. Use Sync Time and utility checks.
5. Apply firmware if required.
6. Continue with hardware/rules/lighting sync actions.

## Practical Examples

### Recovery after USB reconnect

- press Refresh
- if bridge stopped, Start bridge
- verify chip/firmware visible again

### Pre-sync validation

- ensure connected status is green
- run Echo Test quickly
- check FS/list outputs if needed

## Related Features

- [Hardware](7-hardware.md)
- [Firmware](12-firmware.md)
- [Logs](14-logs.md)


## Connection status and cached details

USB discovery, a running bridge and a responsive ESP are different states. The connection indicator reports whether the ESP is responding. When communication is lost, previously received device details may remain visible; the page labels the firmware as last known and explains that the details are cached.

If USB is detected but the ESP is not responding, try restarting the bridge. If it still does not reconnect, check the USB connection and reset the ESP.

## Filesystem and communication checks

**FS Status** shows filesystem type, mount status, used/free capacity, a storage usage bar and whether the rules directory is available. Sizes are shown in readable units.

**Echo Test** sends a communication check through the bridge. The result confirms whether the ESP replied, identifies the device port and explains any failure. This does not activate outputs.
