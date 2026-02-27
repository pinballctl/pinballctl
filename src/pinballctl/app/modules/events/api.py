"""Events API: fire events and stream via SSE."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from queue import Empty
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Any, Dict, Tuple

from flask import Response, current_app, jsonify, request, stream_with_context

from pinballctl.events import EventContext, get_bus, get_event_manager
from pinballctl.events.audit_log import append_event_log, events_log_path
from pinballctl.bridge.state import enqueue_command
from pinballctl.rules.runtime import apply_rules_for_event
from . import api_bp

_JSON_CACHE: Dict[str, Dict[str, Any]] = {}
_POST_FIRE_EXECUTOR = ThreadPoolExecutor(max_workers=8, thread_name_prefix="events-postfire")
_POST_FIRE_STATS_LOCK = Lock()
_BRIDGE_ENQUEUE_LOCK = Lock()
_BRIDGE_ENQUEUE_SKIP_UNTIL_MONO = 0.0
_PERF_FLUSH_LOCK = Lock()
_PERF_FLUSH_LAST_MONO = 0.0
_PERF_FLUSH_INTERVAL_S = 0.5
_PERF_CLEANUP_LAST_MONO = 0.0
_PERF_CLEANUP_INTERVAL_S = 30.0
_POST_FIRE_STATS: Dict[str, int | float] = {
    "submitted": 0,
    "completed": 0,
    "inflight": 0,
    "max_inflight": 0,
    "last_submit_at_ms": 0,
    "last_complete_at_ms": 0,
}


def _enqueue_bridge_event_fast(payload: Dict[str, Any]) -> tuple[bool, str | None]:
    """Fast-fail enqueue when bridge socket is known unavailable.

    Avoids per-event multi-second socket retries from stalling the post-fire worker pool.
    """
    global _BRIDGE_ENQUEUE_SKIP_UNTIL_MONO  # noqa: PLW0603
    now = time.monotonic()
    with _BRIDGE_ENQUEUE_LOCK:
        skip_until = float(_BRIDGE_ENQUEUE_SKIP_UNTIL_MONO or 0.0)
    if now < skip_until:
        return False, "bridge_unavailable_cached"
    try:
        enqueue_command(payload)
        return True, None
    except Exception as exc:
        with _BRIDGE_ENQUEUE_LOCK:
            # Short circuit subsequent enqueue attempts during outages.
            _BRIDGE_ENQUEUE_SKIP_UNTIL_MONO = time.monotonic() + 1.0
        return False, str(exc)


def _cache_key(path: Path) -> tuple[str, int, int] | None:
    try:
        st = path.stat()
    except Exception:
        return None
    return (str(path), int(getattr(st, "st_mtime_ns", 0)), int(getattr(st, "st_size", 0)))


def _perf_workers_dir(instance_path: str) -> Path:
    p = Path(instance_path) / "events" / "perf_workers"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _maybe_flush_global_perf(app) -> None:
    """Write per-worker perf snapshot at a throttled cadence."""
    global _PERF_FLUSH_LAST_MONO, _PERF_CLEANUP_LAST_MONO  # noqa: PLW0603
    now_mono = time.monotonic()
    with _PERF_FLUSH_LOCK:
        if (now_mono - float(_PERF_FLUSH_LAST_MONO or 0.0)) < _PERF_FLUSH_INTERVAL_S:
            return
        _PERF_FLUSH_LAST_MONO = now_mono
    with _POST_FIRE_STATS_LOCK:
        snapshot = {
            "pid": int(os.getpid()),
            "updatedAtMs": int(time.time() * 1000),
            "submitted": int(_POST_FIRE_STATS.get("submitted", 0)),
            "completed": int(_POST_FIRE_STATS.get("completed", 0)),
            "inflight": int(_POST_FIRE_STATS.get("inflight", 0)),
            "maxInflight": int(_POST_FIRE_STATS.get("max_inflight", 0)),
            "lastSubmitAtMs": int(_POST_FIRE_STATS.get("last_submit_at_ms", 0)),
            "lastCompleteAtMs": int(_POST_FIRE_STATS.get("last_complete_at_ms", 0)),
        }
    try:
        out_dir = _perf_workers_dir(app.instance_path)
        out_file = out_dir / f"{snapshot['pid']}.json"
        tmp_file = out_file.with_suffix(".json.tmp")
        tmp_file.write_text(json.dumps(snapshot, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
        tmp_file.replace(out_file)
    except Exception:
        return

    if (now_mono - float(_PERF_CLEANUP_LAST_MONO or 0.0)) < _PERF_CLEANUP_INTERVAL_S:
        return
    _PERF_CLEANUP_LAST_MONO = now_mono
    try:
        cutoff_ms = int(time.time() * 1000) - 120000
        out_dir = _perf_workers_dir(app.instance_path)
        for fp in out_dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                updated = int(data.get("updatedAtMs", 0)) if isinstance(data, dict) else 0
                if updated > 0 and updated < cutoff_ms:
                    fp.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass


def _aggregate_global_perf(app) -> dict[str, Any] | None:
    try:
        out_dir = _perf_workers_dir(app.instance_path)
    except Exception:
        return None
    now_ms = int(time.time() * 1000)
    # Keep workers in the aggregate long enough to avoid oscillation during idle.
    ttl_ms = 10 * 60 * 1000
    workers: list[dict[str, Any]] = []
    try:
        for fp in out_dir.glob("*.json"):
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            updated = int(data.get("updatedAtMs", 0) or 0)
            if updated <= 0 or (now_ms - updated) > ttl_ms:
                continue
            workers.append(data)
    except Exception:
        return None
    if not workers:
        return {
            "submitted": 0,
            "completed": 0,
            "inflight": 0,
            "maxInflight": 0,
            "lastSubmitAtMs": 0,
            "lastCompleteAtMs": 0,
            "pendingTotal": 0,
            "queued": 0,
            "workerCount": 0,
        }
    submitted = sum(int(w.get("submitted", 0) or 0) for w in workers)
    completed = sum(int(w.get("completed", 0) or 0) for w in workers)
    inflight = sum(int(w.get("inflight", 0) or 0) for w in workers)
    max_inflight = max((int(w.get("maxInflight", 0) or 0) for w in workers), default=0)
    last_submit_at_ms = max((int(w.get("lastSubmitAtMs", 0) or 0) for w in workers), default=0)
    last_complete_at_ms = max((int(w.get("lastCompleteAtMs", 0) or 0) for w in workers), default=0)
    pending_total = max(0, submitted - completed)
    pending_queue = max(0, pending_total - inflight)
    return {
        "submitted": submitted,
        "completed": completed,
        "inflight": inflight,
        "maxInflight": max_inflight,
        "lastSubmitAtMs": last_submit_at_ms,
        "lastCompleteAtMs": last_complete_at_ms,
        "pendingTotal": pending_total,
        "queued": pending_queue,
        "workerCount": len(workers),
    }


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


def _post_fire_processing(
    app,
    *,
    envelope,
    bridge_event: Dict[str, Any],
    run_rules: bool = True,
) -> None:
    """Run non-ACK-critical work off the request hot path."""
    try:
        with app.app_context():
            bridge_enqueued = False
            bridge_error: str | None = None
            bridge_enqueued, bridge_error = _enqueue_bridge_event_fast(bridge_event)
            try:
                mgr = get_event_manager(
                    instance_path=app.instance_path,
                    logger=lambda msg: app.logger.debug(msg),
                )
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
            except Exception:
                app.logger.exception("event manager dispatch failed")
            try:
                append_event_log(
                    origin="api",
                    direction="pi->esp",
                    name=envelope.name,
                    source=envelope.source,
                    params=envelope.params,
                    meta={
                        "event_id": envelope.id,
                        "bridge_cmd": "EVENT_FIRE",
                        "bridge_enqueued": bridge_enqueued,
                        "bridge_error": bridge_error,
                    },
                )
            except Exception:
                app.logger.exception("event append_event_log failed")
            if run_rules:
                try:
                    apply_rules_for_event(
                        app.instance_path,
                        name=envelope.name,
                        source=envelope.source,
                        params=envelope.params,
                        origin="rules",
                        logger=lambda msg: app.logger.debug(msg),
                        enqueue_bridge_event=_enqueue_bridge_event_fast,
                    )
                except Exception:
                    app.logger.exception("rule actions failed")
    finally:
        now_ms = int(time.time() * 1000)
        with _POST_FIRE_STATS_LOCK:
            _POST_FIRE_STATS["inflight"] = max(0, int(_POST_FIRE_STATS.get("inflight", 0)) - 1)
            _POST_FIRE_STATS["completed"] = int(_POST_FIRE_STATS.get("completed", 0)) + 1
            _POST_FIRE_STATS["last_complete_at_ms"] = now_ms
        try:
            _maybe_flush_global_perf(app)
        except Exception:
            pass


def _device_class_for_source(source: str) -> str | None:
    mapping = _load_mapping()
    row = mapping.get(source) if isinstance(mapping, dict) else None
    if not isinstance(row, dict):
        return None
    fn = (row.get("function") or "").strip()
    if not fn:
        return None
    function_map = {
        "Button": "button",
        "Switch": "switch",
        "Accelerometer": "gyro",
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
    params = payload.get("params") if isinstance(payload, dict) else None
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return jsonify({"ok": False, "error": "invalid_params"}), 400

    ok, error = _validate_event(name, source, params)
    if not ok:
        return jsonify({"ok": False, "error": error or "invalid_event"}), 400

    bridge_event = {
        "cmd": "EVENT_FIRE",
        "name": name,
        "source": source or "pi.api",
        "seq": int(time.time() * 1000),
    }
    if isinstance(params, dict) and params:
        bridge_event["params"] = dict(params)
        et = params.get("eventType")
        if isinstance(et, str) and et:
            bridge_event["eventType"] = et
    envelope = get_bus().emit(name=name, source=source, params=params)
    derived: list[dict[str, Any]] = []
    try:
        # Keep gameplay reaction paths (e.g., audio cues from shortcut-triggered
        # rules) on the immediate request path to avoid thread-pool queue delay.
        derived = apply_rules_for_event(
            current_app.instance_path,
            name=envelope.name,
            source=envelope.source,
            params=envelope.params,
            origin="rules",
            logger=lambda msg: current_app.logger.debug(msg),
            enqueue_bridge_event=_enqueue_bridge_event_fast,
        )
    except Exception:
        current_app.logger.exception("rule actions failed")
    now_ms = int(time.time() * 1000)
    with _POST_FIRE_STATS_LOCK:
        _POST_FIRE_STATS["submitted"] = int(_POST_FIRE_STATS.get("submitted", 0)) + 1
        _POST_FIRE_STATS["inflight"] = int(_POST_FIRE_STATS.get("inflight", 0)) + 1
        if int(_POST_FIRE_STATS["inflight"]) > int(_POST_FIRE_STATS.get("max_inflight", 0)):
            _POST_FIRE_STATS["max_inflight"] = int(_POST_FIRE_STATS["inflight"])
        _POST_FIRE_STATS["last_submit_at_ms"] = now_ms
    app = current_app._get_current_object()
    _maybe_flush_global_perf(app)
    _POST_FIRE_EXECUTOR.submit(
        _post_fire_processing,
        app,
        envelope=envelope,
        bridge_event=bridge_event,
        run_rules=False,
    )
    if current_app.logger.isEnabledFor(logging.DEBUG):
        current_app.logger.debug(
            "EVENT EMIT name=%s source=%s id=%s params=%s",
            envelope.name,
            envelope.source,
            envelope.id,
            envelope.params,
        )
    return jsonify({
        "ok": True,
        "bridge": {"enqueued": None, "error": None, "async": True},
        "derived": derived,
        "event": {
            "id": envelope.id,
            "ts": envelope.ts,
            "name": envelope.name,
            "source": envelope.source,
            "params": envelope.params,
        },
    })


@api_bp.get("/perf")
def events_perf():
    app = current_app._get_current_object()
    _maybe_flush_global_perf(app)
    global_perf = _aggregate_global_perf(app)
    return jsonify(
        {
            "ok": True,
            "source": {"scope": "global", "workerCount": int(global_perf.get("workerCount", 0))},
            "postFire": {
                "submitted": int(global_perf.get("submitted", 0)),
                "completed": int(global_perf.get("completed", 0)),
                "pendingTotal": int(global_perf.get("pendingTotal", 0)),
                "inflight": int(global_perf.get("inflight", 0)),
                "queued": int(global_perf.get("queued", 0)),
                "maxInflight": int(global_perf.get("maxInflight", 0)),
                "lastSubmitAtMs": int(global_perf.get("lastSubmitAtMs", 0)),
                "lastCompleteAtMs": int(global_perf.get("lastCompleteAtMs", 0)),
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
                    if rec.get("origin") != "bridge":
                        continue
                    if rec.get("direction") != "esp->pi":
                        continue
                    name = rec.get("name")
                    if not isinstance(name, str) or not name:
                        continue
                    source = rec.get("source")
                    source_val = source if isinstance(source, str) else None
                    params = rec.get("params") if isinstance(rec.get("params"), dict) else {}
                    payload = json.dumps({
                        "id": (
                            f"bridge:{rec.get('ts', '')}:{name}:{source_val or ''}:"
                            f"{params.get('seq', '')}:{params.get('eventType', '')}"
                        ),
                        "ts": rec.get("ts"),
                        "name": name,
                        "source": source_val,
                        "params": params,
                    }, separators=(",", ":"), ensure_ascii=True)
                    out.append(f"data: {payload}\n\n")
            except Exception:
                return out
            return out

        try:
            while True:
                bridge_msgs = _drain_bridge_events()
                if bridge_msgs:
                    for msg in bridge_msgs:
                        yield msg
                    continue
                try:
                    ev = q.get(timeout=poll_s)
                except Empty:
                    now = time.monotonic()
                    if (now - last_heartbeat_at) >= heartbeat_s:
                        yield ": keepalive\n\n"
                        last_heartbeat_at = now
                    continue
                payload = json.dumps({
                    "id": ev.id,
                    "ts": ev.ts,
                    "name": ev.name,
                    "source": ev.source,
                    "params": ev.params,
                }, separators=(",", ":"), ensure_ascii=True)
                yield f"data: {payload}\n\n"
        finally:
            bus.unsubscribe(q)

    headers = {
        "Cache-Control": "no-store",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(gen()), headers=headers)
