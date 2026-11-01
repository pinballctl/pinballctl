# Backup / Restore

Open **Overview and System → Backup / Restore** to save and restore project snapshots. This replaces the old Settings Import/Export tab. Settings still contains Project, Access, Firmware and Reporting preferences.

<img src="./media/screenshot-feature-backups.webp" data-source='{"url":"/login","next_url":"/backups/","dark_mode":true,"settle_ms":600,"click":[{"action":"type","selector":"input[name=\"username\"]"},{"action":"type","selector":"input[name=\"password\"]"},{"action":"click","selector":"button[type=\"submit\"]","wait_for":"[data-menu-toggle]"}]}' alt="Backup / Restore library in the application" style="width:100%;height:auto;">

The library lists backups newest first with date/time, scope, size and comment. Search by project, scope or comment; sort by date, size or comment. **View** shows a summary with archive size, file count and compatibility, followed by project metadata and a searchable file table. Each row shows its path, component and size; expand SHA-256 to inspect the full checksum. **Download** returns the original archive. **Delete** removes that backup only, after confirmation; it never deletes current project data. Invalid archives are reported by the library diagnostics instead of being offered for restore.

## Create and upload

Choose **Backup** to open the standard sidebar. Select **Everything** or specific components, optionally add a comment, then create the snapshot. Progress is shown while files are captured and compressed. Each chosen component is a **complete snapshot**, not an incremental delta. A Rules/Lighting snapshot leaves large Media and Audio assets out of the archive.

Create backups between games: project updates pause while a consistent snapshot is captured. SQLite data uses SQLite's backup API rather than copying a live database file. Large full backups can take time and disk space. The current archive limit is 8 GiB compressed and uncompressed, 4 GiB per file, 20,000 entries, with bounded ZIP expansion; configuration JSON is limited to 16 MiB. Keep enough free space for staging, the archive and recovery copies.

**Upload** accepts a versioned Backup / Restore ZIP, validates its paths, ownership, format, inventory, sizes and checksums, and adds it to the local library. Upload never restores anything. Progress distinguishes upload from archive validation. Project, scope, timestamp and comment come from the uploaded manifest.

Archives are stored outside the instance directory, normally `~/.local/share/pinballctl/backups/` (or the XDG data directory). A service administrator may set `PINBALLCTL_BACKUP_DIR` to another dedicated directory outside the instance. This location survives application upgrades and is never included recursively in backups. The application/service user needs read/write access. These archives are not encrypted: protect the storage location and downloaded copies.

<img src="./media/screenshot-backup-create.webp" data-source='{"url": "/login", "next_url": "/backups/", "dark_mode": true, "settle_ms": 700, "click": [{"action": "type", "selector": "input[name=\"username\"]"}, {"action": "type", "selector": "input[name=\"password\"]"}, {"action": "click", "selector": "button[type=\"submit\"]", "wait_for": "[data-menu-toggle]"}], "next_click": [{"action": "click", "selector": "#backup-create", "wait_for": "#backup-comment"}]}' alt="Create Backup sidebar with complete component selection" style="width:100%;height:auto;">

## What a component owns

| Component | Complete snapshot content |
| --- | --- |
| Rules | Rules files, compiled artifacts and persistent SQLite flags/counters; volatile logs and authoring locks excluded |
| Scoring | Scoring configuration except Combos, plus high scores and game history |
| Combos | The entire `combos` collection inside the shared Scoring configuration |
| Lighting | Lighting configuration and derived artifacts |
| Hardware | Hardware mapping/discovery and accelerometer calibration |
| Playfield | Layout and playfield images/assets |
| Media | Scene/asset configuration, assets, fonts and uploaded Godot scenes; display records excluded |
| Displays | Display records and their project settings in the shared Media configuration |
| Audio | Cue/asset configuration and audio assets |
| Settings | Public project name, log level and currency only |
| Service | Service history and attachments |
| User wizards | User-installed JSON wizard definitions |

Scoring/Combos and Media/Displays are logical partitions of shared files. Restoring one replaces its records while preserving the unselected sibling records; this is **not** a merge within a selected component. The replacement preview lists removed logical record IDs as well as file paths. Derived Rules, Hardware and Lighting artifacts are rebuilt before live publication; restore never syncs them to the ESP.

## Secret and transient-data policy

Credentials, password hashes, authentication identity, session/signing keys, Wi-Fi credentials, remote firmware-source settings, host executable paths and runtime ports stay local. Public archives exclude those settings, browser profiles/cookies, active playback/game state, command queues, logs, caches, firmware downloads and host/system files. Godot's host binary and port are preserved even when restoring Displays. Comments and arbitrary user-authored project text are not scanned for secrets: do not put credentials in them.

Persistent rule flags and counters **are** backed up; temporary current-game scoring/playback state is not. A full backup means all supported managed project components above, not a disk image or host operating-system backup. Unknown files outside managed component ownership remain untouched, including when removing other project content.

## Replacement restore

1. Choose **Restore** on a backup.
2. Select any subset of components included in that backup.
3. Keep **Remove all other project content** off for a normal selective restore.
4. Preview the exact replacement/deletion inventory and dependency checks.
5. Stop Audio and Media/display playback. The confirmed restore manages the bridge automatically.
6. Type **REPLACE**, then choose Restore.

Every selected component is replaced **completely**. Current files or records belonging to that component that are absent from its snapshot are removed. There is no merge mode. Unselected components are unchanged by default. Restoring Rules from a full backup does not replace Media, Audio or Lighting.

The optional **Remove all other project content** checkbox is destructive and off by default. It additionally clears every other supported managed component. The preview identifies those deletions; confirmation requires typing **REMOVE OTHER CONTENT**. Backups, protected settings, browser/host files and system installation remain outside this managed deletion scope. If the resulting project would contain broken references, the operation is blocked rather than silently producing an invalid project.

### Full baseline plus frequent partial snapshots

Keep an occasional **Everything** backup with your large Media/Audio library, and take frequent small **Rules + Lighting** snapshots. Restore the full backup first. Once it completes, select Restore on a newer partial backup and restore its components. Each archive is previewed, confirmed and restored separately.

The component selector groups scoring configuration, score history and combos under **Scoring**. Older archives containing only one scoring partition remain supported and explicitly show **Scoring (without combos)** or **Scoring (combos only)**.

## Maintenance, recovery and limits

After confirmation, Restore automatically stops a running bridge, including offline reconnect loops, and restarts it after successful publication using its previous serial port and baud rate. An already stopped bridge stays stopped. There is no separate Pause Bridge step. Startup settings must be identifiable before anything is stopped; otherwise restore is cancelled. Concurrent restore operations cannot manage the bridge simultaneously.

Use the existing Audio/Media runtime controls to stop playback before restoring. Restore never arms coils or syncs configuration to the ESP. Review configuration and sync deliberately afterwards; existing ESP arming, watchdog and coil safety gates continue to apply. Other running web/runtime services may still need a reload.

If restore fails, the bridge stays stopped so recovery can finish safely. If the restore succeeds but bridge restart fails, the error explicitly says the data was restored, includes the recovery backup reference, and asks for a manual bridge start. An interrupted web worker or machine cannot automatically resume this lifecycle: finish recovery and start the bridge manually. Physical Pi/ESP service lifecycle and reconnect tests remain required.

Preview tokens expire after 30 minutes. A changed project, archive or selected reference requires a new preview. Restores use a cross-process access barrier, a durable journal and a generation marker that invalidates the selected component caches in each process on its next access; backups and restore progress remain accessible while ordinary project requests wait. An automatic pre-restore recovery backup is saved before live changes. On an ordinary publication error the previous files are restored; the recovery archive remains in the library with an automatic-recovery comment.

If a worker or machine stops during publication, project access is blocked by a recovery marker. Reload the web service, with bridge/playback stopped, to apply pending journal rollback before normal operation. Keep the backup directory and recovery journal available until recovery completes. If storage fails during rollback itself, stop services and preserve the journal for recovery rather than restarting gameplay. Recovery directories can temporarily contain private copies of protected settings; they are under the private backup store and are never downloadable as an archive.

The barrier covers the application, bridge, rule/scoring event handlers and supported media/audio operations in this version. Third-party scripts or older running processes that directly modify instance files do not participate: stop them before snapshot/restore, and deploy/restart all application processes together when upgrading. This is a maintenance workflow, not hot restore during gameplay. Physical Pi/ESP power-loss, filesystem-failure and service-lifecycle tests remain necessary on the target installation; desktop tests cannot verify coil or external-device behaviour.

Legacy unversioned Settings ZIPs are rejected. The retired Settings import/export endpoints return an explicit migration message; they cannot prove component ownership, complete replacement or secret exclusion. Keep those archives, inspect them offline and migrate their supported configuration through the relevant module into a new versioned backup. There is no automatic legacy extraction into a live project.
