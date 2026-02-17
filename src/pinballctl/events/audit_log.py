"""Append-only JSONL event audit log used by Logs module."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from pinballctl.log_maintenance import rotate_if_needed, prune_archives


_LAST_MAINT_AT: float = 0.0
_MAINT_INTERVAL_S: float = 5.0


def _state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "pinballctl"


def events_log_path() -> Path:
    p = _state_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p / "events.log"


def append_event_log(
    *,
    origin: str,
    direction: str,
    name: str,
    source: str | None,
    params: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Write one compact JSONL event record.

    Best-effort only: logging failures must not break runtime event flow.
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "origin": origin,
        "direction": direction,
        "name": name,
        "source": source,
        "params": params or {},
    }
    if meta:
        record["meta"] = meta
    try:
        fp = events_log_path()
        global _LAST_MAINT_AT  # noqa: PLW0603
        now = time.monotonic()
        if (now - _LAST_MAINT_AT) >= _MAINT_INTERVAL_S:
            rotate_if_needed("events", fp)
            prune_archives("events")
            _LAST_MAINT_AT = now
        with fp.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True))
            f.write("\n")
    except Exception:
        pass
