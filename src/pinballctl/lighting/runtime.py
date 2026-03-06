"""Runtime helpers for lighting scene playback via bridge commands."""
from __future__ import annotations

import json
import time
from threading import Lock
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from pinballctl.bridge.state import enqueue_command, is_headless_mode, rpc_command


_SCENE_STATUS_LOCK = Lock()
_SCENE_STATUS_CACHE: Dict[str, Any] = {"at": 0.0, "value": None}


def _lighting_dir(instance_path: str | Path) -> Path:
    p = Path(instance_path) / "lighting"
    p.mkdir(parents=True, exist_ok=True)
    return p


def lighting_json_path(instance_path: str | Path) -> Path:
    return _lighting_dir(instance_path) / "lighting.json"


def load_lighting_config(instance_path: str | Path) -> Dict[str, Any]:
    path = lighting_json_path(instance_path)
    if not path.exists():
        return {"_version": 1, "fixtures": {}, "scenes": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"_version": 1, "fixtures": {}, "scenes": []}


def scene_exists(instance_path: str | Path, scene_id: str) -> bool:
    if not scene_id:
        return False
    cfg = load_lighting_config(instance_path)
    for scene in cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []:
        if isinstance(scene, dict) and str(scene.get("id")) == str(scene_id):
            return True
    return False


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    source: str = "pi.rules",
    start_frame: int | None = None,
    start_tag: str | None = None,
    paused: bool = False,
) -> bool:
    if not scene_exists(instance_path, scene_id):
        return False
    if is_headless_mode():
        return False
    payload: Dict[str, Any] = {
        "cmd": "LIGHT_SCENE_PLAY",
        "sceneId": str(scene_id),
        "source": source,
        "reqId": uuid4().hex,
    }
    if isinstance(start_frame, int) and start_frame > 0:
        payload["startFrame"] = int(start_frame)
    if isinstance(start_tag, str) and start_tag.strip():
        payload["startTag"] = start_tag.strip()
    if paused:
        payload["paused"] = True
    enqueue_command(payload, wait_for_startup=False)
    return True


def stop_scene(scene_id: str, source: str = "pi.rules") -> None:
    if is_headless_mode():
        return
    enqueue_command(
        {
            "cmd": "LIGHT_SCENE_STOP",
            "sceneId": str(scene_id),
            "source": source,
            "reqId": uuid4().hex,
        },
        wait_for_startup=False,
    )


def play_scene_rpc(
    instance_path: str | Path,
    scene_id: str,
    source: str = "pi.lighting.preview",
    timeout_s: float = 1.5,
) -> Dict[str, Any]:
    if not scene_exists(instance_path, scene_id):
        return {"ok": False, "sceneId": str(scene_id or ""), "reason": "unknown_scene"}
    if is_headless_mode():
        return {"ok": False, "sceneId": str(scene_id or ""), "reason": "bridge_offline"}
    req_id = uuid4().hex
    cmd = {
        "cmd": "LIGHT_SCENE_PLAY",
        "sceneId": str(scene_id),
        "source": source,
        "reqId": req_id,
    }
    try:
        payload = rpc_command(cmd, match_t="LIGHT_SCENE_STATUS", timeout_s=timeout_s)
    except Exception:
        return {"ok": False, "sceneId": str(scene_id or ""), "reason": "rpc_error"}
    if not isinstance(payload, dict):
        return {"ok": False, "sceneId": str(scene_id or ""), "reason": "no_response"}
    return {
        "ok": bool(payload.get("ok", False)),
        "sceneId": str(payload.get("sceneId") or scene_id or ""),
        "reason": str(payload.get("reason") or ""),
    }


def stop_scene_rpc(
    scene_id: str = "*",
    source: str = "pi.lighting.preview",
    timeout_s: float = 1.5,
) -> Dict[str, Any]:
    if is_headless_mode():
        return {"ok": False, "sceneId": str(scene_id or "*"), "reason": "bridge_offline"}
    req_id = uuid4().hex
    cmd = {
        "cmd": "LIGHT_SCENE_STOP",
        "sceneId": str(scene_id or "*"),
        "source": source,
        "reqId": req_id,
    }
    try:
        payload = rpc_command(cmd, match_t="LIGHT_SCENE_STATUS", timeout_s=timeout_s)
    except Exception:
        return {"ok": False, "sceneId": str(scene_id or "*"), "reason": "rpc_error"}
    if not isinstance(payload, dict):
        return {"ok": False, "sceneId": str(scene_id or "*"), "reason": "no_response"}
    return {
        "ok": bool(payload.get("ok", False)),
        "sceneId": str(payload.get("sceneId") or scene_id or "*"),
        "reason": str(payload.get("reason") or ""),
    }


def scene_status(timeout_s: float = 1.5) -> Dict[str, Any]:
    if is_headless_mode():
        return {
            "ok": False,
            "playing": False,
            "sceneId": "",
            "reason": "bridge_offline",
            "activeSceneCount": 0,
            "overridesActive": 0,
            "activeScenes": [],
        }
    now = time.monotonic()
    with _SCENE_STATUS_LOCK:
        cached = _SCENE_STATUS_CACHE.get("value")
        cached_at = float(_SCENE_STATUS_CACHE.get("at") or 0.0)
        if isinstance(cached, dict) and (now - cached_at) < 0.4:
            return dict(cached)
    try:
        payload = rpc_command({"cmd": "LIGHT_SCENE_QUERY", "reqId": uuid4().hex}, match_t="LIGHT_SCENE_STATUS", timeout_s=timeout_s)
    except Exception:
        return {
            "ok": False,
            "playing": False,
            "sceneId": "",
            "reason": "rpc_error",
            "activeSceneCount": 0,
            "overridesActive": 0,
            "activeScenes": [],
        }
    if not isinstance(payload, dict):
        return {
            "ok": False,
            "playing": False,
            "sceneId": "",
            "reason": "no_response",
            "activeSceneCount": 0,
            "overridesActive": 0,
            "activeScenes": [],
        }
    active_scenes = payload.get("activeScenes") if isinstance(payload.get("activeScenes"), list) else []
    active_scene_count_raw = payload.get("activeSceneCount")
    try:
        active_scene_count = int(active_scene_count_raw)
    except Exception:
        active_scene_count = len(active_scenes)
    if active_scene_count < 0:
        active_scene_count = 0
    overrides_raw = payload.get("overridesActive")
    try:
        overrides_active = int(overrides_raw)
    except Exception:
        overrides_active = 0
    if overrides_active < 0:
        overrides_active = 0
    out = {
        "ok": bool(payload.get("ok", True)),
        "playing": bool(payload.get("playing", False)),
        "sceneId": str(payload.get("sceneId") or ""),
        "reason": str(payload.get("reason") or ""),
        "activeSceneCount": active_scene_count,
        "overridesActive": overrides_active,
        "activeScenes": active_scenes,
    }
    with _SCENE_STATUS_LOCK:
        _SCENE_STATUS_CACHE["at"] = time.monotonic()
        _SCENE_STATUS_CACHE["value"] = dict(out)
    return out
