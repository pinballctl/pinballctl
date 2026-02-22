# Changelog

All notable changes to this project will be documented in this file.

---

## [v0.2.0] - 2026-02-22
### Added
- Media overlay placeholders now ingest live scoring values (including score/player/game state data paths used by media runtime).

### Changed
- Media runtime and stage rendering behaviour updated for more consistent preview/runtime parity and improved scaling behavior.
- UI action language standardised across modules to use trash icon + `Remove` wording for destructive actions.
- App shell and module styling updates across core, playfield, lighting, audio, service, scoring, and media screens.
- Dashboard and media module integrations updated to improve runtime status/reporting flows.

### Fixed
- Light-theme top menu rendering bug in the app shell.
- Media runtime reporting issues.
- Additional bug fixes in dashboard/media flows and runtime display behaviour.

## [v0.1.0] - 2025-10-31
### Added
- Initial public release of **pinballctl**.
- Flask-based web control interface (`pinballctl web`).
- Serial bridge daemon for ESP32-S3 communication (`pinballctl bridge`).
- Systemd service installer (`pinballctl service install`).
- CLI command set for start/stop/status/version.
- Packaging and release automation scripts.

### Changed
- None — this is the first version.

### Fixed
- None — baseline release.
