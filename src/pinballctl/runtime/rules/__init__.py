"""Rules runtime helpers."""

from pathlib import Path

from .runtime import apply_rules_for_event

REGISTRY_PATH = Path(__file__).resolve().with_name("registry.json")

__all__ = ["REGISTRY_PATH", "apply_rules_for_event"]
