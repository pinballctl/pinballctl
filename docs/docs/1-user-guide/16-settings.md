# Settings

Settings is the feature for installation-wide configuration and project data transfer.

<img src="./media/screenshot-feature-settings.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Settings feature overview" style="width: 100%;height: auto;">

## Page Structure

Settings has two tabs:

1. `Settings`
2. `Import/Export`

## Settings Tab

<img src="./media/screenshot-feature-settings-settings.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Settings tab overview" style="width: 100%;height: auto;">

Use this tab to manage persistent system values.

Main fields:

- project name
- admin username
- admin password
- remote firmware URL
- log level (`INFO`, `DEBUG`, `VERBOSE`)
- currency (`GBP`, `USD`, `EUR`, `JPY`)
- `Start displays on service startup`

Top action:

- `Save Changes`

Password behavior:

- blank password does not overwrite existing password
- non-empty password replaces admin password

## Import/Export Tab

<img src="./media/screenshot-feature-settings-import-export.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Import and export tab overview" style="width: 100%;height: auto;">

Use this tab to move project data between installations.

### Export project

- downloads a bundle of `src/instance`
- filename includes project name and timestamp
- status text shows progress/completion
- action: `Export`

### Import project

- uploads a bundled project export (`.zip`)
- existing files in `src/instance` are overwritten when present
- confirmation is required before import
- status text shows upload result
- controls: file chooser + `Import`

## Typical Workflow

1. Update values in `Settings`.
2. Click `Save Changes`.
3. Use `Import/Export` for backup, restore, or migration.

## Related Features

- [Media](18-media.md)
- [Wi-Fi](15-wifi.md)
- [Firmware](12-firmware.md)
