"""Isolated media runtime instances.

Each embedded, fullscreen, or windowed launch becomes its own runtime instance.
Display-managed stacks exist only within a single launch mode, so windowed
instances never interfere with embedded or fullscreen rendering.
"""
from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any, Dict, List
from urllib.parse import urlencode
from uuid import uuid4

from pinballctl.media.runtime import (
    BLEND_MODE_PAUSE_LOWER,
    BLEND_MODE_PLAY_OVER,
    BLEND_MODE_STOP_LOWER,
    DEFAULT_SCENE_STACK_BEHAVIOR,
    DUPLICATE_ALLOW,
    DUPLICATE_COALESCE,
    DUPLICATE_DROP_IF_PLAYING,
    DUPLICATE_DROP_IF_QUEUED,
    INTERRUPT_ALLOW,
    INTERRUPT_NO_INTERRUPT,
    INTERRUPT_QUEUE,
    INTERRUPT_RESTART,
    LAUNCH_MODE_EMBEDDED,
    LAUNCH_MODE_FULLSCREEN,
    LAUNCH_MODE_WINDOWED,
    _autoplay_displays,
    _default_displays,
    _default_overlay_values,
    _default_scene_for_display,
    _emit_media_audio_intent_changes,
    _format_elapsed_mmss,
    _get_engine,
    _load_scoring_state_nonblocking,
    _media_base_url,
    _media_state_path,
    _normalize_launch_mode,
    _normalize_stack_behavior,
    _now_ms,
    _read_json,
    _render_layers_for_display,
    _resolve_scene_displays,
    _scene_map,
    _stop_pid,
    _top_session_by_display,
    _utc_now_iso,
    _write_json,
    _is_managed_media_pid,
    _is_pid_alive,
    ensure_media_bus_worker,
    load_media_config,
)

RUNTIME_STORAGE_KEY = "runtimeIsolated"
INSTANCE_STATE_STARTING = "starting"
INSTANCE_STATE_RUNNING = "running"
INSTANCE_STATE_STOPPING = "stopping"
INSTANCE_STATE_STOPPED = "stopped"
INSTANCE_STATE_CRASHED = "crashed"
DESIRED_PRESENT = "present"
DESIRED_ABSENT = "absent"
SURFACE_HEARTBEAT_TIMEOUT_MS = 5000
SURFACE_STARTUP_GRACE_MS = 20000
SURFACE_DETACH_GRACE_MS = 5000
STOPPED_RETENTION_MS = 60000

_ACTIVE_STATES = (
    INSTANCE_STATE_STARTING,
    INSTANCE_STATE_RUNNING,
    INSTANCE_STATE_STOPPING,
)
_DISPLAY_STACK_MODES = (
    LAUNCH_MODE_EMBEDDED,
    LAUNCH_MODE_FULLSCREEN,
)


def _stack_key(display_id: str, mode: str) -> str:
    return f"{_normalize_launch_mode(mode)}:{str(display_id or '').strip()}"


def _public_display_states(stacks: Dict[str, List[str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key, rows in stacks.items():
        mode, _, display_id = key.partition(":")
        if not display_id:
            continue
        row = out.setdefault(display_id, {"display_id": display_id, "embedded": [], "fullscreen": []})
        if mode == LAUNCH_MODE_EMBEDDED:
            row["embedded"] = list(rows)
        elif mode == LAUNCH_MODE_FULLSCREEN:
            row["fullscreen"] = list(rows)
    return out


def _instance_to_surface_row(inst: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(inst.get("instance_id") or ""),
        "runtimeId": str(inst.get("runtime_id") or ""),
        "sceneId": str(inst.get("scene_id") or ""),
        "displayId": str(inst.get("display_id") or ""),
        "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
        "startedAtMs": max(0, int(inst.get("created_at") or 0)),
        "runtimeUrl": str(inst.get("runtime_url") or ""),
        "launchMode": _normalize_launch_mode(inst.get("mode")),
        "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
        "priority": int(inst.get("priority") or 100),
        "blendMode": str(inst.get("blend_mode") or BLEND_MODE_STOP_LOWER),
        "interruptPolicy": str(inst.get("interrupt_policy") or INTERRUPT_NO_INTERRUPT),
        "duplicatePolicy": str(inst.get("duplicate_policy") or DUPLICATE_DROP_IF_PLAYING),
        "audioBehaviour": dict(inst.get("audio_behaviour") if isinstance(inst.get("audio_behaviour"), dict) else {}),
        "state": str(inst.get("state") or ""),
        "desiredState": str(inst.get("desired_state") or ""),
        "lastSeenMs": max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0))),
    }


def _instance_to_output_endpoint(inst: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(inst.get("instance_id") or ""),
        "outputId": str(inst.get("instance_id") or ""),
        "runtimeId": str(inst.get("runtime_id") or ""),
        "sceneId": str(inst.get("scene_id") or ""),
        "createdAtMs": max(0, int(inst.get("created_at") or 0)),
        "type": _normalize_launch_mode(inst.get("mode")),
        "target": {
            "displayId": str(inst.get("display_id") or ""),
            "containerId": str(inst.get("display_id") or "") if _normalize_launch_mode(inst.get("mode")) == LAUNCH_MODE_EMBEDDED else "",
        },
        "displayId": str(inst.get("display_id") or ""),
        "state": str(inst.get("state") or ""),
        "desiredState": str(inst.get("desired_state") or ""),
        "lastFrameTime": max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0))),
        "lastSeenMs": max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0))),
        "runtimeUrl": str(inst.get("runtime_url") or ""),
        "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
        "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
    }


def _session_with_outputs(session: Dict[str, Any], outputs_by_runtime: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    runtime_id = str(session.get("id") or session.get("runtimeId") or "").strip()
    outputs = list(outputs_by_runtime.get(runtime_id, []))
    row = dict(session)
    row["id"] = runtime_id
    row["runtimeId"] = runtime_id
    row["outputIds"] = [str(out.get("id") or "") for out in outputs if str(out.get("id") or "")]
    row["outputs"] = outputs
    return row


def _stop_managed_output_process(instance_path: str | Path, inst: Dict[str, Any] | None) -> None:
    if not isinstance(inst, dict):
        return
    mode = _normalize_launch_mode(inst.get("mode"))
    if mode not in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
        return
    pid = max(0, int((((inst.get("process") or {}).get("pid")) or 0)))
    if pid <= 0:
        return
    if _is_managed_media_pid(instance_path, pid):
        _stop_pid(pid)


def _public_runtime_sessions(
    sessions: List[Dict[str, Any]],
    outputs: List[Dict[str, Any]],
    *,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    outputs_by_runtime: Dict[str, List[Dict[str, Any]]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            continue
        if active_only and str(output.get("desiredState") or "") != DESIRED_PRESENT:
            continue
        runtime_id = str(output.get("runtimeId") or "").strip()
        if runtime_id:
            outputs_by_runtime.setdefault(runtime_id, []).append(output)
    rows: List[Dict[str, Any]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        if active_only and str(session.get("state") or "") not in _ACTIVE_STATES:
            continue
        row = _session_with_outputs(session, outputs_by_runtime)
        if active_only and not row.get("outputs"):
            continue
        rows.append(row)
    rows.sort(key=lambda row: int(row.get("createdAtMs") or 0), reverse=True)
    return rows


class _IsolatedRuntimeRegistry:
    def __init__(self, instance_path: str | Path):
        self.instance_path = str(Path(instance_path).resolve())
        self._lock = Lock()
        self._loaded = False
        self._dirty = False
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Dict[str, Any]] = {}
        self._display_stacks: Dict[str, List[str]] = {}
        self._overlay_values: Dict[str, Any] = _default_overlay_values()
        self._cooldowns: Dict[str, int] = {}
        self._queue_depths: Dict[str, int] = {}

    def _load_locked(self) -> None:
        if self._loaded and self._dirty:
            return
        payload = _read_json(_media_state_path(self.instance_path), {})
        if not isinstance(payload, dict):
            payload = {}
        self._overlay_values = _default_overlay_values()
        if isinstance(payload.get("overlayValues"), dict):
            self._overlay_values.update(payload.get("overlayValues"))
        runtime_raw = payload.get(RUNTIME_STORAGE_KEY) if isinstance(payload.get(RUNTIME_STORAGE_KEY), dict) else {}
        sessions_in = runtime_raw.get("sessions") if isinstance(runtime_raw.get("sessions"), list) else []
        instances_in = runtime_raw.get("instances") if isinstance(runtime_raw.get("instances"), list) else []
        stacks_in = runtime_raw.get("displayStacks") if isinstance(runtime_raw.get("displayStacks"), dict) else {}
        cooldowns_in = runtime_raw.get("cooldowns") if isinstance(runtime_raw.get("cooldowns"), dict) else {}
        queue_depths_in = runtime_raw.get("queueDepths") if isinstance(runtime_raw.get("queueDepths"), dict) else {}

        sessions: Dict[str, Dict[str, Any]] = {}
        for raw in sessions_in:
            if not isinstance(raw, dict):
                continue
            runtime_id = str(raw.get("id") or raw.get("runtimeId") or "").strip()
            scene_id = str(raw.get("sceneId") or raw.get("scene_id") or "").strip()
            if not runtime_id or not scene_id:
                continue
            sessions[runtime_id] = {
                "id": runtime_id,
                "runtimeId": runtime_id,
                "sceneId": scene_id,
                "state": str(raw.get("state") or INSTANCE_STATE_RUNNING).strip().lower() or INSTANCE_STATE_RUNNING,
                "outputIds": [str(x or "").strip() for x in (raw.get("outputIds") if isinstance(raw.get("outputIds"), list) else []) if str(x or "").strip()],
                "createdAtMs": max(0, int(float(raw.get("createdAtMs") or raw.get("created_at") or _now_ms()))),
                "updatedAtMs": max(0, int(float(raw.get("updatedAtMs") or raw.get("updated_at") or raw.get("createdAtMs") or _now_ms()))),
                "health": str(raw.get("health") or "ok").strip() or "ok",
            }
        instances: Dict[str, Dict[str, Any]] = {}
        for raw in instances_in:
            if not isinstance(raw, dict):
                continue
            iid = str(raw.get("instance_id") or raw.get("id") or "").strip()
            sid = str(raw.get("scene_id") or raw.get("sceneId") or "").strip()
            did = str(raw.get("display_id") or raw.get("displayId") or "").strip()
            if not iid or not sid or not did:
                continue
            instances[iid] = {
                "instance_id": iid,
                "runtime_id": str(raw.get("runtime_id") or raw.get("runtimeId") or f"RT-{sid}").strip() or f"RT-{sid}",
                "scene_id": sid,
                "display_id": did,
                "mode": _normalize_launch_mode(raw.get("mode") or raw.get("launchMode")),
                "state": str(raw.get("state") or INSTANCE_STATE_RUNNING).strip().lower() or INSTANCE_STATE_RUNNING,
                "desired_state": str(raw.get("desired_state") or raw.get("desiredState") or DESIRED_PRESENT).strip().lower() or DESIRED_PRESENT,
                "created_at": max(0, int(float(raw.get("created_at") or raw.get("createdAt") or _now_ms()))),
                "updated_at": max(0, int(float(raw.get("updated_at") or raw.get("updatedAt") or raw.get("created_at") or raw.get("createdAt") or _now_ms()))),
                "runtime_url": str(raw.get("runtime_url") or raw.get("runtimeUrl") or "").strip(),
                "preview_viewport": raw.get("preview_viewport") if isinstance(raw.get("preview_viewport"), dict) else raw.get("previewViewport") if isinstance(raw.get("previewViewport"), dict) else None,
                "source": str(raw.get("source") or "").strip(),
                "priority": int(float(raw.get("priority") or 100)),
                "blend_mode": str(raw.get("blend_mode") or raw.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper(),
                "interrupt_policy": str(raw.get("interrupt_policy") or raw.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper(),
                "duplicate_policy": str(raw.get("duplicate_policy") or raw.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper(),
                "audio_behaviour": dict(raw.get("audio_behaviour") if isinstance(raw.get("audio_behaviour"), dict) else raw.get("audioBehaviour") if isinstance(raw.get("audioBehaviour"), dict) else {}),
                "process": {
                    "pid": max(0, int(float(((raw.get("process") or {}).get("pid") if isinstance(raw.get("process"), dict) else raw.get("pid")) or 0))),
                    "started_at": max(0, int(float(((raw.get("process") or {}).get("started_at") if isinstance(raw.get("process"), dict) else raw.get("created_at") or raw.get("createdAt") or _now_ms()) or 0))),
                    "last_seen_at": max(0, int(float(((raw.get("process") or {}).get("last_seen_at") if isinstance(raw.get("process"), dict) else raw.get("updated_at") or raw.get("updatedAt") or _now_ms()) or 0))),
                    "exit_code": ((raw.get("process") or {}).get("exit_code") if isinstance(raw.get("process"), dict) else None),
                },
                "surface": {
                    "attached": bool(((raw.get("surface") or {}).get("attached") if isinstance(raw.get("surface"), dict) else False)),
                    "surface_id": str(((raw.get("surface") or {}).get("surface_id") if isinstance(raw.get("surface"), dict) else "") or ((raw.get("surface") or {}).get("surfaceId") if isinstance(raw.get("surface"), dict) else "") or "").strip(),
                    "attached_at": max(0, int(float(((raw.get("surface") or {}).get("attached_at") if isinstance(raw.get("surface"), dict) else 0) or ((raw.get("surface") or {}).get("attachedAt") if isinstance(raw.get("surface"), dict) else 0) or 0))),
                    "last_heartbeat_at": max(0, int(float(((raw.get("surface") or {}).get("last_heartbeat_at") if isinstance(raw.get("surface"), dict) else 0) or ((raw.get("surface") or {}).get("lastHeartbeatAt") if isinstance(raw.get("surface"), dict) else 0) or 0))),
                    "detached_at": max(0, int(float(((raw.get("surface") or {}).get("detached_at") if isinstance(raw.get("surface"), dict) else 0) or ((raw.get("surface") or {}).get("detachedAt") if isinstance(raw.get("surface"), dict) else 0) or 0))),
                },
            }
        self._sessions = sessions
        self._instances = instances
        self._display_stacks = {
            str(key or "").strip(): [str(x or "").strip() for x in rows if str(x or "").strip() in self._instances]
            for key, rows in stacks_in.items()
            if str(key or "").strip() and isinstance(rows, list)
        }
        self._cooldowns = {
            str(k or "").strip(): max(0, int(float(v or 0)))
            for k, v in cooldowns_in.items()
            if str(k or "").strip()
        }
        self._queue_depths = {
            str(k or "").strip(): max(0, int(float(v or 0)))
            for k, v in queue_depths_in.items()
            if str(k or "").strip()
        }
        self._sync_sessions_locked()
        self._sanitize_stacks_locked()
        self._loaded = True
        self._dirty = False

    def _persist_locked(self) -> None:
        payload = _read_json(_media_state_path(self.instance_path), {})
        if not isinstance(payload, dict):
            payload = {}
        payload["overlayValues"] = dict(self._overlay_values)
        payload[RUNTIME_STORAGE_KEY] = {
            "sessions": [dict(row) for row in sorted(self._sessions.values(), key=lambda r: int(r.get("createdAtMs") or 0))],
            "instances": [dict(row) for row in sorted(self._instances.values(), key=lambda r: int(r.get("created_at") or 0))],
            "displayStacks": {key: list(rows) for key, rows in self._display_stacks.items()},
            "cooldowns": dict(self._cooldowns),
            "queueDepths": dict(self._queue_depths),
        }
        payload["updatedAt"] = _utc_now_iso()
        _write_json(_media_state_path(self.instance_path), payload)
        self._dirty = False

    def _sanitize_stacks_locked(self) -> None:
        for key, rows in list(self._display_stacks.items()):
            cleaned: List[str] = []
            for iid in rows:
                inst = self._instances.get(iid)
                if not isinstance(inst, dict):
                    continue
                if str(inst.get("desired_state") or "") != DESIRED_PRESENT:
                    continue
                if str(inst.get("state") or "") not in _ACTIVE_STATES:
                    continue
                if _normalize_launch_mode(inst.get("mode")) not in _DISPLAY_STACK_MODES:
                    continue
                cleaned.append(iid)
            self._display_stacks[key] = cleaned

    def _touch_locked(self, inst: Dict[str, Any]) -> None:
        inst["updated_at"] = _now_ms()
        self._dirty = True

    def _touch_session_locked(self, runtime_id: str) -> None:
        session = self._sessions.get(str(runtime_id or "").strip())
        if not isinstance(session, dict):
            return
        session["updatedAtMs"] = _now_ms()
        self._dirty = True

    def _sync_sessions_locked(self) -> None:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for inst in self._instances.values():
            runtime_id = str(inst.get("runtime_id") or "").strip()
            if not runtime_id:
                continue
            grouped.setdefault(runtime_id, []).append(inst)
        for runtime_id, rows in grouped.items():
            session = self._sessions.get(runtime_id)
            scene_id = str(rows[0].get("scene_id") or "").strip()
            active = [row for row in rows if self._active_locked(row)]
            state = INSTANCE_STATE_STOPPED
            if any(str(row.get("state") or "") == INSTANCE_STATE_CRASHED for row in rows):
                state = INSTANCE_STATE_CRASHED
            elif any(str(row.get("state") or "") == INSTANCE_STATE_STOPPING for row in rows):
                state = INSTANCE_STATE_STOPPING
            elif active:
                state = INSTANCE_STATE_RUNNING
            elif any(str(row.get("state") or "") == INSTANCE_STATE_STARTING for row in rows):
                state = INSTANCE_STATE_STARTING
            created_at = min(max(0, int(row.get("created_at") or 0)) for row in rows) if rows else _now_ms()
            updated_at = max(max(0, int(row.get("updated_at") or 0)) for row in rows) if rows else created_at
            output_ids = [str(row.get("instance_id") or "") for row in rows if str(row.get("instance_id") or "")]
            if isinstance(session, dict):
                session["sceneId"] = scene_id
                session["state"] = state
                session["outputIds"] = output_ids
                session["createdAtMs"] = created_at
                session["updatedAtMs"] = updated_at
                session["health"] = "ok" if state in _ACTIVE_STATES else ("error" if state == INSTANCE_STATE_CRASHED else "stopped")
            else:
                self._sessions[runtime_id] = {
                    "id": runtime_id,
                    "runtimeId": runtime_id,
                    "sceneId": scene_id,
                    "state": state,
                    "outputIds": output_ids,
                    "createdAtMs": created_at,
                    "updatedAtMs": updated_at,
                    "health": "ok" if state in _ACTIVE_STATES else ("error" if state == INSTANCE_STATE_CRASHED else "stopped"),
                }
        for runtime_id in list(self._sessions.keys()):
            if runtime_id in grouped:
                continue
            session = self._sessions.get(runtime_id)
            if not isinstance(session, dict):
                continue
            session["outputIds"] = []
            session["state"] = INSTANCE_STATE_STOPPED
            session["health"] = "stopped"
        self._dirty = True

    def _active_locked(self, inst: Dict[str, Any]) -> bool:
        now_ms = _now_ms()
        hb = max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0)))
        attached = bool(((inst.get("surface") or {}).get("attached")))
        detached_at = max(0, int(((inst.get("surface") or {}).get("detached_at") or 0)))
        created_at = max(0, int(inst.get("created_at") or 0))
        surface_live = attached and hb > 0 and (now_ms - hb) <= SURFACE_HEARTBEAT_TIMEOUT_MS
        startup_grace = detached_at <= 0 and hb <= 0 and (now_ms - created_at) <= SURFACE_STARTUP_GRACE_MS
        return (
            str(inst.get("desired_state") or DESIRED_PRESENT) == DESIRED_PRESENT
            and str(inst.get("state") or "") in _ACTIVE_STATES
            and (surface_live or startup_grace)
        )

    def _runtime_present_locked(self, inst: Dict[str, Any]) -> bool:
        return (
            str(inst.get("desired_state") or DESIRED_PRESENT) == DESIRED_PRESENT
            and str(inst.get("state") or "") in _ACTIVE_STATES
        )

    def _remove_from_stacks_locked(self, instance_id: str) -> None:
        iid = str(instance_id or "").strip()
        if not iid:
            return
        for key, rows in list(self._display_stacks.items()):
            if iid in rows:
                self._display_stacks[key] = [row for row in rows if row != iid]
                self._dirty = True

    def _cooldown_key(self, display_id: str, mode: str, scene_id: str) -> str:
        return f"{str(display_id or '').strip()}|{_normalize_launch_mode(mode)}|{str(scene_id or '').strip()}"

    def _queue_key(self, display_id: str, mode: str, scene_id: str) -> str:
        return self._cooldown_key(display_id, mode, scene_id)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._load_locked()
            return {
                "overlayValues": dict(self._overlay_values),
                "sessions": [dict(row) for row in sorted(self._sessions.values(), key=lambda r: int(r.get("createdAtMs") or 0), reverse=True)],
                "instances": [dict(row) for row in sorted(self._instances.values(), key=lambda r: int(r.get("created_at") or 0), reverse=True)],
                "displayStates": _public_display_states(self._display_stacks),
            }

    def set_overlay_values(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        clean = {str(k).strip(): v for k, v in updates.items() if str(k).strip()} if isinstance(updates, dict) else {}
        with self._lock:
            self._load_locked()
            self._overlay_values.update(clean)
            self._dirty = True
            self._persist_locked()
            return dict(self._overlay_values)

    def set_overlay_value(self, key: str, value: Any) -> Dict[str, Any]:
        return self.set_overlay_values({str(key or "").strip(): value})

    def active_instances(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._load_locked()
            return [dict(inst) for inst in self._instances.values() if self._active_locked(inst)]

    def active_instances_for(self, *, display_id: str, mode: str) -> List[Dict[str, Any]]:
        did = str(display_id or "").strip()
        mode_norm = _normalize_launch_mode(mode)
        with self._lock:
            self._load_locked()
            if mode_norm in _DISPLAY_STACK_MODES:
                rows = []
                for iid in self._display_stacks.get(_stack_key(did, mode_norm), []):
                    inst = self._instances.get(iid)
                    if isinstance(inst, dict) and self._active_locked(inst):
                        rows.append(dict(inst))
                return rows
            rows = [
                dict(inst) for inst in self._instances.values()
                if str(inst.get("display_id") or "") == did
                and _normalize_launch_mode(inst.get("mode")) == mode_norm
                and self._active_locked(inst)
            ]
            rows.sort(key=lambda row: int(row.get("created_at") or 0))
            return rows

    def find_instance(self, instance_id: str) -> Dict[str, Any] | None:
        iid = str(instance_id or "").strip()
        if not iid:
            return None
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            return dict(inst) if isinstance(inst, dict) else None

    def play_instance(
        self,
        *,
        instance_id: str | None,
        runtime_id: str,
        scene_id: str,
        display_id: str,
        mode: str,
        runtime_url: str,
        preview_viewport: Dict[str, int] | None,
        source: str,
        priority: int,
        blend_mode: str,
        interrupt_policy: str,
        duplicate_policy: str,
        cooldown_ms: int,
        audio_behaviour: Dict[str, Any] | None,
        stack_behavior: str,
        queue_enabled: bool,
        queue_max_length: int,
        queue_dedupe: bool,
        pid: int = 0,
    ) -> Dict[str, Any]:
        now_ms = _now_ms()
        did = str(display_id or "").strip()
        sid = str(scene_id or "").strip()
        mode_norm = _normalize_launch_mode(mode)
        cooldown_key = self._cooldown_key(did, mode_norm, sid)
        queue_key = self._queue_key(did, mode_norm, sid)
        with self._lock:
            self._load_locked()
            last_trigger = int(self._cooldowns.get(cooldown_key) or 0)
            if cooldown_ms > 0 and last_trigger > 0 and (now_ms - last_trigger) < cooldown_ms:
                return {"ok": True, "dropped": True, "reason": "cooldown", "sceneId": sid, "displayId": did}

            active_same = [
                inst for inst in self._instances.values()
                if str(inst.get("display_id") or "") == did
                and str(inst.get("scene_id") or "") == sid
                and _normalize_launch_mode(inst.get("mode")) == mode_norm
                and self._active_locked(inst)
            ]
            if duplicate_policy == DUPLICATE_COALESCE and active_same:
                self._cooldowns[cooldown_key] = now_ms
                self._dirty = True
                first = active_same[-1]
                return {"ok": True, "reused": True, "coalesced": True, "sceneId": sid, "displayId": did, "instanceId": str(first.get("instance_id") or "")}
            if duplicate_policy == DUPLICATE_DROP_IF_PLAYING and active_same:
                first = active_same[-1]
                return {"ok": True, "reused": True, "sceneId": sid, "displayId": did, "instanceId": str(first.get("instance_id") or "")}
            if interrupt_policy == INTERRUPT_QUEUE and active_same:
                if not queue_enabled:
                    return {"ok": True, "reused": True, "sceneId": sid, "displayId": did}
                depth = max(0, int(self._queue_depths.get(queue_key) or 0))
                if queue_dedupe and depth > 0:
                    return {"ok": True, "queued": True, "sceneId": sid, "displayId": did, "queueDepth": depth}
                if depth >= max(0, int(queue_max_length or 0)):
                    return {"ok": True, "dropped": True, "sceneId": sid, "displayId": did, "queueDepth": depth}
                self._queue_depths[queue_key] = depth + 1
                self._cooldowns[cooldown_key] = now_ms
                self._dirty = True
                self._persist_locked()
                return {"ok": True, "queued": True, "sceneId": sid, "displayId": did, "queueDepth": depth + 1}
            if interrupt_policy == INTERRUPT_NO_INTERRUPT and active_same:
                first = active_same[-1]
                return {"ok": True, "reused": True, "sceneId": sid, "displayId": did, "instanceId": str(first.get("instance_id") or "")}

            requested_instance_id = str(instance_id or "").strip()
            if mode_norm in _DISPLAY_STACK_MODES:
                key = _stack_key(did, mode_norm)
                stack = list(self._display_stacks.get(key, []))
                if _normalize_stack_behavior(stack_behavior) != "interrupt":
                    for iid in stack:
                        inst = self._instances.get(iid)
                        if isinstance(inst, dict) and self._active_locked(inst):
                            inst["desired_state"] = DESIRED_ABSENT
                            inst["state"] = INSTANCE_STATE_STOPPING if max(0, int(((inst.get("process") or {}).get("pid") or 0))) > 0 else INSTANCE_STATE_STOPPED
                            self._touch_locked(inst)
                    stack = []
                elif interrupt_policy == INTERRUPT_RESTART:
                    stack = [iid for iid in stack if str((self._instances.get(iid) or {}).get("scene_id") or "") != sid]
                stack.append(requested_instance_id or f"inst_{uuid4().hex[:12]}")
                instance_id = stack[-1]
                self._display_stacks[key] = stack
            else:
                instance_id = requested_instance_id or f"inst_{uuid4().hex[:12]}"

            inst = {
                "instance_id": instance_id,
                "runtime_id": str(runtime_id or "").strip() or f"RT-{uuid4().hex[:8]}",
                "scene_id": sid,
                "display_id": did,
                "mode": mode_norm,
                "state": INSTANCE_STATE_RUNNING if (mode_norm == LAUNCH_MODE_EMBEDDED or pid > 0) else INSTANCE_STATE_STARTING,
                "desired_state": DESIRED_PRESENT,
                "created_at": now_ms,
                "updated_at": now_ms,
                "runtime_url": str(runtime_url or "").strip(),
                "preview_viewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                "source": str(source or "").strip(),
                "priority": int(priority),
                "blend_mode": str(blend_mode or BLEND_MODE_STOP_LOWER).strip().upper(),
                "interrupt_policy": str(interrupt_policy or INTERRUPT_NO_INTERRUPT).strip().upper(),
                "duplicate_policy": str(duplicate_policy or DUPLICATE_DROP_IF_PLAYING).strip().upper(),
                "audio_behaviour": dict(audio_behaviour or {}),
                "process": {
                    "pid": max(0, int(pid or 0)),
                    "started_at": now_ms,
                    "last_seen_at": now_ms,
                    "exit_code": None,
                },
                "surface": {
                    "attached": mode_norm == LAUNCH_MODE_EMBEDDED,
                    "surface_id": "",
                    "attached_at": now_ms if mode_norm == LAUNCH_MODE_EMBEDDED else 0,
                    "last_heartbeat_at": now_ms if mode_norm == LAUNCH_MODE_EMBEDDED else 0,
                    "detached_at": 0,
                },
            }
            self._instances[instance_id] = inst
            self._sync_sessions_locked()
            self._cooldowns[cooldown_key] = now_ms
            self._dirty = True
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def attach_surface(self, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        now_ms = _now_ms()
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict) or not self._runtime_present_locked(inst):
                return {"ok": False, "error": "instance_not_found"}
            inst["surface"]["attached"] = True
            inst["surface"]["surface_id"] = str(surface_id or iid).strip() or iid
            inst["surface"]["attached_at"] = now_ms
            inst["surface"]["last_heartbeat_at"] = now_ms
            inst["surface"]["detached_at"] = 0
            if str(inst.get("state") or "") == INSTANCE_STATE_STARTING:
                inst["state"] = INSTANCE_STATE_RUNNING
            self._touch_locked(inst)
            self._sync_sessions_locked()
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def heartbeat(self, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        sid = str(surface_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        now_ms = _now_ms()
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict) or not self._runtime_present_locked(inst):
                return {"ok": False, "error": "instance_not_found"}
            current_surface_id = str(((inst.get("surface") or {}).get("surface_id") or "")).strip()
            detached_at = max(0, int(((inst.get("surface") or {}).get("detached_at") or 0)))
            if sid and current_surface_id and sid != current_surface_id:
                return {"ok": False, "error": "surface_mismatch"}
            if sid and not current_surface_id and detached_at > 0:
                return {"ok": False, "error": "surface_not_attached"}
            inst["surface"]["attached"] = True
            if sid:
                inst["surface"]["surface_id"] = sid
                if max(0, int(((inst.get("surface") or {}).get("attached_at") or 0))) <= 0:
                    inst["surface"]["attached_at"] = now_ms
            inst["surface"]["last_heartbeat_at"] = now_ms
            inst["surface"]["detached_at"] = 0
            if str(inst.get("state") or "") == INSTANCE_STATE_STARTING:
                inst["state"] = INSTANCE_STATE_RUNNING
            self._touch_locked(inst)
            self._sync_sessions_locked()
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def stop_instance(self, *, scene_id: str | None = None, instance_id: str | None = None) -> Dict[str, Any]:
        sid = str(scene_id or "").strip()
        iid = str(instance_id or "").strip()
        stopped = 0
        with self._lock:
            self._load_locked()
            targets: List[Dict[str, Any]] = []
            if iid:
                inst = self._instances.get(iid)
                if isinstance(inst, dict):
                    targets.append(inst)
                else:
                    targets = [
                        inst for inst in self._instances.values()
                        if str(inst.get("runtime_id") or "") == iid and self._active_locked(inst)
                    ]
            elif sid:
                targets = [inst for inst in self._instances.values() if str(inst.get("scene_id") or "") == sid and self._active_locked(inst)]
            else:
                targets = [inst for inst in self._instances.values() if self._active_locked(inst)]
            for inst in targets:
                inst["desired_state"] = DESIRED_ABSENT
                inst["state"] = INSTANCE_STATE_STOPPING if max(0, int(((inst.get("process") or {}).get("pid") or 0))) > 0 else INSTANCE_STATE_STOPPED
                self._remove_from_stacks_locked(str(inst.get("instance_id") or ""))
                cooldown_key = self._cooldown_key(str(inst.get("display_id") or ""), str(inst.get("mode") or ""), str(inst.get("scene_id") or ""))
                self._cooldowns.pop(cooldown_key, None)
                self._queue_depths.pop(cooldown_key, None)
                self._touch_locked(inst)
                stopped += 1
            if stopped > 0:
                self._sync_sessions_locked()
                self._persist_locked()
            return {"ok": True, "stopped": stopped}

    def complete(self, *, display_id: str, instance_id: str | None = None, scene_id: str | None = None) -> Dict[str, Any]:
        did = str(display_id or "").strip()
        iid = str(instance_id or "").strip()
        sid = str(scene_id or "").strip()
        with self._lock:
            self._load_locked()
            target: Dict[str, Any] | None = None
            if iid:
                inst = self._instances.get(iid)
                if isinstance(inst, dict) and self._active_locked(inst):
                    target = inst
            if target is None:
                for mode in _DISPLAY_STACK_MODES:
                    stack = self._display_stacks.get(_stack_key(did, mode), [])
                    for candidate_id in reversed(stack):
                        inst = self._instances.get(candidate_id)
                        if not isinstance(inst, dict) or not self._active_locked(inst):
                            continue
                        if sid and str(inst.get("scene_id") or "") != sid:
                            continue
                        target = inst
                        break
                    if target is not None:
                        break
            if not isinstance(target, dict):
                return {"ok": False, "error": "instance_not_found"}
            target["desired_state"] = DESIRED_ABSENT
            target["state"] = INSTANCE_STATE_STOPPING if max(0, int(((target.get("process") or {}).get("pid") or 0))) > 0 else INSTANCE_STATE_STOPPED
            self._remove_from_stacks_locked(str(target.get("instance_id") or ""))
            self._touch_locked(target)
            self._sync_sessions_locked()
            self._persist_locked()
            return {"ok": True, "completed": dict(target)}

    def detach_surface(self, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        sid = str(surface_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict):
                return {"ok": False, "error": "instance_not_found"}
            current_surface_id = str(((inst.get("surface") or {}).get("surface_id") or "")).strip()
            if sid and current_surface_id and sid != current_surface_id:
                return {"ok": True, "ignored": True}
            inst["surface"]["attached"] = False
            inst["surface"]["surface_id"] = ""
            inst["surface"]["detached_at"] = _now_ms()
            self._touch_locked(inst)
            self._sync_sessions_locked()
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def detach_embedded_by_display(self, display_id: str) -> Dict[str, Any]:
        did = str(display_id or "").strip()
        if not did:
            return {"ok": False, "error": "missing_display_id"}
        stopped = 0
        with self._lock:
            self._load_locked()
            for iid in list(self._display_stacks.get(_stack_key(did, LAUNCH_MODE_EMBEDDED), [])):
                inst = self._instances.get(iid)
                if not isinstance(inst, dict):
                    continue
                inst["surface"]["attached"] = False
                inst["surface"]["detached_at"] = _now_ms()
                self._touch_locked(inst)
                stopped += 1
            if stopped > 0:
                self._sync_sessions_locked()
                self._persist_locked()
            return {"ok": True, "stopped": stopped}

    def set_process(self, *, instance_id: str, pid: int) -> Dict[str, Any] | None:
        iid = str(instance_id or "").strip()
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict):
                return None
            inst["process"]["pid"] = max(0, int(pid or 0))
            inst["process"]["last_seen_at"] = _now_ms()
            if max(0, int(pid or 0)) > 0 and str(inst.get("state") or "") == INSTANCE_STATE_STARTING:
                inst["state"] = INSTANCE_STATE_RUNNING
            self._touch_locked(inst)
            self._sync_sessions_locked()
            self._persist_locked()
            return dict(inst)

    def reconcile(self) -> Dict[str, Any]:
        now_ms = _now_ms()
        removed = 0
        with self._lock:
            self._load_locked()
            for iid, inst in list(self._instances.items()):
                pid = max(0, int(((inst.get("process") or {}).get("pid") or 0)))
                mode = _normalize_launch_mode(inst.get("mode"))
                hb = max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0)))
                detached_at = max(0, int(((inst.get("surface") or {}).get("detached_at") or 0)))
                created_at = max(0, int(inst.get("created_at") or 0))
                stale_hb = hb > 0 and (now_ms - hb) > SURFACE_HEARTBEAT_TIMEOUT_MS
                detach_expired = detached_at > 0 and (now_ms - detached_at) > SURFACE_DETACH_GRACE_MS
                startup_orphaned = hb <= 0 and (now_ms - created_at) > SURFACE_STARTUP_GRACE_MS
                desired_absent = str(inst.get("desired_state") or DESIRED_PRESENT) == DESIRED_ABSENT
                process_backed = mode in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN)

                if not desired_absent and (stale_hb or (detach_expired and not process_backed) or startup_orphaned):
                    desired_absent = True
                    inst["desired_state"] = DESIRED_ABSENT
                    self._remove_from_stacks_locked(iid)
                    self._touch_locked(inst)

                if desired_absent:
                    self._remove_from_stacks_locked(iid)
                    inst["state"] = INSTANCE_STATE_STOPPED
                    self._touch_locked(inst)
                if str(inst.get("state") or "") in (INSTANCE_STATE_STOPPED, INSTANCE_STATE_CRASHED):
                    age_ms = now_ms - max(0, int(inst.get("updated_at") or inst.get("created_at") or 0))
                    if age_ms > STOPPED_RETENTION_MS:
                        self._remove_from_stacks_locked(iid)
                        self._instances.pop(iid, None)
                        removed += 1
                        self._dirty = True

            self._sanitize_stacks_locked()
            self._sync_sessions_locked()
            if self._dirty:
                self._persist_locked()
            return {"ok": True, "removed": removed, "checked": len(self._instances)}


_REGISTRIES: Dict[str, _IsolatedRuntimeRegistry] = {}
_REGISTRIES_LOCK = Lock()


def _get_registry(instance_path: str | Path) -> _IsolatedRuntimeRegistry:
    key = str(Path(instance_path).resolve())
    with _REGISTRIES_LOCK:
        reg = _REGISTRIES.get(key)
        if reg is None:
            reg = _IsolatedRuntimeRegistry(key)
            _REGISTRIES[key] = reg
        return reg


def _instance_runtime_url(display_id: str, instance_id: str, mode: str, *, base_url: str | None = None, runtime_token: str | None = None, scene_id: str | None = None) -> str:
    root = (base_url or _media_base_url()).rstrip("/")
    query = {"instanceId": str(instance_id or "").strip(), "surface": _normalize_launch_mode(mode)}
    if scene_id:
        query["sceneId"] = str(scene_id)
    if runtime_token:
        query["kiosk_token"] = str(runtime_token)
    return f"{root}/media/runtime/display/{display_id}?{urlencode(query)}"


def list_runtime_instances(instance_path: str | Path) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    snap = reg.snapshot()
    active_instances = reg.active_instances()
    active_outputs = [_instance_to_output_endpoint(row) for row in active_instances if isinstance(row, dict)]
    runtime_sessions = _public_runtime_sessions(
        [row for row in (snap.get("sessions") if isinstance(snap.get("sessions"), list) else []) if isinstance(row, dict)],
        active_outputs,
        active_only=True,
    )
    return {
        "ok": True,
        "runtimeSessions": runtime_sessions,
        "outputEndpoints": active_outputs,
        "instances": snap.get("instances", []),
        "displayStates": snap.get("displayStates", {}),
    }


def attach_runtime_surface(instance_path: str | Path, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    return _get_registry(instance_path).attach_surface(instance_id=instance_id, surface_id=surface_id)


def heartbeat_runtime_surface(instance_path: str | Path, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    return _get_registry(instance_path).heartbeat(instance_id=instance_id, surface_id=surface_id)


def load_media_state(instance_path: str | Path, *, persist: bool = True) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    snap = reg.snapshot()
    instances = [row for row in (snap.get("instances") if isinstance(snap.get("instances"), list) else []) if isinstance(row, dict)]
    active_instances = reg.active_instances()
    outputs = [_instance_to_output_endpoint(inst) for inst in instances]
    active_outputs = [_instance_to_output_endpoint(inst) for inst in active_instances if isinstance(inst, dict)]
    runtime_sessions = _public_runtime_sessions(
        [row for row in (snap.get("sessions") if isinstance(snap.get("sessions"), list) else []) if isinstance(row, dict)],
        active_outputs,
        active_only=True,
    )
    display_states = snap.get("displayStates") if isinstance(snap.get("displayStates"), dict) else {}
    by_id = {str(row.get("instance_id") or ""): row for row in instances if str(row.get("instance_id") or "")}

    sessions: List[Dict[str, Any]] = []
    for display_id, row in display_states.items():
        if not isinstance(row, dict):
            continue
        for mode_name in ("embedded", "fullscreen"):
            for iid in row.get(mode_name, []) if isinstance(row.get(mode_name), list) else []:
                inst = by_id.get(str(iid or ""))
                if not isinstance(inst, dict):
                    continue
                if str(inst.get("desired_state") or "") != DESIRED_PRESENT:
                    continue
                if str(inst.get("state") or "") not in _ACTIVE_STATES:
                    continue
                sessions.append(_instance_to_surface_row(inst))

    surface_sessions = [
        _instance_to_surface_row(inst)
        for inst in active_instances
        if isinstance(inst, dict)
    ]
    active_rows = [
        {
            "sceneId": str(inst.get("scene_id") or ""),
            "displayId": str(inst.get("display_id") or ""),
            "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
            "startedAtMs": max(0, int(inst.get("created_at") or 0)),
            "runtimeUrl": str(inst.get("runtime_url") or ""),
            "launchMode": _normalize_launch_mode(inst.get("mode")),
            "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
        }
        for inst in instances
        if max(0, int(((inst.get("process") or {}).get("pid") or 0))) > 0
        and str(inst.get("state") or "") in _ACTIVE_STATES
    ]
    state = {
        "updatedAt": _utc_now_iso(),
        "engine": {"backend": "chromium", "active": active_rows},
        "sessions": sessions,
        "runtimeSessions": runtime_sessions,
        "outputEndpoints": active_outputs,
        "surfaceSessions": surface_sessions,
        "instances": instances,
        "displayStates": display_states,
        "queue": [],
        "overlayValues": snap.get("overlayValues") if isinstance(snap.get("overlayValues"), dict) else _default_overlay_values(),
    }
    return state


def run_media_maintenance(instance_path: str | Path) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    return _get_registry(instance_path).reconcile()


def _launch_browser_instance(instance_path: str | Path, cfg: Dict[str, Any], display: Dict[str, Any], runtime_url: str, mode: str) -> int | str:
    eng = _get_engine(instance_path)
    effective = eng._effective_display(cfg, display)
    launched = eng._launch_for_display(
        effective,
        runtime_url,
        launch_mode=mode,
        window_scale=max(0.05, min(1.0, float(((cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}).get("windowScale") or 0.25)))),
    )
    if not launched.get("ok"):
        return str(launched.get("error") or "launch_failed")
    proc = launched.get("process")
    pid = max(0, int(getattr(proc, "pid", 0) or 0))
    return pid


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    *,
    base_url: str | None = None,
    runtime_token: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    preview_viewport: Dict[str, int] | None = None,
    stack_behavior: str = DEFAULT_SCENE_STACK_BEHAVIOR,
    event_source: str = "",
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    reg = _get_registry(instance_path)
    mode = _normalize_launch_mode(launch_mode)
    scene = next((s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if str(s.get("id") or "") == str(scene_id)), None)
    if not isinstance(scene, dict):
        return {"ok": False, "error": "scene_not_found"}

    before = load_media_state(instance_path, persist=False)
    interrupt_policy = str(scene.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper()
    duplicate_policy = str(scene.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper()
    queue_cfg = scene.get("queue") if isinstance(scene.get("queue"), dict) else {}
    queue_enabled = bool(queue_cfg.get("enabled", interrupt_policy == INTERRUPT_QUEUE))
    queue_max_length = max(0, int(float(queue_cfg.get("maxLength") or 8)))
    queue_dedupe = bool(queue_cfg.get("dedupe", True))
    cooldown_ms = max(0, int(float(scene.get("cooldownMs") or 0)))
    priority = int(scene.get("priority") or 100)
    blend_mode = str(scene.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper()
    if stack_behavior == "interrupt":
        blend_mode = BLEND_MODE_PAUSE_LOWER
    audio_behaviour = scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}
    results: List[Dict[str, Any]] = []
    runtime_id = f"RT-{uuid4().hex[:8]}"

    for display in _resolve_scene_displays(cfg, scene):
        display_id = str(display.get("id") or "display_1")
        instance_id = f"inst_{uuid4().hex[:12]}"
        runtime_url = _instance_runtime_url(
            display_id,
            instance_id,
            mode,
            base_url=base_url,
            runtime_token=runtime_token,
            scene_id=str(scene.get("id") or scene_id),
        )
        pid = 0
        if mode in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
            if mode == LAUNCH_MODE_FULLSCREEN:
                _get_engine(instance_path).stop_display(display_id)
            launched = _launch_browser_instance(instance_path, cfg, display, runtime_url, mode)
            if isinstance(launched, str):
                return {"ok": False, "error": launched}
            pid = int(launched or 0)

        played = reg.play_instance(
            instance_id=instance_id,
            runtime_id=runtime_id,
            scene_id=str(scene.get("id") or scene_id),
            display_id=display_id,
            mode=mode,
            runtime_url=runtime_url,
            preview_viewport=preview_viewport,
            source=str(event_source or "").strip(),
            priority=priority,
            blend_mode=blend_mode,
            interrupt_policy=interrupt_policy,
            duplicate_policy=duplicate_policy,
            cooldown_ms=cooldown_ms,
            audio_behaviour=audio_behaviour,
            stack_behavior=stack_behavior,
            queue_enabled=queue_enabled,
            queue_max_length=queue_max_length,
            queue_dedupe=queue_dedupe,
            pid=pid,
        )
        if not played.get("ok"):
            return played
        if played.get("queued") or played.get("dropped") or played.get("reused"):
            results.append(
                {
                    "ok": True,
                    "runtimeId": runtime_id,
                    "sceneId": str(scene.get("id") or scene_id),
                    "displayId": display_id,
                    "runtimeUrl": runtime_url,
                    "launchMode": mode,
                    **played,
                }
            )
            continue
        inst = played.get("instance") if isinstance(played.get("instance"), dict) else {}
        if pid > 0:
            reg.set_process(instance_id=str(inst.get("instance_id") or ""), pid=pid)
        results.append(
            {
                "ok": True,
                "id": str(inst.get("instance_id") or ""),
                "instanceId": str(inst.get("instance_id") or ""),
                "runtimeId": str(inst.get("runtime_id") or runtime_id),
                "sceneId": str(inst.get("scene_id") or ""),
                "displayId": str(inst.get("display_id") or ""),
                "pid": max(0, int(((inst.get("process") or {}).get("pid") or pid))),
                "runtimeUrl": str(inst.get("runtime_url") or runtime_url),
                "launchMode": mode,
                "surfaceId": str(inst.get("instance_id") or ""),
            }
        )

    run_media_maintenance(instance_path)
    after = load_media_state(instance_path, persist=False)
    _emit_media_audio_intent_changes(instance_path, cfg, before.get("sessions"), after.get("sessions"))
    first = results[0] if results else {}
    return {
        "ok": True,
        "sceneId": str(first.get("sceneId") or scene_id),
        "runtimeId": str(first.get("runtimeId") or runtime_id),
        "displayId": str(first.get("displayId") or ""),
        "displayIds": [str(row.get("displayId") or "") for row in results],
        "instanceId": str(first.get("instanceId") or ""),
        "runtimeUrl": str(first.get("runtimeUrl") or ""),
        "pid": int(first.get("pid") or 0),
        "launchMode": mode,
        "reused": any(bool(row.get("reused")) for row in results),
        "queued": any(bool(row.get("queued")) for row in results),
        "dropped": any(bool(row.get("dropped")) for row in results),
        "results": results,
    }


def stop_scene(instance_path: str | Path, scene_id: str | None = None, session_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    reg = _get_registry(instance_path)
    before = load_media_state(instance_path, persist=False)
    if session_id:
        stop_targets = [
            row for row in (before.get("instances") if isinstance(before.get("instances"), list) else [])
            if isinstance(row, dict)
            and (
                str(row.get("instance_id") or "") == str(session_id)
                or str(row.get("runtime_id") or "") == str(session_id)
            )
        ]
    elif scene_id:
        stop_targets = [
            row for row in (before.get("instances") if isinstance(before.get("instances"), list) else [])
            if isinstance(row, dict) and str(row.get("scene_id") or "") == str(scene_id)
        ]
    else:
        stop_targets = [
            row for row in (before.get("instances") if isinstance(before.get("instances"), list) else [])
            if isinstance(row, dict)
        ]
    result = reg.stop_instance(scene_id=scene_id, instance_id=session_id)
    for row in stop_targets:
        _stop_managed_output_process(instance_path, row)
    run_media_maintenance(instance_path)
    after = load_media_state(instance_path, persist=False)
    _emit_media_audio_intent_changes(instance_path, cfg, before.get("sessions"), after.get("sessions"))
    return {"ok": True, "stopped": int(result.get("stopped") or 0)}


def complete_scene(
    instance_path: str | Path,
    *,
    display_id: str,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    reg = _get_registry(instance_path)
    before = load_media_state(instance_path, persist=False)
    result = reg.complete(display_id=str(display_id or "").strip(), instance_id=session_id, scene_id=scene_id)
    if not result.get("ok"):
        return result
    _stop_managed_output_process(
        instance_path,
        (result.get("completed") if isinstance(result.get("completed"), dict) else None),
    )
    run_media_maintenance(instance_path)
    after = load_media_state(instance_path, persist=False)
    _emit_media_audio_intent_changes(instance_path, cfg, before.get("sessions"), after.get("sessions"))
    return {"ok": True, "completed": result.get("completed")}


def detach_embedded_surface(instance_path: str | Path, display_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    result = _get_registry(instance_path).detach_embedded_by_display(str(display_id or "").strip())
    run_media_maintenance(instance_path)
    return result


def detach_surface(instance_path: str | Path, session_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    result = _get_registry(instance_path).detach_surface(instance_id=str(session_id or "").strip(), surface_id=surface_id)
    _stop_managed_output_process(
        instance_path,
        (result.get("instance") if isinstance(result.get("instance"), dict) else None),
    )
    run_media_maintenance(instance_path)
    return result


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    event_name = str(name or "").strip().upper()
    payload = params if isinstance(params, dict) else {}
    reg = _get_registry(instance_path)

    if event_name in ("SCORING_EVAL", "SCORE_CHANGED"):
        updates: Dict[str, Any] = {}
        if "score" in payload:
            try:
                updates["score"] = f"{max(0, int(float(payload.get('score') or 0))):08d}"
            except Exception:
                pass
        if updates:
            reg.set_overlay_values(updates)
        return {"ok": True, "processed": bool(updates), "updates": updates}

    if event_name == "MEDIA_SET_OVERLAY":
        key = str(payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "missing_key"}
        return {"ok": True, "processed": True, "overlayValues": reg.set_overlay_value(key, payload.get("value"))}

    if event_name == "MEDIA_SCENE_PLAY":
        scene_id = str(payload.get("sceneId") or "").strip()
        if not scene_id:
            return {"ok": False, "error": "missing_scene_id"}
        return play_scene(
            instance_path,
            scene_id=scene_id,
            base_url=str(payload.get("baseUrl") or "").strip() or None,
            runtime_token=str(payload.get("runtimeToken") or "").strip() or None,
            launch_mode=str(payload.get("launchMode") or LAUNCH_MODE_EMBEDDED).strip().lower() or LAUNCH_MODE_EMBEDDED,
            preview_viewport=payload.get("previewViewport") if isinstance(payload.get("previewViewport"), dict) else None,
            stack_behavior=str(payload.get("stackBehavior") or DEFAULT_SCENE_STACK_BEHAVIOR).strip().lower() or DEFAULT_SCENE_STACK_BEHAVIOR,
            event_source=str(source or "").strip(),
        )

    if event_name == "MEDIA_SCENE_STOP":
        return stop_scene(
            instance_path,
            scene_id=str(payload.get("sceneId") or "").strip() or None,
            session_id=str(payload.get("sessionId") or "").strip() or None,
        )

    if event_name == "MEDIA_STOP_ALL":
        return stop_scene(instance_path, scene_id=None, session_id=None)

    if event_name == "MEDIA_SCENE_COMPLETE":
        display_id = str(payload.get("displayId") or "").strip()
        if not display_id:
            return {"ok": False, "error": "missing_display_id"}
        return complete_scene(
            instance_path,
            display_id=display_id,
            session_id=str(payload.get("sessionId") or "").strip() or None,
            scene_id=str(payload.get("sceneId") or "").strip() or None,
        )

    return {"ok": True, "processed": False}


def runtime_display_payload(
    instance_path: str | Path,
    display_id: str,
    scene_id: str | None = None,
    *,
    session_id: str | None = None,
    surface_type: str | None = None,
    instance_id: str | None = None,
    surface_id: str | None = None,
) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    reg = _get_registry(instance_path)
    req_instance_id = str(instance_id or session_id or "").strip()
    req_surface_id = str(surface_id or "").strip() or None
    if req_instance_id:
        try:
            reg.heartbeat(instance_id=req_instance_id, surface_id=req_surface_id)
        except Exception:
            pass
    requested_instance = reg.find_instance(req_instance_id) if req_instance_id else None
    reg.reconcile()
    state = load_media_state(instance_path, persist=False)
    displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    display = next((d for d in displays if str(d.get("id") or "") == str(display_id)), None)
    if not display:
        display = next((d for d in displays if str(d.get("role") or "") == str(display_id)), None)
    if not display:
        display = displays[0] if displays else _default_displays()[0]
    resolved_display_id = str(display.get("id") or "display_1")
    requested_scene_id = str(scene_id or "").strip()
    surface = str(surface_type or "").strip().lower()

    selected_instances: List[Dict[str, Any]] = []
    allow_display_fallback = True
    if req_instance_id:
        inst = reg.find_instance(req_instance_id)
        if isinstance(inst, dict) and str(inst.get("desired_state") or "") != DESIRED_PRESENT:
            if surface in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
                return {
                    "ok": True,
                    "renderer": "chromium",
                    "updatedAt": state.get("updatedAt") or _utc_now_iso(),
                    "display": display,
                    "active": None,
                    "scene": None,
                    "asset": None,
                    "layers": [],
                    "overlayValues": state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values(),
                    "settings": {"runtimePollMs": max(40, int(float(((cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}).get("runtimePollMs") or 150))))},
                    "shouldClose": True,
                    "instanceId": req_instance_id,
                }
            allow_display_fallback = True
            req_instance_id = ""
            inst = None
        if isinstance(inst, dict) and str(inst.get("desired_state") or "") == DESIRED_PRESENT and str(inst.get("state") or "") in _ACTIVE_STATES:
            if surface and _normalize_launch_mode(inst.get("mode")) != surface:
                selected_instances = []
            else:
                selected_instances = [inst]
                resolved_display_id = str(inst.get("display_id") or resolved_display_id).strip() or resolved_display_id
                allow_display_fallback = False
    if not selected_instances and allow_display_fallback and surface == LAUNCH_MODE_WINDOWED:
        rows = reg.active_instances_for(display_id=resolved_display_id, mode=LAUNCH_MODE_WINDOWED)
        if requested_scene_id:
            rows = [row for row in rows if str(row.get("scene_id") or "") == requested_scene_id]
        selected_instances = [rows[-1]] if rows else []
    elif not selected_instances and allow_display_fallback and surface == LAUNCH_MODE_FULLSCREEN:
        selected_instances = reg.active_instances_for(display_id=resolved_display_id, mode=LAUNCH_MODE_FULLSCREEN)
        if requested_scene_id:
            selected_instances = [row for row in selected_instances if str(row.get("scene_id") or "") == requested_scene_id]
    elif not selected_instances and allow_display_fallback:
        selected_instances = reg.active_instances_for(display_id=resolved_display_id, mode=LAUNCH_MODE_EMBEDDED)
        if requested_scene_id:
            selected_instances = [row for row in selected_instances if str(row.get("scene_id") or "") == requested_scene_id]

    if not selected_instances and requested_scene_id:
        scenes_by_id = _scene_map(cfg)
        forced_scene = scenes_by_id.get(requested_scene_id)
        if isinstance(forced_scene, dict):
            selected_instances = [
                {
                    "instance_id": f"virtual_{resolved_display_id}_{requested_scene_id}",
                    "scene_id": requested_scene_id,
                    "display_id": resolved_display_id,
                    "mode": surface or LAUNCH_MODE_WINDOWED,
                    "state": INSTANCE_STATE_RUNNING,
                    "desired_state": DESIRED_PRESENT,
                    "created_at": _now_ms(),
                    "runtime_url": "",
                    "preview_viewport": None,
                    "priority": int(forced_scene.get("priority") or 100),
                    "blend_mode": str(forced_scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
                    "interrupt_policy": str(forced_scene.get("interruptPolicy") or INTERRUPT_ALLOW),
                    "duplicate_policy": str(forced_scene.get("duplicatePolicy") or DUPLICATE_ALLOW),
                    "audio_behaviour": dict(forced_scene.get("audioBehaviour") if isinstance(forced_scene.get("audioBehaviour"), dict) else {}),
                    "process": {"pid": 0},
                    "surface": {"last_heartbeat_at": 0},
                }
            ]

    session_rows = [_instance_to_surface_row(inst) for inst in selected_instances]
    layers = _render_layers_for_display(cfg, resolved_display_id, session_rows)
    top = layers[-1] if layers else None
    scene = top.get("scene") if isinstance(top, dict) and isinstance(top.get("scene"), dict) else None
    asset = top.get("asset") if isinstance(top, dict) and isinstance(top.get("asset"), dict) else None
    active = None
    if isinstance(top, dict):
        top_inst = selected_instances[-1] if selected_instances else {}
        active = {
            "instanceId": str(top.get("sessionId") or ""),
            "sessionId": str(top.get("sessionId") or ""),
            "sceneId": str((top.get("scene") or {}).get("id") or ""),
            "displayId": resolved_display_id,
            "pid": max(0, int(((top_inst.get("process") or {}).get("pid") or 0))),
            "startedAtMs": int(top.get("startedAtMs") or 0),
            "runtimeUrl": str(top_inst.get("runtime_url") or ""),
            "launchMode": _normalize_launch_mode(top.get("launchMode")),
        }

    overlay_values = state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else {}
    merged_overlay_values: Dict[str, Any] = dict(overlay_values)
    scoring_state = _load_scoring_state_nonblocking(instance_path)
    game_active = False
    if isinstance(scoring_state, dict):
        score_val = int(float(scoring_state.get("score") or 0))
        merged_overlay_values["score"] = f"{max(0, score_val):08d}"
        game = scoring_state.get("game") if isinstance(scoring_state.get("game"), dict) else {}
        started_ms = int(float(game.get("startedAtMs") or 0)) if isinstance(game, dict) else 0
        ended_ms = int(float(game.get("endedAtMs") or 0)) if isinstance(game, dict) else 0
        game_active = bool(game.get("active")) if isinstance(game, dict) else False
        now_ms = _now_ms()
        elapsed_ms = (now_ms - started_ms) if (started_ms > 0 and game_active) else (max(0, ended_ms - started_ms) if started_ms > 0 else 0)
        merged_overlay_values["game_elapsed_time"] = _format_elapsed_mmss(elapsed_ms)
        merged_overlay_values["player"] = str(scoring_state.get("player") or merged_overlay_values.get("player") or "1")
        merged_overlay_values["ball"] = str(scoring_state.get("ball") or merged_overlay_values.get("ball") or "1")
        merged_overlay_values["credit"] = str(scoring_state.get("credit") or merged_overlay_values.get("credit") or "0")

    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    configured_poll_ms = max(40, int(float(settings.get("runtimePollMs") or 150)))
    runtime_poll_ms = min(configured_poll_ms, 80) if game_active else configured_poll_ms
    return {
        "ok": True,
        "renderer": "chromium",
        "updatedAt": state.get("updatedAt") or _utc_now_iso(),
        "display": display,
        "active": active,
        "scene": scene,
        "asset": asset,
        "layers": layers,
        "overlayValues": merged_overlay_values,
        "settings": {"runtimePollMs": runtime_poll_ms},
        "shouldClose": False,
        "instanceId": req_instance_id or str((requested_instance or {}).get("instance_id") or ""),
    }
