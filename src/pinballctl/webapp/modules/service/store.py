"""Read the Service Log's saved maintenance entries."""

import json
from pathlib import Path


def log_path(instance_path: str | Path) -> Path:
    return Path(instance_path) / "service" / "log.json"


def load_entries(instance_path: str | Path) -> list[dict]:
    try:
        data = json.loads(log_path(instance_path).read_text())
    except FileNotFoundError:
        return []
    if not isinstance(data, list):
        raise ValueError("Expected a list of service entries")
    return [entry for entry in data if isinstance(entry, dict)]
