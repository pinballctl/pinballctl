# ESP Development Plan

## Purpose
This document captures:
- A focused review of current Pi-side functionality.
- The ESP-side functionality required to reach runtime parity for rules/event execution and lighting control.
- A phased implementation plan with acceptance criteria.

## Non-Negotiable Constraints
- Preserve existing event message behavior/performance:
  - Current framed event handling (`EVENT` / `EVENT_FIRE` + stats/ack flow) has already tested fast and reliable.
  - Do not break or redesign this path unless a concrete missing requirement is identified.
- Keep firmware config-driven from uploaded module artifacts:
  - Runtime behavior must be driven by deployed data (rules, lighting, hardware mapping, and related module outputs), not hardcoded gameplay logic.
  - Pi remains the authoring layer; ESP remains deterministic runtime executor of uploaded config.

The transport baseline is **frames-only JSON** over serial:
- 4-byte big-endian length header.
- UTF-8 JSON payload.
- No newline-delimited command transport.

## Current App Review (Pi Side)

### Existing Runtime Layers
- `events` runtime:
  - In-process `EventBus` with envelopes (`id`, `ts`, `name`, `source`, `params`).
  - `EventManager` route model (`system:*`, `hardware:<deviceClass>:<event>`, `custom`, plus `all`/`event:<name>`).
  - Registry-driven event catalog from `src/pinballctl/app/modules/rules/registry.json`.
- `rules` runtime:
  - Evaluates persisted rules from `src/instance/rules/rules.json`.
  - Supports trigger groups, condition groups, action execution.
  - Emits derived events and forwards to bridge (`EVENT_FIRE`).
- `lighting` runtime:
  - Scene model in `src/instance/lighting/lighting.json`.
  - Bridge commands for scene start/stop (`LIGHT_SCENE_PLAY`, `LIGHT_SCENE_STOP`).
  - Compiled blob support (`lighting.pd`) on Pi side.
- `scoring` runtime:
  - Event-driven scoring config/state/high-score persistence.
  - Bus worker processing in-order event updates.
- `audio` + `media` runtime:
  - Rule actions can trigger Pi-local cues/scenes.
  - These are Pi-hosted capabilities and not hard real-time firmware responsibilities.

### Existing ESP Bridge/Protocol Surface
- Bridge command path uses framed JSON writes (`_send_cmd` in `src/pinballctl/bridge/daemon.py`).
- Firmware frame receiver in `src/firmware/src/System.cpp` is length-prefixed, stateful, non-blocking.
- `ProtocolHandler` currently handles:
  - Boot/info/fs: `GET_INFO`, `GET_FS_STATUS`, `MOUNT_FS`, `FS_LIST`, `FS_MANIFEST_GET`, `FS_MANIFEST_UPDATE`, `GET_FLASH_INFO`.
  - Rules/event stubs: `SET_RULES`, `EVENT`, `EVENT_FIRE`, `EVENT_STATS`, `EVENT_STATS_RESET`.
  - Lighting stubs: `LIGHT_SCENE_PLAY`, `LIGHT_SCENE_STOP`.
  - Blob transport: `BLOB_BEGIN`/typed payload frame/`BLOB_END`.
  - Diagnostics/time: `ECHO`, `EVT_STREAM_START/STOP`, `SYNC_TIME`, `GET_HW`.

### Current Firmware Capabilities (Already Working)
- Boot lifecycle/status reporting:
  - FS mount/status broadcast on boot.
  - Controller info and heartbeat/ping output.
- Event message handling:
  - Accepts `EVENT` and `EVENT_FIRE` frames.
  - Tracks and reports event ingress counters via `EVENT_STATS`.
- Blob/file handling:
  - Accepts blob uploads and validates mapping/rules blob headers.
  - Applies mapping blob at boot when present.
- Discovery/diagnostics:
  - Hardware scan streaming (`GET_HW` / `HW_*` frames).
  - Event stream test tooling (`EVT_STREAM_START/STOP`).
- Lighting/rules command endpoints exist as protocol hooks today:
  - `SET_RULES`, `LIGHT_SCENE_PLAY`, `LIGHT_SCENE_STOP`.
  - Runtime execution behind those hooks is the main planned expansion.

### Gap Summary
Pi-side authoring/execution is broad. Firmware currently handles framed transport, event ingress, blob lifecycle, and status telemetry, but runtime execution is still scaffolded for:
- Rule evaluation and action execution.
- Real lighting scene engine.
- Event/controller state machines (credits/game/ball/mode style controllers).
- Deterministic real-time scheduling and safety-gated output control.

## ESP End-State Responsibilities

### Core Runtime Contract
ESP should become the real-time executor for:
- Switch/button/sensor input ingestion and debouncing.
- Event generation and routing.
- Rule evaluation and action execution.
- Coil/output/lighting actuation with hard safety enforcement.

Pi should remain:
- Authoring/orchestration layer.
- Deployment, sync, diagnostics, and UI.
- Non-real-time services (media/audio/scoring if intentionally left Pi-side).

### Safety Invariants (Must Hold)
- Output actuation requires explicit enable/arm state.
- Coil pulse/hold limits enforced entirely on firmware side.
- Watchdog/fault paths force safe output state and require explicit recovery.
- Flood/duplicate command protection for high-current outputs.
- Safe defaults applied at boot and after communication loss.

## Main Event Controllers Needed on ESP

These controllers should exist as explicit firmware modules with independent state and tests.

### 1) Input Controller
- Normalizes physical input signals into canonical events.
- Supports registry-style hardware semantics:
  - Button: `PRESSED`, `RELEASED`, `CLICKED`, `DOUBLE_CLICKED`, `HELD`, `REPEAT_WHILE_HELD`.
  - Switch: `OPENED`, `CLOSED`, `CHANGED`, `ACTIVE_FOR_MS`, `INACTIVE_FOR_MS`.
- Handles per-source timing windows and debounce.

### 2) Event Router Controller
- Maintains event envelope schema parity (name/source/params/seq/time).
- Routes to rule engine and telemetry publisher.
- Maintains event stats counters (`EVENT_STATS` compatibility).

### 3) Rule Engine Controller
- Loads compiled ruleset (`rules.pd` schema-backed format).
- Evaluates trigger groups/condition groups with `ALL`/`ANY` semantics.
- Supports indexed lookup by event key for bounded per-event runtime.
- Enforces deterministic execution order and bounded action budget per tick.

### 4) Game State Controller
- Maintains firmware-owned flags/counters needed by conditions:
  - Flags: `TILT`, `ENABLED`, `HAS_CREDIT`, `GAME_ACTIVE`, `BALL_IN_PLAY`, `IDLE`.
  - Counters: `CREDITS`, `BALL_NUMBER`, `PLAYER_COUNT`.
- Emits system events (`GAME_STARTED`, `BALL_STARTED`, `ENABLE_GRANTED`, etc.)
  when state transitions occur.

### 5) Safety Controller
- Owns watchdog, fault latching, auto-shutdown behavior.
- Applies fallback outputs immediately on fault.
- Publishes structured fault events/status.

### 6) Coil/Output Controller
- Executes `pulse_coil` and `set_output` actions with strict policy checks.
- Tracks active outputs and auto-timeouts.
- Separates command intent from physical actuation path.

### 7) Lighting Controller
- Loads `lighting.pd` scenes.
- Supports `LIGHT_SCENE_PLAY` and `LIGHT_SCENE_STOP` as real runtime operations.
- Supports `startFrame` / `startTag` / `paused` semantics where present.
- Handles scene priority and blend policy deterministically.

### 8) Persistence/Version Controller
- Maintains local blob metadata (size/hash/revision) for mapping/rules/lighting.
- Reports current runtime revisions to Pi.
- Supports safe boot restore and compatibility checks.

## Pi Feature Parity Targets for ESP Rules Engine

### Trigger Support
- System events from registry categories.
- Hardware events by device class and event key.
- Custom event names with same validation strategy as registry (`^[A-Z0-9_]+$`).

### Condition Support
- `flag` comparisons.
- `counter` comparisons.
- `time_since_event` comparisons.
- `device_state` comparisons (coil/switch/output).

### Action Support (Priority Order)
- P0 (firmware real-time core):
  - `emit_event`
  - `set_flag`
  - `set_counter`
  - `inc_counter`
  - `pulse_coil`
  - `set_output`
  - `apply_lighting_scene`
  - `stop_lighting_scene`
- P1 (optional split with Pi):
  - `play_audio_cue`, `stop_audio_cue`, `toggle_audio_cue` (remain Pi-owned unless needed on ESP).
  - `media_play_scene`, `media_stop_scene`, `media_stop_all` (remain Pi-owned).
- Planned/non-runtime placeholders:
  - `led_pattern`, `delay` can be represented in compiled format but initially no-op unless implemented.

## Data Flow and Artifacts

### Existing Artifacts
- Authoring rules: `src/instance/rules/rules.json`
- Compiled rules blob: `src/instance/rules/rules.pd`
- Mapping blob: `src/instance/hardware/mapping.pb`
- Lighting blob: `src/instance/lighting/lighting.pd`

### Target Runtime Flow
1. Pi saves authoring JSON.
2. Pi compiles deterministic blob(s) with schema + hash.
3. Pi deploys via framed blob transport (`BLOB_BEGIN` + typed data frame + `BLOB_END`).
4. ESP validates blob(s), stores to `/cfg/*`, activates if valid.
5. ESP reports active revision/status.

## Protocol Additions Recommended

All commands remain framed JSON.

### Recommended new commands/events
- `GET_RULES_STATUS` -> active schema/revision/hash, loaded/not loaded, last error.
- `RULES_APPLY` -> activate already-uploaded blob atomically.
- `GET_LIGHTING_STATUS` -> active scenes, current frame/tag, runtime limits.
- `GET_RUNTIME_FLAGS` / `GET_RUNTIME_COUNTERS` -> game-state visibility.
- `FAULT_STATUS` event/report -> active faults + recovery requirements.

### Response Design Guidance
- Include `reqId` echo on request-response pairs.
- Include explicit `ok` and machine-parseable `reason` on failures.
- Include `rev`/`sha256` fields for status-bearing payloads.

## Implementation Phases

### Phase 0: Baseline Hardening
- Preserve current event ingress semantics and throughput as a regression gate.
- Finalize frame parser robustness and malformed-frame handling tests.
- Add command budget/backpressure metrics for serial queue pressure.
- Acceptance:
  - Existing event message behavior remains unchanged and passes current soak/latency expectations.
  - No parser lockups under partial/garbled frames.
  - Deterministic recovery from oversize/invalid header lengths.

### Phase 1: Rules Runtime Skeleton on ESP
- Load and validate `rules.pd` end-to-end.
- Build event-key index lookup and no-op executor path.
- Wire `EVENT_FIRE` into runtime path (no side effects yet).
- Acceptance:
  - `SET_RULES`/blob update produces active rules revision.
  - `GET_RULES_STATUS` returns loaded schema/hash.

### Phase 2: Event + Game State Controllers
- Implement input normalization and event synthesis.
- Implement flags/counters state container with transition events.
- Support condition evaluation (`flag`, `counter`, `time_since_event`).
- Acceptance:
  - Rule matching parity validated against Pi-side fixtures.

### Phase 3: Real Action Execution
- Implement `pulse_coil` and `set_output` through safety controller.
- Implement `emit_event`, `set_flag`, `set_counter`, `inc_counter`.
- Integrate watchdog/fault latching behavior.
- Acceptance:
  - High-current outputs obey hard limits under stress tests.

### Phase 4: Lighting Runtime
- Load `lighting.pd` and implement scene scheduler.
- Replace `LIGHT_SCENE_PLAY/STOP` stubs with active playback engine.
- Support priority, cast targeting, start offsets/tags.
- Acceptance:
  - Scene timing and stop/play semantics match Pi expectations.

### Phase 5: Sync Lifecycle + Observability
- Add status/report commands for rules/lighting/runtime state.
- Add revision-diff sync policy (push only on mismatch).
- Add persistent restore behavior after ESP reboot.
- Acceptance:
  - Pi can verify ESP runtime parity without manual inspection.

## Test Plan

### Firmware Unit/Module Tests
- Frame parser edge cases: split header/body, invalid length, timeout resets.
- Rules blob validation: bad magic/version/size/hash.
- Rule matcher correctness with representative trigger/condition fixtures.
- Safety controller: watchdog, timeout, re-enable requirements.

### Integration Tests (Pi + ESP)
- Deploy mapping/rules/lighting blobs and verify status parity.
- Event ingress soak (`EVENT_FIRE`) with bounded latency and no queue collapse.
- Lighting scene stress with concurrent events and action bursts.
- Disconnect/reconnect and reboot persistence behavior.

### Regression Gates
- Never reintroduce newline-delimited command transport.
- Maintain backward compatibility where practical; otherwise version-gate explicitly.
- Verify no path allows unsafe coil activation while disabled/faulted.

## Definition of Done (ESP Runtime Track)
- ESP executes rules deterministically for supported trigger/condition/action set.
- Lighting scenes run on ESP with production-ready start/stop semantics.
- Safety invariants are enforced fully on-device.
- Pi can inspect runtime status/revisions and only redeploy when needed.
- End-to-end behavior is reproducible via automated integration checks.

## Immediate Next Tasks
1. Implement `GET_RULES_STATUS` in firmware + bridge/UI status endpoint.
2. Introduce firmware rule-engine module scaffold (index lookup + evaluator interfaces).
3. Define compact runtime structs for flags/counters/event history.
4. Replace `LIGHT_SCENE_PLAY/STOP` stubs with minimal scheduler over compiled ops.
5. Add protocol/integration tests for framed command + blob + status lifecycle.
