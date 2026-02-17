from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"PING","target":"*","color":str(params.get("color", "#ffffff")),"speed":max(1,int(params.get("speed",120) or 120)),"thickness":max(0.01,float(params.get("thickness",0.12) or 0.12)),"falloff":max(0.0,min(1.0,float(params.get("falloff",0.85) or 0.85))),"origin":str(params.get("origin", "center") or "center").strip().lower(),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period=runtime.speed_period_ms(op.get("speed",120)); step=max(16,min(80,int(period/40))); color=str(op.get("color") or "#ffffff"); brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    thickness=float(op.get("thickness",0.12)); thickness=0.01 if thickness<=0 else thickness; falloff=runtime.clamp01(op.get("falloff",0.85),0.85)
    origin=str(op.get("origin") or "center").strip().lower()
    if origin == "top":
        ox, oy = 0.5, 0.0
    elif origin == "bottom":
        ox, oy = 0.5, 1.0
    elif origin == "left":
        ox, oy = 0.0, 0.5
    elif origin == "right":
        ox, oy = 1.0, 0.5
    else:
        ox, oy = 0.5, 0.5
    max_d=0.0
    for p in pixels:
        d=math.hypot(float(p.get("x",0.5))-ox,float(p.get("y",0.5))-oy)
        if d>max_d: max_d=d
    if max_d<=0: max_d=1.0
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        phase=(float(t_ms-start_t_ms)%float(period))/float(period); frame=[]
        for p in pixels:
            d=math.hypot(float(p.get("x",0.5))-ox,float(p.get("y",0.5))-oy); d_norm=d/max_d; delta=abs(d_norm-phase)
            if delta>thickness: inten=0.0
            else:
                edge=1.0-(delta/thickness); radial=max(0.0,1.0-d_norm*(1.0-falloff)); inten=edge*radial
            frame.append(runtime.pixel_change(p,color,brightness,inten))
        out[t_ms]=frame

    return out

PATTERN = PatternPlugin(
    id="ping", label="ping", op_name="PING", order=17,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'speed', 'label': 'Speed', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'thickness', 'label': 'Thickness', 'type': 'number', 'default': 0.12, 'min': 0.01, 'max': 1, 'step': 0.01}, {'key': 'falloff', 'label': 'Falloff', 'type': 'number', 'default': 0.85, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'origin', 'label': 'Origin', 'type': 'select', 'default': 'center', 'options': [{'value': 'center', 'label': 'center'}, {'value': 'top', 'label': 'top'}, {'value': 'bottom', 'label': 'bottom'}, {'value': 'left', 'label': 'left'}, {'value': 'right', 'label': 'right'}]}],
    build_op=build_op, expand_op=expand,
)
