"""Pattern registry loader for lighting plugins stored in app/modules/lighting/patterns.

This module intentionally avoids importing `pinballctl.app.modules.lighting` package
(at import time) to prevent circular imports with `lighting_blob`.
"""
from __future__ import annotations

from functools import lru_cache
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Dict, List


_PLUGIN_PACKAGE = "_pinballctl_lighting_plugins"


def _plugin_dir() -> Path:
    # .../src/pinballctl/lighting/patterns.py -> .../src/pinballctl/app/modules/lighting/patterns
    here = Path(__file__).resolve()
    return here.parents[1] / "app" / "modules" / "lighting" / "patterns"


def _load_module(name: str, path: Path) -> ModuleType:
    full_name = f"{_PLUGIN_PACKAGE}.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod


@lru_cache(maxsize=1)
def _plugins() -> List[Any]:
    root = _plugin_dir()
    if not root.exists():
        return []

    # Create synthetic package container for relative imports like `.registry`.
    if _PLUGIN_PACKAGE not in sys.modules:
        pkg = ModuleType(_PLUGIN_PACKAGE)
        pkg.__path__ = [str(root)]  # type: ignore[attr-defined]
        sys.modules[_PLUGIN_PACKAGE] = pkg

    _load_module("registry", root / "registry.py")

    out: List[Any] = []
    for path in sorted(root.glob("*.py")):
        name = path.stem
        if name.startswith("_") or name in {"__init__", "registry", "runtime"}:
            continue
        mod = _load_module(name, path)
        pat = getattr(mod, "PATTERN", None)
        if pat is not None:
            out.append(pat)
    out.sort(key=lambda p: (int(getattr(p, "order", 100)), str(getattr(p, "id", ""))))
    return out


@lru_cache(maxsize=1)
def _by_id() -> Dict[str, Any]:
    return {str(getattr(p, "id", "")): p for p in _plugins()}


@lru_cache(maxsize=1)
def _aliases() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in _plugins():
        pid = str(getattr(p, "id", ""))
        if not pid:
            continue
        out[pid] = pid
        for a in tuple(getattr(p, "aliases", ()) or ()):  # type: ignore[arg-type]
            out[str(a).strip().lower()] = pid
    return out


@lru_cache(maxsize=1)
def _by_op() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for p in _plugins():
        op = getattr(p, "op_name", None)
        if op:
            out[str(op).upper()] = p
    return out


def list_pattern_specs() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in _plugins():
        out.append(
            {
                "id": str(getattr(p, "id", "")),
                "label": str(getattr(p, "label", getattr(p, "id", ""))),
                "params": list(getattr(p, "params", []) or []),
            }
        )
    return out


def normalize_pattern_name(value: Any) -> str:
    key = str(value or "solid").strip().lower().replace("-", "_").replace(" ", "_")
    resolved = _aliases().get(key)
    if resolved:
        return resolved
    return "solid" if "solid" in _by_id() else key


def default_params_for_pattern(pattern: Any) -> Dict[str, Any]:
    pid = normalize_pattern_name(pattern)
    p = _by_id().get(pid)
    if p is None:
        return {}
    out: Dict[str, Any] = {}
    for row in list(getattr(p, "params", []) or []):
        if isinstance(row, dict) and "key" in row:
            out[str(row["key"])] = row.get("default")
    return out


def merge_params_with_defaults(pattern: Any, params: Dict[str, Any] | None) -> Dict[str, Any]:
    out = default_params_for_pattern(pattern)
    if isinstance(params, dict):
        out.update(params)
    return out


def build_pattern_op(pattern: Any, params: Dict[str, Any], brightness: float) -> Dict[str, Any] | None:
    pid = normalize_pattern_name(pattern)
    p = _by_id().get(pid)
    fn = getattr(p, "build_op", None) if p is not None else None
    if callable(fn):
        return fn(params, brightness)
    return None


def expand_pattern_op(op_name: str, runtime: Any, scene: Dict[str, Any], op_row: Dict[str, Any], duration_ms: int, start_t_ms: int) -> Dict[int, List[Dict[str, Any]]]:
    p = _by_op().get(str(op_name or "").upper())
    fn = getattr(p, "expand_op", None) if p is not None else None
    if callable(fn):
        return fn(runtime, scene, op_row, duration_ms, start_t_ms)
    return {}


__all__ = [
    "list_pattern_specs",
    "normalize_pattern_name",
    "default_params_for_pattern",
    "merge_params_with_defaults",
    "build_pattern_op",
    "expand_pattern_op",
]
