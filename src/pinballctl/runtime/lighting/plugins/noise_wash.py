from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    cm = str(params.get("colorMode", "fixed") or "fixed").strip().lower()
    if cm not in ("fixed", "rainbow"):
        cm = "fixed"
    return {
        "op": "NOISE_WASH",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "scale": max(0.2, min(4.0, float(params.get("scale", 1.3) or 1.3))),
        "contrast": max(0.2, min(3.0, float(params.get("contrast", 1.1) or 1.1))),
        "colorMode": cm,
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 48)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    scale = max(0.2, min(4.0, float(op.get("scale", 1.3) or 1.3)))
    contrast = max(0.2, min(3.0, float(op.get("contrast", 1.1) or 1.1)))
    cm = str(op.get("colorMode") or "fixed").strip().lower()
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        tt = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        w = 2.0 * math.pi
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            n1 = math.sin(w * (x * scale + tt * 0.85))
            n2 = math.sin(w * (y * scale * 0.9 - tt * 0.63))
            n3 = math.sin(w * ((x + y) * scale * 0.65 + tt * 0.42))
            n = (n1 + n2 + n3) / 3.0
            v = (n * 0.5 + 0.5)
            v = max(0.0, min(1.0, pow(v, 1.0 / contrast)))
            px_color = runtime.hex_from_hsv((x * 0.4 + y * 0.3 + tt * 0.8) % 1.0, 1.0, 1.0) if cm == "rainbow" else color
            frame.append(runtime.pixel_change(p, px_color, brightness, v))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="noise_wash",
    label="noise wash",
    op_name="NOISE_WASH",
    order=27,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "scale", "label": "Scale", "type": "number", "default": 1.3, "min": 0.2, "max": 4.0, "step": 0.1},
        {"key": "contrast", "label": "Contrast", "type": "number", "default": 1.1, "min": 0.2, "max": 3.0, "step": 0.1},
        {"key": "colorMode", "label": "ColourMode", "type": "select", "default": "fixed", "options": [{"value": "fixed", "label": "fixed"}, {"value": "rainbow", "label": "rainbow"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)

