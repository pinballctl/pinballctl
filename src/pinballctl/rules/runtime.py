"""Shared rules runtime used by both API and bridge event ingress paths."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import time
from datetime import datetime
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


def _load_mapping_rows(instance_path: str | Path) -> dict[str, dict[str, Any]]:
    p = Path(instance_path) / "hardware" / "mapping.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for uid, row in data.items():
        if isinstance(uid, str) and isinstance(row, dict):
            out[uid] = row
    return out


def _parse_gpio_pin(uid: str) -> int | None:
    parts = str(uid or "").split("__")
    if len(parts) < 4:
        return None
    if parts[-2] != "GPIO":
        return None
    chan = str(parts[-1] or "").strip()
    if not chan.isdigit():
        return None
    pin = int(chan)
    return pin if pin >= 0 else None


def _build_lcd_config_map(instance_path: str | Path) -> dict[str, dict[str, Any]]:
    rows = _load_mapping_rows(instance_path)
    groups: dict[str, list[dict[str, Any]]] = {}
    for uid, row in rows.items():
        fn = str(row.get("function") or "").strip()
        if fn not in ("LCD Display", "LCD1602"):
            continue
        comp_id = str(row.get("componentId") or "").strip()
        role = str(row.get("componentRole") or "").strip().upper()
        if not comp_id or role not in ("SDA", "SCL"):
            continue
        groups.setdefault(comp_id, []).append(
            {
                "uid": uid,
                "role": role,
                "pin": _parse_gpio_pin(uid),
                "address": str(row.get("i2cAddress") or "0x27").strip() or "0x27",
                "cols": row.get("lcdCols", 16),
                "rows": row.get("lcdRows", 2),
            }
        )
    out: dict[str, dict[str, Any]] = {}
    for comp_id, members in groups.items():
        sda = next((m for m in members if m.get("role") == "SDA"), None)
        scl = next((m for m in members if m.get("role") == "SCL"), None)
        if not sda or not scl:
            continue
        sda_pin = sda.get("pin")
        scl_pin = scl.get("pin")
        if not isinstance(sda_pin, int) or not isinstance(scl_pin, int) or sda_pin == scl_pin:
            continue
        try:
            addr = int(str(sda.get("address") or "0x27"), 0)
        except Exception:
            addr = 0x27
        if addr < 0x03 or addr > 0x77:
            addr = 0x27
        try:
            cols = int(sda.get("cols", 16))
        except Exception:
            cols = 16
        try:
            rows_count = int(sda.get("rows", 2))
        except Exception:
            rows_count = 2
        cols = max(8, min(40, cols))
        rows_count = max(1, min(4, rows_count))
        did = f"LCD_DISPLAY::{comp_id}"
        out[did] = {
            "target": did,
            "sdaPin": sda_pin,
            "sclPin": scl_pin,
            "address": f"0x{addr:02x}",
            "cols": cols,
            "rows": rows_count,
        }
    return out


def _resolve_lcd_config(
    target: str,
    params: dict[str, Any],
    lcd_configs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    # Prefer current mapping config by explicit target/lcdId/device.
    lookup_ids: list[str] = []
    for cand in (target, params.get("lcdId"), params.get("device")):
        if isinstance(cand, str) and cand.strip():
            lookup_ids.append(cand.strip())
    for cand in lookup_ids:
        cfg = lcd_configs.get(cand)
        if isinstance(cfg, dict):
            return dict(cfg)
    # Backward-compat fallback: if there is exactly one LCD configured,
    # use it even when an action carries a stale LCD id after pin remap.
    if len(lcd_configs) == 1:
        only = next(iter(lcd_configs.values()))
        if isinstance(only, dict):
            return dict(only)
    # Last fallback to action params.
    cfg: dict[str, Any] = {"target": target}
    for key in ("sdaPin", "sclPin", "address", "cols", "rows"):
        if key in params:
            cfg[key] = params.get(key)
    return cfg


_LCD_PLACEHOLDER_RE = re.compile(r"\[([A-Z0-9_]+)\]", re.IGNORECASE)


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _lcd_placeholder_values(
    instance_path: str | Path,
    *,
    event_name: str,
    event_source: str | None,
    event_params: dict[str, Any],
) -> dict[str, str]:
    base = Path(instance_path)
    scoring_state = _read_json_dict(base / "scoring" / "state.json")
    bridge_state = _read_json_dict(base / "bridge" / "bridge_state.json")
    now = datetime.now().astimezone()

    active_multiplier = scoring_state.get("activeMultiplier")
    if not isinstance(active_multiplier, dict):
        active_multiplier = {}

    game_state = scoring_state.get("game")
    if not isinstance(game_state, dict):
        game_state = {}

    def _as_str(value: Any, default: str = "") -> str:
        if value is None:
            return default
        return str(value)

    def _num_str(value: Any, default: str = "0") -> str:
        try:
            return str(int(value))
        except Exception:
            return default

    def _float_str(value: Any, default: str = "1.0") -> str:
        try:
            out = f"{float(value):g}"
            return out or default
        except Exception:
            return default

    pi_ip = _local_host_ip()
    esp_ip = _as_str(bridge_state.get("ip"), "").strip()
    if esp_ip in ("", "-", "0.0.0.0", "none", "None", "null", "Null"):
        esp_ip = ""

    return {
        "EVENT_NAME": _as_str(event_name, ""),
        "EVENT_SOURCE": _as_str(event_source, ""),
        "EVENT_TYPE": _as_str(event_params.get("eventType"), ""),
        "SCORE": _num_str(scoring_state.get("score"), "0"),
        "PLAYER": _num_str(scoring_state.get("player"), "1"),
        "BALL": _num_str(scoring_state.get("ball"), "1"),
        "CREDITS": _num_str(scoring_state.get("credits"), "0"),
        "MULTIPLIER": _float_str(active_multiplier.get("value"), "1.0"),
        "GAME_ACTIVE": "ON" if bool(game_state.get("active")) else "OFF",
        "IP_ADDRESS": pi_ip,
        "PI_IP_ADDRESS": pi_ip,
        "ESP_IP_ADDRESS": esp_ip,
        "RSSI": _as_str(bridge_state.get("rssi"), ""),
        "PORT": _as_str(bridge_state.get("port"), ""),
        "FIRMWARE": _as_str(bridge_state.get("firmware"), ""),
        "CHIP": _as_str(bridge_state.get("chip"), ""),
        "CONTROLLER": _as_str(bridge_state.get("controller"), ""),
        "PROFILE": _as_str(bridge_state.get("profile"), ""),
        "DATE": now.strftime("%d %b %Y"),
        "TIME": now.strftime("%H:%M"),
        "DATETIME": now.strftime("%d %b %Y %H:%M"),
    }


def _local_host_ip() -> str:
    # Best-effort local host IP for placeholders when bridge state has no IP.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            ip = str(s.getsockname()[0] or "").strip()
        finally:
            s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        ip = str(ip or "").strip()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    # Linux: hostname -I gives active interface addresses.
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=0.5)
        if out.returncode == 0:
            for token in (out.stdout or "").split():
                ip = str(token or "").strip()
                if ip and "." in ip and not ip.startswith("127."):
                    return ip
    except Exception:
        pass
    # macOS: common Wi-Fi interface query.
    try:
        out = subprocess.run(["ipconfig", "getifaddr", "en0"], capture_output=True, text=True, timeout=0.5)
        ip = str((out.stdout or "").strip())
        if out.returncode == 0 and ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return ""


def _expand_lcd_placeholders(template: str, values: dict[str, str]) -> str:
    if not template:
        return ""

    def _replace(match: re.Match[str]) -> str:
        key = str(match.group(1) or "").upper()
        if key in values:
            return values.get(key) or ""
        return match.group(0)

    return _LCD_PLACEHOLDER_RE.sub(_replace, template)


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
            group_window_ms = grp.get("windowMs")
            for item in grp.get("items") if isinstance(grp.get("items"), list) else []:
                if isinstance(item, dict):
                    row = dict(item)
                    row["__groupWindowMs"] = group_window_ms
                    out.append(row)
    legacy = rule.get("triggers")
    if isinstance(legacy, list):
        for item in legacy:
            if isinstance(item, dict):
                row = dict(item)
                row["__groupWindowMs"] = None
                out.append(row)
    return out


def _positive_int(value: Any) -> int | None:
    try:
        n = int(value)
    except Exception:
        return None
    return n if n > 0 else None


def _event_detail_ms(params: Dict[str, Any]) -> int | None:
    direct = _positive_int(params.get("detailMs"))
    if direct is not None:
        return direct
    payload = params.get("payload")
    if isinstance(payload, dict):
        nested = _positive_int(payload.get("detailMs"))
        if nested is not None:
            return nested
    return None


def _rule_matches_event(rule: Dict[str, Any], name: str, source: str | None, params: Dict[str, Any]) -> bool:
    if not rule.get("enabled", True):
        return False
    event_type = params.get("eventType") if isinstance(params.get("eventType"), str) else None
    detail_ms = _event_detail_ms(params)
    for trig in _trigger_items(rule):
        trig_event = trig.get("event")
        if isinstance(trig_event, str) and trig_event and trig_event != name:
            continue
        trig_type = str(trig.get("type") or "").strip().lower()
        trig_source = trig.get("source")
        if isinstance(trig_source, str) and trig_source:
            # System triggers commonly persist source="system" from the UI.
            # Runtime system events can originate from bridge/app sources,
            # so treat "system" as a wildcard source for system triggers.
            if trig_type not in ("system", "game", "gameplay"):
                if (source or "") != trig_source:
                    continue
            elif trig_source.strip().lower() not in (
                "system",
                "*",
                "any",
                # Rules UI stores system category keys here (not event origin).
                # Treat them as category tags, not strict source filters.
                "game",
                "credits",
                "modes",
                "bridge",
                "faults",
                "gameplay",
            ):
                if (source or "") != trig_source:
                    continue
        trig_fn = trig.get("fn")
        if isinstance(trig_fn, str) and trig_fn:
            trig_fn_upper = trig_fn.upper()
            if not event_type or trig_fn_upper != event_type.upper():
                continue
            trig_params = trig.get("params") if isinstance(trig.get("params"), dict) else {}
            if trig_fn_upper == "DOUBLE_CLICKED":
                window_ms = _positive_int(trig_params.get("windowMs"))
                if window_ms is None:
                    window_ms = _positive_int(trig.get("__groupWindowMs"))
                if window_ms is not None and detail_ms is not None and detail_ms > window_ms:
                    continue
            elif trig_fn_upper == "HELD":
                min_ms = _positive_int(trig_params.get("minMs"))
                if min_ms is not None and detail_ms is not None and detail_ms != min_ms:
                    continue
            elif trig_fn_upper == "REPEAT_WHILE_HELD":
                repeat_ms = _positive_int(trig_params.get("repeatMs"))
                if repeat_ms is not None and detail_ms is not None and detail_ms != repeat_ms:
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
    lcd_configs = _build_lcd_config_map(instance_path)
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
                continue
            if action_type == "set_lcd_text":
                a_params = action.get("params") if isinstance(action.get("params"), dict) else {}
                target = str(a_params.get("device") or a_params.get("lcdId") or action.get("target") or "").strip()
                line1_tpl = str(a_params.get("line1") or "")
                line2_tpl = str(a_params.get("line2") or "")
                if not target:
                    continue
                placeholder_values = _lcd_placeholder_values(
                    instance_path,
                    event_name=name,
                    event_source=source,
                    event_params=payload,
                )
                line1 = _expand_lcd_placeholders(line1_tpl, placeholder_values).strip()
                line2 = _expand_lcd_placeholders(line2_tpl, placeholder_values).strip()
                lcd_cfg = _resolve_lcd_config(target, a_params, lcd_configs)
                resolved_target = str(lcd_cfg.get("target") or target).strip() or target
                lcd_cmd: Dict[str, Any] = {
                    "cmd": "LCD_SET",
                    "target": resolved_target,
                    "line1": line1[:16],
                    "line2": line2[:16],
                }
                for key in ("sdaPin", "sclPin", "address", "cols", "rows"):
                    if key in lcd_cfg:
                        lcd_cmd[key] = lcd_cfg.get(key)
                clear_first = a_params.get("clearFirst")
                if isinstance(clear_first, str):
                    lcd_cmd["clearFirst"] = clear_first.strip().lower() in ("1", "true", "yes", "on")
                elif clear_first is not None:
                    lcd_cmd["clearFirst"] = bool(clear_first)
                enqueued, enqueue_error = enqueue_fn(lcd_cmd)
                append_event_log(
                    origin=origin,
                    direction="pi->esp",
                    name="LCD_SET",
                    source="pi.rules",
                    params={
                        "target": resolved_target,
                        "line1": lcd_cmd.get("line1"),
                        "line2": lcd_cmd.get("line2"),
                        "sdaPin": lcd_cmd.get("sdaPin"),
                        "sclPin": lcd_cmd.get("sclPin"),
                        "address": lcd_cmd.get("address"),
                        "cols": lcd_cmd.get("cols"),
                        "rows": lcd_cmd.get("rows"),
                    },
                    meta={"event": name, "bridge_enqueued": enqueued, "bridge_error": enqueue_error},
                )
                emitted.append(
                    {
                        "type": "set_lcd_text",
                        "target": resolved_target,
                        "ok": bool(enqueued),
                        "error": enqueue_error,
                    }
                )
    return emitted
