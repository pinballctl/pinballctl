# Architecture

Pinball CTL splits orchestration and real-time control across Pi and ESP.

## Responsibility Split

- Pi (`pinballctl` app + bridge):
  - Authoring/configuration persistence.
  - HTTP/UI and orchestration workflows.
  - Bridge command enqueue, RPC correlation, and state sync.
- ESP32-S3 firmware:
  - Real-time switch/output processing.
  - Runtime safety (enable gating, timeouts, watchdog/fault behavior).
  - Deterministic command execution close to hardware.

## Transport Boundary

Pi <-> ESP communication is framed JSON only:
- 4-byte big-endian length header.
- UTF-8 JSON payload.
- No newline/line-based command transport.

## Data/Artifact Flow

- User edits config in Pi UI modules.
- Pi persists source artifacts under `src/instance/*`.
- Pi pushes runtime payloads to ESP via bridge commands.
- ESP acknowledges status and publishes telemetry/events back through the bridge.

## Operational Principle

Keep latency-critical behavior local on ESP.
Use Pi for orchestration, persistence, and non-real-time logic.
