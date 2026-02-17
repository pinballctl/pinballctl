from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"THEATER_CHASE","target":"*","color":str(params.get("color", "#ffffff")),"speed":max(1,int(params.get("speed",120) or 120)),"spacing":max(2,int(params.get("spacing",3) or 3)),"tail":max(0,int(params.get("tail",0) or 0)),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=runtime.clamp_step(op.get("speed",120),default=120); color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0); spacing=max(2,int(op.get("spacing",3) or 3)); tail=max(0,int(op.get("tail",0) or 0)); sidx=0
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        frame=[]
        for p in pixels:
            n=max(1,int(p.get("pixelCount",1))); i=int(p.get("pixelIndex",0) or 0); head=sidx%n; d=(i-head)%spacing; lit=(d==0) or (tail>0 and d<=tail); inten=1.0 if d==0 else (max(0.0,1.0-(float(d)/float(max(1,tail+1)))) if lit else 0.0)
            frame.append(runtime.pixel_change(p,color,brightness,inten))
        out[t_ms]=frame; sidx+=1

    return out

PATTERN = PatternPlugin(
    id="theater_chase", label="theater chase", op_name="THEATER_CHASE", order=12,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'speed', 'label': 'Speed', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'spacing', 'label': 'Spacing', 'type': 'number', 'default': 3, 'min': 2, 'step': 1, 'integer': True}, {'key': 'tail', 'label': 'Tail', 'type': 'number', 'default': 0, 'min': 0, 'step': 1, 'integer': True}],
    build_op=build_op, expand_op=expand,
)
