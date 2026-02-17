from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def _text_bits(text: str) -> List[int]:
    s = str(text or "").upper()
    if not s:
        s = "PINBALL"
    bits: List[int] = []
    for ch in s:
        v = ord(ch) & 0x3F
        for b in range(5, -1, -1):
            bits.append(1 if ((v >> b) & 0x1) else 0)
        bits.append(0)
    if not any(bits):
        return [1, 0, 1, 1, 0, 0, 1, 0]
    return bits


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "left") or "left").strip().lower()
    if direction not in ("left", "right", "up", "down"):
        direction = "left"
    return {
        "op": "TICKER",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "window": max(1, min(12, int(params.get("window", 3) or 3))),
        "direction": direction,
        "text": str(params.get("text", "PINBALL")),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(120, int(period_ms / 20)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    window = max(1, min(12, int(op.get("window", 3) or 3)))
    direction = str(op.get("direction") or "left").strip().lower()
    bits = _text_bits(op.get("text"))
    nbits = len(bits)
    if direction in ("left", "right"):
        key = lambda p: (float(p.get("x", 0.5)), float(p.get("y", 0.5)))
    else:
        key = lambda p: (float(p.get("y", 0.5)), float(p.get("x", 0.5)))
    ordered = sorted(enumerate(pixels), key=lambda it: key(it[1]))
    order_idx = [i for i, _ in ordered]
    if direction in ("right", "down"):
        order_idx = list(reversed(order_idx))
    rank = {pi: ri for ri, pi in enumerate(order_idx)}
    total = max(1, len(order_idx))
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        ofs = int((t_ms - start_t_ms) / max(1, step))
        frame = []
        for pi, p in enumerate(pixels):
            ri = rank.get(pi, 0)
            head = (ri + ofs) % max(1, total)
            bidx = head % nbits
            lit = 0.0
            for j in range(window):
                bj = (bidx - j) % nbits
                if bits[bj]:
                    lit = max(lit, 1.0 - (float(j) / float(max(1, window))))
            frame.append(runtime.pixel_change(p, color, brightness, lit))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="ticker",
    label="ticker",
    op_name="TICKER",
    order=30,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "window", "label": "Window", "type": "number", "default": 3, "min": 1, "max": 12, "step": 1, "integer": True},
        {"key": "direction", "label": "Direction", "type": "select", "default": "left", "options": [{"value": "left", "label": "left"}, {"value": "right", "label": "right"}, {"value": "up", "label": "up"}, {"value": "down", "label": "down"}]},
        {"key": "text", "label": "Text", "type": "text", "default": "PINBALL"},
    ],
    build_op=build_op,
    expand_op=expand,
)

