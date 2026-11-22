from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"RIPPLE","target":"*","color":str(params.get("color", "#ffffff")),"speed":max(1,int(params.get("speed",120) or 120)),"rings":max(1,min(12,int(params.get("rings",3) or 3))),"thickness":max(0.01,min(0.5,float(params.get("thickness",0.08) or 0.08))),"falloff":max(0.0,min(1.0,float(params.get("falloff",0.85) or 0.85))),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=runtime.clamp_step(op.get("speed",120),default=120); color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0); rings=max(1,int(op.get("rings",3) or 3)); thickness=max(0.01,min(0.5,float(op.get("thickness",0.08) or 0.08))); falloff=runtime.clamp01(op.get("falloff",0.85),0.85)
    max_dist=math.sqrt(0.5); idx=0
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        ring=(float(idx)/100.0)%1.0; frame=[]
        for p in pixels:
            dx=float(p.get("x",0.5))-0.5; dy=float(p.get("y",0.5))-0.5; d_norm=math.sqrt(dx*dx+dy*dy)/max_dist
            wave=((d_norm*rings)-(ring*rings))%1.0; local=wave if wave>=0 else (wave+1.0); edge=min(local,1.0-local)
            band=max(0.0,1.0-(edge/max(0.0001,thickness))); radial=max(0.0,1.0-d_norm*(1.0-falloff)); inten=max(0.0,min(1.0,band*radial))
            frame.append(runtime.pixel_change(p,color,brightness,inten))
        out[t_ms]=frame; idx+=1

    return out

PATTERN = PatternPlugin(
    id="ripple", label="ripple", op_name="RIPPLE", order=19,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'speed', 'label': 'Speed', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'rings', 'label': 'Rings', 'type': 'number', 'default': 3, 'min': 1, 'max': 12, 'step': 1, 'integer': True}, {'key': 'thickness', 'label': 'Thickness', 'type': 'number', 'default': 0.08, 'min': 0.01, 'max': 0.5, 'step': 0.01}, {'key': 'falloff', 'label': 'Falloff', 'type': 'number', 'default': 0.85, 'min': 0, 'max': 1, 'step': 0.05}],
    build_op=build_op, expand_op=expand,
)
