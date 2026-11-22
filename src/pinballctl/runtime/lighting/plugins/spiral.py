from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def _origin_xy(origin: str) -> tuple[float, float]:
    o = str(origin or "center").strip().lower()
    if o == "top":
        return 0.5, 0.0
    if o == "bottom":
        return 0.5, 1.0
    if o == "left":
        return 0.0, 0.5
    if o == "right":
        return 1.0, 0.5
    return 0.5, 0.5


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "out") or "out").strip().lower()
    if direction not in ("out", "in"):
        direction = "out"
    return {
        "op": "SPIRAL",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "turns": max(0.5, float(params.get("turns", 2.0) or 2.0)),
        "thickness": max(0.01, min(0.45, float(params.get("thickness", 0.08) or 0.08))),
        "direction": direction,
        "origin": str(params.get("origin", "center") or "center").strip().lower(),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 40)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    turns = max(0.5, float(op.get("turns", 2.0) or 2.0))
    thick = max(0.01, min(0.45, float(op.get("thickness", 0.08) or 0.08)))
    direction = str(op.get("direction") or "out").strip().lower()
    ox, oy = _origin_xy(op.get("origin"))
    sign = 1.0 if direction == "out" else -1.0
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        frame = []
        for p in pixels:
            dx = float(p.get("x", 0.5)) - ox
            dy = float(p.get("y", 0.5)) - oy
            r = math.sqrt(dx * dx + dy * dy) / math.sqrt(0.5)
            a = (math.atan2(dy, dx) + math.pi) / (2.0 * math.pi)
            s = (a + sign * r * turns) % 1.0
            d = abs(((s - phase + 0.5) % 1.0) - 0.5)
            inten = max(0.0, 1.0 - (d / thick))
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="spiral",
    label="spiral",
    op_name="SPIRAL",
    order=21,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "turns", "label": "Turns", "type": "number", "default": 2.0, "min": 0.5, "max": 8.0, "step": 0.1},
        {"key": "thickness", "label": "Thickness", "type": "number", "default": 0.08, "min": 0.01, "max": 0.45, "step": 0.01},
        {"key": "direction", "label": "Direction", "type": "select", "default": "out", "options": [{"value": "out", "label": "out"}, {"value": "in", "label": "in"}]},
        {"key": "origin", "label": "Origin", "type": "select", "default": "center", "options": [{"value": "center", "label": "center"}, {"value": "top", "label": "top"}, {"value": "bottom", "label": "bottom"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)

