from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


def build_op(params: Dict[str, Any], brightness: float) -> Dict[str, Any]:
    color = str(params.get("color", "#ffffff"))
    intensity = float(params.get("intensity", 1.0)) if isinstance(params.get("intensity"), (int, float)) else 1.0
    return {"op": "SOLID", "target": "*", "color": color, "intensity": intensity, "brightness": brightness}

PATTERN = PatternPlugin(
    id="solid",
    label="solid",
    params=[
        {"key": "color", "label": "Colour", "type": "color", "default": "#ffffff"},
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
    ],
    build_op=build_op,
    expand_op=None,
    op_name="SOLID",
    order=1,
)
