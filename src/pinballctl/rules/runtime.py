"""Shared rules runtime used by both API and bridge event ingress paths."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict

from pinballctl.bridge.state import enqueue_command
from pinballctl.events import EventContext, get_bus, get_event_manager
from pinballctl.events.audit_log import append_event_log
from pinballctl.lighting.runtime import play_scene, stop_scene
from pinballctl.audio.runtime import load_audio_state, play_cue, stop_cue
from pinballctl.media.runtime import play_scene as media_play_scene, stop_scene as media_stop_scene

BridgeEnqueueFn = Callable[[Dict[str, Any]], tuple[bool, str | None]]
LoggerFn = Callable[[str], None]


def _log(logger: LoggerFn | None, msg: str) -> None:
    if logger is None:
        return
    try:
        logger(msg)
    except Exception:
        pass


def _enqueue_bridge_event_default(payload: Dict[str, Any]) -> tuple[bool, str | None]:
    try:
        enqueue_command(payload)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _rules_path(instance_path: str | Path) -> Path:
    return Path(instance_path) / "rules" / "rules.json"


def _load_rules(instance_path: str | Path) -> list[dict]:
    p = _rules_path(instance_path)
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    out = [r for r in raw if isinstance(r, dict)]
    _canonicalize_hardware_trigger_events(out)
    return out


_BUTTON_GESTURE_FNS = {
    "PRESSED",
    "RELEASED",
    "CLICKED",
    "DOUBLE_CLICKED",
    "HELD",
    "REPEAT_WHILE_HELD",
}


def _canonicalize_hardware_trigger_events(rules: list[dict]) -> None:
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        items: list[dict] = []
        triggers = rule.get("triggers")
        if isinstance(triggers, list):
            items.extend([t for t in triggers if isinstance(t, dict)])
        groups = rule.get("triggerGroups")
        if isinstance(groups, dict):
            for g in groups.get("groups") if isinstance(groups.get("groups"), list) else []:
                if not isinstance(g, dict):
                    continue
                gi = g.get("items")
                if isinstance(gi, list):
                    items.extend([t for t in gi if isinstance(t, dict)])
        for trig in items:
            if str(trig.get("type") or "").strip().lower() != "hardware":
                continue
            fn = str(trig.get("fn") or "").strip().upper()
            if fn not in _BUTTON_GESTURE_FNS:
                continue
            ev = str(trig.get("event") or "").strip().upper()
            if not ev:
                continue
            for suffix in (
                "_N_DOUBLE_CLICKED",
                "_DOUBLE_CLICKED",
                "_REPEAT_WHILE_HELD",
                "_CLICKED",
                "_RELEASED",
                "_HELD",
                "_PRESSED",
            ):
                if ev.endswith(suffix):
                    ev = ev[: -len(suffix)]
                    break
            if ev.endswith("_N"):
                ev = ev[:-2]
            trig["event"] = f"{ev}_PRESSED" if ev else trig.get("event")


def _trigger_items(rule: Dict[str, Any]) -> list[dict]:
    out: list[dict] = []
    groups = rule.get("triggerGroups")
    if isinstance(groups, dict):
        for grp in groups.get("groups") if isinstance(groups.get("groups"), list) else []:
            if not isinstance(grp, dict):
                continue
            for item in grp.get("items") if isinstance(grp.get("items"), list) else []:
                if isinstance(item, dict):
                    out.append(item)
    legacy = rule.get("triggers")
    if isinstance(legacy, list):
        for item in legacy:
            if isinstance(item, dict):
                out.append(item)
    return out


def _rule_matches_event(rule: Dict[str, Any], name: str, source: str | None, params: Dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False
    event_type = params.get("eventType") if isinstance(params.get("eventType"), str) else None
    for trig in _trigger_items(rule):
        trig_event = trig.get("event")
        if isinstance(trig_event, str) and trig_event and trig_event != name:
            continue
        trig_source = trig.get("source")
        if isinstance(trig_source, str) and trig_source:
            if (source or "") != trig_source:
                continue
        trig_fn = trig.get("fn")
        if isinstance(trig_fn, str) and trig_fn:
            if not event_type or trig_fn.upper() != event_type.upper():
                continue
        return True
    return False


def _emit_derived_event(
    instance_path: str | Path,
    name: str,
    source: str | None,
    params: Dict[str, Any],
    *,
    origin: str,
    logger: LoggerFn | None,
    enqueue_bridge_event: BridgeEnqueueFn,
) -> Dict[str, Any]:
    envelope = get_bus().emit(name=name, source=source, params=params)
    try:
        mgr = get_event_manager(instance_path=str(instance_path), logger=logger)
        mgr.dispatch(
            EventContext(
                id=envelope.id,
                ts=envelope.ts,
                name=envelope.name,
                source=envelope.source,
                params=envelope.params,
                origin=origin,
            )
        )
    except Exception as exc:
        _log(logger, f"rules derived dispatch failed: {exc}")

    bridge_cmd = {
        "cmd": "EVENT_FIRE",
        "name": name,
        "source": source or "pi.rules",
        "seq": int(time.time() * 1000),
    }
    if params:
        bridge_cmd["params"] = dict(params)
    enqueued, enqueue_error = enqueue_bridge_event(bridge_cmd)

    append_event_log(
        origin=origin,
        direction="pi->esp",
        name=name,
        source=source,
        params=params,
        meta={
            "event_id": envelope.id,
            "bridge_cmd": "EVENT_FIRE",
            "bridge_enqueued": enqueued,
            "bridge_error": enqueue_error,
        },
    )
    return {
        "id": envelope.id,
        "name": envelope.name,
        "source": envelope.source,
        "bridge_enqueued": enqueued,
        "bridge_error": enqueue_error,
    }


def apply_rules_for_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None,
    origin: str = "rules",
    logger: LoggerFn | None = None,
    enqueue_bridge_event: BridgeEnqueueFn | None = None,
) -> list[Dict[str, Any]]:
    """Evaluate matching rules for one event and execute rule actions.

    This intentionally mirrors existing behavior:
    - Rule actions run for the incoming event.
    - `emit_event` actions create derived events, dispatch them, and forward to bridge.
    - Derived events are not recursively re-evaluated in this same call.
    """
    payload = params if isinstance(params, dict) else {}
    enqueue_fn = enqueue_bridge_event or _enqueue_bridge_event_default
    emitted: list[Dict[str, Any]] = []
    for rule in _load_rules(instance_path):
        if not _rule_matches_event(rule, name, source, payload):
            continue
        for action in rule.get("actions") if isinstance(rule.get("actions"), list) else []:
            if not isinstance(action, dict):
                continue
            action_type = action.get("type")
            if action_type == "emit_event":
                target = action.get("target")
                if not isinstance(target, str) or not target.strip():
                    continue
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                derived_source = a_params.get("source") if isinstance(a_params.get("source"), str) else "pi.rules"
                derived_params = {k: v for k, v in a_params.items() if k != "source"}
                emitted.append(
                    _emit_derived_event(
                        instance_path,
                        target.strip(),
                        derived_source,
                        derived_params,
                        origin=origin,
                        logger=logger,
                        enqueue_bridge_event=enqueue_fn,
                    )
                )
                continue
            if action_type == "apply_lighting_scene":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                scene_id = a_params.get("sceneId") or action.get("target")
                if not isinstance(scene_id, str) or not scene_id.strip():
                    continue
                start_at = str(a_params.get("startAt") or "start").strip().lower()
                if start_at not in ("start", "frame", "tag"):
                    start_at = "start"
                start_mode = str(a_params.get("startMode") or "play").strip().lower()
                paused = start_mode == "paused" or bool(a_params.get("startPaused"))
                start_frame: int | None = None
                start_tag: str | None = None
                if start_at == "frame":
                    try:
                        sf = int(a_params.get("startFrame", 0))
                    except Exception:
                        sf = 0
                    if sf > 0:
                        start_frame = sf
                elif start_at == "tag":
                    tag = str(a_params.get("startTag") or "").strip()
                    if tag:
                        start_tag = tag
                ok = False
                err = None
                try:
                    ok = play_scene(
                        instance_path,
                        scene_id=scene_id.strip(),
                        source="pi.rules",
                        start_frame=start_frame,
                        start_tag=start_tag,
                        paused=paused,
                    )
                except Exception as exc:
                    err = str(exc)
                append_event_log(
                    origin=origin,
                    direction="pi->esp",
                    name="LIGHT_SCENE_PLAY",
                    source="pi.rules",
                    params={
                        "sceneId": scene_id.strip(),
                        "startAt": start_at,
                        "startFrame": start_frame,
                        "startTag": start_tag,
                        "paused": paused,
                    },
                    meta={"event": name, "ok": ok, "error": err},
                )
                emitted.append(
                    {
                        "type": "apply_lighting_scene",
                        "sceneId": scene_id.strip(),
                        "startAt": start_at,
                        "startFrame": start_frame,
                        "startTag": start_tag,
                        "paused": paused,
                        "ok": ok,
                        "error": err,
                    }
                )
                continue
            if action_type == "stop_lighting_scene":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                scene_id = a_params.get("sceneId") or action.get("target") or "*"
                err = None
                try:
                    stop_scene(scene_id=str(scene_id).strip() or "*", source="pi.rules")
                except Exception as exc:
                    err = str(exc)
                append_event_log(
                    origin=origin,
                    direction="pi->esp",
                    name="LIGHT_SCENE_STOP",
                    source="pi.rules",
                    params={"sceneId": str(scene_id).strip() or "*"},
                    meta={"event": name, "error": err},
                )
                emitted.append(
                    {
                        "type": "stop_lighting_scene",
                        "sceneId": str(scene_id).strip() or "*",
                        "ok": err is None,
                        "error": err,
                    }
                )
                continue
            if action_type == "play_audio_cue":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                cue_id = str(a_params.get("cueId") or action.get("target") or "").strip()
                if not cue_id:
                    continue
                play_mode = str(a_params.get("playMode") or "layer").strip().lower()
                if play_mode not in ("restart", "layer", "ignore"):
                    play_mode = "layer"
                cue_overrides: Dict[str, Any] = {}
                if play_mode == "restart":
                    cue_overrides = {"restartPolicy": "restart"}
                elif play_mode == "ignore":
                    cue_overrides = {"restartPolicy": "ignore"}
                result: Dict[str, Any] = {"ok": False, "error": "unknown"}
                try:
                    result = play_cue(instance_path, cue_id, preview=False, overrides=cue_overrides)
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="AUDIO_CUE_PLAY",
                    source="pi.rules",
                    params={"cueId": cue_id, "playMode": play_mode, "ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "play_audio_cue",
                        "cueId": cue_id,
                        "playMode": play_mode,
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                        "playbackId": result.get("playbackId"),
                    }
                )
                continue
            if action_type == "stop_audio_cue":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                cue_id = str(a_params.get("cueId") or action.get("target") or "").strip()
                result: Dict[str, Any] = {"ok": False, "error": "unknown"}
                try:
                    result = stop_cue(instance_path, cue_id=cue_id or None, preview_only=False)
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="AUDIO_CUE_STOP",
                    source="pi.rules",
                    params={"cueId": cue_id, "ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "stop_audio_cue",
                        "cueId": cue_id,
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                        "stopped": result.get("stopped"),
                    }
                )
                continue
            if action_type == "toggle_audio_cue":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                cue_id = str(a_params.get("cueId") or action.get("target") or "").strip()
                if not cue_id:
                    continue
                play_mode = str(a_params.get("playMode") or "layer").strip().lower()
                if play_mode not in ("restart", "layer", "ignore"):
                    play_mode = "layer"
                was_active = False
                try:
                    runtime_state = load_audio_state(instance_path)
                    active = runtime_state.get("engine", {}).get("active", [])
                    for row in active if isinstance(active, list) else []:
                        if not isinstance(row, dict):
                            continue
                        if str(row.get("cueId") or "").strip() != cue_id:
                            continue
                        if bool(row.get("preview")):
                            continue
                        if bool(row.get("orphan")):
                            continue
                        was_active = True
                        break
                except Exception:
                    was_active = False

                result: Dict[str, Any]
                mode: str
                if was_active:
                    mode = "stop"
                    try:
                        result = stop_cue(instance_path, cue_id=cue_id, preview_only=False)
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}
                else:
                    mode = "play"
                    cue_overrides: Dict[str, Any] = {}
                    if play_mode == "restart":
                        cue_overrides = {"restartPolicy": "restart"}
                    elif play_mode == "ignore":
                        cue_overrides = {"restartPolicy": "ignore"}
                    try:
                        result = play_cue(instance_path, cue_id, preview=False, overrides=cue_overrides)
                    except Exception as exc:
                        result = {"ok": False, "error": str(exc)}

                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="AUDIO_CUE_TOGGLE",
                    source="pi.rules",
                    params={"cueId": cue_id, "mode": mode, "playMode": play_mode, "ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "toggle_audio_cue",
                        "cueId": cue_id,
                        "mode": mode,
                        "playMode": play_mode,
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                        "playbackId": result.get("playbackId"),
                        "stopped": result.get("stopped"),
                    }
                )
                continue
            if action_type == "media_play_scene":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                scene_id = str(a_params.get("sceneId") or action.get("target") or "").strip()
                if not scene_id:
                    continue
                result: Dict[str, Any]
                try:
                    result = media_play_scene(instance_path, scene_id=scene_id, launch_mode="embedded")
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="MEDIA_SCENE_PLAY",
                    source="pi.rules",
                    params={"sceneId": scene_id, "ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "media_play_scene",
                        "sceneId": scene_id,
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                    }
                )
                continue
            if action_type == "media_stop_scene":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                scene_id = str(a_params.get("sceneId") or action.get("target") or "").strip()
                if not scene_id:
                    continue
                result: Dict[str, Any]
                try:
                    result = media_stop_scene(instance_path, scene_id=scene_id)
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="MEDIA_SCENE_STOP",
                    source="pi.rules",
                    params={"sceneId": scene_id, "ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "media_stop_scene",
                        "sceneId": scene_id,
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                        "stopped": result.get("stopped"),
                    }
                )
                continue
            if action_type == "media_stop_all":
                result: Dict[str, Any]
                try:
                    result = media_stop_scene(instance_path, scene_id=None)
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}
                append_event_log(
                    origin=origin,
                    direction="pi->pi",
                    name="MEDIA_STOP_ALL",
                    source="pi.rules",
                    params={"ruleEvent": name},
                    meta={"event": name, "result": result},
                )
                emitted.append(
                    {
                        "type": "media_stop_all",
                        "ok": bool(result.get("ok")),
                        "error": result.get("error"),
                        "stopped": result.get("stopped"),
                    }
                )
    return emitted
