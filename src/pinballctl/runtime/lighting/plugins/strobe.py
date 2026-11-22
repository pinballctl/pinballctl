from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"STROBE","target":"*","color":str(params.get("color", "#ffffff")),"rateHz":float(params.get("rateHz",8) or 8),"dutyCycle":float(params.get("dutyCycle",0.5) or 0.5),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    rate=float(op.get("rateHz",8.0) or 8.0); rate=max(0.5,rate); period=max(2,int(round(1000.0/rate))); step=max(16,int(period/4))
    duty=runtime.clamp01(op.get("dutyCycle",0.5),0.5); color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        on=((t_ms-start_t_ms)%period) < int(round(period*duty)); out[t_ms]=[runtime.pixel_change(p,color,brightness,1.0 if on else 0.0) for p in pixels]

    return out

PATTERN = PatternPlugin(
    id="strobe", label="strobe", op_name="STROBE", order=7,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'rateHz', 'label': 'RateHz', 'type': 'number', 'default': 8, 'min': 0.5, 'max': 60, 'step': 0.5}, {'key': 'dutyCycle', 'label': 'DutyCycle', 'type': 'number', 'default': 0.5, 'min': 0.05, 'max': 0.95, 'step': 0.05}],
    build_op=build_op, expand_op=expand,
)
