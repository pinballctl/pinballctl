# Bridge Event Flow

## Event Paths

There are two distinct paths through the bridge:

1. Response-required RPC:
- Used for control/status operations.
- Correlated using `reqId`.
- Examples: `GET_INFO`, `FS_*`, `SET_RULES`.

2. Fire-and-forget event flow:
- Used for high-volume gameplay telemetry/events.
- Examples: `EVENT_FIRE`, `EVT` stream payloads.

## Routing Model

- Pi modules enqueue commands to bridge.
- Bridge performs framed send/receive and central routing.
- ESP executes runtime behavior and publishes events/status upstream.

## Throughput Guidance

Observed soak tests in this repo history show practical sustained throughput around the mid-hundreds of events/sec on current hardware/runtime.

Conservative planning guidance:
- Design sustained flows with headroom (`<= 350-400 evt/s`).
- Keep burst-only traffic separate from control RPC.
- Keep ultra-latency-critical reactions on ESP.
