# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]

## [v0.10.0] - 2026-10-18

### Added
- Unified website with feature pages, integrated documentation, site search with a docs-only filter, and a dedicated Start Building guide.
- Legacy documentation-domain holding page with links to the new docs, plus automatic GitHub Pages build and deployment.
- Consistent right-side settings panels across Hardware, Rules, Scoring, Media, Lighting and Service Log.

### Changed
- Refreshed application branding, navigation, forms, tables, buttons and light/dark themes. All Tools replaces Modules, with favourites separated from account controls.
- Reworked Media Scenes around a large preview and adjacent layer stack. Browse Scenes and settings use side panels; selecting a layer highlights it, while its sliders icon opens settings.
- Reworked Lighting around a stage and scene-settings column, a fixture summary table with per-fixture settings, improved cast selection and runtime tables.
- Simplified Audio, Scoring and other module layouts by removing nested cards and duplicate headings. Upload actions open dedicated dialogs.
- Sync actions start muted and highlight only when a configuration difference is confirmed.
- Documentation links open the new website docs in a separate tab. Updated guides, marketing content, SEO metadata and regenerated 97 screenshot captures.
- Filesystem diagnostics show readable storage usage and mount status; Echo Test shows clear success and failure results.

### Fixed
- Missing Playfield LCD elements whose saved binding referred to a linked secondary pin.
- LCD previews now use the configured background colour with a white outline consistently across Playfield, Lighting and Live View.
- Low-contrast lighting preview OFF states in light mode, drawer backdrop flicker, inconsistent icon sizing and missing icon definitions.
- Misleading ESPLink presentation of cached device information when the ESP is no longer responding.

### Upgrade and validation
- Firmware remains v0.0.11. This release does not change coil safety limits or require a new firmware build.
- Browser checks covered editor interactions, diagnostic success/error states, shared panel sizing, both themes and mobile widths. Linked-binding regression tests and JavaScript syntax checks passed.
- Website build and local-link validation passed for 63 searchable pages and both GitHub Pages artifacts.
- A bridge restart recovered an observed ESP communication stall; its underlying cause has not been established.

## [v0.9.0] - 2026-10-17
### Added
- Per-pin coil driver configuration with conservative defaults and support for pulse, PWM hold, and paired-coil arrangements. ESP-side arming, watchdogs, pulse/hold limits, cooldowns and fault handling enforce output safety.
- A Performance module under Platform, with throughput, queue, delivery-latency and overload history, plus a bridge load-test utility.
- Automatic recovery from isolated delivery overloads with firmware v0.0.11: disarm, discard stale activations, pause runtime output actions, wait for cooldown and healthy queues, then restore the previous armed state through the existing safety checks. No development UI or designated Start button is required.
- Persistent overload lockout after three incidents within 60 seconds; firmware faults and failed recovery handshakes remain disarmed. Held inputs must release and press again after recovery. Platform overload, recovery and fault notifications are available on the host event bus.

### Changed
- Standardized frames-only serial communication and improved connection ownership, reconnect behaviour, command correlation and bounded event delivery.
- Consolidated hardware, rules and lighting deployment around the shared transfer flow, with configuration confirmation and clearer failure handling.
- Scoring notifications remain on the Pi when no rules listener requires forwarding and the deployed rules are confirmed. Forwarded notifications carry compact event metadata rather than full score state.
- ESP-owned lighting and static LCD rule actions execute once on the ESP; dynamic LCD text remains host-expanded. Connected Live View input follows the ESP/bridge path, with host fallback when offline.
- Improved logging maintenance and suppressed unchanged coil heartbeat/status log noise without reducing safety heartbeat frequency.
- Hardened session-secret handling, service lifecycle, media/audio startup and runtime error handling.

### Fixed
- Restored packaged Flask UI assets and module registries in wheels and source distributions; synchronized the package version with release metadata.
- Duplicate event processing from Live View input, derived events and echoed scoring notifications, which could repeat scoring, audio and other host effects.
- Live View event-stream loss and duplicate notifications, plus lighting preview lag and unnecessary marker rebuilding.
- Hardware/coil configuration confirmation failures, lighting sync stalls and inconsistent sync completion handling.
- Host repetition of lighting already executed by firmware, and loss of event parameters across compact ESP echoes.
- Stale button hold/click gestures and pending output timers surviving an overload recovery.

### Upgrade and validation
- Godot media runtime continues to require the repository checkout containing `src/godot` and a local Godot installation; the Python wheel does not bundle the Godot project.
- Install firmware v0.0.11 alongside this application release, then confirm hardware, coil, rules and lighting configuration sync. Older firmware cannot perform automatic overload recovery.
- Coil configurations remain disabled until explicitly configured and enabled. Recovery never clears firmware safety faults or relaxes output limits. Discarded events are not replayed; scoring/effects may be missed during cooldown.
- Validated with 88 Python tests, native coil-safety/button-recovery tests, and ESP dev-board checks. Two isolated overloads recovered in approximately 2.7 seconds; a third within one minute correctly stayed disarmed.
- Combined scoring/audio/lighting checks completed 900 events, including a 100 events/sec burst, without overload. At 250 fully loaded events/sec the existing queue-delay guard tripped; this is not a claim of sustained 250 events/sec gameplay capacity. Hardware testing used an unloaded dev board; armed-state restoration was covered by software safety tests.


## [v0.8.0] - 2026-03-28
### Added
- Added a full Godot-backed media runtime workflow with dedicated Godot project assets, runtime daemon support, WebSocket command handling, and new runtime-focused test coverage.
- Added a clearer Media Runtime engine/launch UI split, including stable display selection, launch-mode control, runtime status reporting, and token update tooling for Godot scenes.
- Added Live View stage controls for both media scenes and lighting scenes so authored runtime content can be triggered directly from the live stage preview.

### Changed
- Media runtime is now fully Godot-first; the old Chromium runtime path and related isolated runtime plumbing were removed from the active media flow.
- Godot runtime lifecycle handling was refined so display targeting, window reuse, `no_scene` launch behavior, debug panel layout, and layered scene playback behave consistently through the shared media runtime APIs.
- Live View stage controls were aligned with the Media Runtime launch flow, using the same display ids and launch semantics for scene playback.
- Live View lighting preview was expanded to render lighting-scene playback directly on the stage, including local-only fallback behavior when the bridge is offline.

### Fixed
- Fixed duplicate or incorrect media launches caused by mismatched Live View display/runtime identifiers and diverging scene-launch code paths.
- Fixed Live View lighting playback mismatches so compiled scene state now accumulates correctly over time; chase-style scenes render with the expected multi-pixel width.
- Fixed Live View regressions around event-driven preview handling, including lag from over-applied rule actions and flipper/output visuals sticking on.
- Fixed Live View and lighting preview behavior when the bridge is offline so lighting scenes can still play locally in the stage preview without hardware runtime connectivity.

## [v0.7.0] - 2026-03-22
### Added
- Added a new isolated media runtime implementation built around authoritative runtime sessions with attached output endpoints, replacing the earlier mixed output/session model.
- Added a dedicated media scene renderer for the runtime display page and expanded media runtime test coverage, including runtime/audio integration checks.
- Added runtime-table improvements including heartbeat age, start time, and optional auto-refresh.

### Changed
- Media runtime lifecycle was substantially reworked so embedded, windowed, and fullscreen outputs share the same player page while reporting through a single heartbeat-driven runtime registry.
- Runtime reporting is now read-only from the Media UI path: runtime table refresh no longer mutates player state, and display polling now doubles as the liveness signal.
- Live View and Media runtime interactions were tightened so scene replay, runtime grouping, and output isolation behave deterministically across embedded and external players.
- Media release cleanup removed dead legacy runtime code paths and old standalone heartbeat API plumbing that was no longer used by the active runtime.
- Firmware/runtime artefacts and related media/audio integration paths were refreshed as part of the broader media/runtime rewrite cycle.

### Fixed
- Fixed multiple long-standing media runtime issues including duplicate runtime rows, embedded/windowed interference, stale runtime reporting, stop-target collisions, and unreliable refresh behavior.
- Fixed intermittent windowed registration races where the player could open but remain stuck with no heartbeat in the runtime table.
- Fixed duplicate window launches so replaying an already-running windowed/fullscreen scene now reuses the existing player instead of spawning another Chromium window.
- Fixed embedded replay after stop, surface detach/reattach handling, and stale heartbeat handling so players no longer disappear and reappear unpredictably.
- Fixed several window close/cleanup paths and Chromium runtime handling regressions related to media stop/leave flows.

## [v0.6.0] - 2026-03-17
### Added
- Added a second `RGB Strip` firmware backend using `NeoPixel`, while retaining the existing FastLED-backed driver for compatibility and hardware-specific selection.
- Hardware driver metadata/UI now expose explicit `FastLED` and `NeoPixel` options for `RGB Strip` outputs.

### Changed
- Lighting blob compilation was substantially optimized to emit frame deltas instead of re-sending unchanged pixel states, dramatically reducing generated `lighting.pd` size and ESP-side write pressure.
- Zero-intensity lighting states now compile to explicit `off` operations rather than color writes with zero intensity, further shrinking payloads and reducing dynamic scene churn.
- Lighting local preview and ESP runtime control are now separated correctly: UI `Play` stays local, while `Play on ESP` is the only path that sends runtime play/stop commands to the bridge.
- Firmware build tooling was updated so `utils/build-firmware.sh` compiles the sketch entrypoint correctly and includes the `Adafruit NeoPixel` dependency needed for the new RGB backend.

### Fixed
- Fixed dynamic white scene corruption on affected ESP32-S3/LED-strip combinations by adding the `NeoPixel` backend option; `sparkle` and `chase` scenes can now run cleanly when that backend is selected.
- Fixed hardware driver dropdown rendering so stored driver values still map to the correct UI labels (`FastLED` / `NeoPixel`) instead of showing raw internal names.
- Fixed lighting editor preview behavior where local playback also triggered ESP runtime playback/stops unintentionally.

## [v0.5.0] - 2026-03-07
### Added
- New lighting runtime layering model with scene priority and blend handling (`overlay`, `pause lower priority`, `stop lower priority`) plus active-scene tracking.
- Lighting Runtime tab in the Lighting module with live ESP/runtime scene state, active scene list, resolved scene names, priority, and blend display.
- Expanded lighting pattern library (including `Alternating` rename/rework and multiple new animation presets), with alphabetical pattern selection.
- Improved step-style pattern editors with colour pickers, add/remove controls, and per-step intensity support.
- ESP-side RGB enhancements for single-pixel addressing and one-shot blink support for fast button-driven hit feedback.
- Driver/profile runtime expansion in firmware for broader multi-driver and LCD workflows.

### Changed
- Lighting scene runtime was substantially rewritten and simplified for centralised control and lower per-frame overhead.
- Lighting layering/override behaviour was refactored so `Target Pixel` style direct writes consistently take precedence over scene output.
- ESP Play/Stop flow in Lighting now uses clearer runtime state handling, better action feedback, and friendlier error surfaces.
- Lighting sync/apply flow was hardened around manifest/blob deploy and runtime apply sequencing.
- Play-on-ESP availability logic now correctly distinguishes local preview vs ESP preview (including headless/disconnected guard behavior).
- Audio module Runtime view moved into its own top-level tab in the module tab set.
- Logs module tailing/refresh behaviour received stability fixes.
- Firmware flashing workflow/scripts were updated to align with newer `esptool` CLI expectations and remove deprecated call patterns.

### Fixed
- Multiple lighting regressions around scene play/stop, status reporting, sync state badges, and stale UI state after successful sync.
- Lighting preview editor layout issues (cutoff/cropping) and runtime tab visibility/data binding issues.
- Hardware-vs-Live View trigger parity issues where button-driven light behaviour diverged from simulated events.
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
- Firmware artefacts/version metadata were refreshed (including updated firmware version headers/bundles).

### Changed
- Logs archive selector labels now show a cleaner `date/time • size` format.
- Logs archive size display now auto-scales between `KB`, `MB`, and `GB`.
- Lighting editor selection and interaction flow updated:
  - Shift-select/deselect support for additional pixels.
  - Improved drag-select behaviour outside timeline mode.
  - Line-pixel selection now highlights grouped strip context.
- Playfield editor now supports arrow-key fine positioning for component adjustments.

### Fixed
- Media fullscreen launches now honour selected target displays more reliably when host display metadata reports ambiguous origins.
- Media stage keyboard nudging now supports consistent 1px arrow-key movement of selected overlays, with improved non-selected arrow-key focus behaviour.
- Logs archive dropdown now excludes zero-byte archives.
- Media runtime/reporting and scaling regressions were addressed.
- Lighting editor fixes for new-pixel positioning and numeric-field update timing behaviour.

## [v0.2.0] - 2026-02-22
### Added
- Media overlay placeholders now ingest live scoring values (including score/player/game state data paths used by media runtime).

### Changed
- Media runtime and stage rendering behaviour updated for more consistent preview/runtime parity and improved scaling behaviour.
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
