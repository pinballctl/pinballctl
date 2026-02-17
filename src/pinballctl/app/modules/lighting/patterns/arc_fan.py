from __future__ import annotations

import math
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
    direction = str(params.get("direction", "clockwise") or "clockwise").strip().lower()
    if direction not in ("clockwise", "counterclockwise"):
        direction = "clockwise"
    return {
        "op": "ARC_FAN",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "beamCount": max(1, min(8, int(params.get("beamCount", 3) or 3))),
        "beamSpreadDeg": max(0.0, min(160.0, float(params.get("beamSpreadDeg", 25) or 25))),
        "beamWidthDeg": max(2.0, min(90.0, float(params.get("beamWidthDeg", 16) or 16))),
        "tail": max(0.0, min(1.0, float(params.get("tail", 0.65) or 0.65))),
        "origin": str(params.get("origin", "center") or "center").strip().lower(),
        "direction": direction,
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
    beam_count = max(1, min(8, int(op.get("beamCount", 3) or 3)))
    beam_spread = math.radians(max(0.0, min(160.0, float(op.get("beamSpreadDeg", 25) or 25))))
    beam_width = math.radians(max(2.0, min(90.0, float(op.get("beamWidthDeg", 16) or 16))))
    tail = runtime.clamp01(op.get("tail", 0.65), 0.65)
    ox, oy = _origin_xy(op.get("origin"))
    clockwise = str(op.get("direction") or "clockwise").strip().lower() == "clockwise"
    half_span = beam_spread * 0.5
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        head = (phase if clockwise else (1.0 - phase)) * (2.0 * math.pi)
        beam_angles = []
        for i in range(beam_count):
            q = 0.5 if beam_count == 1 else (float(i) / float(beam_count - 1))
            off = -half_span + q * beam_spread
            beam_angles.append(head + off)
        frame = []
        for p in pixels:
            dx = float(p.get("x", 0.5)) - ox
            dy = float(p.get("y", 0.5)) - oy
            dist = math.sqrt(dx * dx + dy * dy)
            ang = math.atan2(dy, dx)
            radial = 1.0 - min(1.0, dist / math.sqrt(0.5)) * (1.0 - tail)
            m = 0.0
            for ba in beam_angles:
                d = abs((ang - ba + math.pi) % (2.0 * math.pi) - math.pi)
                v = max(0.0, 1.0 - (d / max(0.0001, beam_width)))
                if v > m:
                    m = v
            inten = max(0.0, min(1.0, m * radial))
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="arc_fan",
    label="arc fan",
    op_name="ARC_FAN",
    order=29,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "beamCount", "label": "BeamCount", "type": "number", "default": 3, "min": 1, "max": 8, "step": 1, "integer": True},
        {"key": "beamSpreadDeg", "label": "BeamSpreadDeg", "type": "number", "default": 25, "min": 0, "max": 160, "step": 1, "integer": True},
        {"key": "beamWidthDeg", "label": "BeamWidthDeg", "type": "number", "default": 16, "min": 2, "max": 90, "step": 1, "integer": True},
        {"key": "tail", "label": "Tail", "type": "number", "default": 0.65, "min": 0.0, "max": 1.0, "step": 0.05},
        {"key": "origin", "label": "Origin", "type": "select", "default": "center", "options": [{"value": "center", "label": "center"}, {"value": "top", "label": "top"}, {"value": "bottom", "label": "bottom"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}]},
        {"key": "direction", "label": "Direction", "type": "select", "default": "clockwise", "options": [{"value": "clockwise", "label": "clockwise"}, {"value": "counterclockwise", "label": "counterclockwise"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)

