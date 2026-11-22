"""Start configured default displays from the media supervisor."""

import logging
from pathlib import Path
from threading import Event

from .runtime import load_media_config, load_media_state, play_scene

LOG = logging.getLogger(__name__)


def _autostart_media_targets(cfg: dict) -> list[dict]:
    displays = [d for d in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(d, dict)]
    scenes = [s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if isinstance(s, dict)]
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    default_map = settings.get("defaultScenesByDisplay") if isinstance(settings.get("defaultScenesByDisplay"), dict) else {}
    autoplay_map = settings.get("autoplayByDisplay") if isinstance(settings.get("autoplayByDisplay"), dict) else {}

    targets: list[dict] = []
    used_pairs: set[tuple[str, str]] = set()

    for d in displays:
        if not bool(d.get("enabled", True)):
            continue
        did = str(d.get("id") or "").strip()
        if not bool(autoplay_map.get(did, False)):
            continue
        sid = str(default_map.get(did) or "").strip()
        if not sid:
            continue
        scene = next((s for s in scenes if str(s.get("id") or "").strip() == sid), None)
        if not isinstance(scene, dict):
            continue
        pair = (did, sid)
        if pair in used_pairs:
            continue
        targets.append({"displayId": did, "sceneId": sid})
        used_pairs.add(pair)

    if targets:
        return targets
    return []


def run(instance: Path, stopping: Event) -> None:
    config = load_media_config(instance)
    if not bool((config.get("settings") or {}).get("enabled", True)):
        return
    targets = _autostart_media_targets(config)
    if not targets:
        return

    state = load_media_state(instance)
    active = (state.get("engine") or {}).get("active") or []
    active_pairs = {(row.get("displayId"), row.get("sceneId")) for row in active if isinstance(row, dict)}
    pending = [row for row in targets if (row["displayId"], row["sceneId"]) not in active_pairs]

    # The desktop session can become ready after the service starts.
    for _ in range(18):
        retry = []
        for target in pending:
            if stopping.is_set():
                return
            result = play_scene(instance, scene_id=target["sceneId"], display_id=target["displayId"])
            if result.get("ok"):
                continue
            error = str(result.get("error") or "unknown_error")
            LOG.warning("Media autoplay failed for scene %s: %s", target["sceneId"], error)
            if error in {"launch_failed", "process_exited"}:
                retry.append(target)
        if not retry or stopping.wait(5):
            return
        pending = retry
