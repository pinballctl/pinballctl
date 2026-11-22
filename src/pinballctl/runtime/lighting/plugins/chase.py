from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "CHASE", "target": "*", "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 120) or 120)),
        "width": max(1, int(params.get("width", 3) or 3)),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    step = runtime.clamp_step(op.get("speed", 120), default=120)
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    width = int(op.get("width", 3)) if isinstance(op.get("width"), (int, float)) else 3
    if width < 1:
        width = 1
    idx = 0
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        frame = []
        for p in pixels:
            n = int(p.get("pixelCount", 1)); i = int(p.get("pixelIndex", 0) or 0)
            head = idx % max(1, n)
            dist = (i - head) % max(1, n)
            frame.append(runtime.pixel_change(p, color, brightness, 1.0 if dist < width else 0.0))
        out[t_ms] = frame
        idx += 1
    return out

PATTERN = PatternPlugin(
    id="chase", label="chase", op_name="CHASE", order=4,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "width", "label": "Width", "type": "number", "default": 3, "min": 1, "step": 1, "integer": True},
    ],
    build_op=build_op, expand_op=expand,
)
