from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"RADAR","target":"*","color":str(params.get("color", "#ffffff")),"speed":max(1,int(params.get("speed",120) or 120)),"sweepDeg":max(5,min(180,int(params.get("sweepDeg",35) or 35))),"tail":max(0.0,min(1.0,float(params.get("tail",0.65) or 0.65))),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=runtime.clamp_step(op.get("speed",120),default=120); color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0); sweep=max(5,min(180,int(op.get("sweepDeg",35) or 35))); tail=runtime.clamp01(op.get("tail",0.65),0.65)
    half=(float(sweep)*math.pi)/360.0; idx=0
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        head=(float(idx)/100.0)*(2.0*math.pi); frame=[]
        for p in pixels:
            x=float(p.get("x",0.5))-0.5; y=float(p.get("y",0.5))-0.5; a=math.atan2(y,x); d=abs((a-head+math.pi)%(2.0*math.pi)-math.pi)
            if d>half: inten=0.0
            else:
                edge=1.0-(d/max(0.0001,half)); shaped=pow(max(0.0,edge),0.55); floor=0.35+tail*0.45; inten=max(0.0,min(1.0,floor+shaped*(1.0-floor)))
            frame.append(runtime.pixel_change(p,color,brightness,inten))
        out[t_ms]=frame; idx+=1

    return out

PATTERN = PatternPlugin(
    id="radar", label="radar", op_name="RADAR", order=18,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'speed', 'label': 'Speed', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'sweepDeg', 'label': 'SweepDeg', 'type': 'number', 'default': 35, 'min': 5, 'max': 180, 'step': 1, 'integer': True}, {'key': 'tail', 'label': 'Tail', 'type': 'number', 'default': 0.65, 'min': 0, 'max': 1, 'step': 0.05}],
    build_op=build_op, expand_op=expand,
)
