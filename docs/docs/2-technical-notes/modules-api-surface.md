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
- `scoring`: config/state/high-scores/history endpoints.
- `playfield`: layout state, options, image upload/remove, hardware list.

## Runtime Media/Audio

- `media`: config/state/environment, asset upload/delete/file, play/stop, overlay updates.
- `audio`: config/state/devices, asset upload/delete/preview/file, play/stop.

## Platform/Operations

- `firmware`: local/remote versions, asset download, version removal.
- `logs`: chunked log reads, purge, archive listing.
- `settings`: settings read/write, project export/import.
- `service`: service-log entry CRUD and attachments.
- `wifi`: status and save.

## Note

For exact route definitions, refer directly to module `api.py` files in:
`src/pinballctl/app/modules/*/api.py`.
