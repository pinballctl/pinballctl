"""Persistence endpoints for the rules editor UI."""

import json
import hashlib
import time
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from flask import request, jsonify, current_app
from pinballctl.bridge.state import enqueue_command, queue_blob_put, read_state as read_bridge_state
from pinballctl.ops.rules_blob import build_rules_pd, build_rules_pd_bytes, decode_rules_pd_bytes
from pinballctl.app.sync_state import update_sync_state
from . import api_bp

DURATION_FRAME_MS = 500

def _store_dir():
    """Ensure the instance rules directory exists and return it."""
    p = Path(current_app.instance_path) / "rules"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _rules_path():
    """Return the path to the rules JSON document."""
    return _store_dir() / "rules.json"

def _registry_path():
    """Return the path to the rules registry JSON document."""
    return Path(__file__).resolve().parent / "registry.json"

DEFAULT_REGISTRY = {
    "triggers": {
        "hardware": {
            "description": "Physical hardware inputs from mapping.json",
            "deviceClasses": {
                "button": {
                    "label": "Button",
                    "events": [
                        {"key": "CLICKED", "label": "Clicked"},
                        {"key": "DOUBLE_CLICKED", "label": "Double Clicked", "params": ["windowMs"]},
                        {"key": "HELD", "label": "Held", "params": ["minMs"]},
                        {"key": "PRESSED", "label": "Pressed"},
                        {"key": "RELEASED", "label": "Released"},
                        {"key": "REPEAT_WHILE_HELD", "label": "Repeat While Held", "params": ["repeatMs"]},
                    ],
                },
                "switch": {
                    "label": "Switch / Opto",
                    "events": [
                        {"key": "CLOSED", "label": "Closed"},
                        {"key": "OPENED", "label": "Opened"},
                        {"key": "CHANGED", "label": "Changed State"},
                        {"key": "ACTIVE_FOR_MS", "label": "Active for Duration", "params": ["minMs"]},
                        {"key": "INACTIVE_FOR_MS", "label": "Inactive for Duration", "params": ["minMs"]},
                    ],
                },
                "gyro": {
                    "label": "Tilt / Motion",
                    "events": [
                        {"key": "TILT_NUDGE", "label": "Nudge Detected"},
                        {"key": "TILT_WARNING", "label": "Tilt Warning"},
                        {"key": "TILT_TRIGGERED", "label": "Tilt Triggered"},
                        {"key": "LIFTED", "label": "Table Lifted"},
                        {"key": "DROPPED", "label": "Table Dropped"},
                    ],
                },
                "nfc": {
                    "label": "NFC / RFID",
                    "events": [
                        {"key": "NFC_SCANNED", "label": "Tag Scanned"},
                        {"key": "NFC_MATCHED", "label": "Known Tag Scanned", "params": ["tagIds"]},
                    ],
                },
            },
        },
        "system": {
            "description": "Predefined system and gameplay events",
            "categories": {
                "game": {
                    "label": "Game",
                    "events": [
                        "GAME_STARTED",
                        "GAME_ENDED",
                        "BALL_STARTED",
                        "BALL_ENDED",
                        "PLAYER_ADDED",
                    ],
                },
                "credits": {
                    "label": "Credits",
                    "events": [
                        "CREDITS_CHANGED",
                        "HAS_CREDIT_TRUE",
                        "HAS_CREDIT_FALSE",
                    ],
                },
                "modes": {
                    "label": "Modes",
                    "events": [
                        "MODE_STARTED",
                        "MODE_ENDED",
                    ],
                },
                "system": {
                    "label": "System",
                    "events": [
                        "BOOT_COMPLETED",
                        "ENABLE_GRANTED",
                        "ENABLE_REVOKED",
                        "IDLE_ENTERED",
                        "IDLE_EXITED",
                    ],
                },
                "bridge": {
                    "label": "Bridge / Connectivity",
                    "events": [
                        "BRIDGE_CONNECTED",
                        "BRIDGE_DISCONNECTED",
                        "CONFIG_SYNCED",
                    ],
                },
                "faults": {
                    "label": "Faults / Safety",
                    "events": [
                        "FAULT_RAISED",
                        "FAULT_CLEARED",
                        "WATCHDOG_TRIGGERED",
                    ],
                },
            },
        },
        "custom": {
            "description": "User-defined custom events",
            "freeText": True,
            "validation": "^[A-Z0-9_]+$",
            "example": "START_GAME_REQUESTED",
        },
    },
    "conditions": {
        "flag": {
            "label": "Flag",
            "operators": ["=="],
            "values": [True, False],
            "flags": [
                "TILT",
                "ENABLED",
                "HAS_CREDIT",
                "GAME_ACTIVE",
                "BALL_IN_PLAY",
                "IDLE",
            ],
        },
        "counter": {
            "label": "Counter",
            "operators": ["==", "!=", "<", "<=", ">", ">="],
            "counters": [
                "CREDITS",
                "BALL_NUMBER",
                "PLAYER_COUNT",
            ],
        },
        "time_since_event": {
            "label": "Time Since Event",
            "operators": [">", ">=", "<", "<="],
            "params": ["event", "valueMs"],
        },
        "device_state": {
            "label": "Device State",
            "operators": ["=="],
            "states": {
                "coil": ["ACTIVE", "INACTIVE"],
                "switch": ["OPEN", "CLOSED"],
                "output": ["HIGH", "LOW"],
            },
        },
    },
    "actions": {
        "emit_event": {"label": "Emit Event", "params": ["event"]},
        "set_flag": {"label": "Set Flag", "params": ["flag", "value"]},
        "set_counter": {"label": "Set Counter", "params": ["counter", "value"]},
        "inc_counter": {"label": "Increment Counter", "params": ["counter", "delta"]},
        "pulse_coil": {"label": "Pulse", "params": ["device", "durationMs"], "targetSource": "hardware.outputs"},
        "set_output": {"label": "Set Output", "params": ["device", "value"], "targetSource": "hardware.outputs"},
        "apply_lighting_scene": {
            "label": "Apply Lighting Scene",
            "params": ["sceneId", "startAt", "startFrame", "startTag", "startMode"],
            "targetSource": "lighting.scenes",
        },
        "stop_lighting_scene": {"label": "Stop Lighting Scene", "params": ["sceneId"], "targetSource": "lighting.scenes"},
        "play_audio_cue": {"label": "Play Audio Cue", "params": ["cueId", "playMode"], "targetSource": "audio.cues"},
        "stop_audio_cue": {"label": "Stop Audio Cue", "params": ["cueId"], "targetSource": "audio.cues"},
        "toggle_audio_cue": {"label": "Toggle Audio Cue", "params": ["cueId", "playMode"], "targetSource": "audio.cues"},
        "media_play_scene": {"label": "Play Media Scene", "params": ["sceneId"], "targetSource": "media.scenes"},
        "media_stop_scene": {"label": "Stop Media Scene", "params": ["sceneId"], "targetSource": "media.scenes"},
        "media_stop_all": {"label": "Stop All Media", "params": []},
        "led_pattern": {"label": "LED Pattern", "params": ["group", "pattern", "durationMs"], "planned": True},
        "delay": {"label": "Delay", "params": ["durationMs"], "planned": True},
    },
}

TAG_PALETTE = ["#5b9bd5", "#70ad47", "#ed7d31", "#ffc000", "#4472c4", "#a5a5a5"]
_last_rules_sync_log_at: float | None = None

def _load_registry():
    p = _registry_path()
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return DEFAULT_REGISTRY

def _load_rules_list():
    """Load the saved list of rules or return an empty list."""
    p = _rules_path()
    if not p.exists():
        return []
    try:
        rules = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(rules, list):
            return rules
    except Exception:
        pass
    return []

def _normalize_rules(rules):
    normalized = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        rule.setdefault("name", "")
        rule.setdefault("tags", [])
        rule.setdefault("logic", "ALL")
        rule.setdefault("conditionLogic", "ALL")
        rule.setdefault("triggers", [])
        rule.setdefault("conditions", [])
        rule.setdefault("actions", [])
        rule.setdefault("enabled", True)
        rule.setdefault("notes", "")

        if not isinstance(rule.get("triggerGroups"), dict):
            rule["triggerGroups"] = {"logic": rule.get("logic") or "ALL", "groups": []}
            if isinstance(rule.get("triggers"), list) and rule["triggers"]:
                rule["triggerGroups"]["groups"].append({
                    "logic": rule.get("logic") or "ALL",
                    "windowMs": 750,
                    "items": rule["triggers"],
                })
        trigger_groups = rule["triggerGroups"]
        trigger_groups.setdefault("logic", rule.get("logic") or "ALL")
        trigger_groups["groups"] = trigger_groups.get("groups") if isinstance(trigger_groups.get("groups"), list) else []
        for group in trigger_groups["groups"]:
            if not isinstance(group, dict):
                continue
            group.setdefault("logic", "ALL")
            group.setdefault("windowMs", 750)
            group["items"] = group.get("items") if isinstance(group.get("items"), list) else []

        if not isinstance(rule.get("conditionGroups"), dict):
            rule["conditionGroups"] = {"logic": rule.get("conditionLogic") or "ALL", "groups": []}
            if isinstance(rule.get("conditions"), list) and rule["conditions"]:
                rule["conditionGroups"]["groups"].append({
                    "logic": rule.get("conditionLogic") or "ALL",
                    "items": rule["conditions"],
                })
        condition_groups = rule["conditionGroups"]
        condition_groups.setdefault("logic", rule.get("conditionLogic") or "ALL")
        condition_groups["groups"] = condition_groups.get("groups") if isinstance(condition_groups.get("groups"), list) else []
        for group in condition_groups["groups"]:
            if not isinstance(group, dict):
                continue
            group.setdefault("logic", "ALL")
            group["items"] = group.get("items") if isinstance(group.get("items"), list) else []

        for trig in rule.get("triggers", []) or []:
            if not isinstance(trig, dict):
                continue
            ttype = trig.get("type")
            if ttype in ("game", "gameplay"):
                trig["type"] = "system"
        for action in rule.get("actions", []) or []:
            if not isinstance(action, dict):
                continue
            params = action.get("params") if isinstance(action.get("params"), dict) else {}
            action["params"] = params
            action_type = str(action.get("type") or "").strip()
            if action_type == "play_audio_cue":
                cue_id = str(params.get("cueId") or action.get("target") or "").strip()
                action["target"] = cue_id
                params["cueId"] = cue_id
                play_mode = str(params.get("playMode") or "layer").strip().lower()
                if play_mode not in ("restart", "layer", "ignore"):
                    play_mode = "layer"
                params["playMode"] = play_mode
                continue
            if action_type == "stop_audio_cue":
                cue_id = str(params.get("cueId") or action.get("target") or "").strip()
                action["target"] = cue_id
                params["cueId"] = cue_id
                continue
            if action_type == "toggle_audio_cue":
                cue_id = str(params.get("cueId") or action.get("target") or "").strip()
                action["target"] = cue_id
                params["cueId"] = cue_id
                play_mode = str(params.get("playMode") or "layer").strip().lower()
                if play_mode not in ("restart", "layer", "ignore"):
                    play_mode = "layer"
                params["playMode"] = play_mode
                continue
            if action_type == "media_play_scene":
                scene_id = str(params.get("sceneId") or action.get("target") or "").strip()
                action["target"] = scene_id
                params["sceneId"] = scene_id
                continue
            if action_type == "media_stop_scene":
                scene_id = str(params.get("sceneId") or action.get("target") or "").strip()
                action["target"] = scene_id
                params["sceneId"] = scene_id
                continue
            if action_type == "media_stop_all":
                action["target"] = ""
                action["params"] = {}
                continue
            if action_type != "apply_lighting_scene":
                continue
            scene_id = params.get("sceneId") or action.get("target") or ""
            scene_id = str(scene_id).strip()
            action["target"] = scene_id
            params["sceneId"] = scene_id

            start_mode = str(params.get("startMode") or "play").strip().lower()
            if start_mode not in ("play", "paused"):
                start_mode = "play"
            params["startMode"] = start_mode

            start_at = str(params.get("startAt") or "start").strip().lower()
            if start_at not in ("start", "frame", "tag"):
                start_at = "start"
            params["startAt"] = start_at

            if start_at == "frame":
                try:
                    frame = int(params.get("startFrame", 1))
                except Exception:
                    frame = 1
                if frame < 1:
                    frame = 1
                params["startFrame"] = frame
                params.pop("startTag", None)
            elif start_at == "tag":
                tag = str(params.get("startTag") or "").strip().lower()
                params["startTag"] = tag
                params.pop("startFrame", None)
            else:
                params.pop("startFrame", None)
                params.pop("startTag", None)
        normalized.append(rule)
    return normalized

def _rules_store_dir() -> Path:
    """Return the instance rules directory."""
    p = Path(current_app.instance_path) / "rules"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _rules_pd_path() -> Path:
    return _rules_store_dir() / "rules.pd"


def _rules_meta_path() -> Path:
    return _rules_store_dir() / "rules_meta.json"


def _lighting_json_path() -> Path:
    p = Path(current_app.instance_path) / "lighting"
    p.mkdir(parents=True, exist_ok=True)
    return p / "lighting.json"


def _audio_json_path() -> Path:
    p = Path(current_app.instance_path) / "audio"
    p.mkdir(parents=True, exist_ok=True)
    return p / "audio.json"


def _media_json_path() -> Path:
    p = Path(current_app.instance_path) / "media"
    p.mkdir(parents=True, exist_ok=True)
    return p / "media.json"


def _audio_cue_ids() -> list[dict]:
    p = _audio_json_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    cues = raw.get("cues") if isinstance(raw, dict) else None
    if not isinstance(cues, list):
        return []
    out = []
    for cue in cues:
        if not isinstance(cue, dict):
            continue
        cid = str(cue.get("id") or "").strip()
        if not cid:
            continue
        name = str(cue.get("name") or cid).strip() or cid
        bus = str(cue.get("bus") or "sfx").strip().lower() or "sfx"
        out.append({"id": cid, "name": name, "bus": bus, "enabled": bool(cue.get("enabled", True))})
    out.sort(key=lambda c: str(c.get("name") or c.get("id") or "").lower())
    return out


def _lighting_scene_ids() -> list[dict]:
    p = _lighting_json_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    scenes = raw.get("scenes") if isinstance(raw, dict) else None
    if not isinstance(scenes, list):
        return []
    out = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        sid = s.get("id")
        title = s.get("title")
        if not isinstance(sid, str) or not sid.strip():
            continue
        sid = sid.strip()
        stitle = title.strip() if isinstance(title, str) and title.strip() else sid
        duration = s.get("duration") if isinstance(s, dict) else {}
        unit = str(duration.get("unit", "seconds")).strip().lower() if isinstance(duration, dict) else "seconds"
        value = duration.get("value", 0) if isinstance(duration, dict) else 0
        try:
            v = float(value)
        except Exception:
            v = 0.0
        if unit == "frames":
            frame_count = max(1, int(round(v)))
        elif unit == "minutes":
            frame_count = max(1, int(round((max(0.0, v) * 60_000) / DURATION_FRAME_MS)))
        else:
            frame_count = max(1, int(round((max(0.0, v) * 1_000) / DURATION_FRAME_MS)))
        markers = s.get("markers") if isinstance(s.get("markers"), list) else []
        tags = []
        for marker in markers:
            if not isinstance(marker, dict):
                continue
            tag = str(marker.get("tag") or "").strip()
            if not tag:
                continue
            try:
                at_ms = int(marker.get("atMs", 0))
            except Exception:
                at_ms = 0
            if at_ms < 0:
                at_ms = 0
            tags.append(
                {
                    "tag": tag,
                    "atMs": at_ms,
                    "frame": max(1, int(round(at_ms / DURATION_FRAME_MS)) + 1),
                }
            )
        tags.sort(key=lambda t: int(t.get("atMs", 0)))
        out.append({"id": sid, "title": stitle, "frameCount": frame_count, "tags": tags})
    return out


def _media_scene_ids() -> list[dict]:
    p = _media_json_path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    scenes = raw.get("scenes") if isinstance(raw, dict) else None
    if not isinstance(scenes, list):
        return []
    out = []
    for s in scenes:
        if not isinstance(s, dict):
            continue
        sid = str(s.get("id") or "").strip()
        if not sid:
            continue
        name = str(s.get("name") or sid).strip() or sid
        out.append({"id": sid, "title": name})
    out.sort(key=lambda x: str(x.get("title") or x.get("id") or "").lower())
    return out


def _write_rules_meta(blob: bytes) -> None:
    meta_path = _rules_meta_path()
    bundle = decode_rules_pd_bytes(blob)
    meta = {
        "sha256": hashlib.sha256(blob).hexdigest(),
        "size": len(blob),
        "builtAt": bundle.built_at,
        "sourceHash": bundle.source_hash,
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _build_rules_pd_from_path(rules_path: Path) -> bytes:
    blob = build_rules_pd_bytes(rules_path)
    return blob
def _save_rules_list(rules):
    """Write the provided rules list to disk."""
    p = _rules_path()
    p.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")

@api_bp.get("/catalog")
def api_rules_catalog():
    """Return static metadata that drives the rules builder UI."""
    return jsonify({
        "ok": True,
        "registry": _load_registry(),
        "tagPalette": TAG_PALETTE,
        "lightingScenes": _lighting_scene_ids(),
        "audioCues": _audio_cue_ids(),
        "mediaScenes": _media_scene_ids(),
    })

@api_bp.get("/list")
def api_rules_list():
    """Return the full rules list stored in the instance directory."""
    return jsonify({"ok": True, "rules": _normalize_rules(_load_rules_list())})

@api_bp.post("/save")
def api_rules_save():
    """Validate and persist a list of rules provided by the client."""
    body = request.get_json(silent=True) or {}
    rules = body.get("rules")
    if not isinstance(rules, list):
        return jsonify({"ok": False, "error": "rules must be a list"}), 400
    normalized = _normalize_rules(rules)
    rules_path = _rules_path()
    tmp_path = rules_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        blob = _build_rules_pd_from_path(tmp_path)
        _rules_pd_path().write_bytes(blob)
        _write_rules_meta(blob)
        tmp_path.replace(rules_path)
    except Exception:
        current_app.logger.exception("Failed to compile rules.pd on save")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return jsonify({"ok": False, "error": "rules_compile_failed"}), 500
    enqueue_command({"cmd": "SET_RULES", "rules": normalized})
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})

@api_bp.get("/hardware")
def api_rules_hardware():
    """Return mapped hardware devices for rules selectors."""
    mapping_path = Path(current_app.instance_path) / "hardware" / "mapping.json"
    if not mapping_path.exists():
        return jsonify({"ok": True, "devices": []})
    try:
        raw = json.loads(mapping_path.read_text(encoding="utf-8"))
        data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}
    function_map = {
        "Button": ("button", "input"),
        "Switch": ("switch", "input"),
        "Accelerometer": ("gyro", "input"),
        "NFC": ("nfc", "input"),
        "Solenoid": ("coil", "output"),
        "LED": ("output", "output"),
        "RGB Strip": ("led", "output"),
    }
    devices = []
    for uid, row in data.items():
        if not isinstance(row, dict):
            continue
        fn = (row.get("function") or "").strip()
        if not fn:
            continue
        friendly = (row.get("friendly") or "").strip() or uid
        device_class, direction = function_map.get(fn, ("other", "unknown"))
        devices.append({
            "id": uid,
            "friendly": friendly,
            "function": fn,
            "deviceClass": device_class,
            "direction": direction,
        })
    devices.sort(key=lambda d: d["friendly"].lower())
    return jsonify({"ok": True, "devices": devices})

@api_bp.post("/sync")
def api_rules_sync():
    """Build rules.pd, push runtime rules, and queue blob transfer to the ESP."""
    st = read_bridge_state()
    if not st.get("connected") or not st.get("port"):
        return jsonify({
            "ok": False,
            "error": "bridge_not_connected",
            "bridge": {"connected": st.get("connected"), "port": st.get("port")},
        }), 409

    def _parse_iso(ts: str | None):
        try:
            if not ts:
                return None
            return datetime.fromisoformat(ts)
        except Exception:
            return None

    now = datetime.now(timezone.utc)
    last_update = _parse_iso(st.get("updated_at"))
    if not last_update or (now - last_update).total_seconds() > 3.0:
        echo_before = st.get("echo_at") or 0
        updated_before = st.get("updated_at") or ""
        try:
            enqueue_command({"cmd": "ECHO"})
        except Exception:
            return jsonify({"ok": False, "error": "bridge_unreachable"}), 409
        deadline = time.time() + 3.0
        while time.time() < deadline:
            latest = read_bridge_state()
            if (latest.get("echo_at") or 0) > echo_before:
                break
            echo_status = latest.get("echo_status") or {}
            if echo_status.get("t") == "ECHO" and echo_status.get("ok") is True:
                break
            if (latest.get("updated_at") or "") != updated_before:
                break
            time.sleep(0.1)
        else:
            return jsonify({"ok": False, "error": "bridge_unresponsive"}), 409

    rules_path = _rules_store_dir() / "rules.json"
    output_path = _rules_pd_path()
    try:
        normalized = _normalize_rules(_load_rules_list())
    except Exception:
        current_app.logger.exception("Failed to load rules.json for runtime sync")
        return jsonify({"ok": False, "error": "missing_rules"}), 404

    try:
        enqueue_command({"cmd": "SET_RULES", "rules": normalized})
    except Exception:
        current_app.logger.exception("Failed to queue SET_RULES command")
        return jsonify({"ok": False, "error": "bridge_unreachable"}), 409

    if not output_path.exists():
        current_app.logger.info("Compiling rules to rules.pd")
        try:
            result = build_rules_pd(rules_path=rules_path, output_path=output_path)
            _write_rules_meta(output_path.read_bytes())
        except FileNotFoundError:
            return jsonify({"ok": False, "error": "missing_rules"}), 404
        except Exception:
            current_app.logger.exception("Failed to build rules.pd")
            return jsonify({"ok": False, "error": "build_failed"}), 500
        current_app.logger.info("Saved rules.pd locally: %s", result.output_path)

    blob = output_path.read_bytes()
    payload_len = struct.unpack("<I", blob[8:12])[0] if len(blob) >= 12 else 0
    payload_sha = blob[12:44].hex() if len(blob) >= 44 else ""
    try:
        queue_blob_put("rules", str(output_path), "/cfg/rules.pd")
    except Exception:
        current_app.logger.exception("Failed to queue rules.pd transfer")
        return jsonify({"ok": False, "error": "queue_failed"}), 500

    current_app.logger.info("Uploading rules.pd to ESP…")
    return jsonify({
        "ok": True,
        "filename": "rules.pd",
        "bytes": payload_len,
        "sha256": payload_sha,
        "esp_path": "/cfg/rules.pd",
    })


@api_bp.get("/sync/status")
def api_rules_sync_status():
    """Return the latest blob transfer status from the bridge state."""
    st = read_bridge_state()
    status = st.get("blob_status") or {}
    global _last_rules_sync_log_at
    if status.get("state") == "done" and status.get("ok") and status.get("blobType") == "rules":
        blob_at = st.get("blob_at") or 0
        if _last_rules_sync_log_at != blob_at:
            _last_rules_sync_log_at = blob_at
            try:
                path = _rules_store_dir() / "rules.pd"
                sha = ""
                size = None
                if path.exists():
                    data = path.read_bytes()
                    sha = hashlib.sha256(data).hexdigest()
                    size = len(data)
                    update_sync_state(current_app.instance_path, "rules", sha)
                current_app.logger.info(
                    "Rules uploaded successfully: %s sha=%s bytes=%s",
                    status.get("path") or "/cfg/rules.pd",
                    sha,
                    size,
                )
            except Exception:
                current_app.logger.exception("Failed to log rules upload completion")
    return jsonify({
        "blob_status": status,
        "blob_at": st.get("blob_at"),
        "bridge": {"connected": st.get("connected"), "port": st.get("port")},
    })
