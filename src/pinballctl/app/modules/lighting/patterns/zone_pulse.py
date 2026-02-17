from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .registry import PatternPlugin


def _group_key(runtime, pixel: Dict[str, Any], group_by: str, prefix_len: int) -> str:
    fid = str(pixel.get("target") or "")
    row = runtime.fixtures.get(fid, {}) if isinstance(runtime.fixtures.get(fid), dict) else {}
    if group_by == "type":
        return str(row.get("type") or "unknown")
    if group_by == "prefix":
        n = max(1, min(16, int(prefix_len)))
        return fid[:n] if fid else "unknown"
    return fid or "unknown"


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    group_by = str(params.get("groupBy", "fixture") or "fixture").strip().lower()
    if group_by not in ("fixture", "type", "prefix"):
        group_by = "fixture"
    return {
        "op": "ZONE_PULSE",
        "target": "*",
        "color": str(params.get("color", "#ffffff")),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "groupBy": group_by,
        "prefixLen": max(1, min(16, int(params.get("prefixLen", 3) or 3))),
        "overlap": max(0.0, min(1.0, float(params.get("overlap", 0.15) or 0.15))),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out
    period_ms = runtime.speed_period_ms(op.get("speed", 80))
    step = max(16, min(80, int(period_ms / 36)))
    color = str(op.get("color") or "#ffffff")
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)
    group_by = str(op.get("groupBy") or "fixture").strip().lower()
    prefix_len = max(1, min(16, int(op.get("prefixLen", 3) or 3)))
    overlap = max(0.0, min(1.0, float(op.get("overlap", 0.15) or 0.15)))
    groups: Dict[str, List[int]] = {}
    for i, p in enumerate(pixels):
        k = _group_key(runtime, p, group_by, prefix_len)
        groups.setdefault(k, []).append(i)
    order: List[str] = sorted(groups.keys())
    if not order:
        return out
    n = len(order)
    per_group = max(120, int(period_ms / max(1, n)))
    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        phase = int((t_ms - start_t_ms) / max(1, per_group))
        active = phase % n
        local = ((t_ms - start_t_ms) % max(1, per_group)) / float(max(1, per_group))
        pulse = 1.0 - abs(local * 2.0 - 1.0)
        frame = []
        for pi, p in enumerate(pixels):
            inten = 0.0
            for gi in range(n):
                is_active = gi == active
                if not is_active and overlap <= 0.0:
                    continue
                if pi not in groups[order[gi]]:
                    continue
                g = pulse if is_active else (pulse * overlap)
                if g > inten:
                    inten = g
            frame.append(runtime.pixel_change(p, color, brightness, inten))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="zone_pulse",
    label="zone pulse",
    op_name="ZONE_PULSE",
    order=28,
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "groupBy", "label": "GroupBy", "type": "select", "default": "fixture", "options": [{"value": "fixture", "label": "fixture"}, {"value": "type", "label": "type"}, {"value": "prefix", "label": "prefix"}]},
        {"key": "prefixLen", "label": "PrefixLen", "type": "number", "default": 3, "min": 1, "max": 16, "step": 1, "integer": True},
        {"key": "overlap", "label": "Overlap", "type": "number", "default": 0.15, "min": 0.0, "max": 1.0, "step": 0.05},
    ],
    build_op=build_op,
    expand_op=expand,
)

