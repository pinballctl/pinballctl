"""API endpoints for project settings and import/export."""

from __future__ import annotations

import io
import json
import re
import shutil
import stat
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from flask import Blueprint, current_app, jsonify, request, send_file

from ...settings_store import load_settings as load_store_settings, save_settings as save_store_settings, apply_to_app
from ... import _get_user_pass_from_config

api_bp = Blueprint("settings_api", __name__)


def _instance_dir() -> Path:
    """Resolve the instance directory (already ensured in create_app)."""
    return Path(current_app.instance_path)


@api_bp.get("/data")
def get_settings():
    """Return current settings."""
    return jsonify(load_store_settings(current_app.instance_path))


@api_bp.post("/save")
def save_settings():
    """Save project settings (currently only name)."""
    payload = request.get_json(silent=True) or {}
    data = load_store_settings(current_app.instance_path)
    # Allow selected keys to be overridden
    allowed = ("name", "AUTH_USER", "AUTH_PASSWORD", "REMOTE_FIRMWARE_URL", "LOG_LEVEL", "CURRENCY", "START_DISPLAYS")
    for key in allowed:
        if key in payload:
            val = payload.get(key)
            if key == "START_DISPLAYS":
                data[key] = bool(val)
                continue
            if isinstance(val, str):
                val = val.strip()
            # Do not overwrite password with blank
            if key == "AUTH_PASSWORD" and not val:
                continue
            data[key] = val
    save_store_settings(current_app.instance_path, data)
    apply_to_app(current_app, data)
    # Refresh auth getter so login sees updated credentials immediately
    current_app.config["_AUTH_GET_USER_PASS"] = lambda: _get_user_pass_from_config(current_app)
    return jsonify({"ok": True, "data": data})


def _safe_member_path(member: zipfile.ZipInfo) -> Path | None:
    """Prevent zip traversal by rejecting absolute/parent paths."""
    rel = Path(member.filename)
    if rel.is_absolute():
        return None
    if any(part in ("..", "") for part in rel.parts):
        return None
    return rel


def _export_filename(project_name: str | None) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", project_name or "project").strip("-") or "project"
    stamp = datetime.now().strftime("%Y%m%d%H%M")
    return f"{safe}-{stamp}.zip"


@api_bp.get("/export")
def export_project():
    """Package the entire instance directory into a zip."""
    inst = _instance_dir()
    data = load_store_settings(current_app.instance_path)
    filename = _export_filename(data.get("name"))

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp_path = Path(tmp.name)
    tmp.close()

    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in inst.rglob("*"):
            if path.is_dir():
                continue
            try:
                mode = path.lstat().st_mode
            except OSError:
                current_app.logger.warning("Skipping unreadable export path: %s", path)
                continue
            # Zip export only supports regular files; skip sockets/FIFOs/devices.
            if not stat.S_ISREG(mode):
                current_app.logger.debug("Skipping non-regular export path: %s", path)
                continue
            rel = path.relative_to(inst)
            zf.write(path, arcname=rel.as_posix())

    return send_file(
        tmp_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


@api_bp.post("/import")
def import_project():
    """Import a zip of instance data; files overwrite existing ones."""
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file provided"}), 400
    up = request.files["file"]
    if not up or not up.filename:
        return jsonify({"ok": False, "error": "Invalid file"}), 400

    inst = _instance_dir()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        up.save(tmp.name)
        tmp_path = Path(tmp.name)

    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for member in zf.infolist():
                rel = _safe_member_path(member)
                if rel is None:
                    current_app.logger.warning("Skipping unsafe path in import: %s", member.filename)
                    continue
                dest = inst / rel
                if member.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member, "r") as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst)
    except zipfile.BadZipFile:
        return jsonify({"ok": False, "error": "Invalid zip file"}), 400
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    return jsonify({"ok": True})
