from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"FIRE","target":"*","cooling":max(0.0,min(1.0,float(params.get("cooling",0.4) or 0.4))),"sparking":max(0.0,min(1.0,float(params.get("sparking",0.25) or 0.25))),"speed":max(1,int(params.get("speed",90) or 90)),"seed":int(params.get("seed",1337) or 1337),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=runtime.clamp_step(op.get("speed",90),default=90); cooling=runtime.clamp01(op.get("cooling",0.4),0.4); sparking=runtime.clamp01(op.get("sparking",0.25),0.25); brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    rng=random.Random(int(op.get("seed",1337) or 1337)); heat=[0.0 for _ in pixels]
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        frame=[]
        for idx,p in enumerate(pixels):
            cool = cooling * (0.02 + rng.random() * 0.08); heat[idx] = max(0.0, heat[idx]-cool)
            if rng.random() < sparking*0.4: heat[idx] = min(1.0, heat[idx] + (0.3 + rng.random()*0.7))
            frame.append(runtime.pixel_change(p, runtime.hex_from_heat(heat[idx]), brightness, heat[idx]))
        out[t_ms]=frame

    return out

PATTERN = PatternPlugin(
    id="fire", label="fire", op_name="FIRE", order=15,
    params=[{'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'speed', 'label': 'Speed', 'type': 'number', 'default': 80, 'min': 1, 'step': 1, 'integer': True}, {'key': 'cooling', 'label': 'Cooling', 'type': 'number', 'default': 0.4, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'sparking', 'label': 'Sparking', 'type': 'number', 'default': 0.25, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'seed', 'label': 'Seed', 'type': 'number', 'default': 1337, 'min': 0, 'step': 1, 'integer': True}],
    build_op=build_op, expand_op=expand,
)
