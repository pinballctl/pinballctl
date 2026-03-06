from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "SPARK_GAP",
        "target": "*",
        "colour": str(params.get("colour", "#ffffff") or "#ffffff"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "gapWidth": max(1, int(params.get("gapWidth", 4) or 4)),
        "gapCount": max(1, int(params.get("gapCount", 2) or 2)),
        "softness": max(0.2, min(4.0, float(params.get("softness", 1.4) or 1.4))),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    ordered = sorted(enumerate(pixels), key=lambda it: (float(it[1].get("x", 0.5)), float(it[1].get("y", 0.5))))
    order_idx = [i for i, _ in ordered]
    rank = {pi: ri for ri, pi in enumerate(order_idx)}
    total = max(1, len(order_idx))

    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=400, maximum=9000)
    step = max(16, min(90, int(period_ms / max(4, total))))
    gap_width = max(1, int(op.get("gapWidth", 4) or 4))
    gap_count = max(1, min(8, int(op.get("gapCount", 2) or 2)))
    softness = max(0.2, min(4.0, float(op.get("softness", 1.4) or 1.4)))
    colour = str(op.get("colour") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = ((t_ms - start_t_ms) % period_ms) / float(period_ms)
        frame = []
        for pi, p in enumerate(pixels):
            ri = rank.get(pi, 0)
            darkness = 0.0
            for g in range(gap_count):
                center = (phase * total + (g * total / gap_count)) % total
                dist = abs(ri - center)
                dist = min(dist, total - dist)
                if dist <= gap_width:
                    depth = 1.0 - (dist / max(1.0, float(gap_width)))
                    darkness = max(darkness, pow(depth, softness))
            intensity = max(0.0, 1.0 - darkness)
            frame.append(runtime.pixel_change(p, colour, brightness, intensity))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="spark_gap",
    label="spark gap",
    op_name="SPARK_GAP",
    order=34,
    params=[
        {"key": "colour", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "gapWidth", "label": "GapWidth", "type": "number", "default": 4, "min": 1, "max": 32, "step": 1, "integer": True},
        {"key": "gapCount", "label": "GapCount", "type": "number", "default": 2, "min": 1, "max": 8, "step": 1, "integer": True},
        {"key": "softness", "label": "Softness", "type": "number", "default": 1.4, "min": 0.2, "max": 4.0, "step": 0.1},
    ],
    build_op=build_op,
    expand_op=expand,
)
