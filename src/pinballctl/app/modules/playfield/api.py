"""API endpoints for saving/loading the playfield layout state."""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from flask import current_app, jsonify, request, send_file, url_for
from . import api_bp

_PLAYFIELD_FITS = {"cover", "contain", "exact"}
_PLAYFIELD_POSITIONS = {
    "center", "top", "bottom", "left", "right",
    "top left", "top right", "bottom left", "bottom right",
}

# ----------------------------- storage helpers --------------------------------
def _store_dir() -> Path:
    """Return/create the instance directory for playfield state."""
    p = Path(current_app.instance_path) / "playfield"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _layout_path() -> Path:
    """Path to the saved layout JSON file."""
    return _store_dir() / "layout.json"

def _playfield_glob() -> str:
    return "playfield.*"

def _hardware_mapping_path() -> Path:
    """Path to the hardware mapping written by the Hardware module."""
    # Re-use the mapping produced by the Hardware module if present
    return Path(current_app.instance_path) / "hardware" / "mapping.json"

# ----------------------------- utilities --------------------------------------
def _now():
    """UTC timestamp string for stored metadata."""
    return datetime.now(timezone.utc).isoformat()

def _read_json(path: Path, default):
    """Read JSON from disk, returning default on any failure."""
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default

def _write_json(path: Path, data) -> None:
    """Write JSON atomically via a temp file."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

def _load_layout_state() -> dict:
    data = _read_json(_layout_path(), {})
    if not isinstance(data, dict):
        data = {}
    return data

def _save_layout_state(data: dict) -> None:
    _write_json(_layout_path(), data)

def _normalize_playfield_fit(value) -> str:
    fit = str(value or "").strip().lower()
    return fit if fit in _PLAYFIELD_FITS else "cover"

def _normalize_playfield_position(value) -> str:
    pos = str(value or "").strip().lower()
    return pos if pos in _PLAYFIELD_POSITIONS else "center"

def _normalize_playfield_opacity(value) -> float:
    try:
        v = float(value)
    except Exception:
        v = 1.0
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return float(v)

def _playfield_meta(layout: dict | None = None) -> dict:
    src = layout if isinstance(layout, dict) else _load_layout_state()
    meta = src.get("playfield") if isinstance(src.get("playfield"), dict) else {}
    name = str(meta.get("name") or "").strip()
    updated = str(meta.get("updatedAt") or "").strip()
    if not name:
        return {}
    return {
        "name": name,
        "updatedAt": updated,
        "fit": _normalize_playfield_fit(meta.get("fit")),
        "position": _normalize_playfield_position(meta.get("position")),
        "opacity": _normalize_playfield_opacity(meta.get("opacity")),
    }

def _playfield_path(meta: dict | None = None) -> Path | None:
    if meta is None:
        meta = _playfield_meta()
    name = str(meta.get("name") or "").strip()
    if not name:
        return None
    p = _store_dir() / name
    return p if p.exists() and p.is_file() else None

def _playfield_url(meta: dict | None = None) -> str | None:
    if meta is None:
        meta = _playfield_meta()
    path = _playfield_path(meta)
    if not path:
        return None
    stamp = str(meta.get("updatedAt") or "").strip() or str(int(path.stat().st_mtime))
    safe = re.sub(r"[^0-9A-Za-zT:_\\-\\.]+", "", stamp)
    return url_for("playfield_api.get_playfield_image", v=safe)

def _playfield_payload(meta: dict | None = None) -> dict | None:
    if meta is None:
        meta = _playfield_meta()
    if not meta:
        return None
    return {
        "name": meta.get("name"),
        "updatedAt": meta.get("updatedAt"),
        "fit": _normalize_playfield_fit(meta.get("fit")),
        "position": _normalize_playfield_position(meta.get("position")),
        "opacity": _normalize_playfield_opacity(meta.get("opacity")),
        "url": _playfield_url(meta),
    }

def _remove_playfield_files() -> None:
    for fp in _store_dir().glob(_playfield_glob()):
        try:
            if fp.is_file():
                fp.unlink()
        except Exception:
            pass

# ----------------------------- API endpoints ----------------------------------
@api_bp.get("/state")
def get_state():
    """Return the saved playfield layout, seeding defaults if missing."""
    data = _load_layout_state()
    if not data:
        data = {
        "_version": 1,
        "updatedAt": _now(),
        "options": {"width": 700, "height": 1400},
        "elements": [],   # {id,type,label,x,y,icon,color}
        "keymap": {},     # key -> elementId
        }
    data["playfield"] = _playfield_payload(_playfield_meta(data))
    return jsonify(data)

@api_bp.post("/state")
def save_state():
    """Persist the provided layout/keymap payload."""
    payload = request.get_json(silent=True) or {}
    existing = _load_layout_state()
    data = {
        "_version": 1,
        "updatedAt": _now(),
        "options": payload.get("options", {"width": 700, "height": 1400}),
        "elements": payload.get("elements", []),
        "keymap": payload.get("keymap", {}),
    }
    playfield = existing.get("playfield") if isinstance(existing.get("playfield"), dict) else None
    if playfield:
        data["playfield"] = {
            "name": str(playfield.get("name") or "").strip(),
            "updatedAt": str(playfield.get("updatedAt") or "").strip(),
            "fit": _normalize_playfield_fit(playfield.get("fit")),
            "position": _normalize_playfield_position(playfield.get("position")),
            "opacity": _normalize_playfield_opacity(playfield.get("opacity")),
        }
    _save_layout_state(data)
    return jsonify({"ok": True, "savedAt": data["updatedAt"]})

@api_bp.get("/image")
def get_playfield_image():
    path = _playfield_path()
    if not path:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return send_file(path, conditional=True)

@api_bp.post("/image")
def upload_playfield_image():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "file_required"}), 400
    content_type = (f.content_type or "").lower().strip()
    allowed = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    ext = allowed.get(content_type)
    if not ext:
        suffix = Path(str(f.filename).strip().lower()).suffix
        ext_from_suffix = {
            ".png": ".png",
            ".jpg": ".jpg",
            ".jpeg": ".jpg",
            ".webp": ".webp",
            ".gif": ".gif",
            ".avif": ".avif",
        }
        ext = ext_from_suffix.get(suffix)
    if not ext:
        return jsonify({"ok": False, "error": "unsupported_type"}), 400
    body = f.read()
    if not body:
        return jsonify({"ok": False, "error": "empty_file"}), 400
    if len(body) > 12 * 1024 * 1024:
        return jsonify({"ok": False, "error": "file_too_large"}), 413

    _remove_playfield_files()
    name = f"playfield{ext}"
    out = _store_dir() / name
    out.write_bytes(body)

    layout = _load_layout_state()
    layout.setdefault("_version", 1)
    layout.setdefault("options", {"width": 700, "height": 1400})
    layout.setdefault("elements", [])
    layout.setdefault("keymap", {})
    existing = layout.get("playfield") if isinstance(layout.get("playfield"), dict) else {}
    layout["updatedAt"] = _now()
    layout["playfield"] = {
        "name": name,
        "updatedAt": _now(),
        "fit": _normalize_playfield_fit(existing.get("fit")),
        "position": _normalize_playfield_position(existing.get("position")),
        "opacity": _normalize_playfield_opacity(existing.get("opacity")),
    }
    _save_layout_state(layout)
    return jsonify({"ok": True, "playfield": _playfield_payload(_playfield_meta(layout))})

@api_bp.delete("/image")
def remove_playfield_image():
    _remove_playfield_files()
    layout = _load_layout_state()
    if isinstance(layout.get("playfield"), dict):
        layout.pop("playfield", None)
        layout["updatedAt"] = _now()
        _save_layout_state(layout)
    return jsonify({"ok": True})

@api_bp.post("/image/options")
def update_playfield_options():
    payload = request.get_json(silent=True) or {}
    layout = _load_layout_state()
    meta = layout.get("playfield") if isinstance(layout.get("playfield"), dict) else None
    if not meta or not str(meta.get("name") or "").strip():
        return jsonify({"ok": False, "error": "playfield_not_found"}), 404
    meta["fit"] = _normalize_playfield_fit(payload.get("fit"))
    meta["position"] = _normalize_playfield_position(payload.get("position"))
    meta["opacity"] = _normalize_playfield_opacity(payload.get("opacity"))
    layout["playfield"] = meta
    layout["updatedAt"] = _now()
    _save_layout_state(layout)
    return jsonify({"ok": True, "playfield": _playfield_payload(_playfield_meta(layout))})

@api_bp.get("/hardware")
def list_hardware():
    """Summarize mapped hardware for UI dropdowns (buttons/leds/other)."""
    path = _hardware_mapping_path()
    mapping = _read_json(path, {"data": {}})
    out = {"buttons": [], "leds": [], "solenoids": [], "other": []}

    try:
        data = mapping.get("data", {})
        function_map = {
            "Button": "button",
            "Switch": "switch",
            "Accelerometer": "gyro",
            "NFC": "nfc",
            "Solenoid": "coil",
            "LED": "led",
            "RGB Strip": "led",
        }
        for key, item in data.items():
            friendly = (item.get("friendly") or "").strip()
            fn = (item.get("function") or "").strip()
            purpose = (item.get("purpose") or "").strip()
            if not friendly and not fn and not purpose:
                continue

            entry = {
                "id": key,
                "friendly": friendly or key,
                "function": fn or "Other",
                "purpose": purpose,
                "deviceClass": function_map.get(fn, "other"),
            }
            fn_lower = entry["function"].strip().lower()
            if fn_lower == "button":
                out["buttons"].append(entry)
            elif fn_lower in ("led", "rgb led", "rgb"):
                out["leds"].append(entry)
            elif fn_lower in ("solenoid", "coil"):
                out["solenoids"].append(entry)
            else:
                out["other"].append(entry)
    except Exception:
        pass

    return jsonify({"ok": True, "components": out})
