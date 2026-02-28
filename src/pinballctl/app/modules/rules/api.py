"""Persistence endpoints for the rules editor UI."""

import json
import hashlib
import time
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any
from flask import request, jsonify, current_app
from pinballctl.bridge.state import enqueue_command, queue_blob_put, read_state as read_bridge_state, rpc_command as bridge_rpc_command
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
        "emit_event": {
            "label": "Emit Event",
            "params": ["event"],
            "ui": {"module": "system", "pathKey": "system_event", "actionLabel": "Fire Event"},
        },
        "set_flag": {
            "label": "Set Flag",
            "params": ["flag", "value"],
            "ui": {"module": "system", "pathKey": "system_flag_set", "actionLabel": "Set Flag Value"},
        },
        "set_counter": {
            "label": "Set Counter",
            "params": ["counter", "value"],
            "ui": {"module": "system", "pathKey": "system_counter", "actionLabel": "Counters"},
        },
        "inc_counter": {
            "label": "Increment Counter",
            "params": ["counter", "delta"],
            "ui": {"module": "system", "pathKey": "system_counter", "actionLabel": "Counters"},
        },
        "pulse": {
            "label": "Pulse",
            "params": ["device", "durationMs"],
            "targetSource": "hardware.outputs",
            "ui": {"module": "system", "pathKey": "system_pin_output", "actionLabel": "Pin Output"},
        },
        "set_output": {
            "label": "Set Output",
            "params": ["device", "value"],
            "targetSource": "hardware.outputs",
            "ui": {"module": "system", "pathKey": "system_pin_output", "actionLabel": "Pin Output"},
        },
        "set_lcd_text": {
            "label": "Set LCD Text",
            "params": ["device", "line1", "line2", "clearFirst"],
            "targetSource": "hardware.lcds",
            "ui": {
                "module": "system",
                "pathKey": "system_lcd_text",
                "actionLabel": "LCD Text",
                "fields": [
                    {
                        "bind": "target",
                        "label": "LCD Device",
                        "kind": "select",
                        "source": "hardware.lcds",
                        "required": True,
                        "requiredMessage": "Select an LCD device.",
                        "placeholder": "Select LCD…",
                        "sync": ["params.device", "params.lcdId"],
                        "col": "col-12 col-lg-4",
                    },
                    {"bind": "params.line1", "label": "Line 1", "kind": "text", "maxLength": 16, "col": "col-12 col-lg-4"},
                    {"bind": "params.line2", "label": "Line 2", "kind": "text", "maxLength": 16, "col": "col-12 col-lg-4"},
                    {"bind": "params.clearFirst", "label": "Clear display before writing", "kind": "checkbox", "col": "col-12"},
                    {
                        "kind": "help_tokens",
                        "label": "Placeholders",
                        "col": "col-12",
                        "tokens": [
                            {"token": "[SCORE]", "summary": "Current score"},
                            {"token": "[PLAYER]", "summary": "Current player"},
                            {"token": "[BALL]", "summary": "Current ball"},
                            {"token": "[CREDITS]", "summary": "Credits count"},
                            {"token": "[MULTIPLIER]", "summary": "Active score multiplier"},
                            {"token": "[EVENT_NAME]", "summary": "Trigger event name"},
                            {"token": "[EVENT_SOURCE]", "summary": "Trigger event source"},
                            {"token": "[EVENT_TYPE]", "summary": "Trigger event type"},
                            {"token": "[IP_ADDRESS]", "summary": "Bridge IP (if available)"},
                            {"token": "[RSSI]", "summary": "Bridge RSSI (if available)"},
                            {"token": "[PORT]", "summary": "Bridge serial port"},
                            {"token": "[FIRMWARE]", "summary": "Firmware version"},
                            {"token": "[CONTROLLER]", "summary": "Controller id"},
                            {"token": "[CHIP]", "summary": "Chip id"},
                            {"token": "[PROFILE]", "summary": "Hardware profile"},
                            {"token": "[TIME]", "summary": "Local time (HH:MM)"},
                            {"token": "[DATE]", "summary": "Local date"},
                            {"token": "[DATETIME]", "summary": "Local date/time"},
                        ],
                    },
                ],
            },
        },
        "apply_lighting_scene": {
            "label": "Apply Lighting Scene",
            "params": ["sceneId", "startAt", "startFrame", "startTag", "startMode"],
            "targetSource": "lighting.scenes",
            "ui": {"module": "lighting", "pathKey": "lighting_apply", "actionLabel": "Play Scene"},
        },
        "stop_lighting_scene": {
            "label": "Stop Lighting Scene",
            "params": ["sceneId"],
            "targetSource": "lighting.scenes",
            "ui": {"module": "lighting", "pathKey": "lighting_stop", "actionLabel": "Stop Scene"},
        },
        "play_audio_cue": {
            "label": "Play Audio Cue",
            "params": ["cueId", "playMode"],
            "targetSource": "audio.cues",
            "ui": {"module": "audio", "pathKey": "audio_play", "actionLabel": "Play Cue"},
        },
        "stop_audio_cue": {
            "label": "Stop Audio Cue",
            "params": ["cueId"],
            "targetSource": "audio.cues",
            "ui": {"module": "audio", "pathKey": "audio_stop", "actionLabel": "Stop Cue"},
        },
        "toggle_audio_cue": {
            "label": "Toggle Audio Cue",
            "params": ["cueId", "playMode"],
            "targetSource": "audio.cues",
            "ui": {"module": "audio", "pathKey": "audio_toggle", "actionLabel": "Toggle Cue"},
        },
        "media_play_scene": {
            "label": "Play Media Scene",
            "params": ["sceneId"],
            "targetSource": "media.scenes",
            "ui": {"module": "media", "pathKey": "media_play", "actionLabel": "Play Scene"},
        },
        "media_stop_scene": {
            "label": "Stop Media Scene",
            "params": ["sceneId"],
            "targetSource": "media.scenes",
            "ui": {"module": "media", "pathKey": "media_stop", "actionLabel": "Stop Scene"},
        },
        "media_stop_all": {
            "label": "Stop All Media",
            "params": [],
            "ui": {"module": "media", "pathKey": "media_stop_all", "actionLabel": "Stop All Media"},
        },
        "led_pattern": {"label": "LED Pattern", "params": ["group", "pattern", "durationMs"], "planned": True},
        "delay": {
            "label": "Delay",
            "params": ["durationMs"],
            "planned": True,
            "ui": {"module": "system", "pathKey": "system_delay", "actionLabel": "Delay"},
        },
    },
}

TAG_PALETTE = ["#5b9bd5", "#70ad47", "#ed7d31", "#ffc000", "#4472c4", "#a5a5a5"]
_last_rules_sync_log_at: float | None = None


def _compact_runtime_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Reduce rules to runtime fields required by ESP SET_RULES."""
    mapping_rows = _load_mapping_rows()
    canonical_by_tail: Dict[str, str] = {}
    for key in mapping_rows.keys():
        sid = str(key or "").strip()
        if not sid:
            continue
        idx = sid.find("__")
        tail = sid[idx + 2:] if idx >= 0 else sid
        if tail and tail not in canonical_by_tail:
            canonical_by_tail[tail] = sid

    def _canon_hardware_uid(raw: Any) -> str:
        sid = str(raw or "").strip()
        if not sid:
            return sid
        if sid in mapping_rows:
            return sid
        idx = sid.find("__")
        tail = sid[idx + 2:] if idx >= 0 else sid
        return canonical_by_tail.get(tail, sid)

    compacted: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        out_rule: Dict[str, Any] = {
            "enabled": bool(rule.get("enabled", True)),
            "triggerGroups": {"logic": "ALL", "groups": []},
            "actions": [],
        }

        trigger_groups = rule.get("triggerGroups") if isinstance(rule.get("triggerGroups"), dict) else {}
        tg_logic = str(trigger_groups.get("logic") or "ALL").strip().upper()
        out_rule["triggerGroups"]["logic"] = "ANY" if tg_logic == "ANY" else "ALL"
        groups = trigger_groups.get("groups") if isinstance(trigger_groups.get("groups"), list) else []
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_logic = str(group.get("logic") or "ALL").strip().upper()
            out_group: Dict[str, Any] = {
                "logic": "ANY" if group_logic == "ANY" else "ALL",
                "windowMs": 750,
                "items": [],
            }
            try:
                out_group["windowMs"] = max(50, int(group.get("windowMs", 750)))
            except Exception:
                out_group["windowMs"] = 750
            items = group.get("items") if isinstance(group.get("items"), list) else []
            for trig in items:
                if not isinstance(trig, dict):
                    continue
                trig_type = str(trig.get("type") or "").strip().lower()
                trig_event = str(trig.get("event") or "").strip()
                trig_source = str(trig.get("source") or "").strip()
                trig_fn = str(trig.get("fn") or "").strip().upper()
                trig_params = trig.get("params") if isinstance(trig.get("params"), dict) else {}
                out_trig: Dict[str, Any] = {
                    "type": trig_type,
                    "event": trig_event,
                    "source": _canon_hardware_uid(trig_source) if trig_type == "hardware" else trig_source,
                    "fn": trig_fn,
                }
                if trig_params:
                    out_trig["params"] = trig_params
                out_group["items"].append(out_trig)
            if out_group["items"]:
                out_rule["triggerGroups"]["groups"].append(out_group)

        actions = rule.get("actions") if isinstance(rule.get("actions"), list) else []
        for action in actions:
            if not isinstance(action, dict):
                continue
            action_type = str(action.get("type") or "").strip().lower()
            target = str(action.get("target") or "").strip()
            params = action.get("params") if isinstance(action.get("params"), dict) else {}
            out_action: Dict[str, Any] = {"type": action_type}
            if target:
                out_action["target"] = _canon_hardware_uid(target)

            out_params: Dict[str, Any] = {}
            if action_type == "set_output":
                value = str(params.get("value") or params.get("state") or "").strip().upper()
                if value:
                    out_params["value"] = value
                device = str(params.get("device") or "").strip()
                if device:
                    out_params["device"] = _canon_hardware_uid(device)
            elif action_type == "pulse":
                duration = params.get("durationMs", params.get("ms", params.get("pulseMs", 30)))
                try:
                    out_params["durationMs"] = max(1, int(duration))
                except Exception:
                    out_params["durationMs"] = 30
                value = str(params.get("value") or "").strip().upper()
                if value:
                    out_params["value"] = value
                device = str(params.get("device") or "").strip()
                if device:
                    out_params["device"] = _canon_hardware_uid(device)
            elif action_type == "set_lcd_text":
                # Execute LCD text actions in Pi runtime only so placeholders
                # (e.g. [IP_ADDRESS], [SCORE]) resolve dynamically once.
                # Avoid mirroring to ESP runtime to prevent stale/literal writes.
                continue
            else:
                continue

            if out_params:
                out_action["params"] = out_params
            out_rule["actions"].append(out_action)

        compacted.append(out_rule)
    return compacted


def _push_runtime_rules(rules: List[Dict[str, Any]], timeout_s: float = 5.0) -> tuple[bool, str | None]:
    """Push runtime rules to ESP and wait for RULES_STATUS ack."""
    runtime_rules = _compact_runtime_rules(rules)
    try:
        payload = bridge_rpc_command({"cmd": "SET_RULES", "rules": runtime_rules}, match_t="RULES_STATUS", timeout_s=timeout_s)
    except Exception as exc:
        return False, str(exc)
    if not isinstance(payload, dict):
        return False, "no_rules_status"
    if str(payload.get("status") or "").strip().lower() != "ok":
        return False, str(payload.get("reason") or payload.get("error") or "rules_status_error")
    return True, None

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


_BUTTON_GESTURE_FNS = {
    "PRESSED",
    "RELEASED",
    "CLICKED",
    "DOUBLE_CLICKED",
    "HELD",
    "REPEAT_WHILE_HELD",
}

_BUTTON_GESTURE_SUFFIXES = (
    "_N_DOUBLE_CLICKED",
    "_DOUBLE_CLICKED",
    "_REPEAT_WHILE_HELD",
    "_CLICKED",
    "_RELEASED",
    "_HELD",
    "_PRESSED",
)


def _normalize_event_name(raw: Any) -> str:
    s = str(raw or "").upper()
    out = []
    prev_us = False
    for ch in s:
        if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    while out and out[0] == "_":
        out.pop(0)
    while out and out[-1] == "_":
        out.pop()
    return "".join(out)


def _strip_button_suffixes(event_name: str) -> str:
    ev = _normalize_event_name(event_name)
    if not ev:
        return ""
    for suffix in _BUTTON_GESTURE_SUFFIXES:
        if ev.endswith(suffix):
            ev = ev[: -len(suffix)]
            break
    if ev.endswith("_N"):
        ev = ev[:-2]
    return ev


def _hardware_map_by_id() -> Dict[str, Dict[str, str]]:
    data = _load_mapping_rows()
    if not isinstance(data, dict):
        return {}

    out: Dict[str, Dict[str, str]] = {}
    for uid, row in data.items():
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        friendly = str(row.get("friendly") or "").strip()
        base = _normalize_event_name(friendly) or _normalize_event_name(uid)
        if base.endswith("_N"):
            base = base[:-2]
        out[str(uid)] = {
            "function": fn,
            "base": base,
        }
    return out


def _load_mapping_rows() -> Dict[str, Any]:
    mapping_path = Path(current_app.instance_path) / "hardware" / "mapping.json"
    if not mapping_path.exists():
        return {}
    try:
        raw = json.loads(mapping_path.read_text(encoding="utf-8"))
        data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _parse_gpio_pin(uid: str) -> int | None:
    parts = str(uid or "").split("__")
    if len(parts) < 4:
        return None
    if parts[-2] != "GPIO":
        return None
    chan = str(parts[-1] or "").strip()
    if not chan.isdigit():
        return None
    try:
        pin = int(chan)
    except Exception:
        return None
    return pin if pin >= 0 else None


def _build_hardware_devices(mapping_data: Dict[str, Any]) -> tuple[list[dict], Dict[str, Dict[str, Any]]]:
    function_map = {
        "Button": ("button", "input"),
        "Switch": ("switch", "input"),
        "Accelerometer": ("gyro", "input"),
        "NFC": ("nfc", "input"),
        "Solenoid": ("coil", "output"),
        "Coil": ("coil", "output"),
        "LED": ("output", "output"),
        "RGB Strip": ("led", "output"),
    }
    devices: list[dict] = []
    lcd_by_id: Dict[str, Dict[str, Any]] = {}
    lcd_groups: Dict[str, list[dict]] = {}

    for uid, row in mapping_data.items():
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        if not fn:
            continue
        friendly = str(row.get("friendly") or "").strip() or str(uid)
        if fn in ("LCD Display", "LCD1602"):
            comp_id = str(row.get("componentId") or "").strip()
            role = str(row.get("componentRole") or "").strip().upper()
            if not comp_id or role not in ("SDA", "SCL"):
                continue
            lcd_groups.setdefault(comp_id, []).append(
                {
                    "uid": str(uid),
                    "friendly": friendly,
                    "role": role,
                    "pin": _parse_gpio_pin(str(uid)),
                    "address": str(row.get("i2cAddress") or "0x27").strip() or "0x27",
                    "cols": row.get("lcdCols", 16),
                    "rows": row.get("lcdRows", 2),
                    "driver": str(row.get("driver") or "Default").strip() or "Default",
                }
            )
            continue

        device_class, direction = function_map.get(fn, ("other", "unknown"))
        devices.append({
            "id": str(uid),
            "friendly": friendly,
            "function": fn,
            "deviceClass": device_class,
            "direction": direction,
            "eventBase": (_normalize_event_name(friendly) or _normalize_event_name(uid)).removesuffix("_N"),
        })

    for comp_id, rows in lcd_groups.items():
        if len(rows) < 2:
            continue
        sda = next((r for r in rows if r.get("role") == "SDA"), None)
        scl = next((r for r in rows if r.get("role") == "SCL"), None)
        if not sda or not scl:
            continue
        sda_pin = sda.get("pin")
        scl_pin = scl.get("pin")
        if not isinstance(sda_pin, int) or not isinstance(scl_pin, int):
            continue
        if sda_pin == scl_pin:
            continue
        address_raw = str(sda.get("address") or scl.get("address") or "0x27").strip() or "0x27"
        try:
            address_val = int(address_raw, 0)
        except Exception:
            address_val = 0x27
        if address_val < 0x03 or address_val > 0x77:
            address_val = 0x27
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
        friendly = next((str(r.get("friendly") or "").strip() for r in rows if str(r.get("friendly") or "").strip()), comp_id)
        did = f"LCD_DISPLAY::{comp_id}"
        entry = {
            "id": did,
            "friendly": friendly,
            "function": "LCD Display",
            "deviceClass": "lcd",
            "direction": "display",
            "eventBase": (_normalize_event_name(friendly) or _normalize_event_name(comp_id)).removesuffix("_N"),
            "config": {
                "componentId": comp_id,
                "sdaPin": sda_pin,
                "sclPin": scl_pin,
                "address": f"0x{address_val:02x}",
                "cols": cols,
                "rows": rows_count,
                "driver": str(sda.get("driver") or scl.get("driver") or "Default").strip() or "Default",
                "sdaUid": str(sda.get("uid") or ""),
                "sclUid": str(scl.get("uid") or ""),
            },
        }
        devices.append(entry)
        lcd_by_id[did] = entry["config"]

    devices.sort(key=lambda d: str(d.get("friendly") or d.get("id") or "").lower())
    return devices, lcd_by_id


def _canonical_hardware_trigger_event(source: str, trig_event: str, trig_fn: str, hw_map: Dict[str, Dict[str, str]]) -> str:
    fn_key = str(trig_fn or "").strip().upper()
    if fn_key not in _BUTTON_GESTURE_FNS:
        return _normalize_event_name(trig_event)

    base = _strip_button_suffixes(trig_event)
    if not base:
        base = str((hw_map.get(source) or {}).get("base") or "").strip()
    if not base:
        base = _normalize_event_name(source)
    if not base:
        return "HARDWARE_PRESSED"
    return f"{base}_PRESSED"

def _normalize_rules(rules):
    hw_map = _hardware_map_by_id()
    _, lcd_devices = _build_hardware_devices(_load_mapping_rows())
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

        trigger_items: List[Dict[str, Any]] = []
        trigger_items.extend([t for t in (rule.get("triggers", []) or []) if isinstance(t, dict)])
        for group in trigger_groups["groups"]:
            if not isinstance(group, dict):
                continue
            trigger_items.extend([t for t in (group.get("items") or []) if isinstance(t, dict)])

        for trig in trigger_items:
            if not isinstance(trig, dict):
                continue
            ttype = trig.get("type")
            if ttype in ("game", "gameplay"):
                trig["type"] = "system"
            if trig.get("type") == "hardware":
                source = str(trig.get("source") or "").strip()
                fn = str(trig.get("fn") or "").strip().upper()
                trig["fn"] = fn
                trig["event"] = _canonical_hardware_trigger_event(
                    source=source,
                    trig_event=str(trig.get("event") or "").strip(),
                    trig_fn=fn,
                    hw_map=hw_map,
                )

        for action in rule.get("actions", []) or []:
            if not isinstance(action, dict):
                continue
            params = action.get("params") if isinstance(action.get("params"), dict) else {}
            action["params"] = params
            action_type = str(action.get("type") or "").strip()
            action_type_key = "".join(ch for ch in action_type.lower() if ch.isalnum())
            if action_type_key == "pulsecoil":
                action["type"] = "pulse"
                ms = params.get("durationMs", params.get("ms", params.get("pulseMs", 30)))
                try:
                    ms_val = int(ms)
                except Exception:
                    ms_val = 30
                if ms_val < 1:
                    ms_val = 1
                params["durationMs"] = ms_val
                params.pop("ms", None)
                params.pop("pulseMs", None)
                action_type = "pulse"
            if action_type == "set_output" and str(params.get("value") or "").strip().upper() == "PULSE":
                action["type"] = "pulse"
                ms = params.get("durationMs", params.get("pulseMs", params.get("ms", 30)))
                try:
                    ms_val = int(ms)
                except Exception:
                    ms_val = 30
                if ms_val < 1:
                    ms_val = 1
                action["params"] = {
                    "durationMs": ms_val,
                }
                action_type = "pulse"
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
            if action_type == "set_lcd_text":
                target = str(
                    params.get("device")
                    or params.get("lcdId")
                    or action.get("target")
                    or ""
                ).strip()
                action["target"] = target
                params["device"] = target
                params["lcdId"] = target
                params["line1"] = str(params.get("line1") or "").strip()
                params["line2"] = str(params.get("line2") or "").strip()
                clear_first_raw = params.get("clearFirst", False)
                if isinstance(clear_first_raw, str):
                    params["clearFirst"] = clear_first_raw.strip().lower() in ("1", "true", "yes", "on")
                else:
                    params["clearFirst"] = bool(clear_first_raw)
                cfg = lcd_devices.get(target) if target else None
                if isinstance(cfg, dict):
                    params["sdaPin"] = int(cfg.get("sdaPin", 0))
                    params["sclPin"] = int(cfg.get("sclPin", 0))
                    params["address"] = str(cfg.get("address") or "0x27")
                    params["cols"] = int(cfg.get("cols", 16))
                    params["rows"] = int(cfg.get("rows", 2))
                    params["driver"] = str(cfg.get("driver") or "Default")
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
    runtime_push = {"ok": False, "error": "bridge_not_connected"}
    try:
        st = read_bridge_state()
        if st.get("connected") and st.get("port"):
            ok, err = _push_runtime_rules(normalized, timeout_s=5.0)
            runtime_push = {"ok": bool(ok), "error": err}
            if not ok:
                # Fall back to queued command so runtime may still update asynchronously.
                enqueue_command({"cmd": "SET_RULES", "rules": _compact_runtime_rules(normalized)})
                current_app.logger.warning("SET_RULES RPC failed on save; queued fallback: %s", err)
        else:
            runtime_push = {"ok": False, "error": "bridge_not_connected"}
    except Exception:
        current_app.logger.exception("Failed to push runtime rules on save")
    return jsonify({"ok": True, "ts": datetime.now(timezone.utc).isoformat(), "runtimePush": runtime_push})

@api_bp.get("/hardware")
def api_rules_hardware():
    """Return mapped hardware devices for rules selectors."""
    data = _load_mapping_rows()
    devices, _ = _build_hardware_devices(data)
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

    ok, err = _push_runtime_rules(normalized, timeout_s=6.0)
    if not ok:
        current_app.logger.error("SET_RULES RPC failed during rules sync: %s", err)
        return jsonify({"ok": False, "error": "set_rules_failed", "detail": err}), 409

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
