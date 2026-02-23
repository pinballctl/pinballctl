# Changelog

All notable changes to this project will be documented in this file.

---

## [v0.3.0] - 2026-02-23
### Added
- Logs module toolbar now includes a `Download` action to export the currently selected log file (current or archive).
- Login screen now includes a password reveal toggle.
- Firmware artifacts/version metadata were refreshed (including updated firmware version headers/bundles).

### Changed
- Logs archive selector labels now show a cleaner `date/time • size` format.
- Logs archive size display now auto-scales between `KB`, `MB`, and `GB`.
- Lighting editor selection and interaction flow updated:
  - Shift-select/deselect support for additional pixels.
  - Improved drag-select behavior outside timeline mode.
  - Line-pixel selection now highlights grouped strip context.
- Playfield editor now supports arrow-key fine positioning for component adjustments.

### Fixed
- Media fullscreen launches now honor selected target displays more reliably when host display metadata reports ambiguous origins.
- Media stage keyboard nudging now supports consistent 1px arrow-key movement of selected overlays, with improved non-selected arrow-key focus behavior.
- Logs archive dropdown now excludes zero-byte archives.
- Media runtime/reporting and scaling regressions were addressed.
- Lighting editor fixes for new-pixel positioning and numeric-field update timing behavior.

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
