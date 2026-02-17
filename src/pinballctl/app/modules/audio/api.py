"""Audio API: config, assets, devices, and playback controls."""
from __future__ import annotations

from flask import current_app, jsonify, request, send_file

from pinballctl.audio.runtime import (
    load_audio_config,
    save_audio_config,
    load_audio_state,
    get_output_environment,
    upload_asset,
    delete_asset,
    get_asset_file,
    play_cue,
    preview_asset,
    preview_cue,
    stop_cue,
    stop_runtime_entry,
)

from . import api_bp


@api_bp.get("/config")
def audio_config_get():
    return jsonify({"ok": True, "config": load_audio_config(current_app.instance_path)})


@api_bp.post("/config")
def audio_config_save():
    body = request.get_json(silent=True) or {}
    cfg = body.get("config") if isinstance(body, dict) else None
    if not isinstance(cfg, dict):
        return jsonify({"ok": False, "error": "invalid_config"}), 400
    saved = save_audio_config(current_app.instance_path, cfg)
    return jsonify({"ok": True, "config": saved})


@api_bp.get("/state")
def audio_state_get():
    return jsonify({"ok": True, "state": load_audio_state(current_app.instance_path)})


@api_bp.get("/devices")
def audio_devices_get():
    force = str(request.args.get("refresh") or "").strip().lower() in ("1", "true", "yes")
    env = get_output_environment(current_app.instance_path, force_refresh=force)
    # Keep `devices` top-level for backward compatibility with existing UI code.
    return jsonify({"ok": True, **env, "devices": env.get("devices", [])})


@api_bp.post("/assets/upload")
def audio_asset_upload():
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "error": "missing_file"}), 400
    display_name = str(request.form.get("displayName") or "").strip() or None
    res = upload_asset(current_app.instance_path, f, display_name=display_name)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/assets/delete")
def audio_asset_delete():
    body = request.get_json(silent=True) or {}
    asset_id = str((body or {}).get("assetId") or "").strip()
    if not asset_id:
        return jsonify({"ok": False, "error": "missing_asset_id"}), 400
    res = delete_asset(current_app.instance_path, asset_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/assets/preview")
def audio_asset_preview():
    body = request.get_json(silent=True) or {}
    asset_id = str((body or {}).get("assetId") or "").strip()
    if not asset_id:
        return jsonify({"ok": False, "error": "missing_asset_id"}), 400
    res = preview_asset(current_app.instance_path, asset_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/cues/preview")
def audio_cue_preview():
    body = request.get_json(silent=True) or {}
    cue = body.get("cue") if isinstance(body, dict) else None
    try:
        seek_ms = int((body or {}).get("seekMs") or 0) if isinstance(body, dict) else 0
    except Exception:
        seek_ms = 0
    if not isinstance(cue, dict):
        return jsonify({"ok": False, "error": "invalid_cue"}), 400
    res = preview_cue(current_app.instance_path, cue, seek_ms=seek_ms)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.get("/assets/file/<asset_id>")
def audio_asset_file(asset_id: str):
    try:
        res = get_asset_file(current_app.instance_path, asset_id)
    except Exception:
        current_app.logger.exception("audio asset lookup failed: %s", asset_id)
        return jsonify({"ok": False, "error": "asset_lookup_failed"}), 500
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "asset_not_found")}), 404
    path = res["path"]
    try:
        return send_file(path, conditional=True)
    except FileNotFoundError:
        return jsonify({"ok": False, "error": "asset_missing"}), 404
    except Exception:
        current_app.logger.exception("audio asset send failed: %s", asset_id)
        return jsonify({"ok": False, "error": "asset_send_failed"}), 500


@api_bp.post("/play")
def audio_play():
    body = request.get_json(silent=True) or {}
    cue_id = str((body or {}).get("cueId") or "").strip()
    preview = bool((body or {}).get("preview", False))
    if not cue_id:
        return jsonify({"ok": False, "error": "missing_cue_id"}), 400
    res = play_cue(current_app.instance_path, cue_id, preview=preview)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/stop")
def audio_stop():
    body = request.get_json(silent=True) or {}
    cue_id = str((body or {}).get("cueId") or "").strip() or None
    preview_only = bool((body or {}).get("previewOnly", False))
    res = stop_cue(current_app.instance_path, cue_id=cue_id, preview_only=preview_only)
    return jsonify(res)


@api_bp.post("/runtime/stop")
def audio_runtime_stop():
    body = request.get_json(silent=True) or {}
    playback_id = str((body or {}).get("playbackId") or "").strip() or None
    try:
        pid_raw = (body or {}).get("pid")
        pid = int(pid_raw) if pid_raw is not None and str(pid_raw).strip() != "" else None
    except Exception:
        pid = None
    res = stop_runtime_entry(current_app.instance_path, playback_id=playback_id, pid=pid)
    status = 200 if res.get("ok") else 404
    return jsonify(res), status
