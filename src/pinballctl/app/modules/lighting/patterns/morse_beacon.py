from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .registry import PatternPlugin


_MORSE: Dict[str, str] = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-",
    "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----.",
}


def _dot_ms(value: Any) -> int:
    try:
        v = int(value)
    except Exception:
        v = 120
    if v < 40:
        return 40
    if v > 1000:
        return 1000
    return v


def _timeline(message: str, dot_ms: int) -> List[Tuple[bool, int]]:
    text = str(message or "SOS").upper()
    on_dot = dot_ms
    on_dash = dot_ms * 3
    gap_symbol = dot_ms
    gap_letter = dot_ms * 3
    gap_word = dot_ms * 7

    events: List[Tuple[bool, int]] = []
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch == " ":
            events.append((False, gap_word))
            continue
        code = _MORSE.get(ch)
        if not code:
            continue
        for si, symbol in enumerate(code):
            events.append((True, on_dash if symbol == "-" else on_dot))
            if si != len(code) - 1:
                events.append((False, gap_symbol))
        if i != len(chars) - 1 and chars[i + 1] != " ":
            events.append((False, gap_letter))
    if not events:
        return [(True, on_dot), (False, gap_symbol), (True, on_dot), (False, gap_word)]
    if events[-1][0]:
        events.append((False, gap_word))
    return events


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "MORSE_BEACON",
        "target": "*",
        "colour": str(params.get("colour", "#ffffff") or "#ffffff"),
        "dotMs": _dot_ms(params.get("dotMs", 120)),
        "message": str(params.get("message", "SOS") or "SOS"),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    dot_ms = _dot_ms(op.get("dotMs", 120))
    seq = _timeline(str(op.get("message") or "SOS"), dot_ms)
    cycle = sum(d for _, d in seq)
    if cycle <= 0:
        return out

    step = max(20, min(120, int(dot_ms / 2)))
    colour = str(op.get("colour") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        elapsed = (t_ms - start_t_ms) % cycle
        acc = 0
        on = False
        for state, dur in seq:
            acc += dur
            if elapsed < acc:
                on = state
                break
        frame = [runtime.pixel_change(p, colour, brightness, 1.0 if on else 0.0) for p in pixels]
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="morse_beacon",
    label="morse beacon",
    op_name="MORSE_BEACON",
    order=31,
    params=[
        {"key": "colour", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "dotMs", "label": "DotMs", "type": "number", "default": 120, "min": 40, "max": 1000, "step": 10, "integer": True},
        {"key": "message", "label": "Message", "type": "text", "default": "SOS"},
    ],
    build_op=build_op,
    expand_op=expand,
)
