from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "top") or "top").strip().lower()
    legacy = {"from_top": "top", "from_bottom": "bottom", "from_left": "left", "from_right": "right"}
    direction = legacy.get(direction, direction)
    if direction not in ("top", "bottom", "left", "right"):
        direction = "top"
    band = int(params.get("band", 14) or 14)
    if band < 1:
        band = 1
    if band > 100:
        band = 100
    cm = str(params.get("colorMode", "fixed") or "fixed").strip().lower()
    if cm not in ("fixed", "rainbow"):
        cm = "fixed"
    return {
        "op": "WAVE", "target": "*", "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 120) or 120)),
        "direction": direction, "band": band, "hold": str(params.get("hold", "off") or "off").strip().lower() in ("until_repeat", "on", "true", "1"),
        "colorMode": cm, "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 120))
    step = max(16, min(80, int(period_ms / 40)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    direction = str(op.get("direction") or "top").strip().lower()
    band = int(op.get("band", 14)) if isinstance(op.get("band"), (int, float)) else 14
    width = max(0.02, min(1.0, float(band) / 100.0))
    cm = str(op.get("colorMode") or "fixed").strip().lower()
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        center = (float(t_ms - start_t_ms) % float(period_ms)) / float(period_ms)
        frame = []
        for p in pixels:
            if direction == "bottom":
                pos = 1.0 - float(p.get("y", 0.5))
            elif direction == "left":
                pos = 1.0 - float(p.get("x", 0.5))
            elif direction == "right":
                pos = float(p.get("x", 0.5))
            else:
                pos = float(p.get("y", 0.5))
            dist = abs(pos - center)
            env = max(0.0, 1.0 - (dist / width))
            px_color = runtime.hex_from_hsv(pos + center, 1.0, 1.0) if cm == "rainbow" else color
            frame.append(runtime.pixel_change(p, px_color, brightness, env))
        out[t_ms] = frame
    return out

PATTERN = PatternPlugin(
    id="wave", label="wave", op_name="WAVE", order=5,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "direction", "label": "Direction", "type": "select", "default": "top", "options": [{"value": "top", "label": "top"}, {"value": "bottom", "label": "bottom"}, {"value": "left", "label": "left"}, {"value": "right", "label": "right"}]},
        {"key": "colorMode", "label": "ColourMode", "type": "select", "default": "fixed", "options": [{"value": "fixed", "label": "fixed"}, {"value": "rainbow", "label": "rainbow"}]},
        {"key": "band", "label": "Band", "type": "number", "default": 14, "min": 1, "max": 100, "step": 1, "integer": True},
        {"key": "hold", "label": "Hold", "type": "select", "default": "off", "options": [{"value": "off", "label": "off"}, {"value": "until_repeat", "label": "until repeat"}]},
    ],
    build_op=build_op, expand_op=expand,
)
