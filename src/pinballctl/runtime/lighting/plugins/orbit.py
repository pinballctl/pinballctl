from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def _perimeter_point(t: float) -> tuple[float, float]:
    v = t % 1.0
    if v < 0.25:
        p = v / 0.25
        return p, 0.0
    if v < 0.5:
        p = (v - 0.25) / 0.25
        return 1.0, p
    if v < 0.75:
        p = (v - 0.5) / 0.25
        return 1.0 - p, 1.0
    p = (v - 0.75) / 0.25
    return 0.0, 1.0 - p


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "clockwise") or "clockwise").strip().lower()
    if direction not in ("clockwise", "counterclockwise"):
        direction = "clockwise"
    return {
        "op": "ORBIT",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "radius": max(0.01, min(0.25, float(params.get("radius", 0.06) or 0.06))),
        "tail": max(0.0, min(1.0, float(params.get("tail", 0.5) or 0.5))),
        "direction": direction,
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 50)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    radius = max(0.01, min(0.25, float(op.get("radius", 0.06) or 0.06)))
    tail = max(0.0, min(1.0, float(op.get("tail", 0.5) or 0.5)))
    clockwise = str(op.get("direction") or "clockwise").strip().lower() == "clockwise"
    tail_steps = max(1, int(2 + tail * 12))
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        head_phase = phase if clockwise else (1.0 - phase)
        samples = []
        for i in range(tail_steps):
            back = (float(i) / float(max(1, tail_steps - 1))) * (0.25 + tail * 0.6)
            s = head_phase - back if clockwise else head_phase + back
            x, y = _perimeter_point(s)
            gain = 1.0 - (float(i) / float(max(1, tail_steps)))
            samples.append((x, y, gain))
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            m = 0.0
            for sx, sy, gain in samples:
                dx = x - sx
                dy = y - sy
                d = math.sqrt(dx * dx + dy * dy)
                base = max(0.0, 1.0 - (d / radius))
                # Aggressive core profile to avoid washed/faded look.
                v = (base ** 0.35) * (0.8 + 0.2 * gain)
                if v > m:
                    m = v
            # Strong active floor so lit pixels look clearly ON.
            inten = min(1.0, m if m < 0.01 else (0.22 + 0.78 * m))
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="orbit",
    label="orbit",
    op_name="ORBIT",
    order=23,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "radius", "label": "Radius", "type": "number", "default": 0.06, "min": 0.01, "max": 0.25, "step": 0.01},
        {"key": "tail", "label": "Tail", "type": "number", "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.05},
        {"key": "direction", "label": "Direction", "type": "select", "default": "clockwise", "options": [{"value": "clockwise", "label": "clockwise"}, {"value": "counterclockwise", "label": "counterclockwise"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)
