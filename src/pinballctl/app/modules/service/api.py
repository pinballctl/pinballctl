"""API endpoints for the service log."""
from __future__ import annotations

import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from flask import current_app, jsonify, request, send_from_directory
from . import api_bp

SERVICE_TYPES = ("SERVICE", "REPAIR", "RECALL", "WARRANTY")
ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".pdf", ".docx"}
MAX_ATTACHMENTS = 5

def _store_dir() -> Path:
    p = Path(current_app.instance_path) / "service"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _log_path() -> Path:
    return _store_dir() / "log.json"

def _attachments_dir() -> Path:
    p = _store_dir() / "attachments"
    p.mkdir(parents=True, exist_ok=True)
    return p

def _load_entries() -> List[Dict[str, Any]]:
    fp = _log_path()
    if not fp.exists():
        return []
    try:
        data = json.loads(fp.read_text())
        if isinstance(data, list):
            return [e for e in data if isinstance(e, dict)]
    except Exception:
        pass
    return []

def _save_entries(entries: List[Dict[str, Any]]) -> None:
    fp = _log_path()
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2))
    tmp.replace(fp)

def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if len(value) == 10 and value[4] == "-" and value[7] == "-":
            return datetime.fromisoformat(value)
        return datetime.fromisoformat(value)
    except Exception:
        return None

def _normalize_attachments(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str) and item.strip():
                out.append({"label": item.strip()})
        return out
    if isinstance(value, str) and value.strip():
        return [{"label": line.strip()} for line in value.splitlines() if line.strip()]
    return []

def _save_attachments(files, existing_count: int = 0) -> List[Dict[str, Any]]:
    saved: List[Dict[str, Any]] = []
    if not files:
        return saved
    if len(files) + existing_count > MAX_ATTACHMENTS:
        raise ValueError("too_many_attachments")
    dest = _attachments_dir()
    for file in files:
        if not file or not file.filename:
            continue
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise ValueError("invalid_attachment_type")
        stored = f"{uuid4().hex}{ext}"
        path = dest / stored
        file.save(path)
        mime = file.mimetype or mimetypes.guess_type(file.filename)[0] or "application/octet-stream"
        saved.append({
            "filename": stored,
            "original": file.filename,
            "size": path.stat().st_size,
            "mime": mime,
        })
    return saved

def _entry_matches(entry: Dict[str, Any], type_filter: str | None, start: datetime | None, end: datetime | None) -> bool:
    if type_filter and entry.get("service_type") != type_filter:
        return False
    if start or end:
        created = entry.get("created_at")
        try:
            created_dt = datetime.fromisoformat(created)
        except Exception:
            return False
        if start and created_dt < start:
            return False
        if end and created_dt > end:
            return False
    return True

@api_bp.get("/log")
def list_entries():
    type_filter = request.args.get("type") or ""
    if type_filter and type_filter not in SERVICE_TYPES:
        type_filter = ""
    start = _parse_date(request.args.get("from"))
    end = _parse_date(request.args.get("to"))
    entries = _load_entries()
    filtered = [e for e in entries if _entry_matches(e, type_filter or None, start, end)]
    filtered.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    return jsonify({
        "ok": True,
        "entries": filtered,
        "count": len(filtered),
    })

@api_bp.post("/log")
def create_entry():
    payload = request.get_json(silent=True) or {}
    form = request.form if request.form else {}
    service_type = form.get("service_type") or payload.get("service_type") or ""
    if service_type not in SERVICE_TYPES:
        return jsonify({"ok": False, "error": "invalid_service_type"}), 400
    title = (form.get("title") or payload.get("title") or "").strip()
    description = (form.get("description") or payload.get("description") or "").strip()
    outcome = (form.get("outcome") or payload.get("outcome") or "").strip()
    engineer = (form.get("engineer") or payload.get("engineer") or "").strip()
    if not title or not description or not engineer:
        return jsonify({"ok": False, "error": "missing_fields"}), 400
    try:
        files = request.files.getlist("attachments")
        attachments = _save_attachments(files) if files else _normalize_attachments(payload.get("attachments"))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    entry = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "engineer": engineer,
        "service_type": service_type,
        "title": title,
        "description": description,
        "parts_replaced": (form.get("parts_replaced") or payload.get("parts_replaced") or "").strip(),
        "outcome": outcome,
        "follow_up": (form.get("follow_up") or payload.get("follow_up") or "").strip(),
        "attachments": attachments,
    }
    entries = _load_entries()
    entries.append(entry)
    _save_entries(entries)
    return jsonify({"ok": True, "entry": entry})

@api_bp.post("/log/<entry_id>")
def update_entry(entry_id: str):
    payload = request.get_json(silent=True) or {}
    form = request.form if request.form else {}
    service_type = form.get("service_type") or payload.get("service_type") or ""
    if service_type not in SERVICE_TYPES:
        return jsonify({"ok": False, "error": "invalid_service_type"}), 400
    title = (form.get("title") or payload.get("title") or "").strip()
    description = (form.get("description") or payload.get("description") or "").strip()
    outcome = (form.get("outcome") or payload.get("outcome") or "").strip()
    engineer = (form.get("engineer") or payload.get("engineer") or "").strip()
    if not title or not description or not engineer:
        return jsonify({"ok": False, "error": "missing_fields"}), 400
    entries = _load_entries()
    entry = next((e for e in entries if e.get("id") == entry_id), None)
    if not entry:
        return jsonify({"ok": False, "error": "not_found"}), 404
    keep_list = form.getlist("keep_attachments")
    keep_present = "keep_attachments_present" in form
    if not keep_list and isinstance(payload.get("keep_attachments"), list):
        keep_list = [str(v) for v in payload.get("keep_attachments") if v]
        keep_present = True
    if payload.get("keep_attachments_present"):
        keep_present = True
    existing = entry.get("attachments") or []
    if keep_present:
        keep_set = set(keep_list)
        kept = [att for att in existing if att.get("filename") in keep_set]
    else:
        kept = list(existing)
    removed = [att for att in existing if att not in kept]
    try:
        files = request.files.getlist("attachments")
        new_attachments = _save_attachments(files, existing_count=len(kept)) if files else []
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    for att in removed:
        filename = att.get("filename")
        if filename:
            path = _attachments_dir() / filename
            if path.exists():
                path.unlink()
    entry.update({
        "engineer": engineer,
        "service_type": service_type,
        "title": title,
        "description": description,
        "parts_replaced": (form.get("parts_replaced") or payload.get("parts_replaced") or "").strip(),
        "outcome": outcome,
        "follow_up": (form.get("follow_up") or payload.get("follow_up") or "").strip(),
        "attachments": kept + new_attachments,
    })
    _save_entries(entries)
    return jsonify({"ok": True, "entry": entry})

@api_bp.get("/log/<entry_id>")
def get_entry(entry_id: str):
    entries = _load_entries()
    for entry in entries:
        if entry.get("id") == entry_id:
            return jsonify({"ok": True, "entry": entry})
    return jsonify({"ok": False, "error": "not_found"}), 404

@api_bp.get("/attachment/<filename>")
def get_attachment(filename: str):
    if not filename or "/" in filename or "\\" in filename:
        return jsonify({"ok": False, "error": "invalid_name"}), 400
    path = _attachments_dir() / filename
    if not path.exists():
        return jsonify({"ok": False, "error": "not_found"}), 404
    return send_from_directory(_attachments_dir(), filename, as_attachment=False)
