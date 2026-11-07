# Bridge Protocol

## Framing

All Pi -> ESP commands and ESP -> Pi responses/events use framed transport:
- `uint32_be length`
- `length` bytes UTF-8 JSON payload

No line-based parsing is supported.

## Command Shape

Commands are JSON objects with explicit `cmd` values.
Typical commands include:
- `HELLO`
- `GET_INFO`
- `SET_RULES`
- `EVENT_FIRE`
- `BLOB_BEGIN` / `BLOB_CHUNK` / `BLOB_END`

Response-required commands should include a `reqId` so bridge/clients can correlate replies.

## Bridge Behavior

- Outbound send path serializes compact JSON and writes framed bytes.
- Inbound receive path decodes frames, parses JSON, and routes by message type.
- High-rate event traffic is intentionally handled separately from strict RPC flow.

## Safety/Compatibility Rules

- Do not reintroduce newline-delimited command transport.
- Keep payloads explicit and version-friendly.
- Preserve backwards compatibility where feasible; version intentional breaking changes.


## Manager observations and controlled outputs

Physical input event frames include `physical:true`; synthetic `EVENT_FIRE` confirmations include `synthetic:true`. Only bridge-validated physical provenance can feed bound coin/start inputs and Ball observations. Generic Events requests cannot supply private provenance metadata or reserved manager names. Deploy the matching firmware when enabling managers.

The Pi reads configured occupancy switches with the framed `GET_INPUT_LEVELS` command, passing up to 16 watched source IDs. The `INPUT_LEVELS` reply contains boolean GPIO levels for initialized input watches. Physical input events also carry `inputHigh` when available. Ball Management treats low as the asserted input level before applying the configured sensor polarity. Missing values leave occupancy unconfirmed.

`{"cmd":"GET_RUNTIME_CLOCK"}` returns `{"t":"RUNTIME_CLOCK","tsMs":<ESP millis>}` through the same length-prefixed JSON transport. Manager-triggered output requests use this fresh clock with existing `RULE_ACTIONS` guards; a missing/rejected clock or output acknowledgement never bypasses arming, recovery or pulse limits. No automatic physical retries occur. See [ownership and recovery](management-ownership.md).
