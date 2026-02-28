"""Sync state helpers for local artifact tracking."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def _sync_state_path(instance_path: str | Path) -> Path:
    base = Path(instance_path)
    base.mkdir(parents=True, exist_ok=True)
    bridge_dir = base / "bridge"
    bridge_dir.mkdir(parents=True, exist_ok=True)
    new_path = bridge_dir / "sync_state.json"
    legacy_path = base / "sync_state.json"
    # One-time migration from legacy location.
    if not new_path.exists() and legacy_path.exists():
        try:
            legacy_path.replace(new_path)
        except Exception:
            pass
    return new_path


def read_sync_state(instance_path: str | Path) -> Dict[str, Any]:
    path = _sync_state_path(instance_path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def update_sync_state(instance_path: str | Path, key: str, sha256: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    data = read_sync_state(instance_path)
    row: Dict[str, Any] = {
        "lastSyncedAt": datetime.now(timezone.utc).isoformat(),
        "sha256": sha256,
    }
    if isinstance(extra, dict):
        row.update(extra)
    data[key] = row
    path = _sync_state_path(instance_path)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
