from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"BREATH","target":"*","color":str(params.get("color", "#ffffff")),"periodMs":max(200,int(params.get("periodMs",1800) or 1800)),"minIntensity":float(params.get("minIntensity",0.05) or 0.05),"maxIntensity":float(params.get("maxIntensity",1.0) or 1.0),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period=runtime.clamp_step(op.get("periodMs",1800),default=1800,lo=200,hi=20000); step=max(16,int(period/30)); min_i=runtime.clamp01(op.get("minIntensity",0.05),0.05); max_i=runtime.clamp01(op.get("maxIntensity",1.0),1.0)
    if max_i<min_i: max_i=min_i
    color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        phase=2.0*math.pi*float(t_ms-start_t_ms)/float(period); env=0.5*(math.sin(phase-(math.pi/2.0))+1.0); inten=min_i+(max_i-min_i)*env
        out[t_ms]=[runtime.pixel_change(p,color,brightness,inten) for p in pixels]

    return out

PATTERN = PatternPlugin(
    id="breath", label="breath", op_name="BREATH", order=8,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'periodMs', 'label': 'PeriodMs', 'type': 'number', 'default': 1800, 'min': 200, 'step': 50, 'integer': True}, {'key': 'minIntensity', 'label': 'MinIntensity', 'type': 'number', 'default': 0.05, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'maxIntensity', 'label': 'MaxIntensity', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}],
    build_op=build_op, expand_op=expand,
)
