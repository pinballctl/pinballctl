"""Authentication configuration shared by web workers."""
from __future__ import annotations

import fcntl
import os
import secrets
from pathlib import Path


def session_secret(instance_path: str | Path, configured: str | None = None) -> str:
    """Honor explicit keys, otherwise persist a private per-installation key."""
    explicit = os.environ.get("PINBALLCTL_SECRET") or configured
    if explicit and explicit != "dev-not-secret-change-me":
        return explicit
    path = Path(instance_path) / "settings" / ".session-secret"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        value = handle.read().strip()
        if not value:
            value = secrets.token_hex(32)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        return value
