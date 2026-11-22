"""Events API: fire events and stream via SSE."""
from __future__ import annotations

from collections import deque
import json
import time
from queue import Empty
from typing import Any

from flask import Response, current_app, jsonify, request, stream_with_context

from pinballctl.runtime.events import get_bus, get_event_manager
from pinballctl.runtime.events.audit_log import events_log_path
from pinballctl.runtime.events.ingress import fire, load_registry, snapshot_fire_perf
from . import api_bp

_SSE_BRIDGE_DRAIN_BATCH = 32


@api_bp.get("/registry")
def events_registry():
    registry = load_registry()
    triggers = registry.get("triggers") if isinstance(registry, dict) else {}
    return jsonify({"ok": True, "triggers": triggers})


@api_bp.get("/coverage")
def events_coverage():
    mgr = get_event_manager(instance_path=current_app.instance_path)
    return jsonify({"ok": True, "coverage": mgr.coverage()})


@api_bp.post("/fire")
def fire_event():
    payload = request.get_json(silent=True)
    body, status = fire(current_app.instance_path, payload if isinstance(payload, dict) else {})
    response = jsonify(body)
    return response if status == 200 else (response, status)


@api_bp.get("/perf")
def events_perf():
    perf = snapshot_fire_perf()
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
        poll_s = 0.02
        heartbeat_s = 2.0
        last_heartbeat_at = time.monotonic()
        pending_bridge = deque()
        seen_ids = {}

        def first_delivery(payload):
            event_id = payload.get("id")
            if not event_id:
                return True
            if event_id in seen_ids:
                return False
            seen_ids[event_id] = None
            if len(seen_ids) > 512:
                del seen_ids[next(iter(seen_ids))]
            return True

        def _streamable_log_record(rec: dict[str, Any]) -> bool:
            origin = str(rec.get("origin") or "").strip().lower()
            direction = str(rec.get("direction") or "").strip().lower()
            name = str(rec.get("name") or "").strip().upper()
            meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
            bridge_cmd = str(meta.get("bridge_cmd") or "").strip().upper()
            is_bridge_inbound = (origin == "bridge" and direction == "esp->pi"
                                 and meta.get("t") != "EVENT_DROP" and not meta.get("local_dispatched"))
            # Forward only API event-fire envelopes (not every API log line)
            # so SSE clients on different workers can still see UI-triggered
            # hardware events.
            is_api_event_fire = (origin == "api" and bridge_cmd == "EVENT_FIRE"
                                 and bool(meta.get("local_processed")))
            # Forward LCD runtime commands so Live View can render current text.
            is_rules_lcd_set = origin == "rules" and direction == "pi->esp" and name == "LCD_SET"
            # Forward lighting scene runtime commands so Live View can run scene
            # playback even when running headless/offline.
            is_rules_light_scene = (
                origin == "rules"
                and direction == "pi->esp"
                and name in {"LIGHT_SCENE_PLAY", "LIGHT_SCENE_STOP"}
            )
            is_local_scoring = origin == "scoring" and bool(meta.get("event_id"))
            is_derived = origin == "rules" and bridge_cmd == "EVENT_FIRE" and bool(meta.get("event_id"))
            return is_bridge_inbound or is_api_event_fire or is_rules_lcd_set or is_rules_light_scene or is_local_scoring or is_derived

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
                    chunk = fh.read(65536)
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
                            "id": (rec.get("meta") or {}).get("event_id") or (
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
            yield ": connected\n\n"
            while True:
                if not pending_bridge:
                    pending_bridge.extend(_drain_bridge_events())
                if pending_bridge:
                    # Interleave with bus events to avoid starving locally-fired
                    # events when bridge traffic is busy.
                    for _ in range(min(len(pending_bridge), _SSE_BRIDGE_DRAIN_BATCH)):
                        message = pending_bridge.popleft()
                        if first_delivery(json.loads(message[6:])):
                            yield message
                try:
                    ev = q.get(timeout=0 if pending_bridge else poll_s)
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
                if first_delivery({"id": ev.id}):
                    yield f"data: {payload}\n\n"
        finally:
            bus.unsubscribe(q)

    headers = {
        "Cache-Control": "no-store",
        "Content-Type": "text/event-stream",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(gen()), headers=headers)
