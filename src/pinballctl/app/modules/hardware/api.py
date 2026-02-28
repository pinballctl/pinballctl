"""API for hardware discovery/mapping; stores state in the Flask instance dir."""
# File: hardware/api.py
import json, time, hashlib
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

def _drivers_catalog_path() -> Path:
    """Path to drivers.json used by hardware driver dropdown/validation."""
    return Path(__file__).resolve().parent / "drivers.json"


def _default_catalog() -> Dict[str, Any]:
    return {
        "defaults": {"drivers": ["Default"]},
        "functions": {
            "Button": {"notes": "Debounced input handled on ESP.", "drivers": [{"name": "Default"}]},
            "LED": {"notes": "Single on/off output.", "drivers": [{"name": "Default"}]},
            "Coil": {"notes": "Fire + hold logic / safety on ESP.", "drivers": [{"name": "Default"}]},
            "RGB Strip": {"notes": "Addressable LEDs (FastLED on ESP).", "drivers": [{"name": "Default"}]},
            "Accelerometer": {"notes": "Used by Gyro class / DMP.", "drivers": [{"name": "Default"}]},
            "LCD Display": {
                "aliases": ["LCD1602"],
                "notes": "I2C character LCD (HD44780 compatible).",
                "drivers": [{"name": "LCD1602I2C"}],
            },
        },
    }


def _load_driver_catalog() -> Dict[str, Any]:
    """Load and normalize drivers.json into a schema-driven catalog."""
    raw: Dict[str, Any] = {}
    p = _drivers_catalog_path()
    if p.exists():
        try:
            parsed = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw = parsed
        except Exception:
            raw = {}
    if not raw:
        raw = _default_catalog()

    # Legacy format fallback: { "Function": ["Default", ...], "*": ["Default"] }
    if "functions" not in raw:
        fn_map: Dict[str, Any] = {}
        default_drivers = ["Default"]
        for fn, vals in raw.items():
            if not isinstance(fn, str):
                continue
            if fn == "*":
                if isinstance(vals, list):
                    default_drivers = [str(v).strip() for v in vals if str(v).strip()] or ["Default"]
                continue
            if not isinstance(vals, list):
                continue
            drivers = []
            for item in vals:
                name = str(item).strip()
                if name:
                    drivers.append({"name": name})
            if drivers:
                fn_map[fn] = {"notes": "", "drivers": drivers}
        raw = {"defaults": {"drivers": default_drivers}, "functions": fn_map}

    defaults = raw.get("defaults") if isinstance(raw.get("defaults"), dict) else {}
    default_drivers = defaults.get("drivers") if isinstance(defaults.get("drivers"), list) else ["Default"]
    default_drivers = [str(v).strip() for v in default_drivers if str(v).strip()] or ["Default"]

    functions_raw = raw.get("functions") if isinstance(raw.get("functions"), dict) else {}
    functions: Dict[str, Any] = {}
    drivers_by_function: Dict[str, List[str]] = {"*": default_drivers}
    aliases: Dict[str, str] = {"Solenoid": "Coil"}

    for fn_name, fn_cfg in functions_raw.items():
        if not isinstance(fn_name, str):
            continue
        fn_key = fn_name.strip()
        if not fn_key:
            continue
        if not isinstance(fn_cfg, dict):
            fn_cfg = {}
        notes = str(fn_cfg.get("notes") or "").strip()
        aliases_list = []
        if isinstance(fn_cfg.get("aliases"), list):
            aliases_list = [str(v).strip() for v in fn_cfg.get("aliases") if str(v).strip()]
            for a in aliases_list:
                aliases[a] = fn_key

        drivers_raw = fn_cfg.get("drivers") if isinstance(fn_cfg.get("drivers"), list) else []
        drivers: List[Dict[str, Any]] = []
        driver_names: List[str] = []
        for drv in drivers_raw:
            if isinstance(drv, str):
                d = {"name": drv.strip()}
            elif isinstance(drv, dict):
                d = dict(drv)
                d["name"] = str(d.get("name") or "").strip()
            else:
                continue
            if not d["name"]:
                continue
            if d["name"] in driver_names:
                continue
            if "label" in d:
                d["label"] = str(d.get("label") or "").strip() or d["name"]
            if not isinstance(d.get("settings"), list):
                d["settings"] = []
            if not isinstance(d.get("link"), dict):
                d["link"] = {}
            drivers.append(d)
            driver_names.append(d["name"])
        if not driver_names:
            driver_names = list(default_drivers)
            drivers = [{"name": d, "label": d, "settings": [], "link": {}} for d in driver_names]

        functions[fn_key] = {
            "notes": notes,
            "aliases": aliases_list,
            "drivers": drivers,
        }
        drivers_by_function[fn_key] = driver_names

    if not functions:
        fallback = _default_catalog()
        raw = fallback
        functions_raw = raw.get("functions") if isinstance(raw.get("functions"), dict) else {}
        functions = {}
        drivers_by_function = {"*": ["Default"]}
        aliases = {"Solenoid": "Coil", "LCD1602": "LCD Display"}
        for fn_key, fn_cfg in functions_raw.items():
            if not isinstance(fn_cfg, dict):
                continue
            drivers = fn_cfg.get("drivers") if isinstance(fn_cfg.get("drivers"), list) else []
            norm_drivers = []
            driver_names = []
            for drv in drivers:
                if isinstance(drv, dict) and str(drv.get("name") or "").strip():
                    norm_drivers.append(drv)
                    driver_names.append(str(drv.get("name")))
            if not driver_names:
                norm_drivers = [{"name": "Default", "label": "Default", "settings": [], "link": {}}]
                driver_names = ["Default"]
            functions[fn_key] = {
                "notes": str(fn_cfg.get("notes") or ""),
                "aliases": list(fn_cfg.get("aliases") or []),
                "drivers": norm_drivers,
            }
            drivers_by_function[fn_key] = driver_names

    return {
        "defaults": {"drivers": default_drivers},
        "functions": functions,
        "driversByFunction": drivers_by_function,
        "aliases": aliases,
    }


def _canonical_function_name(value: str, catalog: Dict[str, Any]) -> str:
    fn = str(value or "").strip()
    if not fn:
        return ""
    aliases = catalog.get("aliases") if isinstance(catalog.get("aliases"), dict) else {}
    return str(aliases.get(fn) or fn)


def _driver_profile(catalog: Dict[str, Any], function_name: str, driver_name: str) -> Dict[str, Any]:
    fn = _canonical_function_name(function_name, catalog)
    functions = catalog.get("functions") if isinstance(catalog.get("functions"), dict) else {}
    fn_cfg = functions.get(fn) if isinstance(functions.get(fn), dict) else {}
    drivers = fn_cfg.get("drivers") if isinstance(fn_cfg.get("drivers"), list) else []
    requested = str(driver_name or "").strip()
    for drv in drivers:
        if not isinstance(drv, dict):
            continue
        if str(drv.get("name") or "") == requested and requested:
            return drv
    if drivers:
        first = drivers[0]
        if isinstance(first, dict):
            return first
    return {"name": "Default", "settings": [], "link": {}}


def _normalize_driver_name(fn: str, driver: str) -> str:
    """Normalize driver values against catalog defaults for the function."""
    catalog = _load_driver_catalog()
    function_name = _canonical_function_name(fn, catalog)
    value = str(driver or "").strip()
    if not function_name:
        return value or "Default"
    profile = _driver_profile(catalog, function_name, value)
    return str(profile.get("name") or "Default")

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
    catalog = _load_driver_catalog()
    functions_cfg = catalog.get("functions") if isinstance(catalog.get("functions"), dict) else {}
    function_names = list(functions_cfg.keys())
    function_meta = {
        fn: {"notes": str((cfg or {}).get("notes") or "")}
        for fn, cfg in functions_cfg.items()
        if isinstance(cfg, dict)
    }
    return jsonify({
        "functions": function_names,
        "functionMeta": function_meta,
        "drivers": catalog.get("driversByFunction") or {"*": ["Default"]},
        "functionProfiles": functions_cfg,
        "aliases": catalog.get("aliases") or {},
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
    catalog = _load_driver_catalog()
    functions_cfg = catalog.get("functions") if isinstance(catalog.get("functions"), dict) else {}
    valid_functions = set(functions_cfg.keys())
    valid_safety = {"HIGH", "LOW"}

    function_dynamic_keys: Dict[str, set[str]] = {}
    for fn, fn_cfg in functions_cfg.items():
        keys: set[str] = set()
        if not isinstance(fn_cfg, dict):
            continue
        for drv in (fn_cfg.get("drivers") or []):
            if not isinstance(drv, dict):
                continue
            for fld in (drv.get("settings") or []):
                if isinstance(fld, dict):
                    k = str(fld.get("key") or "").strip()
                    if k:
                        keys.add(k)
            link = drv.get("link") if isinstance(drv.get("link"), dict) else {}
            for lk in (
                "roleField",
                "secondaryUidField",
                "linkedPrimaryField",
                "componentIdField",
            ):
                kv = str(link.get(lk) or "").strip()
                if kv:
                    keys.add(kv)
        if keys:
            function_dynamic_keys[fn] = keys

    # Normalize incoming keys to current discovered UIDs before validation.
    data = _remap_mapping_to_current_pins(data, pins)

    # PRUNE unknown UIDs first (be forgiving with legacy keys)
    pruned_count = 0
    for uid in list(data.keys()):
        if uid not in valid_uids:
            del data[uid]
            pruned_count += 1

    # Validate remaining entries
    link_groups: Dict[str, Dict[str, Any]] = {}
    pin_by_uid = {str(p.get("uid") or ""): p for p in pins if isinstance(p, dict)}
    for uid, row in data.items():
        if not isinstance(row, dict):
            errors.append({"uid": uid, "field": "*", "error": "invalid_row"})
            continue

        friendly = (row.get("friendly") or "").strip()
        raw_func = (row.get("function") or "").strip()
        func = _canonical_function_name(raw_func, catalog)
        safety = (row.get("safety") or "").strip().upper()
        driver = _normalize_driver_name(func, row.get("driver"))

        if len(friendly) > 64:
            errors.append({"uid": uid, "field": "friendly", "error": "too_long"})

        if func and func not in valid_functions:
            errors.append({"uid": uid, "field": "function", "error": "unknown_function"})

        if safety and safety not in valid_safety:
            errors.append({"uid": uid, "field": "safety", "error": "invalid_value"})
        allowed_driver_list = []
        if func:
            raw_allowed = (catalog.get("driversByFunction") or {}).get(func)
            if isinstance(raw_allowed, list):
                allowed_driver_list = [str(v).strip() for v in raw_allowed if str(v).strip()]
        if not allowed_driver_list:
            raw_fallback = (catalog.get("driversByFunction") or {}).get("*", ["Default"])
            if isinstance(raw_fallback, list):
                allowed_driver_list = [str(v).strip() for v in raw_fallback if str(v).strip()]
        if not allowed_driver_list:
            allowed_driver_list = ["Default"]
        allowed_drivers = set(allowed_driver_list)
        if driver not in allowed_drivers:
            errors.append({"uid": uid, "field": "driver", "error": "driver_invalid"})
            driver = allowed_driver_list[0]

        # Normalize back
        row["friendly"] = friendly
        row["function"] = func
        row["driver"] = driver
        row["safety"] = safety if safety in valid_safety else ""
        row.pop("purpose", None)

        # Clear stale dynamic keys from previously selected functions.
        for fn_name, dynamic_keys in function_dynamic_keys.items():
            if fn_name == func:
                continue
            for k in dynamic_keys:
                row.pop(k, None)

        if func:
            profile = _driver_profile(catalog, func, driver)
            settings = profile.get("settings") if isinstance(profile.get("settings"), list) else []
            normalized_setting_values: Dict[str, Any] = {}
            for fld in settings:
                if not isinstance(fld, dict):
                    continue
                key = str(fld.get("key") or "").strip()
                if not key:
                    continue
                ftype = str(fld.get("type") or "text").strip().lower()
                default = fld.get("default")
                raw = row.get(key, default)
                if ftype == "number":
                    try:
                        val = int(raw)
                    except Exception:
                        val = int(default) if isinstance(default, (int, float, str)) and str(default).strip() else 0
                    if "min" in fld:
                        try:
                            val = max(int(fld["min"]), val)
                        except Exception:
                            pass
                    if "max" in fld:
                        try:
                            val = min(int(fld["max"]), val)
                        except Exception:
                            pass
                    normalized_setting_values[key] = val
                elif ftype == "hex":
                    try:
                        n = int(str(raw or default or "0x27"), 0)
                    except Exception:
                        n = int(str(default or "0x27"), 0) if str(default or "").strip() else 0x27
                    min_v = int(fld.get("min", 0))
                    max_v = int(fld.get("max", 255))
                    if n < min_v or n > max_v:
                        errors.append({"uid": uid, "field": key, "error": "invalid_value"})
                        n = max(min_v, min(max_v, n))
                    normalized_setting_values[key] = f"0x{n:02x}"
                elif ftype == "select":
                    options = [str(v).strip() for v in (fld.get("options") or []) if str(v).strip()]
                    val = str(raw or default or "").strip()
                    if options and val not in options:
                        errors.append({"uid": uid, "field": key, "error": "invalid_value"})
                        val = options[0]
                    normalized_setting_values[key] = val
                else:
                    normalized_setting_values[key] = str(raw or default or "").strip()
                row[key] = normalized_setting_values[key]

            link = profile.get("link") if isinstance(profile.get("link"), dict) else {}
            if bool(link.get("enabled")):
                role_field = str(link.get("roleField") or "componentRole").strip()
                secondary_uid_field = str(link.get("secondaryUidField") or "secondaryPinUid").strip()
                linked_primary_field = str(link.get("linkedPrimaryField") or "linkedPrimaryUid").strip()
                component_id_field = str(link.get("componentIdField") or "componentId").strip()
                component_prefix = str(link.get("componentIdPrefix") or "comp").strip() or "comp"
                roles = [str(v).strip().upper() for v in (link.get("roles") or []) if str(v).strip()]
                role_set = set(roles)

                role = str(row.get(role_field) or (roles[0] if roles else "")).strip().upper()
                if role_set and role not in role_set:
                    errors.append({"uid": uid, "field": role_field, "error": "invalid_value"})
                    role = roles[0] if roles else role
                row[role_field] = role
                row[secondary_uid_field] = str(row.get(secondary_uid_field) or "").strip()
                row[linked_primary_field] = str(row.get(linked_primary_field) or "").strip()

                comp_id = str(row.get(component_id_field) or "").strip()
                if not comp_id:
                    linked_primary = str(row.get(linked_primary_field) or "").strip()
                    base_uid = linked_primary or uid
                    comp_id = f"{component_prefix}-{_uid_tail(base_uid).lower().replace('__', '-')}"
                row[component_id_field] = comp_id

                req_pin_type = str(link.get("requirePinType") or "").strip().upper()
                if req_pin_type:
                    pin = pin_by_uid.get(uid) or {}
                    discovered_pin_type = str(pin.get("type") or "").strip().upper()
                    if discovered_pin_type != req_pin_type:
                        errors.append({"uid": uid, "field": "function", "error": "requires_pin_type"})

                if comp_id:
                    bucket = link_groups.setdefault(comp_id, {"rows": [], "link": link, "settings": [str(s.get("key") or "").strip() for s in settings if isinstance(s, dict)]})
                    bucket["rows"].append({
                        "uid": uid,
                        "role": role,
                        "driver": driver,
                        "function": func,
                        "settings": {k: normalized_setting_values.get(k) for k in bucket["settings"] if k},
                    })

        if isinstance(existing_map.get(uid), dict):
            # Preserve physical metadata fields authored outside hardware UI.
            if "pixelCount" in existing_map[uid] and "pixelCount" not in row:
                row["pixelCount"] = existing_map[uid].get("pixelCount")

    for comp_id, group in link_groups.items():
        rows = group.get("rows") if isinstance(group.get("rows"), list) else []
        link = group.get("link") if isinstance(group.get("link"), dict) else {}
        roles = [str(v).strip().upper() for v in (link.get("roles") or []) if str(v).strip()]
        role_set = set(roles)
        role_field = str(link.get("roleField") or "componentRole").strip()
        settings_keys = [str(v).strip() for v in (group.get("settings") or []) if str(v).strip()]
        if len(rows) != 2:
            errors.append({"uid": comp_id, "field": "componentId", "error": "pair_requires_two_pins"})
            continue
        row_roles = {str(r.get("role") or "").upper() for r in rows}
        if role_set and row_roles != role_set:
            errors.append({"uid": comp_id, "field": role_field, "error": "pair_requires_roles"})
        row_uids = [str(r.get("uid") or "").strip() for r in rows]
        if not row_uids[0] or not row_uids[1] or row_uids[0] == row_uids[1]:
            errors.append({"uid": comp_id, "field": "componentId", "error": "pair_invalid_pins"})
        drivers = {str(r.get("driver") or "").strip() for r in rows}
        if len(drivers) != 1:
            errors.append({"uid": comp_id, "field": "driver", "error": "pair_mismatch"})
        functions = {str(r.get("function") or "").strip() for r in rows}
        if len(functions) != 1:
            errors.append({"uid": comp_id, "field": "function", "error": "pair_mismatch"})
        for key in settings_keys:
            vals = {str((r.get("settings") or {}).get(key) or "").strip() for r in rows}
            if len(vals) != 1:
                errors.append({"uid": comp_id, "field": key, "error": "pair_mismatch"})

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
