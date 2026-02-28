from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List, Pattern, Protocol


LoggerFn = Callable[[str], None]


@dataclass(frozen=True)
class EventContext:
    """Normalized event payload passed to handlers."""

    id: str
    ts: float
    name: str
    source: str | None
    params: Dict[str, Any]
    origin: str


@dataclass(frozen=True)
class EventDispatchReport:
    """Outcome metadata for one dispatch call."""

    route_keys: List[str]
    handlers_run: int


class EventHandler(Protocol):
    """Handler contract for Pi-side event processing."""

    def handle(self, ctx: EventContext) -> None: ...


class _NoopHandler:
    """Default placeholder handler for known event routes."""

    def __init__(self, label: str) -> None:
        self._label = label

    def handle(self, ctx: EventContext) -> None:
        # Intentional no-op; this is an explicit hook point for future logic.
        _ = (self._label, ctx)


class _MappingResolver:
    """Resolve hardware source id -> rules device class using mapping.json."""

    _FUNCTION_MAP = {
        "Button": "button",
        "Switch": "switch",
        "Accelerometer": "gyro",
        "NFC": "nfc",
        "Solenoid": "coil",
        "Coil": "coil",
        "LED": "output",
        "RGB Strip": "led",
    }

    def __init__(self, instance_path: str | None = None) -> None:
        self._instance_path = Path(instance_path) if instance_path else _default_instance_path()
        self._mapping_path = self._instance_path / "hardware" / "mapping.json"
        self._lock = Lock()
        self._cache_mtime_ns = -1
        self._cache: Dict[str, str] = {}

    def resolve(self, source: str | None) -> str | None:
        if not source:
            return None
        self._reload_if_needed()
        return self._cache.get(source)

    def _reload_if_needed(self) -> None:
        with self._lock:
            try:
                st = self._mapping_path.stat()
            except Exception:
                self._cache = {}
                self._cache_mtime_ns = -1
                return
            if st.st_mtime_ns == self._cache_mtime_ns:
                return
            self._cache_mtime_ns = st.st_mtime_ns
            self._cache = self._load_mapping()

    def _load_mapping(self) -> Dict[str, str]:
        try:
            raw = json.loads(self._mapping_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
        if not isinstance(data, dict):
            return {}
        out: Dict[str, str] = {}
        for source, row in data.items():
            if not isinstance(source, str) or not isinstance(row, dict):
                continue
            fn = (row.get("function") or "").strip()
            dc = self._FUNCTION_MAP.get(fn)
            if dc:
                out[source] = dc
        return out


class EventCatalog:
    """Parsed view of rules registry event definitions."""

    def __init__(
        self,
        system_events: set[str],
        hardware_events: Dict[str, set[str]],
        custom_pattern: Pattern[str] | None,
    ) -> None:
        self.system_events = system_events
        self.hardware_events = hardware_events
        self.custom_pattern = custom_pattern

    @classmethod
    def from_registry(cls, registry: Dict[str, Any]) -> "EventCatalog":
        triggers = registry.get("triggers") if isinstance(registry, dict) else {}

        system_events: set[str] = set()
        system = triggers.get("system") if isinstance(triggers, dict) else {}
        categories = system.get("categories") if isinstance(system, dict) else {}
        if isinstance(categories, dict):
            for meta in categories.values():
                events = meta.get("events") if isinstance(meta, dict) else []
                if isinstance(events, list):
                    for name in events:
                        if isinstance(name, str) and name:
                            system_events.add(name)

        hardware_events: Dict[str, set[str]] = {}
        hardware = triggers.get("hardware") if isinstance(triggers, dict) else {}
        device_classes = hardware.get("deviceClasses") if isinstance(hardware, dict) else {}
        if isinstance(device_classes, dict):
            for class_name, meta in device_classes.items():
                if not isinstance(class_name, str) or not isinstance(meta, dict):
                    continue
                events = meta.get("events")
                names: set[str] = set()
                if isinstance(events, list):
                    for entry in events:
                        if isinstance(entry, str) and entry:
                            names.add(entry)
                        elif isinstance(entry, dict):
                            key = entry.get("key")
                            if isinstance(key, str) and key:
                                names.add(key)
                if names:
                    hardware_events[class_name] = names

        custom_pattern = None
        custom = triggers.get("custom") if isinstance(triggers, dict) else {}
        if isinstance(custom, dict) and custom.get("freeText"):
            pat = custom.get("validation")
            if isinstance(pat, str) and pat:
                try:
                    custom_pattern = re.compile(pat)
                except re.error:
                    custom_pattern = None

        return cls(system_events=system_events, hardware_events=hardware_events, custom_pattern=custom_pattern)


class EventManager:
    """Central Pi-side event manager with explicit route registration."""

    def __init__(
        self,
        catalog: EventCatalog,
        resolver: _MappingResolver,
        logger: LoggerFn | None = None,
    ) -> None:
        self._catalog = catalog
        self._resolver = resolver
        self._logger = logger
        self._handlers: Dict[str, List[EventHandler]] = {}
        self._lock = Lock()

    def register(self, route_key: str, handler: EventHandler) -> None:
        if not route_key or handler is None:
            return
        with self._lock:
            self._handlers.setdefault(route_key, []).append(handler)

    def dispatch(self, ctx: EventContext) -> EventDispatchReport:
        keys = self._route_keys(ctx)
        ran = 0
        for key in keys:
            handlers = self._handlers.get(key, [])
            for handler in handlers:
                handler.handle(ctx)
                ran += 1
        if self._logger and keys:
            self._logger(
                "event-mgr dispatch "
                f"name={ctx.name} source={ctx.source} origin={ctx.origin} "
                f"routes={','.join(keys)} handlers={ran}"
            )
        return EventDispatchReport(route_keys=keys, handlers_run=ran)

    def coverage(self) -> Dict[str, Any]:
        """Return route and behavior coverage.

        Notes:
        - Route coverage answers "is each expected route key registered?"
        - Behavior coverage excludes placeholder `_NoopHandler` registrations.
        """
        expected: set[str] = set()
        for ev in sorted(self._catalog.system_events):
            expected.add(f"system:{ev}")
        for dc, names in sorted(self._catalog.hardware_events.items()):
            for ev in sorted(names):
                expected.add(f"hardware:{dc}:{ev}")
        if self._catalog.custom_pattern is not None:
            expected.add("custom")

        registered = {k for k, v in self._handlers.items() if v}
        missing = sorted(expected - registered)
        behavior_registered = {
            k
            for k, handlers in self._handlers.items()
            if handlers and any(not isinstance(h, _NoopHandler) for h in handlers)
        }
        behavior_missing = sorted(expected - behavior_registered)
        return {
            "expected_count": len(expected),
            "route_registered_count": len(registered),
            "route_missing_count": len(missing),
            "route_missing": missing,
            "route_complete": not missing,
            "behavior_registered_count": len(behavior_registered),
            "behavior_missing_count": len(behavior_missing),
            "behavior_missing": behavior_missing,
            "behavior_complete": not behavior_missing,
        }

    def _route_keys(self, ctx: EventContext) -> List[str]:
        keys: List[str] = ["all", f"event:{ctx.name}"]
        if ctx.name in self._catalog.system_events:
            keys.append(f"system:{ctx.name}")

        event_type = ctx.params.get("eventType") if isinstance(ctx.params.get("eventType"), str) else None
        if event_type:
            dc = self._resolver.resolve(ctx.source)
            if dc and event_type in self._catalog.hardware_events.get(dc, set()):
                keys.append(f"hardware:{dc}:{event_type}")

        if self._catalog.custom_pattern and self._catalog.custom_pattern.match(ctx.name):
            keys.append("custom")

        # stable order + dedupe
        out: List[str] = []
        seen = set()
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            out.append(k)
        return out


def _default_instance_path() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "src":
            inst = p / "instance"
            inst.mkdir(parents=True, exist_ok=True)
            return inst
    inst = Path.cwd() / "src" / "instance"
    inst.mkdir(parents=True, exist_ok=True)
    return inst


def _default_registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "app" / "modules" / "rules" / "registry.json"


def _load_registry(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def build_default_event_manager(
    instance_path: str | None = None,
    registry_path: str | None = None,
    logger: LoggerFn | None = None,
) -> EventManager:
    reg_path = Path(registry_path) if registry_path else _default_registry_path()
    registry = _load_registry(reg_path)
    catalog = EventCatalog.from_registry(registry)
    mgr = EventManager(catalog=catalog, resolver=_MappingResolver(instance_path), logger=logger)

    # Register stubs for all rules-defined system and hardware routes.
    for ev in sorted(catalog.system_events):
        mgr.register(f"system:{ev}", _NoopHandler(f"system:{ev}"))
    for dc, names in sorted(catalog.hardware_events.items()):
        for ev in sorted(names):
            mgr.register(f"hardware:{dc}:{ev}", _NoopHandler(f"hardware:{dc}:{ev}"))
    if catalog.custom_pattern is not None:
        mgr.register("custom", _NoopHandler("custom"))

    return mgr


_MANAGER_BY_INSTANCE: Dict[str, EventManager] = {}
_MANAGER_LOCK = Lock()


def get_event_manager(
    instance_path: str | None = None,
    registry_path: str | None = None,
    logger: LoggerFn | None = None,
) -> EventManager:
    inst = str(Path(instance_path).resolve()) if instance_path else str(_default_instance_path().resolve())
    with _MANAGER_LOCK:
        mgr = _MANAGER_BY_INSTANCE.get(inst)
        if mgr is None:
            mgr = build_default_event_manager(instance_path=inst, registry_path=registry_path, logger=logger)
            _MANAGER_BY_INSTANCE[inst] = mgr
        return mgr
