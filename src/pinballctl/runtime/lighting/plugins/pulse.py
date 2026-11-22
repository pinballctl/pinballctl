from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    period_ms = int(params.get("periodMs", 600) or 600)
    if period_ms < 100:
        period_ms = 100
    return {"op": "PULSE", "target": "*", "color": str(params.get("color", "#ffffff")), "periodMs": period_ms, "brightness": brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.clamp_step(op.get("periodMs", 600), default=600, lo=100, hi=10000)
    step = max(16, int(period_ms / 20))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    import math
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = 2.0 * math.pi * float(t_ms - start_t_ms) / float(period_ms)
        env = 0.5 * (math.sin(phase - (math.pi / 2.0)) + 1.0)
        out[t_ms] = [runtime.pixel_change(p, color, brightness, env) for p in pixels]
    return out

PATTERN = PatternPlugin(
    id="pulse", label="pulse", op_name="PULSE", order=2,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "periodMs", "label": "PeriodMs", "type": "number", "default": 600, "min": 100, "step": 10, "integer": True},
    ],
    build_op=build_op, expand_op=expand,
)
