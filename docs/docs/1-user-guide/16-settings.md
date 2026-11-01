# Settings

Settings contains installation-wide preferences. Project snapshots are managed in [Backup / Restore](25-backup-restore.md).

<img src="./media/screenshot-feature-settings.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Settings feature overview" style="width: 100%;height: auto;">

## Page Structure

Settings has four tabs: **Project**, **Access**, **Firmware**, and **Reporting**.

## Project and Installation Settings

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

## Project backups

Open **Overview and System → Backup / Restore** for complete or selective snapshots, upload/download and replacement restores. The former Settings Import/Export tab is retired. Old unversioned ZIPs are not restored automatically; see the [backup guide](25-backup-restore.md) for policy, migration limits and recovery.

## Related Features

- [Media](18-media.md)
- [Wi-Fi](15-wifi.md)
- [Firmware](12-firmware.md)
