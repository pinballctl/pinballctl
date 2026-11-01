"""Settings endpoints; project snapshots live in Backup / Restore."""

from __future__ import annotations


from flask import Blueprint, current_app, jsonify, request
from werkzeug.security import generate_password_hash

from ...settings_store import load_settings as load_store_settings, save_settings as save_store_settings, apply_to_app
from ... import _get_user_pass_from_config

api_bp = Blueprint("settings_api", __name__)


def _public_settings(data: dict) -> dict:
    return {k: v for k, v in data.items() if k not in {"AUTH_PASSWORD", "AUTH_PASSWORD_HASH", "SECRET_KEY"}}


@api_bp.get("/data")
def get_settings():
    """Return current settings."""
    return jsonify(_public_settings(load_store_settings(current_app.instance_path)))


@api_bp.post("/save")
def save_settings():
    """Save project settings (currently only name)."""
    payload = request.get_json(silent=True) or {}
    data = load_store_settings(current_app.instance_path)
    # Allow selected keys to be overridden
    allowed = ("name", "AUTH_USER", "AUTH_PASSWORD", "REMOTE_FIRMWARE_URL", "LOG_LEVEL", "CURRENCY")
    for key in allowed:
        if key in payload:
            val = payload.get(key)
            if isinstance(val, str):
                val = val.strip()
            # Do not overwrite password with blank
            if key == "AUTH_PASSWORD":
                if not val:
                    continue
                if not isinstance(val, str):
                    return jsonify({"ok": False, "error": "Password must be text"}), 400
                data["AUTH_PASSWORD_HASH"] = generate_password_hash(val)
                data.pop("AUTH_PASSWORD", None)
                continue
            data[key] = val
    save_store_settings(current_app.instance_path, data)
    apply_to_app(current_app, data)
    # Refresh auth getter so login sees updated credentials immediately
    current_app.config["_AUTH_GET_USER_PASS"] = lambda: _get_user_pass_from_config(current_app)
    return jsonify({"ok": True, "data": _public_settings(data)})


@api_bp.get("/export")
@api_bp.post("/import")
def retired_transfer():
    """Legacy archives cannot guarantee replacement, ownership or secret policy."""
    return jsonify(ok=False, error="legacy_transfer_retired",
                   detail="Use Backup / Restore. Legacy unversioned Settings ZIPs require explicit offline migration; they are never restored automatically.",
                   replacement="/backups/"), 410
