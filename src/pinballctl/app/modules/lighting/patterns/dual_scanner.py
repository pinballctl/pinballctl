from __future__ import annotations

from typing import Any, Dict

from .registry import PatternPlugin


def _ping_pong(idx: int, total: int) -> int:
    if total <= 1:
        return 0
    span = (total - 1) * 2
    x = idx % span
    return x if x < total else (span - x)


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    direction = str(params.get("direction", "x") or "x").strip().lower()
    if direction not in ("x", "y"):
        direction = "x"
    return {
        "op": "DUAL_SCANNER",
        "target": "*",
        "colour1": str(params.get("colour1", "#00bfff") or "#00bfff"),
        "colour2": str(params.get("colour2", "#ff2a6d") or "#ff2a6d"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "trail": max(1, int(params.get("trail", 4) or 4)),
        "direction": direction,
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    direction = str(op.get("direction") or "x").strip().lower()
    key = (lambda p: (float(p.get("x", 0.5)), float(p.get("y", 0.5)))) if direction == "x" else (lambda p: (float(p.get("y", 0.5)), float(p.get("x", 0.5))))
    ordered = sorted(enumerate(pixels), key=lambda it: key(it[1]))
    order_idx = [i for i, _ in ordered]
    rank = {pi: ri for ri, pi in enumerate(order_idx)}
    total = max(1, len(order_idx))

    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=300, maximum=6000)
    step = max(16, min(80, int(period_ms / max(2, total))))
    trail = max(1, min(16, int(op.get("trail", 4) or 4)))
    colour1 = str(op.get("colour1") or "#00bfff")
    colour2 = str(op.get("colour2") or "#ff2a6d")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    frame_idx = 0
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        head1 = _ping_pong(frame_idx, total)
        head2 = (total - 1) - head1
        frame = []
        for pi, p in enumerate(pixels):
            ri = rank.get(pi, 0)
            d1 = abs(ri - head1)
            d2 = abs(ri - head2)
            i1 = max(0.0, 1.0 - (float(d1) / float(trail)))
            i2 = max(0.0, 1.0 - (float(d2) / float(trail)))
            if i1 >= i2:
                frame.append(runtime.pixel_change(p, colour1, brightness, i1))
            else:
                frame.append(runtime.pixel_change(p, colour2, brightness, i2))
        out[t_ms] = frame
        frame_idx += 1
    return out


PATTERN = PatternPlugin(
    id="dual_scanner",
    label="dual scanner",
    op_name="DUAL_SCANNER",
    order=33,
    params=[
        {"key": "colour1", "label": "Colour 1", "type": "color", "default": "#00bfff"},
        {"key": "colour2", "label": "Colour 2", "type": "color", "default": "#ff2a6d"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "trail", "label": "Trail", "type": "number", "default": 4, "min": 1, "max": 16, "step": 1, "integer": True},
        {"key": "direction", "label": "Direction", "type": "select", "default": "x", "options": [{"value": "x", "label": "x"}, {"value": "y", "label": "y"}]},
    ],
    build_op=build_op,
    expand_op=expand,
)
