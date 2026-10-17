# Wi-Fi

Wi-Fi is the feature for viewing and updating network connection settings.

<img src="./media/screenshot-feature-wifi.webp" data-source='{"url":"/login","next_url":"/wifi","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Wi-Fi feature overview" style="width: 100%;height: auto;">

## What This Feature Does

It shows live network state and lets you update SSID/password from the web interface.

## Current Status Card

Displays:

- SSID
- IP
- State
- Connected badge (`Yes`/`No`)

Status refreshes regularly (about every 5 seconds).

## Update Settings Form

Fields:

- SSID (required)
- Password

Actions:

- `Save`

UI feedback:

- saving spinner
- success message
- error alert if save fails

## Save Behaviour

Saves are submitted to Wi-Fi API and status refresh is triggered after successful update.

Use this for first setup changes or network migration.

## Planned Capability

Planned: Wi-Fi connected services will provide support for global leaderboards.

## Practical Examples

### Move machine to new venue network

1. Enter new SSID/password.
2. Save.
3. Confirm new IP and connected badge.

### Verify remote support readiness

Confirm connected badge and IP before remote browser/API operations.

## Related Features

- [Dashboard](5-dashboard.md)
- [Settings](16-settings.md)
