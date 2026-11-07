# Settings

Settings holds the project name, application login, firmware source, and reporting preferences. Manage project archives separately in Backup / Restore.

## At a glance

**Project**. Set the project name.

**Access**. Set the web sign-in credentials.

**Firmware**. Set the remote manifest source.

**Reporting**. Choose the log level and display currency.

## Before you start

Sign in with permission to change installation settings. Know how to recover access before changing credentials or networking.

## Change and verify a preference

1. Open **Settings** and choose **Project**, **Access**, **Firmware** or **Reporting**. **Expected:** the relevant fields appear without any legacy archive controls.

2. Edit the required value. Leave the password blank to preserve it, or enter a new password to replace it. **Expected:** Save Changes becomes available when an edit exists.

3. Choose **Save Changes** and read the result. Reopen the tab to verify the saved value; for credentials, verify a fresh login. **Expected:** the intended preference persists.

4. To export, upload or restore a project, open **Overview and System → Backup / Restore**. **Expected:** archives are managed separately from installation preferences.

<img src="./media/screenshot-feature-settings.webp" data-source='{"url":"/login","next_url":"/settings","dark_mode":true,"settle_ms":320,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Settings feature overview" style="width: 100%;height: auto;">

1. The four tabs separate preference types. 2. Project contains the project name. 3. Save Changes persists edits; archive operations are in another module.

## Check the result

A changed Pi login is not a changed application login. Protected credentials and host settings remain local during project restores.

**Safety:** Keep credentials out of screenshots, backup comments and user-authored project text. Do not expose the HTTP interface on an untrusted network without transport protection.

## Troubleshooting

If Save Changes is disabled, check whether a value actually changed. For a failed save, preserve the reported error and check service access to its data directory. For lost access, inspect configured environment/saved credentials rather than resetting arbitrary files.

## Related guides

Next: [Backup / Restore](25-backup-restore.md), [Wi-Fi](15-wifi.md), [Firmware](12-firmware.md).

## Settings tabs

### Page Structure

Settings has four tabs: **Project**, **Access**, **Firmware**, and **Reporting**.

### Project

Set the **Project name** used to identify your project. This tab contains project identity only.

### Access

Set the **Admin username** and, when needed, a new **Admin password** for signing in. Leaving the password blank preserves the existing password; entering a new password replaces it when you save. Access credentials remain local and are excluded from project backups.

### Firmware

Set the **Remote firmware URL**, the default remote manifest source used by the firmware tools. Manage firmware versions and installation in the [Firmware module](12-firmware.md). This installation-specific source setting is excluded from project backups.

### Reporting

Choose the **Log level**:

- **Normal** (`INFO`): important status messages and errors.
- **Debug** (`DEBUG`): detailed traffic.
- **Verbose** (`VERBOSE`): full event traffic.

Choose **Currency** (`GBP`, `USD`, `EUR` or `JPY`) for dashboard demo values.

### Save changes

Choose **Save Changes** in the page header after editing a value. The button is disabled when there are no changes or a save is in progress. The browser remembers the last Settings tab you opened.

### Project backups

Open **Overview and System → Backup / Restore** for complete or selective snapshots, upload/download and replacement restores. Settings no longer contains Export, Import or Restore controls. Downloading and uploading archives, previewing replacements and confirming a restore all happen in Backup / Restore. Old unversioned ZIPs are not restored automatically; see the [backup guide](25-backup-restore.md) for policy, migration limits and recovery.

## Related Features

- [Backup / Restore](25-backup-restore.md)
- [Media](18-media.md)
- [Wi-Fi](15-wifi.md)
- [Firmware](12-firmware.md)
