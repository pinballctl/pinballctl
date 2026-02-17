"""Log rotation and archive retention helpers for pinballctl."""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Dict, List


def _state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "pinballctl"


def _archive_root() -> Path:
    p = _state_dir() / "log-archives"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _log_rotate_bytes() -> int:
    raw = os.environ.get("PINBALLCTL_LOG_ROTATE_BYTES", "10485760").strip()  # 10 MiB default
    try:
        value = int(raw)
    except Exception:
        value = 10 * 1024 * 1024
    return max(256 * 1024, value)


def _log_retention_days() -> int:
    raw = os.environ.get("PINBALLCTL_LOG_RETENTION_DAYS", "14").strip()
    try:
        value = int(raw)
    except Exception:
        value = 14
    return max(1, value)


def _log_keep_archives() -> int:
    raw = os.environ.get("PINBALLCTL_LOG_KEEP_ARCHIVES", "80").strip()
    try:
        value = int(raw)
    except Exception:
        value = 80
    return max(5, value)


def current_log_paths() -> Dict[str, Path]:
    state = _state_dir()
    state.mkdir(parents=True, exist_ok=True)
    return {
        "bridge": state / "bridge.log",
        "espraw": state / "esp-raw.log",
        "events": state / "events.log",
        "error": state / "gunicorn-error.log",
        "access": state / "gunicorn-access.log",
    }


def _archive_dir(target: str) -> Path:
    p = _archive_root() / target
    p.mkdir(parents=True, exist_ok=True)
    return p


def rotate_if_needed(target: str, path: Path) -> Path | None:
    """Copy current log to archive and truncate current file when size threshold is exceeded."""
    try:
        if not path.exists():
            return None
        if path.stat().st_size < _log_rotate_bytes():
            return None
    except Exception:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = _archive_dir(target) / f"{target}-{ts}.log"
    i = 2
    while archive.exists():
        archive = _archive_dir(target) / f"{target}-{ts}-{i}.log"
        i += 1
    try:
        shutil.copy2(path, archive)
        # copytruncate style: preserve inode so long-running writers continue writing safely.
        with path.open("r+b") as f:
            f.truncate(0)
        return archive
    except Exception:
        return None


def prune_archives(target: str) -> None:
    """Delete old archives by age and keep-count."""
    keep_days = _log_retention_days()
    keep_count = _log_keep_archives()
    try:
        d = _archive_dir(target)
        files = [p for p in d.glob("*.log") if p.is_file()]
    except Exception:
        return
    if not files:
        return
    now = datetime.now(timezone.utc).timestamp()
    max_age_s = keep_days * 86400
    # First prune by age.
    survivors: List[Path] = []
    for p in files:
        try:
            age = now - p.stat().st_mtime
        except Exception:
            age = 0
        if age > max_age_s:
            try:
                p.unlink()
            except Exception:
                pass
            continue
        survivors.append(p)
    # Then prune by count (newest wins).
    survivors.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in survivors[keep_count:]:
        try:
            p.unlink()
        except Exception:
            pass


def list_archives(target: str, limit: int = 200) -> List[dict]:
    out: List[dict] = []
    try:
        files = [p for p in _archive_dir(target).glob("*.log") if p.is_file()]
    except Exception:
        return out
    files.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in files[: max(1, limit)]:
        try:
            st = p.stat()
            out.append(
                {
                    "name": p.name,
                    "size": st.st_size,
                    "mtime": int(st.st_mtime),
                }
            )
        except Exception:
            continue
    return out


def resolve_archive(target: str, archive_name: str) -> Path | None:
    safe = os.path.basename(archive_name or "")
    if not safe:
        return None
    p = _archive_dir(target) / safe
    try:
        resolved = p.resolve()
        resolved.relative_to(_archive_dir(target).resolve())
    except Exception:
        return None
    if not resolved.exists() or not resolved.is_file():
        return None
    return resolved


_MAINT_LOCK = Lock()
_LAST_MAINT_AT = 0.0


def maintain_logs_once(throttle_s: float = 30.0) -> None:
    """Rotate current logs by size and prune archives by retention policy."""
    import time

    global _LAST_MAINT_AT  # noqa: PLW0603
    now = time.time()
    if now - _LAST_MAINT_AT < max(1.0, float(throttle_s)):
        return
    with _MAINT_LOCK:
        now = time.time()
        if now - _LAST_MAINT_AT < max(1.0, float(throttle_s)):
            return
        for target, path in current_log_paths().items():
            rotate_if_needed(target, path)
            prune_archives(target)
        _LAST_MAINT_AT = now
