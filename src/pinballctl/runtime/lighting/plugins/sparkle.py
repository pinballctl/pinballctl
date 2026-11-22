from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"SPARKLE","target":"*","density":max(0.0,min(1.0,float(params.get("density",0.2) or 0.2))),"minOnMs":max(1,int(params.get("minOnMs",40) or 40)),"maxOnMs":max(1,int(params.get("maxOnMs",180) or 180)),"palette":[str(params.get("color", "#ffffff"))],"seed":int(params.get("seed",1337) or 1337),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    step=50; density=runtime.clamp01(op.get("density",0.2),0.2); min_on=max(1,int(op.get("minOnMs",40) or 40)); max_on=max(min_on,int(op.get("maxOnMs",180) or 180))
    min_f=max(1,int(round(min_on/step))); max_f=max(min_f,int(round(max_on/step))); palette=op.get("palette") if isinstance(op.get("palette"), list) else [str(op.get("color") or "#ffffff")]
    palette=[str(c) for c in palette if str(c).strip()] or ["#ffffff"]; brightness=runtime.clamp01(op.get("brightness",1.0),1.0)
    rng=random.Random(int(op.get("seed",1337) or 1337)); active=[0 for _ in pixels]; colors=[palette[0] for _ in pixels]
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        frame=[]
        for idx,p in enumerate(pixels):
            if active[idx]>0:
                active[idx]-=1; frame.append(runtime.pixel_change(p,colors[idx],brightness,1.0)); continue
            if rng.random()<density:
                active[idx]=rng.randint(min_f,max_f); colors[idx]=palette[rng.randrange(len(palette))]; frame.append(runtime.pixel_change(p,colors[idx],brightness,1.0))
            else:
                frame.append(runtime.pixel_change(p,colors[idx],brightness,0.0))
        out[t_ms]=frame

    return out

PATTERN = PatternPlugin(
    id="sparkle", label="sparkle", op_name="SPARKLE", order=6,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'density', 'label': 'Density', 'type': 'number', 'default': 0.2, 'min': 0.01, 'max': 1, 'step': 0.01}, {'key': 'minOnMs', 'label': 'MinOnMs', 'type': 'number', 'default': 40, 'min': 1, 'step': 1, 'integer': True}, {'key': 'maxOnMs', 'label': 'MaxOnMs', 'type': 'number', 'default': 180, 'min': 1, 'step': 1, 'integer': True}, {'key': 'seed', 'label': 'Seed', 'type': 'number', 'default': 1337, 'min': 0, 'step': 1, 'integer': True}],
    build_op=build_op, expand_op=expand,
)
