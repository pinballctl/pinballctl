from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin

import math
import random


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    return {"op":"FADE_STAGGER","target":"*","color":str(params.get("color", "#ffffff")),"periodMs":max(200,int(params.get("periodMs",1800) or 1800)),"minBrightness":float(params.get("minBrightness",0.05) or 0.05),"maxBrightness":float(params.get("maxBrightness",1.0) or 1.0),"phaseOffset":float(params.get("phaseOffset",0.35) or 0.35),"seed":int(params.get("seed",1337) or 1337),"brightness":brightness}


def expand(runtime, scene: Dict[str, Any], op: Dict[str, Any], duration_ms: int, start_t_ms: int):
    out = runtime.empty_frames(start_t_ms, duration_ms)
    pixels = runtime.prepare_pixels(scene, op)
    if not pixels:
        return out

    period=runtime.clamp_step(op.get("periodMs",1800),default=1800,lo=200,hi=20000); step=max(16,int(period/30)); min_b=runtime.clamp01(op.get("minBrightness",0.05),0.05); max_b=runtime.clamp01(op.get("maxBrightness",1.0),1.0)
    if max_b<min_b: max_b=min_b
    phase_offset=runtime.clamp01(op.get("phaseOffset",0.35),0.35); seed=int(op.get("seed",1337) or 1337); color=str(op.get("color") or "#ffffff")
    rng=random.Random(seed); jitter=[rng.random() for _ in range(max(1,len(pixels)))]; rates=[0.85 + (rng.random()*0.35) for _ in range(max(1,len(pixels)))]
    for t_ms in runtime.iter_frames(start_t_ms,duration_ms,step):
        frame=[]
        for idx,p in enumerate(pixels):
            ph=(2.0*math.pi*float(t_ms-start_t_ms)*rates[idx%len(rates)]/float(period)) + (max(0.05,phase_offset)*2.0*math.pi*jitter[idx%len(jitter)])
            env=0.5*(math.sin(ph-(math.pi/2.0))+1.0); bright=min_b+(max_b-min_b)*env
            frame.append(runtime.pixel_change(p,color,bright,1.0))
        out[t_ms]=frame

    return out

PATTERN = PatternPlugin(
    id="fade_stagger", label="fade stagger", op_name="FADE_STAGGER", order=10,
    params=[{'key': 'color', 'label': 'Colour', 'type': 'color', 'default': '#ffffff'}, {'key': 'brightness', 'label': 'Brightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'periodMs', 'label': 'PeriodMs', 'type': 'number', 'default': 1800, 'min': 200, 'step': 50, 'integer': True}, {'key': 'minBrightness', 'label': 'MinBrightness', 'type': 'number', 'default': 0.05, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'maxBrightness', 'label': 'MaxBrightness', 'type': 'number', 'default': 1.0, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'phaseOffset', 'label': 'PhaseOffset', 'type': 'number', 'default': 0.35, 'min': 0, 'max': 1, 'step': 0.05}, {'key': 'seed', 'label': 'Seed', 'type': 'number', 'default': 1337, 'min': 0, 'step': 1, 'integer': True}],
    build_op=build_op, expand_op=expand,
)
