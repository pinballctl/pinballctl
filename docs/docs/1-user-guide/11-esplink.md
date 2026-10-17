# ESPLink

ESPLink manages Pi-to-ESP connectivity, bridge control, firmware apply flow, and runtime utility actions.

<img src="./media/screenshot-feature-esplink.webp" data-source='{"url":"/login","next_url":"/esplink","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="ESPLink feature overview" style="width: 100%;height: auto;">

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

<img src="./media/screenshot-feature-esplink-file-list-modal.webp" data-source='{"url":"/login","next_url":"/esplink","dark_mode":true,"settle_ms":420,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}],"next_click":[{"action":"click","selector":"#esp-fs-list","wait_for":"#esp-fs-list-modal.show"},{"action":"wait","selector":"#esp-fs-list-modal.show","timeout_ms":2000}],"target":"#esplink-root"}' alt="ESPLink file list modal open" style="width: 100%;height: auto;">

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

- [Hardware](10-hardware.md)
- [Firmware](12-firmware.md)
- [Logs](14-logs.md)
