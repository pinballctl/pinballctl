from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    style = str(params.get("style", "plus") or "plus").strip().lower()
    if style not in ("plus", "x"):
        style = "plus"
    direction = str(params.get("direction", "forward") or "forward").strip().lower()
    if direction not in ("forward", "reverse"):
        direction = "forward"
    return {
        "op": "CROSS_SWEEP",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "width": max(0.01, min(0.4, float(params.get("width", 0.08) or 0.08))),
        "style": style,
        "direction": direction,
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
    width = max(0.01, min(0.4, float(op.get("width", 0.08) or 0.08)))
    style = str(op.get("style") or "plus").strip().lower()
    reverse = str(op.get("direction") or "forward").strip().lower() == "reverse"
    inv_sqrt2 = 1.0 / math.sqrt(2.0)
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        c = 1.0 - phase if reverse else phase
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            if style == "x":
                d1 = abs((x - y) - (2.0 * c - 1.0)) * inv_sqrt2
                d2 = abs((x + y - 1.0) - (2.0 * c - 1.0)) * inv_sqrt2
                d = min(d1, d2)
            else:
                d = min(abs(x - c), abs(y - c))
            inten = max(0.0, 1.0 - (d / width))
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="cross_sweep",
    label="cross sweep",
    op_name="CROSS_SWEEP",
    order=26,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "width", "label": "Width", "type": "number", "default": 0.08, "min": 0.01, "max": 0.4, "step": 0.01},
        {"key": "style", "label": "Style", "type": "select", "default": "plus", "options": [{"value": "plus", "label": "plus"}, {"value": "x", "label": "x"}]},
        {"key": "direction", "label": "Direction", "type": "select", "default": "forward", "options": [{"value": "forward", "label": "forward"}, {"value": "reverse", "label": "reverse"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)

