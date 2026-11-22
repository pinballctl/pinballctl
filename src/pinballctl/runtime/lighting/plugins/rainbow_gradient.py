from __future__ import annotations

from typing import Any, Dict

from .registry import PatternPlugin


def _clamp01(v: Any, default: float = 1.0) -> float:
    try:
        x = float(v)
    except Exception:
        x = float(default)
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    speed = int(params.get("speed", 70) or 70)
    if speed < 1:
        speed = 1
    if speed > 100:
        speed = 100
    spread = int(params.get("spread", 100) or 100)
    if spread < 10:
        spread = 10
    if spread > 400:
        spread = 400
    return {
        "op": "RAINBOW_GRADIENT",
        "target": "*",
        "speed": speed,
        "spread": spread,
        "saturation": _clamp01(params.get("saturation", 1.0), 1.0),
        "brightness": _clamp01(params.get("brightness", brightness), brightness),
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 70))
    step = max(16, min(80, int(period_ms / 40)))
    spread = runtime.clamp_step(op.get("spread", 100), default=100, lo=10, hi=400) / 100.0
    saturation = runtime.clamp01(op.get("saturation", 1.0), 1.0)
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = ((float(t_ms - start_t_ms) / float(period_ms)) % 1.0)
        frame = []
        for p in pixels:
            hue = (phase + float(p.get("pixelPos", 0.0)) * spread) % 1.0
            frame.append(runtime.pixel_change(p, runtime.hex_from_hsv(hue, saturation, 1.0), brightness, 1.0))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="rainbow_gradient",
    label="rainbow gradient",
    op_name="RAINBOW_GRADIENT",
    order=6,
    aliases=("moving_rainbow",),
    params=[
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 70, "min": 1, "max": 100, "step": 1, "integer": True},
        {"key": "spread", "label": "Spread", "type": "number", "default": 100, "min": 10, "max": 400, "step": 5, "integer": True},
        {"key": "saturation", "label": "Saturation", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
    ],
    build_op=build_op,
    expand_op=expand,
)
