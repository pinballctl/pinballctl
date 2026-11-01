# Modules API Surface

This page lists the current high-level API surface for major modules.

## Core Status/Control

- `dashboard`: runtime/system status payloads.
- `esplink`: bridge/device status, bridge lifecycle, device RPCs, sync status, firmware upload.
- `events`: registry, coverage, fire-event ingress, perf, stream.

## Configuration Modules

- `rules`: catalog, rules CRUD/save, hardware sources, sync + sync status.
- `hardware`: discovered pins/meta, mapping CRUD, mapping sync + sync status.
- `lighting`: state/config save, compile, preview, sync + sync status, fixtures layout.
- `game`: `/api/game/status`, `/api/game/config`, `/api/game/command`; authoritative game/credit/player snapshots and idempotent typed requests.
- `ball`: `/api/ball/status`, `/api/ball/config`, `/api/ball/command`; physical observations, configuration, simulation and operator reconciliation. Both require the existing authenticated app session. Commands require a stable `id`, `command` and typed `params`; never resend an uncertain operation with a different ID.
- `scoring`: config/state/high-scores/history endpoints; per-player scoring under the manager turn context.
- `playfield`: layout state, options, image upload/remove, hardware list.

## Runtime Media/Audio

- `media`: config/state/environment, asset upload/delete/file, play/stop, overlay updates.
- `audio`: config/state/devices, asset upload/delete/preview/file, play/stop.

## Platform/Operations

- `firmware`: local/remote versions, asset download, version removal.
- `logs`: chunked log reads, purge, archive listing.
- `settings`: installation settings read/write (`GET /api/settings/data`, `POST /api/settings/save`). Retired `GET /api/settings/export` and `POST /api/settings/import` return HTTP 410 with a migration message; they do not export or restore data.
- `backups`: project snapshot library, create/upload/download, inventory inspection, replacement preview, restore and progress jobs. See [Backup / Restore](../1-user-guide/25-backup-restore.md) for supported scope and recovery.
- `service`: service-log entry CRUD and attachments.
- `wifi`: status and save.

## Note

For exact route definitions, refer directly to module `api.py` files in:
`src/pinballctl/app/modules/*/api.py`.
