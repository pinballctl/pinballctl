from __future__ import annotations

import math
import random
from typing import Any, Dict, Tuple

from .registry import PatternPlugin


def _origin(mode: str, cycle: int, seed: int) -> Tuple[float, float]:
    m = mode.strip().lower()
    if m == "top":
        return (0.5, 0.0)
    if m == "bottom":
        return (0.5, 1.0)
    if m == "left":
        return (0.0, 0.5)
    if m == "right":
        return (1.0, 0.5)
    if m == "random":
        rng = random.Random(seed + cycle * 7919)
        return (rng.random(), rng.random())
    return (0.5, 0.5)


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    mode = str(params.get("origin", "center") or "center").strip().lower()
    if mode not in ("center", "top", "bottom", "left", "right", "random"):
        mode = "center"
    return {
        "op": "IMPACT_BURST",
        "target": "*",
        "colour": str(params.get("colour", "#ffffff") or "#ffffff"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "ringWidth": max(0.03, min(0.8, float(params.get("ringWidth", 0.18) or 0.18))),
        "decay": max(0.5, min(8.0, float(params.get("decay", 2.2) or 2.2))),
        "origin": mode,
        "seed": int(params.get("seed", 7) or 7),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=500, maximum=7000)
    step = max(16, min(90, int(period_ms / 36)))
    colour = str(op.get("colour") or "#ffffff")
    ring_w = max(0.03, min(0.8, float(op.get("ringWidth", 0.18) or 0.18)))
    decay = max(0.5, min(8.0, float(op.get("decay", 2.2) or 2.2)))
    mode = str(op.get("origin") or "center")
    seed = int(op.get("seed", 7) or 7)
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    max_d = math.sqrt(2.0)
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        elapsed = t_ms - start_t_ms
        cycle = int(elapsed / period_ms)
        phase = (elapsed % period_ms) / float(period_ms)
        ox, oy = _origin(mode, cycle, seed)
        radius = phase * max_d * 1.2
        envelope = math.exp(-phase * decay)
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            d = math.sqrt((x - ox) ** 2 + (y - oy) ** 2)
            ring = math.exp(-((d - radius) ** 2) / max(1e-6, ring_w * ring_w))
            core = 1.0 if phase < 0.08 and d < (ring_w * 0.8) else 0.0
            intensity = max(0.0, min(1.0, max(core, ring * envelope)))
            frame.append(runtime.pixel_change(p, colour, brightness, intensity))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="impact_burst",
    label="impact burst",
    op_name="IMPACT_BURST",
    order=35,
    params=[
        {"key": "colour", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "ringWidth", "label": "RingWidth", "type": "number", "default": 0.18, "min": 0.03, "max": 0.8, "step": 0.01},
        {"key": "decay", "label": "Decay", "type": "number", "default": 2.2, "min": 0.5, "max": 8.0, "step": 0.1},
        {"key": "origin", "label": "Origin", "type": "select", "default": "center", "options": [{"value": "center", "label": "center"}, {"value": "top", "label": "top"}, {"value": "bottom", "label": "bottom"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}, {"value": "random", "label": "random"}]},
        {"key": "seed", "label": "Seed", "type": "number", "default": 7, "step": 1, "integer": True},
    ],
    build_op=build_op,
    expand_op=expand,
)
