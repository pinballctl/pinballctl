"""Media API: config, assets, displays, and runtime controls."""
from __future__ import annotations

import json

from flask import Response, current_app, jsonify, request, send_file

from pinballctl.media.runtime import (
    attach_runtime_surface,
    heartbeat_runtime_surface,
    complete_scene,
    detach_embedded_surface,
    detach_surface,
    delete_media_font,
    delete_asset,
    get_asset_file,
    get_media_font_file,
    get_media_environment,
    list_media_fonts,
    load_media_config,
    load_media_state,
    media_fonts_stylesheet,
    list_runtime_instances,
    play_scene,
    process_event,
    runtime_display_payload,
    save_media_config,
    set_overlay_value,
    stop_scene,
    upload_asset,
    upload_media_fonts,
)
from .kiosk_auth import make_runtime_token

from . import api_bp


@api_bp.get("/config")
def media_config_get():
    return jsonify({"ok": True, "config": load_media_config(current_app.instance_path)})


@api_bp.post("/config")
def media_config_save():
    body = request.get_json(silent=True) or {}
    cfg = body.get("config") if isinstance(body, dict) else None
    if not isinstance(cfg, dict):
        return jsonify({"ok": False, "error": "invalid_config"}), 400
    saved = save_media_config(current_app.instance_path, cfg)
    return jsonify({"ok": True, "config": saved})


@api_bp.get("/state")
def media_state_get():
    return jsonify({"ok": True, "state": load_media_state(current_app.instance_path)})


@api_bp.get("/runtime/instances")
def media_runtime_instances():
    return jsonify(list_runtime_instances(current_app.instance_path))


@api_bp.get("/environment")
def media_environment_get():
    return jsonify({"ok": True, **get_media_environment(current_app.instance_path)})


@api_bp.get("/fonts")
def media_fonts_get():
    return jsonify({"ok": True, "fonts": list_media_fonts(current_app.instance_path)})


@api_bp.get("/fonts/stylesheet")
def media_fonts_css():
    runtime_token = str(request.args.get("kiosk_token") or "").strip() or None
    css = media_fonts_stylesheet(current_app.instance_path, runtime_token=runtime_token)
    return Response(css, mimetype="text/css", headers={"Cache-Control": "no-store"})


@api_bp.post("/fonts/upload")
def media_fonts_upload():
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "error": "missing_file"}), 400
    res = upload_media_fonts(current_app.instance_path, f)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.get("/fonts/file/<font_id>")
def media_font_file(font_id: str):
    res = get_media_font_file(current_app.instance_path, font_id)
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "not_found")}), 404
    try:
        return send_file(res["path"], conditional=True, mimetype="font/ttf")
    except Exception:
        current_app.logger.exception("media font send failed: %s", font_id)
        return jsonify({"ok": False, "error": "font_send_failed"}), 500


@api_bp.post("/fonts/delete")
def media_font_delete():
    body = request.get_json(silent=True) or {}
    font_id = str((body or {}).get("fontId") or "").strip()
    if not font_id:
        return jsonify({"ok": False, "error": "missing_font_id"}), 400
    res = delete_media_font(current_app.instance_path, font_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/assets/upload")
def media_asset_upload():
    f = request.files.get("file")
    if f is None:
        return jsonify({"ok": False, "error": "missing_file"}), 400
    display_name = str(request.form.get("displayName") or "").strip() or None
    res = upload_asset(current_app.instance_path, f, display_name=display_name)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/assets/delete")
def media_asset_delete():
    body = request.get_json(silent=True) or {}
    asset_id = str((body or {}).get("assetId") or "").strip()
    if not asset_id:
        return jsonify({"ok": False, "error": "missing_asset_id"}), 400
    res = delete_asset(current_app.instance_path, asset_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.get("/assets/file/<asset_id>")
def media_asset_file(asset_id: str):
    res = get_asset_file(current_app.instance_path, asset_id)
    if not res.get("ok"):
        return jsonify({"ok": False, "error": res.get("error", "not_found")}), 404
    try:
        return send_file(res["path"], conditional=True)
    except Exception:
        current_app.logger.exception("media asset send failed: %s", asset_id)
        return jsonify({"ok": False, "error": "asset_send_failed"}), 500


@api_bp.post("/play")
def media_play():
    body = request.get_json(silent=True) or {}
    scene_id = str((body or {}).get("sceneId") or "").strip()
    if not scene_id:
        return jsonify({"ok": False, "error": "missing_scene_id"}), 400
    launch_mode = str((body or {}).get("launchMode") or "").strip().lower() or "fullscreen"
    if launch_mode not in ("fullscreen", "windowed"):
        launch_mode = "fullscreen"
    stack_behavior = str((body or {}).get("stackBehavior") or "").strip().lower() or "replace"
    if stack_behavior not in ("replace", "interrupt"):
        stack_behavior = "replace"
    raw_preview = (body or {}).get("previewViewport")
    preview_viewport = None
    if isinstance(raw_preview, dict):
        try:
            pw = max(1, int(float(raw_preview.get("width") or 0)))
            ph = max(1, int(float(raw_preview.get("height") or 0)))
            preview_viewport = {"width": pw, "height": ph}
        except Exception:
            preview_viewport = None
    base_url = request.host_url.rstrip("/")
    secret = str(current_app.secret_key or current_app.config.get("SECRET_KEY") or "")
    runtime_token = make_runtime_token(secret)
    res = process_event(
        current_app.instance_path,
        name="MEDIA_SCENE_PLAY",
        source="ui.media",
        params={
            "sceneId": scene_id,
            "baseUrl": base_url,
            "runtimeToken": runtime_token,
            "launchMode": launch_mode,
            "previewViewport": preview_viewport,
            "stackBehavior": stack_behavior,
        },
    )
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/stop")
def media_stop():
    body = request.get_json(silent=True) or {}
    scene_id = str((body or {}).get("sceneId") or "").strip() or None
    session_id = str((body or {}).get("sessionId") or "").strip() or None
    res = process_event(
        current_app.instance_path,
        name="MEDIA_SCENE_STOP" if (scene_id or session_id) else "MEDIA_STOP_ALL",
        source="ui.media",
        params={"sceneId": scene_id, "sessionId": session_id},
    )
    return jsonify(res)


@api_bp.post("/overlay/value")
def media_overlay_value():
    body = request.get_json(silent=True) or {}
    key = str((body or {}).get("key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "missing_key"}), 400
    value = (body or {}).get("value")
    res = set_overlay_value(current_app.instance_path, key=key, value=value)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/complete")
def media_scene_complete():
    body = request.get_json(silent=True) or {}
    display_id = str((body or {}).get("displayId") or "").strip()
    if not display_id:
        return jsonify({"ok": False, "error": "missing_display_id"}), 400
    session_id = str((body or {}).get("sessionId") or "").strip() or None
    scene_id = str((body or {}).get("sceneId") or "").strip() or None
    res = process_event(
        current_app.instance_path,
        name="MEDIA_SCENE_COMPLETE",
        source="ui.media",
        params={"displayId": display_id, "sessionId": session_id, "sceneId": scene_id},
    )
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/surface/leave")
def media_surface_leave():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict) or not body:
        try:
            raw = request.get_data(cache=False, as_text=True) or ""
            parsed = json.loads(raw) if raw.strip() else {}
            body = parsed if isinstance(parsed, dict) else {}
        except Exception:
            body = {}
    display_id = str((body or {}).get("displayId") or "").strip()
    session_id = str((body or {}).get("instanceId") or (body or {}).get("sessionId") or "").strip()
    surface_id = str((body or {}).get("surfaceId") or "").strip() or None
    surface = str((body or {}).get("surface") or "").strip().lower()
    if session_id:
        res = detach_surface(current_app.instance_path, session_id=session_id, surface_id=surface_id)
        status = 200 if res.get("ok") else 400
        return jsonify(res), status
    if not display_id:
        return jsonify({"ok": False, "error": "missing_display_id"}), 400
    if surface != "embedded":
        return jsonify({"ok": False, "error": "unsupported_surface"}), 400
    res = detach_embedded_surface(current_app.instance_path, display_id=display_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/surface/attach")
def media_surface_attach():
    body = request.get_json(silent=True) or {}
    instance_id = str((body or {}).get("instanceId") or "").strip()
    surface_id = str((body or {}).get("surfaceId") or "").strip() or None
    if not instance_id:
        return jsonify({"ok": False, "error": "missing_instance_id"}), 400
    res = attach_runtime_surface(current_app.instance_path, instance_id=instance_id, surface_id=surface_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.post("/surface/heartbeat")
def media_surface_heartbeat():
    body = request.get_json(silent=True) or {}
    instance_id = str((body or {}).get("instanceId") or "").strip()
    surface_id = str((body or {}).get("surfaceId") or "").strip() or None
    if not instance_id:
        return jsonify({"ok": False, "error": "missing_instance_id"}), 400
    res = heartbeat_runtime_surface(current_app.instance_path, instance_id=instance_id, surface_id=surface_id)
    status = 200 if res.get("ok") else 400
    return jsonify(res), status


@api_bp.get("/runtime/display/<display_id>")
def media_runtime_display(display_id: str):
    scene_id = str(request.args.get("sceneId") or "").strip() or None
    session_id = str(request.args.get("sessionId") or "").strip() or None
    instance_id = str(request.args.get("instanceId") or "").strip() or None
    surface_id = str(request.args.get("surfaceId") or "").strip() or None
    surface_type = str(request.args.get("surface") or "").strip() or None
    payload = runtime_display_payload(
        current_app.instance_path,
        display_id,
        scene_id=scene_id,
        session_id=session_id,
        instance_id=instance_id,
        surface_id=surface_id,
        surface_type=surface_type,
    )
    return jsonify(payload)
