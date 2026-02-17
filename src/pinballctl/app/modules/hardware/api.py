"""API for hardware discovery/mapping; stores state in the Flask instance dir."""
# File: hardware/api.py
import json, time, hashlib
from datetime import datetime, timezone
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

from flask import request, jsonify, current_app
from pinballctl.bridge.state import queue_blob_put, read_state as read_bridge_state, enqueue_command
from pinballctl.ops.mapping_blob import build_mapping_pb
from pinballctl.app.sync_state import update_sync_state
from . import api_bp

# -----------------------------------------------------------------------------
# Storage paths
# -----------------------------------------------------------------------------
def _store_dir() -> Path:
    """Return/create the instance subdir used to persist hardware data."""
    p = Path(current_app.instance_path) / "hardware"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _mapping_path() -> Path:
    """Path to the mapping.json written by mapping_save."""
    return _store_dir() / "mapping.json"

def _discovered_path() -> Path:
    """Path to the discovered.json persisted by reload_pins."""
    return _store_dir() / "discovered.json"

# -----------------------------------------------------------------------------
# Function catalog (server-driven linked selects)
# -----------------------------------------------------------------------------
FUNCTION_META = {
    "Button": {
        "notes": "Debounced input handled on ESP.",
    },
    "LED": {
        "notes": "Single on/off output.",
    },
    "Solenoid": {
        "notes": "Fire + hold logic / safety on ESP.",
    },
    "RGB Strip": {
        "notes": "Addressable LEDs (FastLED on ESP).",
    },
    "Accelerometer": {
        "notes": "Used by Gyro class / DMP.",
    },
}

# -----------------------------------------------------------------------------
# Default mock set (UID format: <CTRL>__<BOARD>__<TYPE>__<CHAN>)
# -----------------------------------------------------------------------------
CTRL_ID = "ESP_A1B2C3"

DEFAULT_PINS = [
    # On-chip GPIOs
    {"uid": f"{CTRL_ID}__MAIN__GPIO__1",  "board": "MAIN", "type": "GPIO", "chan": "1",  "reported": "DIGITAL_IN"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__2",  "board": "MAIN", "type": "GPIO", "chan": "2",  "reported": "DIGITAL_IN"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__3",  "board": "MAIN", "type": "GPIO", "chan": "3",  "reported": "DIGITAL_IN"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__10", "board": "MAIN", "type": "GPIO", "chan": "10", "reported": "DRIVE_COIL"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__11", "board": "MAIN", "type": "GPIO", "chan": "11", "reported": "DRIVE_COIL"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__12", "board": "MAIN", "type": "GPIO", "chan": "12", "reported": "DRIVE_COIL"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__13", "board": "MAIN", "type": "GPIO", "chan": "13", "reported": "DRIVE_COIL"},
    {"uid": f"{CTRL_ID}__MAIN__GPIO__21", "board": "MAIN", "type": "GPIO", "chan": "21", "reported": "DIGITAL_OUT"},

    # Expansion board on I2C0 @ address 0x20 (MCP23017)
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR20__MCP23017__A0", "board": "EXP_I2C0_ADDR20", "type": "MCP23017", "chan": "A0", "reported": "DIGITAL_OUT"},
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR20__MCP23017__A1", "board": "EXP_I2C0_ADDR20", "type": "MCP23017", "chan": "A1", "reported": "DIGITAL_OUT"},
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR20__MCP23017__B0", "board": "EXP_I2C0_ADDR20", "type": "MCP23017", "chan": "B0", "reported": "DIGITAL_IN"},
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR20__MCP23017__B1", "board": "EXP_I2C0_ADDR20", "type": "MCP23017", "chan": "B1", "reported": "DIGITAL_IN"},

    # Expansion board on I2C0 @ address 0x30 (LED strip driver)
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR30__NEO__DIN6", "board": "EXP_I2C0_ADDR30", "type": "NEO", "chan": "DIN6", "reported": "NEOPIXEL"},
    {"uid": f"{CTRL_ID}__EXP_I2C0_ADDR30__NEO__DIN7", "board": "EXP_I2C0_ADDR30", "type": "NEO", "chan": "DIN7", "reported": "NEOPIXEL"},

    # I2C peripherals
    {"uid": f"{CTRL_ID}__MAIN__I2CDEV__0x68", "board": "MAIN", "type": "I2CDEV", "chan": "0x68", "reported": "I2C_DEVICE"},
]

# -----------------------------------------------------------------------------
# Single source of truth for discovered pins/payload
# -----------------------------------------------------------------------------
def _load_discovered_payload() -> Dict[str, Any]:
    """Load discovered pin data if present; otherwise return empty."""
    p = _discovered_path()
    if p.exists():
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict) and isinstance(data.get("pins"), list):
                return {
                    "controller": data.get("controller") or CTRL_ID,
                    "pins": data["pins"],
                    "reloadedAt": data.get("reloadedAt"),
                    "usingDefaults": data.get("usingDefaults", False),
                    "source": data.get("source"),
                }
            if isinstance(data, list):
                return {"controller": CTRL_ID, "pins": data, "reloadedAt": None, "usingDefaults": False, "source": None}
        except Exception:
            pass
    return {"controller": None, "pins": [], "reloadedAt": None, "usingDefaults": False, "source": None}


def _refresh_from_bridge(timeout_sec: float = 6.0) -> bool:
    """
    Ask the bridge/ESP for hardware (GET_HW) and wait briefly for the
    discovered.json snapshot to update. Returns True if fresh data arrived.
    """
    path = _discovered_path()
    start_mtime = path.stat().st_mtime if path.exists() else 0
    try:
        enqueue_command({"cmd": "GET_HW"})
    except Exception:
        return False

    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if path.exists() and path.stat().st_mtime > start_mtime:
            try:
                data = json.loads(path.read_text())
                if isinstance(data, dict):
                    pins = data.get("pins") or []
                    if isinstance(pins, list) and pins:
                        return True
            except Exception:
                pass
        time.sleep(0.1)
    return False

def get_discovered_pins():
    """Convenience wrapper to return just the pins list."""
    return _load_discovered_payload()["pins"]

# -----------------------------------------------------------------------------
# API endpoints
# -----------------------------------------------------------------------------
@api_bp.get("/meta")
def meta():
    """Return supported functions metadata for the UI."""
    return jsonify({
        "functions": list(FUNCTION_META.keys()),
    })

@api_bp.get("/pins")
def pins():
    """Return discovered pins and controller metadata."""
    refresh = request.args.get("refresh") in ("1", "true", "yes")
    if refresh:
        _refresh_from_bridge()
    payload = _load_discovered_payload()
    return jsonify({
        "controller": payload["controller"],
        "pins": payload["pins"],
        "reloadedAt": payload["reloadedAt"],
        "usingDefaults": payload.get("usingDefaults", False),
        "source": payload.get("source"),
    })

@api_bp.post("/reload")
def reload_pins():
    """Regenerate the discovered pins set by querying the ESP (bridge)."""
    source = request.args.get("source", "esp")
    prev = set(u.get("uid") for u in get_discovered_pins())
    # Attempt to refresh from ESP via bridge; fall back to defaults
    refreshed = False
    if source != "mock":
        refreshed = _refresh_from_bridge()
        # Wait briefly for bridge to write discovered.json
        waited = 0.0
        path = _discovered_path()
        start_mtime = path.stat().st_mtime if path.exists() else 0
        while waited < 6.0:
            time.sleep(0.1)
            waited += 0.1
            if path.exists() and path.stat().st_mtime > start_mtime:
                break
    payload = _load_discovered_payload()
    # Normalize payload metadata before persisting/returning
    payload["reloadedAt"] = payload.get("reloadedAt") or datetime.now(timezone.utc).isoformat()
    payload["usingDefaults"] = payload.get("usingDefaults", False)
    payload["source"] = payload.get("source") or ("esp" if refreshed else source)
    new_pins = payload["pins"] if isinstance(payload.get("pins"), list) else []
    new = set(u.get("uid") for u in new_pins)

    added = sorted(list(new - prev))
    removed = sorted(list(prev - new))
    unchanged = len(new & prev)

    payload = {
        "controller": payload.get("controller") or CTRL_ID,
        "pins": new_pins,
        "source": source,
        "count": len(new_pins),
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "reloadedAt": payload.get("reloadedAt"),
        "usingDefaults": payload.get("usingDefaults", False),
        "refreshed": refreshed,
        "source": payload.get("source"),
    }
    try:
        _discovered_path().write_text(json.dumps(payload, indent=2))
    except Exception:
        payload["persist"] = "failed"
    return jsonify(payload)

@api_bp.get("/mapping")
def mapping_get():
    """
    Return the current mapping dict, but PRUNE any entries whose UIDs
    no longer exist in the discovered pin set (avoids legacy UID errors).
    """
    p = _mapping_path()
    mapping = {}
    if p.exists():
        try:
            raw = json.loads(p.read_text())
            # unwrap envelope if present
            data = raw.get("data") if isinstance(raw, dict) and "data" in raw else raw
            if isinstance(data, dict):
                mapping = data
        except Exception:
            pass

    valid = {pin["uid"] for pin in get_discovered_pins()}
    pruned = {uid: row for uid, row in mapping.items() if uid in valid}
    return jsonify(pruned)

@api_bp.post("/save")
def mapping_save():
    """
    Save mapping with validation. Unknown UIDs are PRUNED (not an error).
    Returns { ok: true, updatedAt, pruned: N } on success,
    or { ok: false, errors: [...] } with 422 on validation issues.
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400

    existing_raw = {}
    mp = _mapping_path()
    if mp.exists():
        try:
            existing_raw = json.loads(mp.read_text())
        except Exception:
            existing_raw = {}
    existing_map = existing_raw.get("data") if isinstance(existing_raw, dict) and isinstance(existing_raw.get("data"), dict) else (existing_raw if isinstance(existing_raw, dict) else {})

    errors = []
    pin_payload = _load_discovered_payload()
    valid_uids = {p["uid"] for p in pin_payload["pins"]}
    valid_functions = set(FUNCTION_META.keys())
    valid_safety = {"HIGH", "LOW"}

    # PRUNE unknown UIDs first (be forgiving with legacy keys)
    pruned_count = 0
    for uid in list(data.keys()):
        if uid not in valid_uids:
            del data[uid]
            pruned_count += 1

    # Validate remaining entries
    for uid, row in data.items():
        if not isinstance(row, dict):
            errors.append({"uid": uid, "field": "*", "error": "invalid_row"})
            continue

        friendly = (row.get("friendly") or "").strip()
        func = (row.get("function") or "").strip()
        safety = (row.get("safety") or "").strip().upper()

        if len(friendly) > 64:
            errors.append({"uid": uid, "field": "friendly", "error": "too_long"})

        if func and func not in valid_functions:
            errors.append({"uid": uid, "field": "function", "error": "unknown_function"})

        if safety and safety not in valid_safety:
            errors.append({"uid": uid, "field": "safety", "error": "invalid_value"})

        # Normalize back
        row["friendly"] = friendly
        row["function"] = func
        row["safety"] = safety if safety in valid_safety else ""
        row.pop("purpose", None)
        if isinstance(existing_map.get(uid), dict):
            # Preserve physical metadata fields authored outside hardware UI.
            if "pixelCount" in existing_map[uid] and "pixelCount" not in row:
                row["pixelCount"] = existing_map[uid].get("pixelCount")

    if errors:
        return jsonify({"ok": False, "errors": errors}), 422

    envelope = {
        "_version": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "controller": pin_payload["controller"],
        "data": data,
    }
    try:
        _mapping_path().write_text(json.dumps(envelope, indent=2))
    except Exception:
        return jsonify({"ok": False, "error": "persist_failed"}), 500

    return jsonify({"ok": True, "updatedAt": envelope["updatedAt"], "pruned": pruned_count})


@api_bp.post("/sync")
def mapping_sync():
    """Build mapping.pb and queue a blob transfer to the ESP."""
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
        # Quick reachability check (ECHO) before we start the transfer.
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

    try:
        base = Path(current_app.instance_path) / "hardware"
        mapping_path = base / "mapping.json"
        output_path = base / "mapping.pb"
        result = build_mapping_pb(mapping_path=mapping_path, output_path=output_path)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "missing_mapping"}), 404
    except Exception as e:
        current_app.logger.exception("Failed to build mapping.pb")
        return jsonify({"ok": False, "error": "build_failed"}), 500

    try:
        queue_blob_put("hardware", str(result.output_path), "/cfg/mapping.pb")
    except Exception:
        current_app.logger.exception("Failed to queue blob transfer")
        return jsonify({"ok": False, "error": "queue_failed"}), 500

    return jsonify({
        "ok": True,
        "path": str(result.output_path),
        "count": result.count,
        "payload_len": result.payload_len,
        "payload_crc32": result.payload_crc32,
    })


@api_bp.get("/sync/status")
def mapping_sync_status():
    """Return the latest blob transfer status from the bridge state."""
    st = read_bridge_state()
    status = st.get("blob_status") or {}
    if status.get("state") == "done" and status.get("ok") and status.get("blobType") == "hardware":
        try:
            path = Path(current_app.instance_path) / "hardware" / "mapping.pb"
            if path.exists():
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                update_sync_state(current_app.instance_path, "hardware", sha)
        except Exception:
            current_app.logger.exception("Failed to update hardware sync state")
    return jsonify({
        "blob_status": status,
        "blob_at": st.get("blob_at"),
        "bridge": {"connected": st.get("connected"), "port": st.get("port")},
    })
