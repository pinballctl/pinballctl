from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"TWINKLE_FADE","target":"*","density":max(0.0,min(1.0,float(params.get("density",0.15) or 0.15))),"riseMs":max(1,int(params.get("riseMs",120) or 120)),"fallMs":max(1,int(params.get("fallMs",240) or 240)),"palette":[str(params.get("color", "#ffffff"))],"seed":int(params.get("seed",1337) or 1337),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=50; density=runtime.clamp01(op.get("density",0.15),0.15); rise=max(1,int(op.get("riseMs",120) or 120)); fall=max(1,int(op.get("fallMs",240) or 240)); rise_f=max(1,int(round(rise/step))); fall_f=max(1,int(round(fall/step))); total=rise_f+fall_f
    palette=op.get("palette") if isinstance(op.get("palette"),list) else [str(op.get("color") or "#ffffff")]; palette=[str(c) for c in palette if str(c).strip()] or ["#ffffff"]; brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    rng=random.Random(int(op.get("seed",1337) or 1337)); ages=[-1 for _ in pixels]; colors=[palette[0] for _ in pixels]
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        frame=[]
        for idx,p in enumerate(pixels):
            if ages[idx] < 0 and rng.random() < density:
                ages[idx]=0; colors[idx]=palette[rng.randrange(len(palette))]
            inten=0.0
            if ages[idx] >= 0:
                age=ages[idx]
                if age < rise_f: inten=float(age+1)/float(rise_f)
                elif age < total: inten=1.0 - (float(age-rise_f+1)/float(fall_f))
                else: ages[idx]=-1; inten=0.0
                if ages[idx] >= 0: ages[idx]+=1
            frame.append(runtime.pixel_change(p,colors[idx],brightness,max(0.0,inten)))
        out[t_ms]=frame

    return out

PATTERN = PatternPlugin(
    id="twinkle_fade", label="twinkle fade", op_name="TWINKLE_FADE", order=14,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'density', 'label': 'Density', 'type': 'number', 'default': 0.15, 'min': 0.01, 'max': 1, 'step': 0.01}, {'key': 'riseMs', 'label': 'RiseMs', 'type': 'number', 'default': 120, 'min': 1, 'step': 1, 'integer': True}, {'key': 'fallMs', 'label': 'FallMs', 'type': 'number', 'default': 240, 'min': 1, 'step': 1, 'integer': True}, {'key': 'seed', 'label': 'Seed', 'type': 'number', 'default': 1337, 'min': 0, 'step': 1, 'integer': True}],
    build_op=build_op, expand_op=expand,
)
