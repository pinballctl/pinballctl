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

Status refreshes in the background about every 5 seconds. Only the status fields update; the page and any unsaved form entries stay in place.

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

On Raspberry Pi OS/Linux with NetworkManager, Save Changes submits the network name and password to NetworkManager and attempts to activate the connection. NetworkManager stores the profile for later connections, including after reboot. A success response means NetworkManager reported activation; it does not guarantee Internet access.

Use a WPA/WPA2 personal network password (8–63 characters or 64 hexadecimal digits). Leave the password blank only for an open network. Enterprise authentication, captive-portal sign-in and hidden-network setup are not provided by this form. macOS and Linux installations without `nmcli` return an unsupported/unavailable error without changing the network.

Changing networks may disconnect your browser or change the Pi address before a response arrives. A browser error or timeout therefore does not prove the change failed. Check the Pi locally or over Ethernet and reconnect at its current address before retrying. Keep local console or Ethernet access available when changing a headless machine's connection. Existing profiles are managed by NetworkManager; this feature does not delete them or guarantee rollback after a failed activation.

### Service permissions

Install and run NetworkManager and its `nmcli` client. The account running `pinball.service` must be authorized by NetworkManager/Polkit to control networking and modify system connection profiles without an interactive authorization prompt. Check `nmcli general permissions` as that service account; headless service permissions can differ from those of a logged-in desktop user. Ask the system administrator to grant only the required NetworkManager actions to the service account. Pinball CTL does not install broad sudo access or change system authorization automatically.

Credentials are passed directly to `nmcli` without a shell and are not returned in API responses or logged by the application. They may be visible to privileged local process inspection while the command runs, and NetworkManager stores them using its normal protected system profile storage. Use a trusted local network for the web interface, or configure HTTPS before sending credentials across an untrusted network.

## Practical Example

1. Keep console or Ethernet access available.
2. Enter the new network name and personal-network password, then save.
3. Check the reported result and actual network status. If the browser disconnects, find the Pi's current address locally and reopen Pinball CTL.
4. Verify reconnection after reboot on the target Pi before relying on unattended operation.

## Related Features

- [Dashboard](5-dashboard.md)
- [Settings](16-settings.md)
