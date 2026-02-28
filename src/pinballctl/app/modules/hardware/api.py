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
    "LCD Display": {
        "notes": "I2C character LCD (2-line, HD44780 via backpack).",
    },
}


def _drivers_catalog_path() -> Path:
    """Path to drivers.json used by hardware driver dropdown/validation."""
    return Path(__file__).resolve().parent / "drivers.json"


def _load_driver_catalog() -> Dict[str, List[str]]:
    """Load function->drivers map from drivers.json with safe defaults."""
    data: Dict[str, List[str]] = {}
    p = _drivers_catalog_path()
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for fn, vals in raw.items():
                    if not isinstance(fn, str):
                        continue
                    if not isinstance(vals, list):
                        continue
                    options = [str(v).strip() for v in vals if str(v).strip()]
                    if options:
                        data[fn] = options
        except Exception:
            data = {}
    if not data:
        data = {}
    if "*" not in data or not isinstance(data.get("*"), list) or not data.get("*"):
        data["*"] = ["Default"]
    return data


def _normalize_driver_name(fn: str, driver: str) -> str:
    """Normalize legacy driver aliases to current catalog names."""
    function_name = str(fn or "").strip()
    value = str(driver or "").strip() or "Default"
    if function_name in ("LCD Display", "LCD1602"):
        if value.lower() in ("", "default", "leddisplay1602", "lcd1602", "lcd1602i2c"):
            return "LCD1602I2C"
    return value

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

def _uid_tail(uid: str) -> str:
    """Stable UID tail key: BOARD__TYPE__CHAN."""
    parts = str(uid or "").split("__")
    if len(parts) < 4:
        return str(uid or "")
    return "__".join(parts[-3:])


def _parse_gpio_pin_from_uid(uid: str) -> int | None:
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
    if pin < 0:
        return None
    return pin


def _remap_mapping_to_current_pins(mapping: Dict[str, Any], pins: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Carry mapping rows across controller-id/UID prefix changes by matching UID tail."""
    if not isinstance(mapping, dict):
        return {}
    by_uid = {str(k): v for k, v in mapping.items() if isinstance(v, dict)}
    by_tail: Dict[str, Dict[str, Any]] = {}
    for uid, row in by_uid.items():
        tail = _uid_tail(uid)
        if tail and tail not in by_tail:
            by_tail[tail] = row

    remapped: Dict[str, Any] = {}
    for pin in pins:
        uid = str((pin or {}).get("uid") or "")
        if not uid:
            continue
        tail = _uid_tail(uid)
        row = by_uid.get(uid) or by_tail.get(tail)
        if isinstance(row, dict):
            remapped[uid] = dict(row)
    return remapped

# -----------------------------------------------------------------------------
# API endpoints
# -----------------------------------------------------------------------------
@api_bp.get("/meta")
def meta():
    """Return supported functions metadata for the UI."""
    drivers = _load_driver_catalog()
    return jsonify({
        "functions": list(FUNCTION_META.keys()),
        "drivers": drivers,
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

    pins = get_discovered_pins()
    remapped = _remap_mapping_to_current_pins(mapping, pins)
    return jsonify(remapped)

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
    pins = pin_payload["pins"]
    valid_uids = {p["uid"] for p in pins}
    valid_functions = set(FUNCTION_META.keys()) | {"LCD1602"}
    drivers_catalog = _load_driver_catalog()
    valid_drivers_by_fn = {
        fn: set(str(v) for v in vals)
        for fn, vals in drivers_catalog.items()
        if isinstance(vals, list) and vals
    }
    valid_safety = {"HIGH", "LOW"}
    valid_lcd_roles = {"SDA", "SCL"}

    # Normalize incoming keys to current discovered UIDs before validation.
    data = _remap_mapping_to_current_pins(data, pins)

    # PRUNE unknown UIDs first (be forgiving with legacy keys)
    pruned_count = 0
    for uid in list(data.keys()):
        if uid not in valid_uids:
            del data[uid]
            pruned_count += 1

    # Validate remaining entries
    lcd_groups: Dict[str, List[Dict[str, Any]]] = {}
    for uid, row in data.items():
        if not isinstance(row, dict):
            errors.append({"uid": uid, "field": "*", "error": "invalid_row"})
            continue

        friendly = (row.get("friendly") or "").strip()
        func = (row.get("function") or "").strip()
        safety = (row.get("safety") or "").strip().upper()
        driver = _normalize_driver_name(func, row.get("driver"))

        if len(friendly) > 64:
            errors.append({"uid": uid, "field": "friendly", "error": "too_long"})

        if func == "LCD1602":
            func = "LCD Display"
        if func and func not in valid_functions:
            errors.append({"uid": uid, "field": "function", "error": "unknown_function"})

        if safety and safety not in valid_safety:
            errors.append({"uid": uid, "field": "safety", "error": "invalid_value"})
        allowed_drivers = valid_drivers_by_fn.get(func, set(valid_drivers_by_fn.get("*", {"Default"}))) if func else set(valid_drivers_by_fn.get("*", {"Default"}))
        if driver not in allowed_drivers:
            errors.append({"uid": uid, "field": "driver", "error": "invalid_value"})
            driver = "Default"

        # Normalize back
        row["friendly"] = friendly
        row["function"] = func
        row["driver"] = driver
        row["safety"] = safety if safety in valid_safety else ""
        row.pop("purpose", None)
        if func != "LCD Display":
            row.pop("componentId", None)
            row.pop("componentRole", None)
            row.pop("secondaryPinUid", None)
            row.pop("linkedPrimaryUid", None)
            row.pop("i2cAddress", None)
            row.pop("lcdCols", None)
            row.pop("lcdRows", None)
        else:
            comp_id = str(row.get("componentId") or "").strip()
            role = str(row.get("componentRole") or "").strip().upper()
            addr_raw = str(row.get("i2cAddress") or "").strip() or "0x27"
            cols_raw = row.get("lcdCols", 16)
            rows_raw = row.get("lcdRows", 2)
            pin = _parse_gpio_pin_from_uid(uid)
            if pin is None:
                errors.append({"uid": uid, "field": "function", "error": "lcd_requires_gpio"})
            if not comp_id:
                linked_primary = str(row.get("linkedPrimaryUid") or "").strip()
                base_uid = linked_primary or uid
                comp_id = f"lcd-{_uid_tail(base_uid).lower().replace('__', '-')}"
            if role not in valid_lcd_roles:
                errors.append({"uid": uid, "field": "componentRole", "error": "invalid_value"})
            try:
                addr_val = int(addr_raw, 0)
            except Exception:
                addr_val = -1
            if addr_val < 0x03 or addr_val > 0x77:
                errors.append({"uid": uid, "field": "i2cAddress", "error": "invalid_i2c_address"})
            try:
                cols_val = int(cols_raw)
            except Exception:
                cols_val = 16
            if cols_val < 8 or cols_val > 40:
                errors.append({"uid": uid, "field": "lcdCols", "error": "invalid_value"})
            try:
                rows_val = int(rows_raw)
            except Exception:
                rows_val = 2
            if rows_val < 1 or rows_val > 4:
                errors.append({"uid": uid, "field": "lcdRows", "error": "invalid_value"})
            row["componentId"] = comp_id
            row["componentRole"] = role
            row["secondaryPinUid"] = str(row.get("secondaryPinUid") or "").strip()
            row["linkedPrimaryUid"] = str(row.get("linkedPrimaryUid") or "").strip()
            row["i2cAddress"] = f"0x{max(0, addr_val):02x}" if addr_val >= 0 else "0x27"
            row["lcdCols"] = max(8, min(40, cols_val))
            row["lcdRows"] = max(1, min(4, rows_val))
            if comp_id:
                lcd_groups.setdefault(comp_id, []).append(
                    {
                        "uid": uid,
                        "pin": pin,
                        "role": role,
                        "addr": row["i2cAddress"],
                        "cols": row["lcdCols"],
                        "rows": row["lcdRows"],
                        "driver": _normalize_driver_name(func, row.get("driver")),
                    }
                )
        if isinstance(existing_map.get(uid), dict):
            # Preserve physical metadata fields authored outside hardware UI.
            if "pixelCount" in existing_map[uid] and "pixelCount" not in row:
                row["pixelCount"] = existing_map[uid].get("pixelCount")

    for comp_id, rows in lcd_groups.items():
        if len(rows) != 2:
            errors.append({"uid": comp_id, "field": "componentId", "error": "lcd_pair_requires_two_pins"})
            continue
        roles = {str(r.get("role") or "") for r in rows}
        if roles != valid_lcd_roles:
            errors.append({"uid": comp_id, "field": "componentRole", "error": "lcd_pair_requires_sda_scl"})
        pins = [r.get("pin") for r in rows]
        if pins[0] is None or pins[1] is None or pins[0] == pins[1]:
            errors.append({"uid": comp_id, "field": "componentId", "error": "lcd_pair_invalid_pins"})
        addrs = {str(r.get("addr") or "") for r in rows}
        if len(addrs) != 1:
            errors.append({"uid": comp_id, "field": "i2cAddress", "error": "lcd_pair_mismatch"})
        cols = {int(r.get("cols") or 0) for r in rows}
        rows_set = {int(r.get("rows") or 0) for r in rows}
        if len(cols) != 1:
            errors.append({"uid": comp_id, "field": "lcdCols", "error": "lcd_pair_mismatch"})
        if len(rows_set) != 1:
            errors.append({"uid": comp_id, "field": "lcdRows", "error": "lcd_pair_mismatch"})
        drivers = {str(r.get("driver") or "Default").strip() or "Default" for r in rows}
        if len(drivers) != 1:
            errors.append({"uid": comp_id, "field": "driver", "error": "lcd_pair_mismatch"})

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
            mapping_json_path = Path(current_app.instance_path) / "hardware" / "mapping.json"
            if path.exists():
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                source_hash = ""
                if mapping_json_path.exists():
                    source_hash = hashlib.sha256(mapping_json_path.read_bytes()).hexdigest()
                update_sync_state(current_app.instance_path, "hardware", sha, extra={"sourceHash": source_hash})
        except Exception:
            current_app.logger.exception("Failed to update hardware sync state")
    return jsonify({
        "blob_status": status,
        "blob_at": st.get("blob_at"),
        "bridge": {"connected": st.get("connected"), "port": st.get("port")},
    })
