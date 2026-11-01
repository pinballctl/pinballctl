# Settings

Settings contains installation-wide preferences. Project snapshots are managed in [Backup / Restore](25-backup-restore.md).

<img src="./media/screenshot-feature-settings.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Settings feature overview" style="width: 100%;height: auto;">

## Page Structure

Settings has four tabs: **Project**, **Access**, **Firmware**, and **Reporting**.

## Project

Set the **Project name** used to identify your project. This tab contains project identity only.

## Access

Set the **Admin username** and, when needed, a new **Admin password** for signing in. Leaving the password blank preserves the existing password; entering a new password replaces it when you save. Access credentials remain local and are excluded from project backups.

## Firmware

Set the **Remote firmware URL**, the default remote manifest source used by the firmware tools. Manage firmware versions and installation in the [Firmware module](12-firmware.md). This installation-specific source setting is excluded from project backups.

## Reporting

Choose the **Log level**:

- **Normal** (`INFO`): important status messages and errors.
- **Debug** (`DEBUG`): detailed traffic.
- **Verbose** (`VERBOSE`): full event traffic.

Choose **Currency** (`GBP`, `USD`, `EUR` or `JPY`) for dashboard demo values.

## Save changes

Choose **Save Changes** in the page header after editing a value. The button is disabled when there are no changes or a save is in progress. The browser remembers the last Settings tab you opened.

## Project backups

Open **Overview and System → Backup / Restore** for complete or selective snapshots, upload/download and replacement restores. Settings no longer contains Export, Import or Restore controls. Downloading and uploading archives, previewing replacements and confirming a restore all happen in Backup / Restore. Old unversioned ZIPs are not restored automatically; see the [backup guide](25-backup-restore.md) for policy, migration limits and recovery.

## Related Features

- [Backup / Restore](25-backup-restore.md)
- [Media](18-media.md)
- [Wi-Fi](15-wifi.md)
- [Firmware](12-firmware.md)
