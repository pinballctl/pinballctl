# Bridge Protocol

The Pi owns the ESP's USB serial connection through the bridge daemon. Each frame starts with a four-byte unsigned big-endian length. That length counts all bytes after the header, including the type byte when present. The firmware assembles partial reads and accepts payload lengths from 1 to 8,192 bytes.

During handshake, the bridge negotiates protocol v2. Untyped command frames carry UTF-8 JSON directly. A typed frame starts its payload with type 1 for JSON, type 2 for binary blob data, type 3 for diagnostic text or type 4 for a compact ESP event. Commands use JSON objects with a `cmd` field. Update firmware and the Pi bridge together for compact events.

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

Physical input frames carry provenance, sequence, time, event name and type, rules version, and the electrical level and gesture duration when available. The bridge expands them to the usual `EVT` record with `physical:true` and full device observations for rules and logging. `EVENT_FIRE` confirmations use `synthetic:true`. Missing watched-input values leave occupancy unconfirmed.

### Compact event frames

The type 4 payload starts with flags, the rules version, a 32-bit sequence and a 32-bit ESP millisecond timestamp. An optional 32-bit gesture duration follows. All multibyte integers are big-endian. The source and event type are UTF-8 strings prefixed with a 16-bit byte length. The name is either another length-prefixed string or reconstructed from the type, source, or source and type joined by an underscore.

The flags use bits 0–1 for input level (0 unknown, 1 low, 2 high), bits 2–3 for the name form (0 literal, 1 type, 2 source plus type, 3 source), bit 4 for duration, and bit 5 for physical input. Bits 6–7 are reserved. Each device observation has a one-byte prefix length shared with the source, a one-byte state code and a length-prefixed suffix. State codes 1–6 correspond to Closed, Open, High, Low, Active and Inactive. Observations continue to the end of the frame. Every frame carries its own complete snapshot.

Diagnostic stream frames use the same type with physical provenance absent, an empty event type and rules version 0. The ESP retains physical events in order when the transmit queue is temporarily full. If the input buffer overflows, the ESP reports the number discarded in `EVENT_INPUT_LOSS` and the Bridge enters overload recovery. Expanded physical events appear in both the ESP raw log and the event audit log.

An ESP event reports which rules runtime version was active for that event. Version 3 applies supported local actions from mixed rules. Pi-side output decisions still go through `RULE_ACTIONS`, which validates timing and input state before sending an action through the coil policy. [Coil Safety](coil-safety.md)

### Hardware Test

`HARDWARE_TEST` uses a browser-generated session ID and replies with `HARDWARE_TEST_STATUS` and the correlated request ID. `start` lists the applied driver's test actions and current state for each mapped device. `poll` renews the session and returns device status in the same order. It can also renew a lamp hold by device ID. `action` executes a supported driver test by device ID, and `stop` returns test outputs to idle. The ESP takes care of output cleanup when the session or a hold expires. This traffic uses bridge RPC and does not generate gameplay events.
