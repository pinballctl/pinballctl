# Bridge Protocol

The Pi owns the ESP's USB serial connection through the bridge daemon. Each frame starts with a four-byte unsigned big-endian length. That length counts all bytes after the header, including the type byte when present. The firmware assembles partial reads and accepts payload lengths from 1 to 8,192 bytes.

During handshake, the bridge negotiates protocol v2 with compatible firmware. Untyped command frames carry UTF-8 JSON directly. A v2 frame starts its payload with type 1 for JSON, type 2 for binary blob data, or type 3 for diagnostic text. Commands use JSON objects with a `cmd` field.

## Commands and replies

| Command or response | Use |
| --- | --- |
| `HELLO`, `GET_INFO` | Negotiate protocol and discover controller identity and rules runtime support. |
| `EVENT_FIRE`, `EVT`, `EVENT_DROP` | Send a synthetic event and observe its acknowledgement or drop. |
| `BLOB_BEGIN`, binary chunks, `BLOB_END` | Transfer compiled mapping, rules or lighting data. Check the apply result and manifest. |
| `COIL_CONFIG`, `COIL_HEARTBEAT`, `COIL_STATUS` | Configure limits, prove bridge liveness and read the ESP's safety state. |
| `GET_INPUT_LEVELS`, `INPUT_LEVELS` | Read up to 16 watched input sources. |
| `GET_RUNTIME_CLOCK`, `RULE_ACTIONS` | Obtain current ESP time and submit time-limited Pi-side output decisions. |

Use bridge RPC and `reqId` for a correlated command response. Unsolicited status and event frames carry a message type in `t`. A heartbeat status updates the safety display. An explicit coil command needs its own correlated reply.

## Deployment

Hardware Sync first sends the coil limits, then applies the compiled mapping. Rules Sync sends `rules.pd`, which includes input watches needed by managers. Lighting uses its own compiled blob. A success requires firmware apply confirmation and an updated manifest entry. [Bridge performance](bridge-performance.md)

## Event provenance and safety

Physical input frames carry `physical:true` and may include `inputHigh`. `EVENT_FIRE` confirmations use `synthetic:true`. The bridge preserves this distinction before dispatching to game or ball managers. Missing watched-input values leave occupancy unconfirmed.

An ESP event reports which rules runtime version was active for that event. Version 3 applies supported local actions from mixed rules. Pi-side output decisions still go through `RULE_ACTIONS`, which validates timing and input state before sending an action through the coil policy. [Coil Safety](coil-safety.md)
