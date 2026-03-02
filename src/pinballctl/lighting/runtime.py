"""Runtime helpers for lighting scene playback via bridge commands."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from pinballctl.bridge.state import enqueue_command, is_headless_mode


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
