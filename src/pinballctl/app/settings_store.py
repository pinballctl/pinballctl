"""Utility helpers for loading/saving user settings from instance dir."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def _legacy_settings_path(instance_path: str | Path) -> Path:
    base = Path(instance_path)
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings.json"


def settings_path(instance_path: str | Path) -> Path:
    base = Path(instance_path)
    base.mkdir(parents=True, exist_ok=True)
    return base / "settings" / "settings.json"


def load_settings(instance_path: str | Path) -> Dict[str, Any]:
    fp = settings_path(instance_path)
    old_fp = _legacy_settings_path(instance_path)
    # One-time migration path: if only legacy file exists, move it to new location.
    if not fp.exists() and old_fp.exists():
        try:
            fp.parent.mkdir(parents=True, exist_ok=True)
            old_fp.replace(fp)
        except Exception:
            # If move fails, still read from legacy path.
            pass
    if not fp.exists():
        if old_fp.exists():
            try:
                return json.loads(old_fp.read_text())
            except Exception:
                return {}
        return {}
    try:
        return json.loads(fp.read_text())
    except Exception:
        return {}


def save_settings(instance_path: str | Path, data: Dict[str, Any]) -> None:
    fp = settings_path(instance_path)
    old_fp = _legacy_settings_path(instance_path)
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(json.dumps(data, indent=2))
    # Remove legacy location once new write succeeds.
    try:
        if old_fp.exists():
            old_fp.unlink()
    except Exception:
        pass


def apply_to_app(app, data: Dict[str, Any]) -> None:
    """Overlay uppercase keys into Flask config."""
    for k, v in (data or {}).items():
        if isinstance(k, str) and k.isupper():
            app.config[k] = v
