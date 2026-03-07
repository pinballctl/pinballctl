# Changelog

All notable changes to this project will be documented in this file.

---

## [v0.5.0] - 2026-03-07
### Added
- New lighting runtime layering model with scene priority and blend handling (`overlay`, `pause lower priority`, `stop lower priority`) plus active-scene tracking.
- Lighting Runtime tab in the Lighting module with live ESP/runtime scene state, active scene list, resolved scene names, priority, and blend display.
- Expanded lighting pattern library (including `Alternating` rename/rework and multiple new animation presets), with alphabetical pattern selection.
- Improved step-style pattern editors with color pickers, add/remove controls, and per-step intensity support.
- ESP-side RGB enhancements for single-pixel addressing and one-shot blink support for fast button-driven hit feedback.
- Driver/profile runtime expansion in firmware for broader multi-driver and LCD workflows.

### Changed
- Lighting scene runtime was substantially rewritten and simplified for centralized control and lower per-frame overhead.
- Lighting layering/override behavior was refactored so `Target Pixel` style direct writes consistently take precedence over scene output.
- ESP Play/Stop flow in Lighting now uses clearer runtime state handling, better action feedback, and friendlier error surfaces.
- Lighting sync/apply flow was hardened around manifest/blob deploy and runtime apply sequencing.
- Play-on-ESP availability logic now correctly distinguishes local preview vs ESP preview (including headless/disconnected guard behavior).
- Audio module Runtime view moved into its own top-level tab in the module tab set.
- Logs module tailing/refresh behavior received stability fixes.
- Firmware flashing workflow/scripts were updated to align with newer `esptool` CLI expectations and remove deprecated call patterns.

### Fixed
- Multiple lighting regressions around scene play/stop, status reporting, sync state badges, and stale UI state after successful sync.
- Lighting preview editor layout issues (cutoff/cropping) and runtime tab visibility/data binding issues.
- Hardware-vs-Live View trigger parity issues where button-driven light behavior diverged from simulated events.
- LED/RGB “stuck on” cases after scene playback and delayed override release timing under active scenes.
- Bridge/log noise from excessive scene status polling by gating polling to active Lighting Stage/Runtime contexts.
- Firmware compile conflict involving duplicate lighting boot guard symbol definitions.
- Additional runtime reliability fixes across bridge/firmware lighting apply/boot reporting paths.

## [v0.4.0] - 2026-02-28
### Added
- New **Live View** module for read-only runtime emulation, including playfield rendering, context-trigger actions, keyboard trigger support, and runtime display preview cards.
- New **Integrity Check** module to scan cross-module dependencies, report orphaned/unused references, and provide resolve actions.
- ESP firmware button gesture support for `PRESSED`, `RELEASED`, `CLICKED`, `DOUBLE_CLICKED`, `HELD`, and `REPEAT_WHILE_HELD`.
- ESP firmware hardware profile support with profile-based pin catalog loading (starting with ESP32-S3 profile structure).
- Bridge/ESP info enrichment and surfacing in ESPLink overview (chip model/revision/cores/controller/profile).
- System `BOOT_COMPLETED` runtime event emission once bridge/ESP runtime handshake is established.

### Changed
- Playfield and Lighting modules were refocused as build tools; live/runtime behaviour moved into Live View.
- Live View now overlays lighting fixtures and plays compiled lighting scene timelines for runtime preview parity.
- Rules/runtime behaviour updated so output/action activation aligns with pin default-state semantics.
- Hardware reload/discovery flow updated to support broader safe pin ranges and profile-driven pin handling.
- Settings and Logs UX updates (layout refinement, tab persistence, clearer export progress state).
- Media/Audio library tables improved with formatted timestamps and file size visibility updates.

### Fixed
- Firmware out-of-sequence event handling now restores affected pins to configured safe defaults.
- Firmware build include path/profile integration regressions.
- Export project failures caused by UNIX socket files being included in ZIP export.
- Audio engine concurrency issue causing duplicate/orphan playback instances under rapid trigger conditions.
- ESPLink overview rendering/runtime errors (including null DOM target updates and duplicated/misplaced fields).
- Hardware pin reload regressions where saved pin metadata/configuration was lost or not persisted correctly.
- Rules-to-runtime event propagation gaps impacting Playfield/Media/Lighting/Audio trigger response.
- Multiple UI consistency issues across Integrity Check, Live View, ESPLink, Settings, and website/docs assets.

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
