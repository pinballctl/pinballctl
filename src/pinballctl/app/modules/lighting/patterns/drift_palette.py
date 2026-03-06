from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .registry import PatternPlugin


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    s = str(value or "").strip()
    if len(s) == 7 and s.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in s[1:]):
        return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16))
    return (255, 255, 255)


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{max(0, min(255, int(r))):02x}{max(0, min(255, int(g))):02x}{max(0, min(255, int(b))):02x}"


def _lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def _palette(raw: Any) -> List[Tuple[int, int, int]]:
    text = str(raw or "").strip()
    if not text:
        text = "#ff0040,#ffb000,#00d1ff,#7cff00"
    out = []
    for token in [t.strip() for t in text.replace("\n", ",").replace(";", ",").split(",") if t.strip()]:
        out.append(_hex_to_rgb(token))
    if len(out) < 2:
        out = [(255, 0, 64), (0, 209, 255)]
    return out


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "DRIFT_PALETTE",
        "target": "*",
        "palette": str(params.get("palette", "#ff0040,#ffb000,#00d1ff,#7cff00") or "#ff0040,#ffb000,#00d1ff,#7cff00"),
        "speed": max(1, int(params.get("speed", 80) or 80)),
        "spread": max(0.0, min(4.0, float(params.get("spread", 1.2) or 1.2))),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    pal = _palette(op.get("palette"))
    plen = len(pal)
    period_ms = runtime.speed_period_ms(op.get("speed", 80), minimum=1200, maximum=12000)
    step = max(16, min(90, int(period_ms / 80)))
    spread = max(0.0, min(4.0, float(op.get("spread", 1.2) or 1.2)))
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step):
        tt = ((t_ms - start_t_ms) % period_ms) / float(period_ms)
        frame = []
        for p in pixels:
            x = float(p.get("x", 0.5))
            y = float(p.get("y", 0.5))
            phase = (tt * plen + (x * 0.7 + y * 0.3) * spread) % plen
            i0 = int(phase) % plen
            i1 = (i0 + 1) % plen
            frac = phase - int(phase)
            c0 = pal[i0]
            c1 = pal[i1]
            rgb = (_lerp(c0[0], c1[0], frac), _lerp(c0[1], c1[1], frac), _lerp(c0[2], c1[2], frac))
            frame.append(runtime.pixel_change(p, _rgb_to_hex(rgb), brightness, 1.0))
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="drift_palette",
    label="drift palette",
    op_name="DRIFT_PALETTE",
    order=36,
    params=[
        {"key": "palette", "label": "Palette", "type": "text", "default": "#ff0040,#ffb000,#00d1ff,#7cff00"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "speed", "label": "Speed", "type": "number", "default": 80, "min": 1, "step": 1, "integer": True},
        {"key": "spread", "label": "Spread", "type": "number", "default": 1.2, "min": 0.0, "max": 4.0, "step": 0.1},
    ],
    build_op=build_op,
    expand_op=expand,
)
