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
    switch_ms = int(params.get("switchMs", 350) or 350)
    if switch_ms < 50:
        switch_ms = 50
    colour1 = str(params.get("colour1", "#ff0000") or "#ff0000")
    colour2 = str(params.get("colour2", "#000000") or "#000000")
    return {
        "op": "ALTERNATING",
        "target": "*",
        "switchMs": switch_ms,
        "colour1": colour1,
        "colour2": colour2,
        "brightness": _clamp01(params.get("brightness", brightness), brightness),
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    colour1 = str(op.get("colour1") or "#ff0000")
    colour2 = str(op.get("colour2") or "#000000")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    switch_ms = runtime.clamp_step(op.get("switchMs", 350), default=350, lo=50, hi=10000)
    t1 = start_t_ms
    t2 = min(duration_ms - 1, start_t_ms + switch_ms) if duration_ms > 0 else start_t_ms

    frame_a = []
    frame_b = []
    for idx, p in enumerate(pixels):
        even = (idx % 2) == 0
        frame_a.append(runtime.pixel_change(p, colour1 if even else colour2, brightness, 1.0))
        frame_b.append(runtime.pixel_change(p, colour2 if even else colour1, brightness, 1.0))
    out[t1] = frame_a
    if t2 > t1:
        out[t2] = frame_b
    return out


PATTERN = PatternPlugin(
    id="alternating",
    label="alternating",
    op_name="ALTERNATING",
    order=4,
    params=[
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "switchMs", "label": "SwitchMs", "type": "number", "default": 350, "min": 50, "step": 10, "integer": True},
        {"key": "colour1", "label": "Colour 1", "type": "color", "default": "#ff0000"},
        {"key": "colour2", "label": "Colour 2", "type": "color", "default": "#000000"},
    ],
    build_op=build_op,
    expand_op=expand,
)
