from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "HEARTBEAT_DOUBLE",
        "target": "*",
        "colour": str(params.get("colour", "#ff2244") or "#ff2244"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "secondLevel": max(0.1, min(1.0, float(params.get("secondLevel", 0.7) or 0.7))),
        "sharpness": max(0.02, min(0.2, float(params.get("sharpness", 0.055) or 0.055))),
        "brightness": brightness,
    }


def _pulse(phase: float, center: float, width: float, level: float = 1.0) -> float:
    d = phase - center
    return level * math.exp(-(d * d) / max(1e-6, width * width))


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=600, maximum=3200)
    step = max(16, min(90, int(period_ms / 48)))
    colour = str(op.get("colour") or "#ff2244")
    second_level = max(0.1, min(1.0, float(op.get("secondLevel", 0.7) or 0.7)))
    sharp = max(0.02, min(0.2, float(op.get("sharpness", 0.055) or 0.055)))
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = ((t_ms - start_t_ms) % period_ms) / float(period_ms)
        i1 = _pulse(phase, 0.12, sharp, 1.0)
        i2 = _pulse(phase, 0.28, sharp * 0.9, second_level)
        tail = math.exp(-max(0.0, phase - 0.30) * 10.0) * 0.20
        intensity = max(0.0, min(1.0, i1 + i2 + tail))
        frame = [runtime.pixel_change(p, colour, brightness, intensity) for p in pixels]
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="heartbeat_double",
    label="heartbeat double",
    op_name="HEARTBEAT_DOUBLE",
    order=38,
    params=[
        {"key": "colour", "label": "Colour", "type": "color", "default": "#ff2244"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "secondLevel", "label": "SecondLevel", "type": "number", "default": 0.7, "min": 0.1, "max": 1.0, "step": 0.05},
        {"key": "sharpness", "label": "Sharpness", "type": "number", "default": 0.055, "min": 0.02, "max": 0.2, "step": 0.005},
    ],
    build_op=build_op,
    expand_op=expand,
)
