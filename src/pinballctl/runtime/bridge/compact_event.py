"""Expand independent ESP input and diagnostic frames into ordinary events."""

from struct import Struct


FRAME_TYPE = 4
_HEADER = Struct(">BBII")
_STATES = ("", "CLOSED", "OPEN", "HIGH", "LOW", "ACTIVE", "INACTIVE")


def decode_event(payload: bytes) -> dict:
    if len(payload) < _HEADER.size:
        raise ValueError("Truncated compact event header")
    flags, rules_version, seq, timestamp = _HEADER.unpack_from(payload)
    if flags & 0xc0 or flags & 3 == 3:
        raise ValueError("Invalid compact event flags")
    offset = _HEADER.size

    def take(size):
        nonlocal offset
        end = offset + size
        if end > len(payload):
            raise ValueError("Truncated compact event")
        value = payload[offset:end]
        offset = end
        return value

    def text():
        return take(int.from_bytes(take(2), "big"))

    detail = int.from_bytes(take(4), "big") if flags & 0x10 else 0
    source = text()
    event_type = text()
    name_mode = (flags >> 2) & 3
    name = (None, event_type, source + b"_" + event_type, source)[name_mode]
    if name is None:
        name = text()
    msg = {"t": "EVT", "name": name.decode(), "source": source.decode(),
           "seq": seq, "tsMs": timestamp}
    if flags & 0x20:
        if not name or not source or not event_type:
            raise ValueError("Missing physical event fields")
        msg.update(physical=True, rulesApplied=True, rulesVersion=rules_version,
                   eventType=event_type.decode(), observedDevices={})
        if flags & 3:
            msg["inputHigh"] = flags & 3 == 2
        if detail:
            msg["detailMs"] = detail
        while offset < len(payload):
            prefix, state = take(2)
            suffix = text()
            if prefix > len(source) or not 0 < state < len(_STATES):
                raise ValueError("Invalid compact device observation")
            key = (source[:prefix] + suffix).decode()
            if not key or key in msg["observedDevices"]:
                raise ValueError("Invalid compact device key")
            msg["observedDevices"][key] = _STATES[state]
    elif offset != len(payload) or detail or flags & 3 or event_type or rules_version:
        raise ValueError("Invalid compact diagnostic event")
    return msg
