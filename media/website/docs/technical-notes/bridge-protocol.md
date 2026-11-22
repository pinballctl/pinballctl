# Bridge Protocol

Encode each USB serial message as an unsigned 32-bit big-endian length followed by exactly that many bytes of UTF-8 JSON. Count bytes after encoding. The firmware receiver validates the length against its frame limit and assembles partial reads before parsing the payload. Send each command as a JSON object with a `cmd` field.

## Commands and replies

| Command | Use |
| --- | --- |
| `HELLO`, `GET_INFO` | Handshake and controller identity |
| `SET_RULES` | Apply a rules payload and check the returned status |
| `EVENT_FIRE` | Inject an event through the controller's synthetic event path |
| `BLOB_BEGIN`, `BLOB_CHUNK`, `BLOB_END` | Transfer a blob in chunks |

Use the bridge RPC path and its `reqId` when the caller needs a correlated reply. Route incoming frames by their `t` field. Keep unsolicited event frames separate from command acknowledgements.

## Manager observations and controlled outputs

Physical input event frames include `physical:true`; synthetic `EVENT_FIRE` confirmations include `synthetic:true`. Only bridge-validated physical provenance can feed bound coin/start inputs and Ball observations. Generic Events requests cannot supply private provenance metadata or reserved manager names.

The Pi reads configured occupancy switches with the framed `GET_INPUT_LEVELS` command, passing up to 16 watched source IDs. The `INPUT_LEVELS` reply contains boolean GPIO levels for initialized input watches. Physical input events also carry `inputHigh` when available. Ball Management treats low as the asserted input level before applying the configured sensor polarity. Missing values leave occupancy unconfirmed.

`{"cmd":"GET_RUNTIME_CLOCK"}` returns `{"t":"RUNTIME_CLOCK","tsMs":<ESP millis>}` through the same length-prefixed JSON transport. Manager-triggered output requests use this fresh clock with existing `RULE_ACTIONS` guards; a missing/rejected clock or output acknowledgement never bypasses arming, recovery or pulse limits. No automatic physical retries occur. See [ownership and recovery](management-ownership.md).
