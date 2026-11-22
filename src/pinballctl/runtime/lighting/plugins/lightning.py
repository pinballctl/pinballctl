from __future__ import annotations

import math
import random
from typing import Any, Dict

from .registry import PatternPlugin


def _seg_dist(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    c1 = vx * wx + vy * wy
    if c1 <= 0.0:
        dx = px - ax
        dy = py - ay
        return math.sqrt(dx * dx + dy * dy)
    c2 = vx * vx + vy * vy
    if c2 <= 1e-9:
        dx = px - ax
        dy = py - ay
        return math.sqrt(dx * dx + dy * dy)
    t = min(1.0, max(0.0, c1 / c2))
    qx = ax + t * vx
    qy = ay + t * vy
    dx = px - qx
    dy = py - qy
    return math.sqrt(dx * dx + dy * dy)


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "LIGHTNING",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "density": max(0.01, min(1.0, float(params.get("density", 0.15) or 0.15))),
        "width": max(0.005, min(0.2, float(params.get("width", 0.035) or 0.035))),
        "decay": max(0.0, min(1.0, float(params.get("decay", 0.45) or 0.45))),
        "branches": max(1, min(6, int(params.get("branches", 2) or 2))),
        "seed": int(params.get("seed", 1337) or 1337),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(90, int(period_ms / 32)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    density = max(0.01, min(1.0, float(op.get("density", 0.15) or 0.15)))
    width = max(0.005, min(0.2, float(op.get("width", 0.035) or 0.035)))
    decay = max(0.0, min(1.0, float(op.get("decay", 0.45) or 0.45)))
    branches = max(1, min(6, int(op.get("branches", 2) or 2)))
    rng = random.Random(int(op.get("seed", 1337) or 1337))
    heat = [0.0 for _ in pixels]
    cool = max(0.0, min(0.999, 1.0 - decay))
    strike_chance = min(0.95, 0.08 + density * 0.42)
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        for i in range(len(heat)):
            heat[i] *= cool
        if rng.random() < strike_chance:
            main_x = rng.random()
            main_end_x = min(1.0, max(0.0, main_x + (rng.random() - 0.5) * 0.35))
            segs = [(main_x, 0.0, main_end_x, 1.0, 1.0)]
            for _ in range(branches - 1):
                bx = min(1.0, max(0.0, main_x + (rng.random() - 0.5) * 0.6))
                by = rng.random() * 0.65
                ex = min(1.0, max(0.0, bx + (rng.random() - 0.5) * 0.45))
                ey = min(1.0, by + 0.2 + rng.random() * 0.6)
                segs.append((bx, by, ex, ey, 0.65))
            for pi, p in enumerate(pixels):
                x = float(p.get("x", 0.5))
                y = float(p.get("y", 0.5))
                m = 0.0
                for ax, ay, bx, by, gain in segs:
                    d = _seg_dist(x, y, ax, ay, bx, by)
                    v = max(0.0, 1.0 - (d / width)) * gain
                    if v > m:
                        m = v
                if m > 0.0:
                    heat[pi] = min(1.0, max(heat[pi], m))
        frame = []
        for pi, p in enumerate(pixels):
            frame.append(runtime.pixel_change(p, color, brightness, heat[pi]))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="lightning",
    label="lightning",
    op_name="LIGHTNING",
    order=22,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "density", "label": "Density", "type": "number", "default": 0.15, "min": 0.01, "max": 1.0, "step": 0.01},
        {"key": "width", "label": "Width", "type": "number", "default": 0.035, "min": 0.005, "max": 0.2, "step": 0.005},
        {"key": "decay", "label": "Decay", "type": "number", "default": 0.45, "min": 0.0, "max": 1.0, "step": 0.05},
        {"key": "branches", "label": "Branches", "type": "number", "default": 2, "min": 1, "max": 6, "step": 1, "integer": True},
        {"key": "seed", "label": "Seed", "type": "number", "default": 1337, "min": 0, "step": 1, "integer": True},
    ],
    build_op=build_op,
    expand_op=expand,
)

