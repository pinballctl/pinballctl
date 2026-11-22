from __future__ import annotations

from typing import Any, Dict, List, Tuple

from .registry import PatternPlugin


def _parse_steps(raw: Any) -> List[Tuple[str, int, float]]:
    text = str(raw or "").strip()
    if not text:
        text = "#ff0000:250:1.00;#000000:250:1.00"
    out: List[Tuple[str, int, float]] = []
    for token in [t.strip() for t in text.replace("\n", ";").replace(",", ";").split(";") if t.strip()]:
        intensity = 1.0
        if ":" in token:
            parts = token.split(":")
            if len(parts) >= 3:
                c, ms, iv = parts[0], parts[1], parts[2]
                try:
                    intensity = float(iv)
                except Exception:
                    intensity = 1.0
            else:
                c, ms = token.split(":", 1)
        elif "@" in token:
            parts = token.split("@")
            if len(parts) >= 3:
                c, ms, iv = parts[0], parts[1], parts[2]
                try:
                    intensity = float(iv)
                except Exception:
                    intensity = 1.0
            else:
                c, ms = token.split("@", 1)
        else:
            c, ms = token, "250"
        colour = str(c or "#ffffff").strip()
        try:
            hold = int(float(ms))
        except Exception:
            hold = 250
        if hold < 20:
            hold = 20
        if hold > 10_000:
            hold = 10_000
        if intensity < 0.0:
            intensity = 0.0
        if intensity > 1.0:
            intensity = 1.0
        out.append((colour, hold, float(intensity)))
    if not out:
        out = [("#ff0000", 250, 1.0), ("#000000", 250, 1.0)]
    return out


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {
        "op": "STEP_SEQUENCE",
        "target": "*",
        "steps": str(params.get("steps", "#ff0000:250:1.00;#000000:250:1.00") or "#ff0000:250:1.00;#000000:250:1.00"),
        "brightness": brightness,
    }


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    steps = _parse_steps(op.get("steps"))
    cycle = sum(ms for _, ms, _ in steps)
    if cycle <= 0:
        return out

    step_ms = max(16, min(100, min(ms for _, ms, _ in steps)))
    brightness = runtime.clamp01(op.get("brightness", 1.0), 1.0)

    for t_ms in runtime.iter_frames(start_t_ms, duration_ms, step_ms):
        elapsed = (t_ms - start_t_ms) % cycle
        acc = 0
        colour = steps[0][0]
        intensity = steps[0][2]
        for c, hold, level in steps:
            acc += hold
            if elapsed < acc:
                colour = c
                intensity = level
                break
        frame = [runtime.pixel_change(p, colour, brightness, intensity) for p in pixels]
        out[t_ms] = frame
    return out


PATTERN = PatternPlugin(
    id="step_sequence",
    label="step sequence",
    op_name="STEP_SEQUENCE",
    order=32,
    params=[
        {"key": "steps", "label": "Steps", "type": "text", "default": "#ff0000:250:1.00;#000000:250:1.00"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
    ],
    build_op=build_op,
    expand_op=expand,
)
