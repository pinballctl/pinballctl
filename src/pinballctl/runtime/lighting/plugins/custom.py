from __future__ import annotations

from typing import Any, Dict, List

from .registry import PatternPlugin


PATTERN = PatternPlugin(
    id="custom",
    label="custom timeline",
    params=[
        {"key": "brightness", "label": "Brightness", "type": "number", "default": 1.0, "min": 0, "max": 1, "step": 0.05},
        {"key": "tween", "label": "Tween", "type": "select", "default": "hold", "options": [{"value": "hold", "label": "hold"}, {"value": "linear", "label": "linear"}]},
    ],
    build_op=None,
    expand_op=None,
    op_name=None,
    order=99,
)
