from __future__ import annotations

import math
import random
from typing import Any, Dict

from .registry import PatternPlugin


def _origin_xy(origin: str) -> tuple[float, float]:
    o = str(origin or "center").strip().lower()
    if o == "top":
        return 0.5, 0.0
    if o == "bottom":
        return 0.5, 1.0
    if o == "left":
        return 0.0, 0.5
    if o == "right":
        return 1.0, 0.5
    return 0.5, 0.5


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "COMET_BURST",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "count": max(1, min(12, int(params.get("count", 5) or 5))),
        "spreadDeg": max(10.0, min(360.0, float(params.get("spreadDeg", 140) or 140))),
        "tail": max(0.02, min(1.0, float(params.get("tail", 0.35) or 0.35))),
        "width": max(0.005, min(0.2, float(params.get("width", 0.03) or 0.03))),
        "origin": str(params.get("origin", "center") or "center").strip().lower(),
        "seed": int(params.get("seed", 1337) or 1337),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 42)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    count = max(1, min(12, int(op.get("count", 5) or 5)))
    spread = math.radians(max(10.0, min(360.0, float(op.get("spreadDeg", 140) or 140))))
    tail = max(0.02, min(1.0, float(op.get("tail", 0.35) or 0.35)))
    width = max(0.005, min(0.2, float(op.get("width", 0.03) or 0.03)))
    ox, oy = _origin_xy(op.get("origin"))
    rng = random.Random(int(op.get("seed", 1337) or 1337))
    base_angle = rng.random() * 2.0 * math.pi
    dirs = []
    if spread >= (2.0 * math.pi - 1e-6):
        for i in range(count):
            a = base_angle + (2.0 * math.pi * float(i) / float(count))
            dirs.append((math.cos(a), math.sin(a)))
    else:
        start_a = base_angle - spread * 0.5
        for i in range(count):
            t = 0.5 if count == 1 else (float(i) / float(count - 1))
            a = start_a + t * spread
            dirs.append((math.cos(a), math.sin(a)))
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            m = 0.0
            for i, (ux, uy) in enumerate(dirs):
                head = (phase - (float(i) / float(max(1, count)))) % 1.0
                hx = ox + ux * head
                hy = oy + uy * head
                dx = x - hx
                dy = y - hy
                along = -(dx * ux + dy * uy)
                side = abs(-dx * uy + dy * ux)
                if along < 0.0 or along > tail:
                    continue
                core = max(0.0, 1.0 - (side / width))
                trail = 1.0 - (along / max(0.0001, tail))
                v = core * trail
                if v > m:
                    m = v
            frame.append(runtime.pixel_change(p, color, brightness, m))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="comet_burst",
    label="comet burst",
    op_name="COMET_BURST",
    order=25,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "count", "label": "Count", "type": "number", "default": 5, "min": 1, "max": 12, "step": 1, "integer": True},
        {"key": "spreadDeg", "label": "SpreadDeg", "type": "number", "default": 140, "min": 10, "max": 360, "step": 1, "integer": True},
        {"key": "tail", "label": "Tail", "type": "number", "default": 0.35, "min": 0.02, "max": 1.0, "step": 0.01},
        {"key": "width", "label": "Width", "type": "number", "default": 0.03, "min": 0.005, "max": 0.2, "step": 0.005},
        {"key": "origin", "label": "Origin", "type": "select", "default": "center", "options": [{"value": "center", "label": "center"}, {"value": "top", "label": "top"}, {"value": "bottom", "label": "bottom"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}]},
        {"key": "seed", "label": "Seed", "type": "number", "default": 1337, "min": 0, "step": 1, "integer": True},
    ],
    build_op=build_op,
    expand_op=expand,
)

