"""Events API: fire events and stream via SSE."""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty
from threading import Lock
from typing import Any, Dict, Tuple
from uuid import uuid4

from flask import Response, current_app, jsonify, request, stream_with_context

from pinballctl.bridge.state import enqueue_command, is_headless_mode
from pinballctl.events import EventContext, get_bus, get_event_manager
from pinballctl.events.audit_log import append_event_log, events_log_path
from pinballctl.rules.runtime import apply_rules_for_event
from . import api_bp

_JSON_CACHE: Dict[str, Dict[str, Any]] = {}
_API_FIRE_STATS_LOCK = Lock()
_SSE_BRIDGE_DRAIN_BATCH = 32
_API_FIRE_STATS: Dict[str, int] = {
    "submitted": 0,
    "completed": 0,
    "bridgeErrors": 0,
    "lastSubmitAtMs": 0,
    "lastCompleteAtMs": 0,
}


def _mark_fire_submit() -> None:
    now_ms = int(time.time() * 1000)
    with _API_FIRE_STATS_LOCK:
        _API_FIRE_STATS["submitted"] = int(_API_FIRE_STATS.get("submitted", 0)) + 1
        _API_FIRE_STATS["lastSubmitAtMs"] = now_ms


def _mark_fire_complete(*, bridge_ok: bool) -> None:
    now_ms = int(time.time() * 1000)
    with _API_FIRE_STATS_LOCK:
        _API_FIRE_STATS["completed"] = int(_API_FIRE_STATS.get("completed", 0)) + 1
        _API_FIRE_STATS["lastCompleteAtMs"] = now_ms
        if not bridge_ok:
            _API_FIRE_STATS["bridgeErrors"] = int(_API_FIRE_STATS.get("bridgeErrors", 0)) + 1


def _snapshot_fire_perf() -> Dict[str, int]:
    with _API_FIRE_STATS_LOCK:
        submitted = int(_API_FIRE_STATS.get("submitted", 0))
        completed = int(_API_FIRE_STATS.get("completed", 0))
        bridge_errors = int(_API_FIRE_STATS.get("bridgeErrors", 0))
        last_submit = int(_API_FIRE_STATS.get("lastSubmitAtMs", 0))
        last_complete = int(_API_FIRE_STATS.get("lastCompleteAtMs", 0))
    pending_total = max(0, submitted - completed)
    return {
        "submitted": submitted,
        "completed": completed,
        "pendingTotal": pending_total,
        "inflight": 0,
        "queued": pending_total,
        "maxInflight": 0,
        "lastSubmitAtMs": last_submit,
        "lastCompleteAtMs": last_complete,
        "bridgeErrors": bridge_errors,
    }


def _enqueue_bridge_event_fast(payload: Dict[str, Any]) -> tuple[bool, str | None]:
    """Enqueue a bridge command and return enqueue status/error."""
    if is_headless_mode():
        return False, "bridge_offline"
    try:
        enqueue_command(payload, wait_for_startup=False)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _process_event_local(
    *,
    instance_path: str,
    name: str,
    source: str | None,
    params: Dict[str, Any],
) -> tuple[str, str, list[Dict[str, Any]]]:
    """Run PI-side event flow when bridge/ESP is offline."""
    envelope = get_bus().emit(name=name, source=source, params=params)
    mgr = get_event_manager(instance_path=instance_path)
    mgr.dispatch(
        EventContext(
            id=envelope.id,
            ts=envelope.ts,
            name=envelope.name,
            source=envelope.source,
            params=envelope.params,
            origin="api",
        )
    )
    derived = apply_rules_for_event(
        instance_path,
        name=envelope.name,
        source=envelope.source,
        params=envelope.params,
        origin="rules",
        logger=lambda msg: current_app.logger.debug(msg),
    )
    return envelope.id, datetime.fromtimestamp(envelope.ts, tz=timezone.utc).isoformat(), derived


def _cache_key(path: Path) -> tuple[str, int, int] | None:
    try:
        st = path.stat()
    except Exception:
        return None
    return (str(path), int(getattr(st, "st_mtime_ns", 0)), int(getattr(st, "st_size", 0)))


def _read_cached_json(path: Path, slot: str) -> Any:
    ck = _cache_key(path)
    entry = _JSON_CACHE.get(slot)
    if entry and ck is not None and entry.get("cache_key") == ck:
        return entry.get("value")
    if ck is None:
        _JSON_CACHE[slot] = {"cache_key": None, "value": None}
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        value = None
    _JSON_CACHE[slot] = {"cache_key": ck, "value": value}
    return value


def _registry_path() -> Path:
    return Path(__file__).resolve().parent.parent / "rules" / "registry.json"


def _load_registry() -> Dict[str, Any]:
    path = _registry_path()
    data = _read_cached_json(path, slot="registry")
    if isinstance(data, dict):
        return data
    return {}


def _hardware_event_index(registry: Dict[str, Any]) -> Tuple[Dict[str, set], Dict[str, set]]:
    triggers = registry.get("triggers") if isinstance(registry, dict) else {}
    hardware = triggers.get("hardware") if isinstance(triggers, dict) else {}
    device_classes = hardware.get("deviceClasses") if isinstance(hardware, dict) else {}
    events_by_class: Dict[str, set] = {}
    params_by_event: Dict[str, set] = {}
    if isinstance(device_classes, dict):
        for class_key, meta in device_classes.items():
            evs = meta.get("events") if isinstance(meta, dict) else []
            names = set()
            for entry in evs if isinstance(evs, list) else []:
                if isinstance(entry, dict):
                    key = entry.get("key")
                    if isinstance(key, str):
                        names.add(key)
                        params = entry.get("params")
                        if isinstance(params, list):
                            params_by_event.setdefault(key, set()).update(
                                p for p in params if isinstance(p, str)
                            )
                elif isinstance(entry, str):
                    names.add(entry)
            if names:
                events_by_class[class_key] = names
    return events_by_class, params_by_event


def _system_event_index(registry: Dict[str, Any]) -> set:
    triggers = registry.get("triggers") if isinstance(registry, dict) else {}
    system = triggers.get("system") if isinstance(triggers, dict) else {}
    categories = system.get("categories") if isinstance(system, dict) else {}
    events = set()
    if isinstance(categories, dict):
        for meta in categories.values():
            evs = meta.get("events") if isinstance(meta, dict) else []
            for entry in evs if isinstance(evs, list) else []:
                if isinstance(entry, str):
                    events.add(entry)
    return events


def _custom_event_pattern(registry: Dict[str, Any]) -> re.Pattern | None:
    triggers = registry.get("triggers") if isinstance(registry, dict) else {}
    custom = triggers.get("custom") if isinstance(triggers, dict) else {}
    if not custom.get("freeText"):
        return None
    pattern = custom.get("validation")
    if isinstance(pattern, str) and pattern:
        try:
            return re.compile(pattern)
        except re.error:
            return None
    return None


def _load_mapping() -> Dict[str, dict]:
    mapping_path = Path(current_app.instance_path) / "hardware" / "mapping.json"
    raw = _read_cached_json(mapping_path, slot=f"mapping:{mapping_path}")
    if raw is None:
        return {}
    if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
        return raw["data"]
    if isinstance(raw, dict):
        return raw
    return {}


def _uid_tail(uid: str) -> str:
    s = str(uid or "").strip()
    if not s:
        return ""
    i = s.find("__")
    return s[i + 2:] if i >= 0 else s


def _canonical_source(source: str | None) -> str | None:
    if source is None:
        return None
    sid = str(source).strip()
    if not sid:
        return None
    mapping = _load_mapping()
    if sid in mapping:
        return sid
    tail = _uid_tail(sid)
    if not tail:
        return sid
    for key in mapping.keys():
        if _uid_tail(key) == tail:
            return key
    return sid


def _device_class_for_source(source: str) -> str | None:
    mapping = _load_mapping()
    row = mapping.get(_canonical_source(source) or source) if isinstance(mapping, dict) else None
    if not isinstance(row, dict):
        return None
    fn = (row.get("function") or "").strip()
    if not fn:
        return None
    function_map = {
        "Button": "button",
        "Switch": "switch",
        "Accelerometer": "accelerometer",
        "NFC": "nfc",
    }
    return function_map.get(fn)


def _validate_params(params: Dict[str, Any], allowed: set) -> Tuple[bool, str | None]:
    filtered = {k: v for k, v in params.items() if k != "eventType"}
    if not filtered:
        return True, None
    if not allowed:
        return False, "params_not_allowed"
    for key in filtered.keys():
        if key not in allowed:
            return False, f"param_not_allowed:{key}"
    missing = [k for k in allowed if k not in filtered]
    if missing:
        return False, f"missing_params:{','.join(missing)}"
    return True, None


def _validate_event(name: str, source: str | None, params: Dict[str, Any]) -> Tuple[bool, str | None]:
    registry = _load_registry()
    hardware_events, hardware_params = _hardware_event_index(registry)
    system_events = _system_event_index(registry)
    custom_pattern = _custom_event_pattern(registry)
    event_type = params.get("eventType") if isinstance(params.get("eventType"), str) else None
    source = _canonical_source(source)

    if name in system_events:
        if event_type:
            return False, "event_type_not_allowed"
        return _validate_params(params, set())

    if source:
        device_class = _device_class_for_source(source)
        if not device_class:
            return False, "unknown_source"
        if not event_type and name in hardware_events.get(device_class, set()):
            event_type = name
        if event_type:
            if event_type not in hardware_events.get(device_class, set()):
                return False, "invalid_event_for_source"
            allowed = hardware_params.get(event_type, set())
            ok, error = _validate_params(params, allowed)
            if not ok:
                return False, error
            if name not in system_events:
                if custom_pattern and not custom_pattern.match(name):
                    return False, "invalid_custom_event"
            return True, None

    if custom_pattern:
        if not custom_pattern.match(name):
            return False, "invalid_custom_event"
        return _validate_params(params, set())

    return False, "unknown_event"


@api_bp.get("/registry")
def events_registry():
    registry = _load_registry()
    triggers = registry.get("triggers") if isinstance(registry, dict) else {}
    return jsonify({"ok": True, "triggers": triggers})


@api_bp.get("/coverage")
def events_coverage():
    mgr = get_event_manager(instance_path=current_app.instance_path)
    return jsonify({"ok": True, "coverage": mgr.coverage()})


@api_bp.post("/fire")
def fire_event():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"ok": False, "error": "missing_name"}), 400
    name = name.strip()
    source = payload.get("source")
    if source is not None and not isinstance(source, str):
        return jsonify({"ok": False, "error": "invalid_source"}), 400
    source = _canonical_source(source)
    params = payload.get("params") if isinstance(payload, dict) else None
    simulated = bool(payload.get("simulated")) if isinstance(payload, dict) else False
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return jsonify({"ok": False, "error": "invalid_params"}), 400

    ok, error = _validate_event(name, source, params)
    if not ok:
        return jsonify({"ok": False, "error": error or "invalid_event"}), 400

    _mark_fire_submit()

    bridge_event = {
        "cmd": "EVENT_FIRE",
        "name": name,
        "source": source or "pi.api",
    }
    if isinstance(params, dict) and params:
        bridge_event["params"] = dict(params)
        et = params.get("eventType")
        if isinstance(et, str) and et:
            bridge_event["eventType"] = et

    bridge_enqueued, bridge_error = _enqueue_bridge_event_fast(bridge_event)
    _mark_fire_complete(bridge_ok=bridge_enqueued)

    event_id = uuid4().hex
    event_ts = datetime.now(timezone.utc).isoformat()
    derived: list[Dict[str, Any]] = []
    local_processed = False
    try:
        local_params = dict(params)
        if simulated:
            local_params["__simulated"] = True
        event_id, event_ts, derived = _process_event_local(
            instance_path=current_app.instance_path,
            name=name,
            source=source,
            params=local_params,
        )
        local_processed = True
    except Exception:
        current_app.logger.exception("local event processing failed name=%s source=%s", name, source)

    try:
        append_event_log(
            origin="api",
            direction="pi->esp",
            name=name,
            source=source,
            params=params,
            meta={
                "event_id": event_id,
                "bridge_cmd": "EVENT_FIRE",
                "bridge_enqueued": bridge_enqueued,
                "bridge_error": bridge_error,
                "local_processed": local_processed,
            },
        )
    except Exception:
        current_app.logger.exception("event append_event_log failed")
    if current_app.logger.isEnabledFor(logging.DEBUG):
        current_app.logger.debug("EVENT FIRE queued name=%s source=%s params=%s", name, source, params)
    return jsonify(
        {
            "ok": True,
            "bridge": {"enqueued": bridge_enqueued, "error": bridge_error, "async": False},
            "derived": derived,
            "event": {
                "id": event_id,
                "ts": event_ts,
                "name": name,
                "source": source,
                "params": params,
            },
        }
    )


@api_bp.get("/perf")
def events_perf():
    perf = _snapshot_fire_perf()
    return jsonify(
        {
            "ok": True,
            "source": {"scope": "process", "workerCount": 1},
            "postFire": {
                "submitted": int(perf.get("submitted", 0)),
                "completed": int(perf.get("completed", 0)),
                "pendingTotal": int(perf.get("pendingTotal", 0)),
                "inflight": int(perf.get("inflight", 0)),
                "queued": int(perf.get("queued", 0)),
                "maxInflight": int(perf.get("maxInflight", 0)),
                "lastSubmitAtMs": int(perf.get("lastSubmitAtMs", 0)),
                "lastCompleteAtMs": int(perf.get("lastCompleteAtMs", 0)),
                "bridgeErrors": int(perf.get("bridgeErrors", 0)),
            },
        }
    )


@api_bp.get("/stream")
def stream_events():
    bus = get_bus()
    q = bus.subscribe()
    bridge_log = events_log_path()
    bridge_offset = 0
    bridge_inode = None
    bridge_tail = ""

    try:
        if bridge_log.exists():
            st = bridge_log.stat()
            bridge_offset = int(st.st_size)
            bridge_inode = int(getattr(st, "st_ino", 0) or 0)
    except Exception:
        bridge_offset = 0
        bridge_inode = None

    def gen():
        nonlocal bridge_offset, bridge_inode, bridge_tail
        # Heartbeats ensure disconnected clients are detected promptly.
        # Without periodic writes, rapid page refresh can leave stale SSE
        # handlers occupying worker threads until the next real event arrives.
        poll_s = 0.05
        heartbeat_s = 2.0
        last_heartbeat_at = time.monotonic()

        def _streamable_log_record(rec: dict[str, Any]) -> bool:
            origin = str(rec.get("origin") or "").strip().lower()
            direction = str(rec.get("direction") or "").strip().lower()
            name = str(rec.get("name") or "").strip().upper()
            meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
            bridge_cmd = str(meta.get("bridge_cmd") or "").strip().upper()
            is_bridge_inbound = origin == "bridge" and direction == "esp->pi"
            # Forward only API event-fire envelopes (not every API log line)
            # so SSE clients on different workers can still see UI-triggered
            # hardware events.
            is_api_event_fire = origin == "api" and bridge_cmd == "EVENT_FIRE"
            # Forward LCD runtime commands so Live View can render current text.
            is_rules_lcd_set = origin == "rules" and direction == "pi->esp" and name == "LCD_SET"
            # Forward lighting scene runtime commands so Live View can run scene
            # playback even when running headless/offline.
            is_rules_light_scene = (
                origin == "rules"
                and direction == "pi->esp"
                and name in {"LIGHT_SCENE_PLAY", "LIGHT_SCENE_STOP"}
            )
            return is_bridge_inbound or is_api_event_fire or is_rules_lcd_set or is_rules_light_scene

        def _drain_bridge_events() -> list[str]:
            nonlocal bridge_offset, bridge_inode, bridge_tail
            out: list[str] = []
            try:
                if not bridge_log.exists():
                    bridge_offset = 0
                    bridge_inode = None
                    bridge_tail = ""
                    return out
                st = bridge_log.stat()
                inode = int(getattr(st, "st_ino", 0) or 0)
                size = int(st.st_size)
                if bridge_inode is None:
                    bridge_inode = inode
                if inode != bridge_inode or size < bridge_offset:
                    bridge_inode = inode
                    bridge_offset = 0
                    bridge_tail = ""
                if size <= bridge_offset:
                    return out
                with bridge_log.open("r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(bridge_offset)
                    chunk = fh.read()
                    bridge_offset = int(fh.tell())
                if not chunk:
                    return out
                text = bridge_tail + chunk
                lines = text.splitlines()
                if text and not text.endswith("\n"):
                    bridge_tail = lines.pop() if lines else text
                else:
                    bridge_tail = ""
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    if not _streamable_log_record(rec):
                        continue
                    name = rec.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    source = rec.get("source")
                    source_val = source if isinstance(source, str) else None
                    params = rec.get("params") if isinstance(rec.get("params"), dict) else {}
                    origin = str(rec.get("origin") or "").strip().lower()
                    payload = json.dumps(
                        {
                            "id": (
                                f"{origin}:{rec.get('ts', '')}:{name}:{source_val or ''}:"
                                f"{params.get('seq', '')}:{params.get('eventType', '')}"
                            ),
                            "ts": rec.get("ts"),
                            "name": name,
                            "source": source_val,
                            "params": params,
                        },
                        separators=(",", ":"),
                        ensure_ascii=True,
                    )
                    out.append(f"data: {payload}\n\n")
            except Exception:
                return out
            return out

        try:
            while True:
                bridge_msgs = _drain_bridge_events()
                if bridge_msgs:
                    # Interleave with bus events to avoid starving locally-fired
                    # events when bridge traffic is busy.
                    for msg in bridge_msgs[:_SSE_BRIDGE_DRAIN_BATCH]:
                        yield msg
                try:
                    ev = q.get(timeout=poll_s)
                except Empty:
                    now = time.monotonic()
                    if (now - last_heartbeat_at) >= heartbeat_s:
                        yield ": keepalive\n\n"
                        last_heartbeat_at = now
                    continue
                payload = json.dumps(
                    {
                        "id": ev.id,
                        "ts": ev.ts,
                        "name": ev.name,
                        "source": ev.source,
                        "params": ev.params,
                    },
                    separators=(",", ":"),
                    ensure_ascii=True,
                )
                yield f"data: {payload}\n\n"
        finally:
            bus.unsubscribe(q)

    headers = {
        "Cache-Control": "no-store",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(gen()), headers=headers)
