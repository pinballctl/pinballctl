from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"COLOR_WIPE","target":"*","color":str(params.get("color", "#ffffff")),"direction":str(params.get("direction", "forward") or "forward").strip().lower(),"stepMs":max(1,int(params.get("stepMs",80) or 80)),"clearAfter":str(params.get("clearAfter", False)).strip().lower() in ("1","true","yes","on"),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=runtime.clamp_step(op.get("stepMs",80),default=80,lo=1,hi=5000); direction=str(op.get("direction") or "forward").strip().lower(); clear=runtime.as_bool(op.get("clearAfter",False),False)
    color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0); max_len=max(1,max(int(p.get("pixelCount",1)) for p in pixels)); cycle=max_len*(2 if clear else 1); idx=0
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        phase=idx%cycle; frame=[]
        for p in pixels:
            n=max(1,int(p.get("pixelCount",1))); i=int(p.get("pixelIndex",0) or 0); pos=(n-1-i) if direction=="reverse" else i
            lit = (pos >= (phase-n)) if (clear and phase>=n) else (pos<=phase)
            frame.append(runtime.pixel_change(p,color,brightness,1.0 if lit else 0.0))
        out[t_ms]=frame; idx+=1

    return out

PATTERN = PatternPlugin(
    id="color_wipe", label="color wipe", op_name="COLOR_WIPE", order=11,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'stepMs', 'label': 'StepMs', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'direction', 'label': 'Direction', 'type': 'select', 'default': 'forward', 'options': [{'value': 'forward', 'label': 'forward'}, {'value': 'reverse', 'label': 'reverse'}]}, {'key': 'clearAfter', 'label': 'ClearAfter', 'type': 'bool', 'default': False}],
    build_op=build_op, expand_op=expand,
)
