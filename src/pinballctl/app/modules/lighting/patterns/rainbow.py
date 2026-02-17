from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    speed = int(params.get("speed", 80) or 80)
    segments = int(params.get("segments", 8) or 8)
    if segments < 1:
        segments = 1
    if segments > 64:
        segments = 64
    return {
        "op": "RAINBOW", "target": "*", "speed": max(1, speed),
        "segments": segments, "saturation": runtime_clamp(params.get("saturation", 0.9)), "brightness": brightness,
    }


def runtime_clamp(v):
    try:
        x = float(v)
    except Exception:
        x = 1.0
    if x < 0:
        return 0.0
    if x > 1:
        return 1.0
    return x


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 40)))
    saturation = runtime.clamp01(op.get("saturation", 1.0), 1.0)
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    segments = int(op.get("segments", 1)) if isinstance(op.get("segments"), (int, float)) else 1
    if segments < 1:
        segments = 1
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        base_hue = ((float(t_ms - start_t_ms) / float(period_ms)) % 1.0)
        frame = []
        for p in pixels:
            hue = (base_hue + float(p.get("pixelPos", 0.0)) * float(segments)) % 1.0
            frame.append(runtime.pixel_change(p, runtime.hex_from_hsv(hue, saturation, 1.0), brightness, 1.0))
        out[t_ms] = frame
    return out

PATTERN = PatternPlugin(
    id="rainbow", label="rainbow", op_name="RAINBOW", order=3,
    aliases=("colour_wheel", "color_wheel"),
    params=[
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "segments", "label": "Segments", "type": "number", "default": 8, "min": 1, "max": 64, "step": 1, "integer": True},
        {"key": "saturation", "label": "Saturation", "type": "number", "default": 0.9, "min": 0, "max": 1, "step": 0.05},
    ],
    build_op=build_op, expand_op=expand,
)
