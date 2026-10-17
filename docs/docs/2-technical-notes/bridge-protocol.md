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
