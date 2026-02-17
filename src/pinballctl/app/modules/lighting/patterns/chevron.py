from __future__ import annotations

import math
from typing import Any, Dict

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "top") or "top").strip().lower()
    if direction not in ("top", "bottom", "left", "right"):
        direction = "top"

    spread_deg = float(params.get("spreadDeg", 60) or 60)
    spread_deg = max(20.0, min(140.0, spread_deg))

    length = float(params.get("length", 0.45) or 0.45)
    length = max(0.05, min(1.5, length))

    thickness = float(params.get("thickness", 0.06) or 0.06)
    thickness = max(0.005, min(0.35, thickness))

    tail = float(params.get("tail", 0.8) or 0.8)
    tail = max(0.0, min(1.0, tail))

    return {
        "op": "CHEVRON",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "direction": direction,
        "spreadDeg": spread_deg,
        "length": length,
        "thickness": thickness,
        "tail": tail,
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 40)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    direction = str(op.get("direction") or "top").strip().lower()
    spread_deg = max(20.0, min(140.0, float(op.get("spreadDeg", 60) or 60)))
    length = max(0.05, min(1.5, float(op.get("length", 0.45) or 0.45)))
    thickness = max(0.005, min(0.35, float(op.get("thickness", 0.06) or 0.06)))
    tail = runtime.clamp01(op.get("tail", 0.8), 0.8)

    # Chevron arm line model in local coordinates:
    # r = distance behind tip (along travel axis), q = lateral distance.
    # Arms follow q = +/- k*r where k = tan(spread/2).
    half_angle = max(5.0, min(70.0, spread_deg / 2.0))
    k = math.tan(math.radians(half_angle))
    # Ensure the chevron can reach edge pixels even with conservative length/spread.
    # Without this, defaults can leave side edges untouched on wide layouts.
    min_edge_reach = 0.52
    reach = k * max(1e-6, length)
    if reach < min_edge_reach:
        k *= (min_edge_reach / max(1e-6, reach))
    denom = math.sqrt(1.0 + k * k)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        if direction == "bottom":
            tip_x, tip_y = 0.5, 1.0 - phase
            ux, uy = 0.0, -1.0
        elif direction == "left":
            tip_x, tip_y = phase, 0.5
            ux, uy = 1.0, 0.0
        elif direction == "right":
            tip_x, tip_y = 1.0 - phase, 0.5
            ux, uy = -1.0, 0.0
        else:  # top
            tip_x, tip_y = 0.5, phase
            ux, uy = 0.0, 1.0

        # Left-hand perpendicular to travel axis.
        nx, ny = -uy, ux
        frame = []
        for p in pixels:
            dx = float(p.get("x", 0.5)) - tip_x
            dy = float(p.get("y", 0.5)) - tip_y

            # r = trailing distance from tip; q = lateral offset.
            r = -(dx * ux + dy * uy)
            if r < 0.0 or r > length:
                frame.append(runtime.pixel_change(p, color, brightness, 0.0))
                continue
            q = dx * nx + dy * ny

            arm_gap = abs(q) - (k * r)
            dist_to_arm = abs(arm_gap) / max(1e-6, denom)
            edge = max(0.0, 1.0 - (dist_to_arm / thickness))

            # Optional trailing fade keeps the tip strongest.
            trail = 1.0 - (r / max(1e-6, length)) * (1.0 - tail)
            intensity = max(0.0, min(1.0, edge * trail))
            frame.append(runtime.pixel_change(p, color, brightness, intensity))

        out[t_ms] = frame

    return out


PATTERN = PatternPlugin(
    id="chevron",
    label="chevron",
    op_name="CHEVRON",
    aliases=("chevron_sweep",),
    order=20,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "direction", "label": "Direction", "type": "select", "default": "top", "options": [
            {"value": "top", "label": "top"},
            {"value": "bottom", "label": "bottom"},
            {"value": "left", "label": "left"},
            {"value": "right", "label": "right"},
        ]},
        {"key": "spreadDeg", "label": "SpreadDeg", "type": "number", "default": 60, "min": 20, "max": 140, "step": 1, "integer": True},
        {"key": "length", "label": "Length", "type": "number", "default": 0.45, "min": 0.05, "max": 1.5, "step": 0.01},
        {"key": "thickness", "label": "Thickness", "type": "number", "default": 0.06, "min": 0.005, "max": 0.35, "step": 0.005},
        {"key": "tail", "label": "Tail", "type": "number", "default": 0.8, "min": 0, "max": 1, "step": 0.05},
    ],
    build_op=build_op,
    expand_op=expand,
)
