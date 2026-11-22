from __future__ import annotations

import random
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "RANDOM_STROBE_GROUPS",
        "target": "*",
        "colour": str(params.get("colour", "#ffffff") or "#ffffff"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "groupCount": max(1, min(12, int(params.get("groupCount", 4) or 4))),
        "duty": max(0.05, min(1.0, float(params.get("duty", 0.35) or 0.35))),
        "seed": int(params.get("seed", 11) or 11),
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

    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=120, maximum=3000)
    step = max(16, min(180, int(period_ms / 12)))
    groups = max(1, min(12, int(op.get("groupCount", 4) or 4)))
    duty = max(0.05, min(1.0, float(op.get("duty", 0.35) or 0.35)))
    seed = int(op.get("seed", 11) or 11)
    colour = str(op.get("colour") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        tick = int((t_ms - start_t_ms) / max(1, step))
        rng = random.Random(seed + tick * 3571)
        active = {g for g in range(groups) if rng.random() < duty}
        if not active:
            active.add(rng.randint(0, groups - 1))
        frame = []
        for pi, p in enumerate(pixels):
            ri = rank.get(pi, 0)
            group = int((ri * groups) / total)
            intensity = 1.0 if group in active else 0.0
            frame.append(runtime.pixel_change(p, colour, brightness, intensity))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="random_strobe_groups",
    label="random strobe groups",
    op_name="RANDOM_STROBE_GROUPS",
    order=37,
    params=[
        {"key": "colour", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "groupCount", "label": "GroupCount", "type": "number", "default": 4, "min": 1, "max": 12, "step": 1, "integer": True},
        {"key": "duty", "label": "Duty", "type": "number", "default": 0.35, "min": 0.05, "max": 1.0, "step": 0.05},
        {"key": "seed", "label": "Seed", "type": "number", "default": 11, "step": 1, "integer": True},
    ],
    build_op=build_op,
    expand_op=expand,
)
