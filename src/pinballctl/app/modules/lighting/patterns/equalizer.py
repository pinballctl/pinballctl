from __future__ import annotations

import random
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "bottom") or "bottom").strip().lower()
    if direction not in ("bottom", "top", "left", "right"):
        direction = "bottom"
    return {
        "op": "EQUALIZER",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "bands": max(2, min(64, int(params.get("bands", 10) or 10))),
        "smoothing": max(0.0, min(1.0, float(params.get("smoothing", 0.65) or 0.65))),
        "direction": direction,
        "seed": int(params.get("seed", 1337) or 1337),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(120, int(period_ms / 18)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    bands = max(2, min(64, int(op.get("bands", 10) or 10)))
    smooth = max(0.0, min(1.0, float(op.get("smoothing", 0.65) or 0.65)))
    direction = str(op.get("direction") or "bottom").strip().lower()
    rng = random.Random(int(op.get("seed", 1337) or 1337))
    levels = [rng.random() for _ in range(bands)]
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        for i in range(bands):
            target = rng.random() * rng.random()
            levels[i] = levels[i] * smooth + target * (1.0 - smooth)
        frame = []
        for p in pixels:
            x = min(1.0, max(0.0, float(p.get("x", 0.5))))
            y = min(1.0, max(0.0, float(p.get("y", 0.5))))
            if direction in ("bottom", "top"):
                bi = min(bands - 1, max(0, int(x * bands)))
                level = levels[bi]
                pos = y if direction == "bottom" else (1.0 - y)
            else:
                bi = min(bands - 1, max(0, int(y * bands)))
                level = levels[bi]
                pos = x if direction == "right" else (1.0 - x)
            edge = 0.08
            cutoff = 1.0 - level
            inten = max(0.0, min(1.0, (pos - cutoff) / max(0.0001, edge)))
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="equalizer",
    label="equalizer",
    op_name="EQUALIZER",
    order=24,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "bands", "label": "Bands", "type": "number", "default": 10, "min": 2, "max": 64, "step": 1, "integer": True},
        {"key": "smoothing", "label": "Smoothing", "type": "number", "default": 0.65, "min": 0.0, "max": 1.0, "step": 0.05},
        {"key": "direction", "label": "Direction", "type": "select", "default": "bottom", "options": [{"value": "bottom", "label": "bottom"}, {"value": "top", "label": "top"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}]},
        {"key": "seed", "label": "Seed", "type": "number", "default": 1337, "min": 0, "step": 1, "integer": True},
    ],
    build_op=build_op,
    expand_op=expand,
)

