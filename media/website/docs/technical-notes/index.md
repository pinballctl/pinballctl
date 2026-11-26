<span id="technical-notes"></span>

# System Overview

Pinball CTL runs across a browser-based admin app, a Raspberry Pi runtime and an ESP32-S3. These notes show which component owns each decision, how configuration reaches the ESP, and how to trace a switch press through to its output.

## How the system is put together

- [Architecture](architecture.md) covers the webapp, runtime, firmware and backglass boundaries.
- [App layout and services](app-layout.md) maps the repository, instance files and service entry points.
- [Management ownership](management-ownership.md) explains how Game, Ball and Scoring share state.
- [Development platform](../build-notes/development-platform.md) covers the local checkout, cabinet services and controller bench.

## Follow an event or deployment

- [Bridge event flow](bridge-event-flow.md) traces physical and Live View events and explains where mixed rules run.
- [Bridge protocol](bridge-protocol.md) describes serial frames, acknowledgements and configuration transfers.
- [Event dispatch internals](event-manager.md) explains how the Pi routes events and where to inspect them.
- [Bridge performance](bridge-performance.md) covers queue timing, sync and overload recovery.
- [Modules API surface](modules-api-surface.md) points to the HTTP and runtime interfaces.

## Coil safety and testing

- [Coil Safety](coil-safety.md) explains automatic arming, heartbeat recovery, faults and the Dashboard status.
- [Coil operating modes](coil-operating-modes.md) covers driver settings, pulse and hold behavior, and paired windings.
- [Firmware regression checks](../developer-guide/firmware-checks.md) describes software and bench verification.

For installation and initial setup, start with [Getting Started](../user-guide/getting-started.md).
