from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import importlib
import pkgutil
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Tuple


BuildOpFn = Callable[[Dict[str, Any], float], Dict[str, Any]]
ExpandOpFn = Callable[[Any, Dict[str, Any], Dict[str, Any], int, int], Dict[int, List[Dict[str, Any]]]]


@dataclass(frozen=True)
class PatternPlugin:
    id: str
    label: str
    params: List[Dict[str, Any]]
    build_op: Optional[BuildOpFn]
    expand_op: Optional[ExpandOpFn]
    op_name: Optional[str] = None
    aliases: Tuple[str, ...] = ()
    order: int = 100


@lru_cache(maxsize=1)
def _plugin_modules() -> List[ModuleType]:
    mods: List[ModuleType] = []
    pkg = __name__.rsplit(".", 1)[0]
    for mod in pkgutil.iter_modules(__import__(pkg, fromlist=["__path__"]).__path__):
        name = mod.name
        if name.startswith("_") or name in {"registry", "runtime"}:
            continue
        mods.append(importlib.import_module(f"{pkg}.{name}"))
    return mods


@lru_cache(maxsize=1)
def plugins() -> List[PatternPlugin]:
    out: List[PatternPlugin] = []
    for mod in _plugin_modules():
        row = getattr(mod, "PATTERN", None)
        if isinstance(row, PatternPlugin):
            out.append(row)
    out.sort(key=lambda p: (int(p.order), p.id))
    return out


@lru_cache(maxsize=1)
def plugin_by_id() -> Dict[str, PatternPlugin]:
    return {p.id: p for p in plugins()}


@lru_cache(maxsize=1)
def alias_map() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in plugins():
        out[p.id] = p.id
        for a in p.aliases:
            out[str(a).strip().lower()] = p.id
    return out


@lru_cache(maxsize=1)
def plugin_by_op_name() -> Dict[str, PatternPlugin]:
    out: Dict[str, PatternPlugin] = {}
    for p in plugins():
        if p.op_name:
            out[p.op_name.upper()] = p
    return out
