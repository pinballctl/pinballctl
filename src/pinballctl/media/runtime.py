"""Media runtime: config persistence, shared asset helpers, and Godot-backed runtime access."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import time
import zipfile
from queue import Empty
from urllib.parse import urlencode
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, List
from uuid import uuid4

from pinballctl.events import get_bus

LAUNCH_MODE_FULLSCREEN = "fullscreen"
LAUNCH_MODE_WINDOWED = "windowed"
LAUNCH_MODE_EMBEDDED = "embedded"
DEFAULT_SCENE_STACK_BEHAVIOR = "replace"
STACK_BEHAVIOR_INTERRUPT = "interrupt"
STACK_BEHAVIOR_REPLACE = "replace"
STACK_BEHAVIOR_SCENE = "scene"
BLEND_MODE_PLAY_OVER = "PLAY_OVER"
BLEND_MODE_PAUSE_LOWER = "PAUSE_LOWER"
BLEND_MODE_STOP_LOWER = "STOP_LOWER"
TRANSITION_CUT = "CUT"
TRANSITION_FADE = "FADE"
TRANSITION_DISSOLVE = "DISSOLVE"
TRANSITION_ZOOM = "ZOOM"
INTERRUPT_ALLOW = "ALLOW"
INTERRUPT_NO_INTERRUPT = "NO_INTERRUPT"
INTERRUPT_RESTART = "RESTART"
INTERRUPT_QUEUE = "QUEUE"
DUPLICATE_ALLOW = "ALLOW"
DUPLICATE_DROP_IF_PLAYING = "DROP_IF_PLAYING"
DUPLICATE_DROP_IF_QUEUED = "DROP_IF_QUEUED"
DUPLICATE_COALESCE = "COALESCE"
MEDIA_AUDIO_APPLY = "MEDIA_AUDIO_APPLY"
MEDIA_AUDIO_RELEASE = "MEDIA_AUDIO_RELEASE"
EMBEDDED_SURFACE_STALE_MS = 60000
VIDEO_SOURCE_EXTS = {
    "mp4", "mkv", "webm", "mov", "m4v", "avi", "mpg", "mpeg", "wmv", "flv", "ts", "m2ts", "mts", "mxf", "ogv", "ogg",
}


def _normalize_scene_transition(raw: Any) -> Dict[str, Any]:
    transition = raw if isinstance(raw, dict) else {}
    typ = str(transition.get("type") or TRANSITION_CUT).strip().upper()
    if typ not in (TRANSITION_CUT, TRANSITION_FADE, TRANSITION_DISSOLVE, TRANSITION_ZOOM):
        typ = TRANSITION_CUT
    duration_ms = max(0, min(5000, int(float(transition.get("durationMs") or 0))))
    if typ == TRANSITION_CUT:
        duration_ms = 0
    return {"type": typ, "durationMs": duration_ms}


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _format_elapsed_mmss(total_ms: int) -> str:
    secs = max(0, int(total_ms // 1000))
    mm = secs // 60
    ss = secs % 60
    return f"{mm:02d}:{ss:02d}"


def _is_video_extension(ext: str) -> bool:
    return str(ext or "").strip().lower().lstrip(".") in VIDEO_SOURCE_EXTS


def _probe_video_duration_ms(path: Path) -> int:
    ffprobe_bin = str(shutil.which("ffprobe") or "").strip()
    if not ffprobe_bin or not path.exists():
        return 0
    try:
        proc = subprocess.run(
            [
                ffprobe_bin,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=5.0,
            check=False,
        )
        if proc.returncode != 0:
            return 0
        seconds = float(str(proc.stdout or "").strip() or 0.0)
        return max(0, int(seconds * 1000.0))
    except Exception:
        return 0


def _default_overlay_values() -> Dict[str, Any]:
    return {
        "player": "1",
        "score": "00000000",
        "ball": "1",
        "credit": "0",
        "game_elapsed_time": "00:00",
    }


def _media_dir(instance_path: str | Path) -> Path:
    p = Path(instance_path) / "media"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _media_assets_dir(instance_path: str | Path) -> Path:
    p = _media_dir(instance_path) / "assets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _media_fonts_dir(instance_path: str | Path) -> Path:
    p = _media_dir(instance_path) / "fonts"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _media_config_path(instance_path: str | Path) -> Path:
    return _media_dir(instance_path) / "media.json"


def _media_state_path(instance_path: str | Path) -> Path:
    return _media_dir(instance_path) / "media_state.json"


def _media_fonts_index_path(instance_path: str | Path) -> Path:
    return _media_fonts_dir(instance_path) / "fonts.json"


def _scoring_state_path(instance_path: str | Path) -> Path:
    return Path(instance_path) / "scoring" / "state.json"


def _load_scoring_state_nonblocking(instance_path: str | Path) -> Dict[str, Any]:
    """Best-effort scoring snapshot read without taking scoring runtime locks."""
    raw = _read_json(_scoring_state_path(instance_path), {})
    return raw if isinstance(raw, dict) else {}


def _safe_asset_name(raw_name: str) -> str:
    name = Path(raw_name or "media.bin").name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not safe:
        safe = f"media_{uuid4().hex[:8]}.bin"
    return safe


def _safe_font_name(raw_name: str) -> str:
    name = Path(raw_name or "font.ttf").name
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    if not safe.lower().endswith(".ttf"):
        safe = f"{Path(safe).stem or f'font_{uuid4().hex[:8]}'}.ttf"
    if not safe:
        safe = f"font_{uuid4().hex[:8]}.ttf"
    return safe


def _custom_font_family(font_id: str) -> str:
    return f"pinballctl_media_font_{re.sub(r'[^A-Za-z0-9_]+', '_', str(font_id or '').strip())}"


def _font_display_name_from_filename(filename: str) -> str:
    stem = Path(filename or "Font").stem
    pretty = stem.replace("_", " ").replace("-", " ").strip()
    pretty = re.sub(r"\s+", " ", pretty)
    return pretty or "Custom Font"


def _load_custom_fonts(instance_path: str | Path) -> List[Dict[str, Any]]:
    raw = _read_json(_media_fonts_index_path(instance_path), [])
    rows = raw if isinstance(raw, list) else []
    kept: List[Dict[str, Any]] = []
    changed = False
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            changed = True
            continue
        filename = str(row.get("filename") or "").strip()
        if not filename:
            changed = True
            continue
        path = _media_fonts_dir(instance_path) / filename
        if not path.exists():
            changed = True
            continue
        font_id = str(row.get("id") or f"font_{idx+1}").strip() or f"font_{idx+1}"
        kept.append(
            {
                "id": font_id,
                "name": str(row.get("name") or _font_display_name_from_filename(filename)).strip() or _font_display_name_from_filename(filename),
                "family": str(row.get("family") or _custom_font_family(font_id)).strip() or _custom_font_family(font_id),
                "filename": filename,
                "sizeBytes": max(0, int(float(row.get("sizeBytes") or path.stat().st_size))),
                "createdAt": str(row.get("createdAt") or _utc_now_iso()).strip() or _utc_now_iso(),
                "source": "custom",
            }
        )
    if changed:
        _write_json(_media_fonts_index_path(instance_path), kept)
    return kept


def _save_custom_fonts(instance_path: str | Path, rows: List[Dict[str, Any]]) -> None:
    _write_json(_media_fonts_index_path(instance_path), rows)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _normalize_launch_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode == LAUNCH_MODE_EMBEDDED:
        return LAUNCH_MODE_EMBEDDED
    if mode == LAUNCH_MODE_WINDOWED:
        return LAUNCH_MODE_WINDOWED
    return LAUNCH_MODE_FULLSCREEN


def _normalize_active_rows(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = int(float(row.get("pid") or 0))
        launch_mode = _normalize_launch_mode(row.get("launchMode"))
        display_id = str(row.get("displayId") or "").strip()
        scene_id = str(row.get("sceneId") or "").strip()
        if (pid <= 0 and launch_mode != LAUNCH_MODE_EMBEDDED) or not display_id or not scene_id:
            continue
        out.append(
            {
                "sceneId": scene_id,
                "displayId": display_id,
                "pid": max(0, pid),
                "startedAtMs": int(float(row.get("startedAtMs") or 0)),
                "runtimeUrl": str(row.get("runtimeUrl") or "").strip(),
                "launchMode": launch_mode,
                "previewViewport": (
                    {
                        "width": max(
                            1,
                            int(
                                float(
                                    ((row.get("previewViewport") or {}).get("width") if isinstance(row.get("previewViewport"), dict) else 0)
                                    or 0
                                )
                            ),
                        ),
                        "height": max(
                            1,
                            int(
                                float(
                                    ((row.get("previewViewport") or {}).get("height") if isinstance(row.get("previewViewport"), dict) else 0)
                                    or 0
                                )
                            ),
                        ),
                    }
                    if isinstance(row.get("previewViewport"), dict)
                    else None
                ),
            }
        )
    return out


def _normalize_stack_behavior(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode == STACK_BEHAVIOR_SCENE:
        return STACK_BEHAVIOR_SCENE
    if mode == STACK_BEHAVIOR_INTERRUPT:
        return STACK_BEHAVIOR_INTERRUPT
    return STACK_BEHAVIOR_REPLACE


def _normalize_session_rows(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        scene_id = str(row.get("sceneId") or "").strip()
        display_id = str(row.get("displayId") or "").strip()
        if not scene_id or not display_id:
            continue
        out.append(
            {
                "id": str(row.get("id") or f"session_{uuid4().hex[:10]}").strip() or f"session_{uuid4().hex[:10]}",
                "sceneId": scene_id,
                "displayId": display_id,
                "pid": max(0, int(float(row.get("pid") or 0))),
                "launchMode": _normalize_launch_mode(row.get("launchMode")),
                "runtimeUrl": str(row.get("runtimeUrl") or "").strip(),
                "startedAtMs": max(0, int(float(row.get("startedAtMs") or 0))),
                "lastSeenMs": max(0, int(float(row.get("lastSeenMs") or 0))),
                "previewViewport": (
                    {
                        "width": max(
                            1,
                            int(float(((row.get("previewViewport") or {}).get("width") if isinstance(row.get("previewViewport"), dict) else 0) or 0)),
                        ),
                        "height": max(
                            1,
                            int(float(((row.get("previewViewport") or {}).get("height") if isinstance(row.get("previewViewport"), dict) else 0) or 0)),
                        ),
                    }
                    if isinstance(row.get("previewViewport"), dict)
                    else None
                ),
                "stackBehavior": _normalize_stack_behavior(row.get("stackBehavior")),
                "source": str(row.get("source") or "").strip(),
                "priority": int(float(row.get("priority") or 100)),
                "blendMode": str(row.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper() if str(row.get("blendMode") or "").strip().upper() in (BLEND_MODE_PLAY_OVER, BLEND_MODE_PAUSE_LOWER, BLEND_MODE_STOP_LOWER) else BLEND_MODE_STOP_LOWER,
                "interruptPolicy": str(row.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper() if str(row.get("interruptPolicy") or "").strip().upper() in (INTERRUPT_ALLOW, INTERRUPT_NO_INTERRUPT, INTERRUPT_RESTART, INTERRUPT_QUEUE) else INTERRUPT_NO_INTERRUPT,
                "duplicatePolicy": str(row.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper() if str(row.get("duplicatePolicy") or "").strip().upper() in (DUPLICATE_ALLOW, DUPLICATE_DROP_IF_PLAYING, DUPLICATE_DROP_IF_QUEUED, DUPLICATE_COALESCE) else DUPLICATE_DROP_IF_PLAYING,
                "audioBehaviour": dict(row.get("audioBehaviour") if isinstance(row.get("audioBehaviour"), dict) else {}),
            }
        )
    return out


def _top_session_by_display(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    top: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        display_id = str(row.get("displayId") or "").strip()
        if not display_id:
            continue
        top[display_id] = row
    return top


def _scene_targets(scene: Dict[str, Any]) -> List[str]:
    screens = scene.get("screens") if isinstance(scene.get("screens"), list) else []
    out: List[str] = []
    for raw in screens:
        val = str(raw or "").strip()
        if val and val not in out:
            out.append(val)
    return out or ["backbox"]


def _display_matches_target(display: Dict[str, Any], target: str) -> bool:
    tgt = str(target or "").strip()
    if not tgt:
        return False
    return str(display.get("id") or "").strip() == tgt or str(display.get("role") or "").strip() == tgt


def _resolve_scene_displays(cfg: Dict[str, Any], scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    displays = [d for d in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(d, dict)]
    if not displays:
        displays = _default_displays()
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for target in _scene_targets(scene):
        match = next((d for d in displays if _display_matches_target(d, target)), None)
        if not match:
            continue
        did = str(match.get("id") or "").strip()
        if not did or did in seen:
            continue
        out.append(match)
        seen.add(did)
    if out:
        return out
    first = displays[0]
    return [first]


def _default_scene_for_display(cfg: Dict[str, Any], display_id: str) -> Dict[str, Any] | None:
    scenes = [s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if isinstance(s, dict)]
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    defaults_map = settings.get("defaultScenesByDisplay") if isinstance(settings.get("defaultScenesByDisplay"), dict) else {}
    default_scene_id = str(defaults_map.get(display_id) or "").strip()
    if default_scene_id:
        scene = next((s for s in scenes if str(s.get("id") or "") == default_scene_id), None)
        if isinstance(scene, dict):
            targets = _scene_targets(scene)
            if display_id in targets:
                return scene
    return None


def _autoplay_displays(cfg: Dict[str, Any]) -> Dict[str, bool]:
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    raw = settings.get("autoplayByDisplay") if isinstance(settings.get("autoplayByDisplay"), dict) else {}
    out: Dict[str, bool] = {}
    for key, value in raw.items():
        did = str(key or "").strip()
        if did:
            out[did] = bool(value)
    return out


def _default_displays() -> List[Dict[str, Any]]:
    return [
        {
            "id": "display_1",
            "name": "Primary Display",
            "width": 1920,
            "height": 1080,
            "x": 0,
            "y": 0,
            "role": "backbox",
            "enabled": True,
            "screenIndex": 1,
        }
    ]


def _default_config() -> Dict[str, Any]:
    return {
        "settings": {
            "enabled": True,
            "previewScale": 0.35,
            "windowScale": 0.25,
            "defaultDisplayRole": "backbox",
            "defaultScenesByDisplay": {},
            "autoplayByDisplay": {},
            "runtimePollMs": 150,
            "godot": {
                "binary": "",
                "port": 17342,
                "autoRestart": True,
                "debugVisible": True,
            },
        },
        "displays": _default_displays(),
        "assets": [],
        "scenes": [],
    }


def _normalize_scene_layer(layer: Dict[str, Any], idx: int) -> Dict[str, Any]:
    typ = str(layer.get("type") or "text").strip().lower()
    if typ == "badge":
        typ = "text"
    if typ == "frame":
        typ = "image"
    if typ not in ("text", "image", "video", "godot_scene"):
        typ = "text"
    bg_raw = str(layer.get("bgColor") or "transparent").strip()
    text_align = str(layer.get("textAlign") or "center").strip().lower()
    if text_align not in ("left", "center", "right"):
        text_align = "center"
    effects_allowed = {
        "shadow",
        "outline",
        "underline",
        "strike",
        "bold",
        "italic",
        "uppercase",
        "tracking",
        "glow",
    }
    text_effects_in = layer.get("textEffects")
    text_effects: List[str] = []
    if isinstance(text_effects_in, list):
        for raw in text_effects_in:
            eff = str(raw or "").strip().lower()
            if eff in effects_allowed and eff not in text_effects:
                text_effects.append(eff)
    out = {
        "id": str(layer.get("id") or f"layer_{idx+1}").strip() or f"layer_{idx+1}",
        "name": str(layer.get("name") or f"Layer {idx+1}").strip() or f"Layer {idx+1}",
        "type": typ,
        "text": str(layer.get("text") or "").strip(),
        "valueKey": str(layer.get("valueKey") or "").strip(),
        "textAlign": text_align,
        "textEffects": text_effects,
        "xPct": max(0.0, min(100.0, float(layer.get("xPct") or 0.0))),
        "yPct": max(0.0, min(100.0, float(layer.get("yPct") or 0.0))),
        "wPct": max(0.0, min(100.0, float(layer.get("wPct") or 20.0))),
        "hPct": max(0.0, min(100.0, float(layer.get("hPct") or 8.0))),
        "rotateDeg": float(layer.get("rotateDeg") or 0.0),
        "scale": max(0.1, min(8.0, float(layer.get("scale") or 1.0))),
        "opacity": max(0.0, min(1.0, float(layer.get("opacity") or 1.0))),
        "color": str(layer.get("color") or "#ffffff").strip() or "#ffffff",
        "bgColor": bg_raw if bg_raw else "transparent",
        "fontSizePx": max(8, min(256, int(float(layer.get("fontSizePx") or 28)))),
        "fontFamily": str(layer.get("fontFamily") or "").strip()[:160],
        "zIndex": max(0, min(9999, int(layer.get("zIndex") or 0))),
        "assetId": str(layer.get("assetId") or "").strip(),
        "sceneEntryPath": str(layer.get("sceneEntryPath") or "").strip(),
        "renderMode": "primary" if str(layer.get("renderMode") or "").strip().lower() == "primary" else "layered",
        "fit": str(layer.get("fit") or "contain").strip().lower() if str(layer.get("fit") or "").strip().lower() in ("cover", "contain", "fill", "none", "scale-down") else "contain",
    }
    if typ == "godot_scene" and out["renderMode"] == "primary":
        out["xPct"] = 0.0
        out["yPct"] = 0.0
        out["wPct"] = 100.0
        out["hPct"] = 100.0
        out["rotateDeg"] = 0.0
        out["opacity"] = 1.0
    if typ != "text":
        out["textEffects"] = []
    return out


def _normalize_scene(scene: Dict[str, Any], idx: int) -> Dict[str, Any]:
    screens_in = scene.get("screens") if isinstance(scene.get("screens"), list) else []
    layers_in = scene.get("layers") if isinstance(scene.get("layers"), list) else []
    screens: List[str] = []
    for raw in screens_in:
        scr = str(raw or "").strip()
        if scr and scr not in screens:
            screens.append(scr)
    if not screens:
        screens = ["backbox"]
    blend_mode = str(scene.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper()
    if blend_mode not in (BLEND_MODE_PLAY_OVER, BLEND_MODE_PAUSE_LOWER, BLEND_MODE_STOP_LOWER):
        blend_mode = BLEND_MODE_STOP_LOWER
    interrupt_policy = str(scene.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper()
    if interrupt_policy not in (INTERRUPT_ALLOW, INTERRUPT_NO_INTERRUPT, INTERRUPT_RESTART, INTERRUPT_QUEUE):
        interrupt_policy = INTERRUPT_NO_INTERRUPT
    duplicate_policy = str(scene.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper()
    if duplicate_policy not in (DUPLICATE_ALLOW, DUPLICATE_DROP_IF_PLAYING, DUPLICATE_DROP_IF_QUEUED, DUPLICATE_COALESCE):
        duplicate_policy = DUPLICATE_DROP_IF_PLAYING
    audio_raw = scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}
    queue_raw = scene.get("queue") if isinstance(scene.get("queue"), dict) else {}
    transition = _normalize_scene_transition(scene.get("transition"))
    def _audio_types(rows: Any) -> List[str]:
        allowed = {"music", "sfx", "voice", "ambient"}
        out: List[str] = []
        if isinstance(rows, list):
            for raw in rows:
                val = str(raw or "").strip().lower()
                if val in allowed and val not in out:
                    out.append(val)
        return out
    normalized_layers = [
        _normalize_scene_layer(layer, i)
        for i, layer in enumerate(layers_in)
        if isinstance(layer, dict)
    ]
    total_layers = len(normalized_layers)
    for layer_idx, layer in enumerate(normalized_layers):
        layer["zIndex"] = max(1, total_layers - layer_idx)
    return {
        "id": str(scene.get("id") or f"scene_{idx+1}").strip() or f"scene_{idx+1}",
        "name": str(scene.get("name") or f"Scene {idx+1}").strip() or f"Scene {idx+1}",
        "screens": screens,
        "priority": int(float(scene.get("priority") or 100)),
        "blendMode": blend_mode,
        "loop": bool(scene.get("loop", True)),
        "mute": bool(scene.get("mute", True)),
        "interruptPolicy": interrupt_policy,
        "duplicatePolicy": duplicate_policy,
        "cooldownMs": max(0, int(float(scene.get("cooldownMs") or 0))),
        "transition": transition,
        "audioBehaviour": {
            "pause": _audio_types(audio_raw.get("pause")),
            "duck": _audio_types(audio_raw.get("duck")),
            "allow": _audio_types(audio_raw.get("allow")) or ["music", "sfx", "voice", "ambient"],
            "resumeOnEnd": bool(audio_raw.get("resumeOnEnd", True)),
        },
        "queue": {
            "enabled": bool(queue_raw.get("enabled", interrupt_policy == INTERRUPT_QUEUE)),
            "maxLength": max(0, min(128, int(float(queue_raw.get("maxLength") or 8)))),
            "dedupe": bool(queue_raw.get("dedupe", True)),
        },
        "layers": normalized_layers,
    }


def normalize_media_config(cfg: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = cfg if isinstance(cfg, dict) else {}
    defaults = _default_config()
    settings_in = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    displays_in = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    assets_in = cfg.get("assets") if isinstance(cfg.get("assets"), list) else []
    scenes_in = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []

    default_scenes_raw = settings_in.get("defaultScenesByDisplay") if isinstance(settings_in.get("defaultScenesByDisplay"), dict) else {}
    default_scenes_by_display = {
        str(k).strip(): str(v).strip()
        for k, v in default_scenes_raw.items()
        if str(k).strip()
    }
    autoplay_raw = settings_in.get("autoplayByDisplay") if isinstance(settings_in.get("autoplayByDisplay"), dict) else {}
    autoplay_by_display = {
        str(k).strip(): bool(v)
        for k, v in autoplay_raw.items()
        if str(k).strip()
    }
    godot_in = settings_in.get("godot") if isinstance(settings_in.get("godot"), dict) else {}
    godot_settings = {
        "binary": str(godot_in.get("binary") or "").strip(),
        "port": max(1024, min(65535, int(float(godot_in.get("port") or 17342)))),
        "autoRestart": bool(godot_in.get("autoRestart", True)),
        "debugVisible": bool(godot_in.get("debugVisible", True)),
    }
    out = {
        "settings": {
            "enabled": bool(settings_in.get("enabled", defaults["settings"]["enabled"])),
            "previewScale": max(0.1, min(1.0, float(settings_in.get("previewScale", defaults["settings"]["previewScale"])))),
            "windowScale": max(0.05, min(1.0, float(settings_in.get("windowScale", defaults["settings"]["windowScale"])))),
            "defaultDisplayRole": str(settings_in.get("defaultDisplayRole") or defaults["settings"]["defaultDisplayRole"]).strip() or "backbox",
            "defaultScenesByDisplay": default_scenes_by_display,
            "autoplayByDisplay": autoplay_by_display,
            "runtimePollMs": max(40, min(5000, int(float(settings_in.get("runtimePollMs") or defaults["settings"]["runtimePollMs"])))),
            "godot": godot_settings,
        },
        "displays": [],
        "assets": [],
        "scenes": [],
    }

    for i, d in enumerate(displays_in):
        if not isinstance(d, dict):
            continue
        did = str(d.get("id") or f"display_{i+1}").strip() or f"display_{i+1}"
        out["displays"].append(
            {
                "id": did,
                "name": str(d.get("name") or did).strip() or did,
                "width": max(64, int(float(d.get("width") or 1920))),
                "height": max(64, int(float(d.get("height") or 1080))),
                "x": int(float(d.get("x") or 0)),
                "y": int(float(d.get("y") or 0)),
                "role": str(d.get("role") or "").strip() or ("backbox" if i == 0 else f"aux_{i+1}"),
                "enabled": bool(d.get("enabled", True)),
                "screenIndex": max(1, int(float(d.get("screenIndex") or (i + 1)))),
            }
        )
    if not out["displays"]:
        out["displays"] = _default_displays()

    for i, a in enumerate(assets_in):
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or f"asset_{uuid4().hex[:10]}").strip()
        if not aid:
            continue
        filename = str(a.get("filename") or "").strip()
        if not filename:
            continue
        ext = Path(filename).suffix.lower().lstrip(".")
        normalized_kind = str(a.get("kind") or "").strip().lower()
        if ext == "pck":
            normalized_kind = "godot_scene"
        elif not normalized_kind:
            normalized_kind = "video" if _is_video_extension(ext) else "image"
        out["assets"].append(
            {
                "id": aid,
                "displayName": str(a.get("displayName") or Path(filename).stem).strip() or Path(filename).stem,
                "filename": filename,
                "kind": normalized_kind,
                "sizeBytes": max(0, int(float(a.get("sizeBytes") or 0))),
                "durationMs": max(0, int(float(a.get("durationMs") or 0))),
                "createdAt": str(a.get("createdAt") or _utc_now_iso()),
                "sourceFormat": str(a.get("sourceFormat") or ext).strip().lower(),
                "playbackFormat": str(a.get("playbackFormat") or (ext if ext in ("ogv", "ogg", "pck") else ("ogv" if _is_video_extension(ext) else ext))).strip().lower(),
                "sceneEntries": [
                    str(entry or "").strip()
                    for entry in (a.get("sceneEntries") if isinstance(a.get("sceneEntries"), list) else [])
                    if str(entry or "").strip()
                ],
                "defaultSceneEntry": str(a.get("defaultSceneEntry") or "").strip(),
            }
        )

    for i, s in enumerate(scenes_in):
        if not isinstance(s, dict):
            continue
        out["scenes"].append(_normalize_scene(s, i))
    return out


def load_media_config(instance_path: str | Path) -> Dict[str, Any]:
    cfg = _read_json(_media_config_path(instance_path), _default_config())
    normalized = normalize_media_config(cfg)
    assets_dir = _media_assets_dir(instance_path)
    for asset in normalized.get("assets", []):
        if not isinstance(asset, dict):
            continue
        filename = str(asset.get("filename") or "").strip()
        if not filename:
            continue
        try:
            asset["sizeBytes"] = max(0, int((assets_dir / filename).stat().st_size))
        except Exception:
            asset["sizeBytes"] = max(0, int(float(asset.get("sizeBytes") or 0)))
        ext = Path(filename).suffix.lower().lstrip(".")
        asset["sourceFormat"] = str(asset.get("sourceFormat") or ext).strip().lower()
        if str(asset.get("kind") or "").strip().lower() == "video" and int(float(asset.get("durationMs") or 0)) <= 0:
            asset["durationMs"] = _probe_video_duration_ms(assets_dir / filename)
        try:
            from pinballctl.media import godot_runtime as _godot_runtime

            conversion = _godot_runtime.get_asset_conversion_status(instance_path, asset)
            if isinstance(conversion, dict):
                asset["conversion"] = conversion
                asset["playbackFormat"] = str(conversion.get("playbackFormat") or asset.get("playbackFormat") or "").strip().lower()
                asset["sourceFormat"] = str(conversion.get("originalFormat") or asset.get("sourceFormat") or "").strip().lower()
        except Exception:
            asset["conversion"] = asset.get("conversion") if isinstance(asset.get("conversion"), dict) else None
    return normalized


def save_media_config(instance_path: str | Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_media_config(cfg)
    _write_json(_media_config_path(instance_path), normalized)
    return normalized


def _detect_system_fonts() -> List[str]:
    fallback_fonts = [
        "Arial",
        "Helvetica",
        "Verdana",
        "Trebuchet MS",
        "Tahoma",
        "Times New Roman",
        "Georgia",
        "Courier New",
        "Monaco",
        "Menlo",
        "Noto Sans",
        "Noto Serif",
        "Roboto",
        "Ubuntu",
        "sans-serif",
        "serif",
        "monospace",
    ]
    fonts: set[str] = set()
    def add_name(raw: str) -> None:
        name = str(raw or "").strip()
        if not name:
            return
        name = re.sub(r"\s+", " ", name)
        if len(name) <= 1:
            return
        if name.startswith("."):
            return
        lowered = name.lower()
        if "lastresort" in lowered:
            return
        if lowered.endswith(" pua"):
            return
        fonts.add(name)

    try:
        if shutil.which("fc-list"):
            proc = subprocess.run(
                ["fc-list", "-f", "%{family}\n"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in (proc.stdout or "").splitlines():
                for name in [p.strip() for p in line.split(",")]:
                    add_name(name)
    except Exception:
        pass

    if not fonts and platform.system().lower() == "darwin" and shutil.which("system_profiler"):
        try:
            proc = subprocess.run(
                ["system_profiler", "SPFontsDataType"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
            )
            for line in (proc.stdout or "").splitlines():
                m = re.match(r"\s*Full Name:\s*(.+)\s*$", line)
                if m:
                    add_name(str(m.group(1) or ""))
        except Exception:
            pass

    if not fonts:
        font_dirs = []
        if platform.system().lower() == "darwin":
            font_dirs = [
                Path("/System/Library/Fonts"),
                Path("/Library/Fonts"),
                Path.home() / "Library/Fonts",
            ]
        elif platform.system().lower() == "linux":
            font_dirs = [
                Path("/usr/share/fonts"),
                Path("/usr/local/share/fonts"),
                Path.home() / ".fonts",
                Path.home() / ".local/share/fonts",
            ]
        exts = {".ttf", ".otf", ".ttc", ".dfont", ".woff", ".woff2"}
        for root in font_dirs:
            try:
                if not root.exists():
                    continue
                count = 0
                for fp in root.rglob("*"):
                    if fp.suffix.lower() not in exts:
                        continue
                    stem = fp.stem.replace("_", " ").replace("-", " ").strip()
                    add_name(stem)
                    count += 1
                    if count >= 800:
                        break
            except Exception:
                continue

    rows = sorted(fonts, key=lambda x: x.lower())
    if not rows:
        return fallback_fonts

    # Keep common cross-platform choices pinned near the top for easier UX.
    pinned = [f for f in fallback_fonts if f in rows]
    tail = [f for f in rows if f not in pinned]
    return (pinned + tail)[:300]


def _font_catalog(instance_path: str | Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_families: set[str] = set()
    for name in _detect_system_fonts():
        label = str(name or "").strip()
        if not label:
            continue
        family = label
        seen_families.add(family.lower())
        rows.append(
            {
                "id": f"system:{label}",
                "name": label,
                "family": family,
                "source": "system",
                "url": "",
            }
        )
    for row in _load_custom_fonts(instance_path):
        family = str(row.get("family") or "").strip()
        if not family:
            continue
        key = family.lower()
        if key in seen_families:
            continue
        seen_families.add(key)
        rows.append(
            {
                **row,
                "url": f"/api/media/fonts/file/{row['id']}",
            }
        )
    return rows


def get_media_environment(instance_path: str | Path) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.get_media_environment(instance_path)


def list_runtime_instances(instance_path: str | Path) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.list_runtime_instances(instance_path)


class _MediaRuntimeState:
    def __init__(self, instance_path: str | Path):
        self.instance_path = str(Path(instance_path).resolve())
        self._lock = Lock()
        self._loaded = False
        self._dirty = False
        self._last_disk_mtime_ns = -1
        self._overlay_values: Dict[str, Any] = _default_overlay_values()
        self._sessions: List[Dict[str, Any]] = []
        self._surface_sessions: List[Dict[str, Any]] = []
        self._queue: List[Dict[str, Any]] = []
        self._last_trigger_ms: Dict[str, int] = {}
        self._last_heartbeat_persist_ms = 0

    def _disk_mtime_ns_locked(self) -> int:
        path = _media_state_path(self.instance_path)
        try:
            return int(path.stat().st_mtime_ns)
        except Exception:
            return -1

    def _reload_locked(self, *, force: bool = False) -> None:
        disk_mtime_ns = self._disk_mtime_ns_locked()
        if not force and self._loaded:
            if self._dirty:
                return
            if disk_mtime_ns <= self._last_disk_mtime_ns:
                return
        persisted = _read_json(_media_state_path(self.instance_path), {"engine": {"active": []}, "overlayValues": {}, "sessions": [], "surfaceSessions": [], "queue": []})
        overlay_values = persisted.get("overlayValues") if isinstance(persisted, dict) and isinstance(persisted.get("overlayValues"), dict) else {}
        self._overlay_values = _default_overlay_values()
        self._overlay_values.update(overlay_values)
        self._sessions = _normalize_session_rows(persisted.get("sessions") if isinstance(persisted, dict) else [])
        self._surface_sessions = _normalize_session_rows(persisted.get("surfaceSessions") if isinstance(persisted, dict) else [])
        self._queue = _normalize_session_rows(persisted.get("queue") if isinstance(persisted, dict) else [])
        self._loaded = True
        self._dirty = False
        self._last_disk_mtime_ns = disk_mtime_ns

    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._reload_locked()

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._reload_locked()
            return {
                "overlayValues": dict(self._overlay_values),
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
            }

    def sweep_dead_surfaces(self) -> Dict[str, Any]:
        with self._lock:
            self._reload_locked()
            before = len(self._surface_sessions)
            now_ms = _now_ms()
            stale_embedded_displays: set[str] = set()
            kept_surfaces: List[Dict[str, Any]] = []
            for row in self._surface_sessions:
                mode = _normalize_launch_mode(row.get("launchMode"))
                if mode == LAUNCH_MODE_EMBEDDED:
                    last_seen = max(0, int(float(row.get("lastSeenMs") or 0)))
                    if last_seen > 0 and (now_ms - last_seen) > EMBEDDED_SURFACE_STALE_MS:
                        did = str(row.get("displayId") or "").strip()
                        if did:
                            stale_embedded_displays.add(did)
                        self._clear_trigger_for_locked(
                            scene_id=str(row.get("sceneId") or ""),
                            display_id=did,
                        )
                        continue
                    kept_surfaces.append(row)
                    continue
                kept_surfaces.append(row)
            self._surface_sessions = kept_surfaces
            if stale_embedded_displays:
                self._sessions = [
                    row for row in self._sessions
                    if not (
                        str(row.get("displayId") or "").strip() in stale_embedded_displays
                        and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
                    )
                ]
            removed = max(0, before - len(self._surface_sessions))
            if removed > 0:
                self._dirty = True
            return {
                "removed": removed,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
            }

    def prune_inactive_process_sessions(self, active_rows: List[Dict[str, Any]] | None) -> Dict[str, Any]:
        live_pids = set()
        for row in active_rows or []:
            pid = max(0, int(float(row.get("pid") or 0)))
            if pid <= 0:
                continue
            live_pids.add(pid)
        with self._lock:
            self._reload_locked()
            before = len(self._surface_sessions)
            self._surface_sessions = [
                row for row in self._surface_sessions
                if _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
                or _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_WINDOWED
                or max(0, int(float(row.get("pid") or 0))) in live_pids
            ]
            removed = max(0, before - len(self._surface_sessions))
            tracked_displays = {
                str(row.get("displayId") or "").strip()
                for row in self._surface_sessions
                if _normalize_launch_mode(row.get("launchMode")) in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_FULLSCREEN)
            }
            self._sessions = [
                row for row in self._sessions
                if str(row.get("displayId") or "").strip() in tracked_displays or _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
            ]
            self._dirty = True
            return {
                "ok": True,
                "removed": removed,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
            }

    def set_overlay_values(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        clean_updates = {str(k).strip(): v for k, v in updates.items() if str(k).strip()} if isinstance(updates, dict) else {}
        with self._lock:
            self._reload_locked()
            self._overlay_values.update(clean_updates)
            self._dirty = True
            return dict(self._overlay_values)

    def set_overlay_value(self, key: str, value: Any) -> Dict[str, Any]:
        return self.set_overlay_values({str(key or "").strip(): value})

    def _replace_surface_locked(self, row: Dict[str, Any]) -> Dict[str, Any]:
        launch_mode = _normalize_launch_mode(row.get("launchMode"))
        display_id = str(row.get("displayId") or "").strip()
        row_id = str(row.get("id") or "").strip()
        if launch_mode in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_FULLSCREEN):
            self._surface_sessions = [
                existing
                for existing in self._surface_sessions
                if not (
                    str(existing.get("displayId") or "").strip() == display_id
                    and _normalize_launch_mode(existing.get("launchMode")) == launch_mode
                )
            ]
        elif row_id:
            self._surface_sessions = [
                existing for existing in self._surface_sessions if str(existing.get("id") or "").strip() != row_id
            ]
        self._surface_sessions.append(dict(row))
        return dict(row)

    def _surface_for_display_locked(self, display_id: str, launch_mode: str) -> Dict[str, Any] | None:
        mode = _normalize_launch_mode(launch_mode)
        did = str(display_id or "").strip()
        return next(
            (
                dict(row)
                for row in self._surface_sessions
                if str(row.get("displayId") or "").strip() == did
                and _normalize_launch_mode(row.get("launchMode")) == mode
            ),
            None,
        )

    def _sync_display_surface_locked(
        self,
        display_id: str,
        launch_mode: str,
        *,
        pid: int | None = None,
        runtime_url: str | None = None,
        surface_id: str | None = None,
    ) -> Dict[str, Any] | None:
        did = str(display_id or "").strip()
        mode = _normalize_launch_mode(launch_mode)
        top = _top_session_by_display(self._sessions).get(did)
        existing = self._surface_for_display_locked(did, mode)
        if not top:
            self._surface_sessions = [
                row for row in self._surface_sessions
                if not (
                    str(row.get("displayId") or "").strip() == did
                    and _normalize_launch_mode(row.get("launchMode")) == mode
                )
            ]
            return None
        row = {
            **top,
            "id": str(surface_id or (existing.get("id") if isinstance(existing, dict) else "") or f"surface_{mode}_{did}"),
            "launchMode": mode,
            "pid": max(0, int(pid if pid is not None else (existing.get("pid") if isinstance(existing, dict) else 0) or 0)),
            "runtimeUrl": str(runtime_url or (existing.get("runtimeUrl") if isinstance(existing, dict) else top.get("runtimeUrl") or "")),
            "lastSeenMs": max(0, int((existing.get("lastSeenMs") if isinstance(existing, dict) else _now_ms()) or _now_ms())),
        }
        return self._replace_surface_locked(row)

    def _clear_trigger_for_locked(self, *, scene_id: str, display_id: str) -> None:
        key = f"{str(display_id or '').strip()}:{str(scene_id or '').strip()}"
        if key in self._last_trigger_ms:
            self._last_trigger_ms.pop(key, None)

    def display_session_rows(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._reload_locked()
            return [dict(row) for row in self._sessions]

    def surface_rows(self) -> List[Dict[str, Any]]:
        with self._lock:
            self._reload_locked()
            return [dict(row) for row in self._surface_sessions]

    def touch_surface(self, session_id: str) -> bool:
        sid = str(session_id or "").strip()
        if not sid:
            return False
        now_ms = _now_ms()
        should_persist = False
        with self._lock:
            self._reload_locked()
            for row in self._surface_sessions:
                if str(row.get("id") or "").strip() != sid:
                    continue
                row["lastSeenMs"] = now_ms
                self._dirty = True
                if (now_ms - int(self._last_heartbeat_persist_ms or 0)) >= 1000:
                    self._last_heartbeat_persist_ms = now_ms
                    should_persist = True
                return should_persist
        return False

    def touch_embedded_surface(self, display_id: str) -> bool:
        did = str(display_id or "").strip()
        if not did:
            return False
        now_ms = _now_ms()
        touched = False
        should_persist = False
        with self._lock:
            self._reload_locked()
            for row in self._surface_sessions:
                if _normalize_launch_mode(row.get("launchMode")) != LAUNCH_MODE_EMBEDDED:
                    continue
                if str(row.get("displayId") or "").strip() != did:
                    continue
                row["lastSeenMs"] = now_ms
                touched = True
            if touched:
                self._dirty = True
                if (now_ms - int(self._last_heartbeat_persist_ms or 0)) >= 1000:
                    self._last_heartbeat_persist_ms = now_ms
                    should_persist = True
        return should_persist

    def play_display_scene(
        self,
        *,
        scene_id: str,
        display_id: str,
        launch_mode: str,
        runtime_url: str,
        preview_viewport: Dict[str, int] | None,
        stack_behavior: str,
        source: str = "",
        priority: int = 100,
        blend_mode: str = BLEND_MODE_STOP_LOWER,
        interrupt_policy: str = INTERRUPT_NO_INTERRUPT,
        duplicate_policy: str = DUPLICATE_DROP_IF_PLAYING,
        cooldown_ms: int = 0,
        audio_behaviour: Dict[str, Any] | None = None,
        queue_enabled: bool = False,
        queue_max_length: int = 8,
        queue_dedupe: bool = True,
    ) -> Dict[str, Any]:
        now_ms = _now_ms()
        behavior = _normalize_stack_behavior(stack_behavior)
        mode = _normalize_launch_mode(launch_mode)
        max_queue_length = max(0, int(queue_max_length or 0))
        with self._lock:
            self._reload_locked()
            target_rows = list(self._sessions)
            trigger_key = f"{display_id}:{scene_id}"
            last_ms = int(self._last_trigger_ms.get(trigger_key) or 0)
            if cooldown_ms > 0 and last_ms > 0 and (now_ms - last_ms) < cooldown_ms:
                return {"ok": True, "dropped": True, "reason": "cooldown", "displayId": display_id, "sceneId": scene_id}
            active_matching = [
                row for row in target_rows
                if str(row.get("displayId") or "") == display_id
                and str(row.get("sceneId") or "") == scene_id
            ]
            queued_matching = [
                row for row in self._queue
                if str(row.get("displayId") or "") == display_id
                and str(row.get("sceneId") or "") == scene_id
            ]
            if duplicate_policy == DUPLICATE_COALESCE:
                if active_matching:
                    self._last_trigger_ms[trigger_key] = now_ms
                    return {"ok": True, "reused": True, "coalesced": True, "reason": "coalesced_playing", "displayId": display_id, "sceneId": scene_id}
                if queued_matching:
                    queued = queued_matching[-1]
                    queued["startedAtMs"] = now_ms
                    queued["runtimeUrl"] = runtime_url
                    queued["previewViewport"] = preview_viewport if isinstance(preview_viewport, dict) else None
                    self._last_trigger_ms[trigger_key] = now_ms
                    self._dirty = True
                    return {"ok": True, "queued": True, "coalesced": True, "reason": "coalesced_queued", "displayId": display_id, "sceneId": scene_id, "queueDepth": len(self._queue)}
            if duplicate_policy == DUPLICATE_DROP_IF_PLAYING and active_matching:
                return {"ok": True, "reused": True, "reason": "duplicate_playing", "displayId": display_id, "sceneId": scene_id}
            if duplicate_policy == DUPLICATE_DROP_IF_QUEUED and queued_matching:
                return {"ok": True, "queued": True, "reason": "duplicate_queued", "displayId": display_id, "sceneId": scene_id}
            if interrupt_policy == INTERRUPT_NO_INTERRUPT and active_matching:
                return {"ok": True, "reused": True, "reason": "no_interrupt", "displayId": display_id, "sceneId": scene_id}
            if interrupt_policy == INTERRUPT_QUEUE and active_matching:
                if not queue_enabled:
                    return {"ok": True, "reused": True, "reason": "queue_disabled", "displayId": display_id, "sceneId": scene_id}
                if queue_dedupe and queued_matching:
                    return {"ok": True, "queued": True, "reason": "queue_deduped", "displayId": display_id, "sceneId": scene_id, "queueDepth": len(self._queue)}
                if max_queue_length >= 0:
                    scene_queue_depth = sum(
                        1
                        for row in self._queue
                        if str(row.get("displayId") or "") == display_id
                        and str(row.get("sceneId") or "") == scene_id
                    )
                    if scene_queue_depth >= max_queue_length:
                        return {"ok": True, "dropped": True, "reason": "queue_full", "displayId": display_id, "sceneId": scene_id, "queueDepth": scene_queue_depth}
                row = {
                    "id": f"session_{uuid4().hex[:10]}",
                    "sceneId": scene_id,
                    "displayId": display_id,
                    "launchMode": mode,
                    "runtimeUrl": runtime_url,
                    "startedAtMs": now_ms,
                    "previewViewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                    "stackBehavior": behavior,
                    "source": str(source or "").strip(),
                    "priority": int(priority),
                    "blendMode": str(blend_mode or BLEND_MODE_STOP_LOWER),
                    "interruptPolicy": str(interrupt_policy or INTERRUPT_NO_INTERRUPT),
                    "duplicatePolicy": str(duplicate_policy or DUPLICATE_DROP_IF_PLAYING),
                    "audioBehaviour": dict(audio_behaviour or {}),
                }
                self._queue.append(row)
                self._last_trigger_ms[trigger_key] = now_ms
                self._dirty = True
                return {"ok": True, "queued": True, "displayId": display_id, "sceneId": scene_id, "queueDepth": len(self._queue)}
            if interrupt_policy == INTERRUPT_RESTART and active_matching:
                target_rows = [
                    row for row in target_rows
                    if not (
                        str(row.get("displayId") or "") == display_id
                        and str(row.get("sceneId") or "") == scene_id
                    )
                ]
            if str(blend_mode or BLEND_MODE_STOP_LOWER) == BLEND_MODE_STOP_LOWER:
                target_rows = [
                    row for row in target_rows
                    if not (
                        str(row.get("displayId") or "") == display_id
                        and int(row.get("priority") or 100) < int(priority)
                    )
                ]
            if behavior == STACK_BEHAVIOR_REPLACE:
                target_rows = [
                    row for row in target_rows
                    if not (
                        str(row.get("displayId") or "") == display_id
                    )
                ]
            else:
                target_rows = [
                    row for row in target_rows
                    if not (
                        str(row.get("displayId") or "") == display_id
                        and str(row.get("sceneId") or "") == scene_id
                    )
                ]
            row = {
                "id": f"session_{uuid4().hex[:10]}",
                "sceneId": scene_id,
                "displayId": display_id,
                "launchMode": mode,
                "runtimeUrl": runtime_url,
                "startedAtMs": now_ms,
                "lastSeenMs": now_ms,
                "previewViewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                "stackBehavior": behavior,
                "source": str(source or "").strip(),
                "priority": int(priority),
                "blendMode": str(blend_mode or BLEND_MODE_STOP_LOWER),
                "interruptPolicy": str(interrupt_policy or INTERRUPT_NO_INTERRUPT),
                "duplicatePolicy": str(duplicate_policy or DUPLICATE_DROP_IF_PLAYING),
                "audioBehaviour": dict(audio_behaviour or {}),
            }
            target_rows.append(row)
            self._sessions = target_rows
            self._last_trigger_ms[trigger_key] = now_ms
            self._dirty = True
            return dict(row)

    def upsert_display_surface(
        self,
        *,
        display_id: str,
        launch_mode: str,
        pid: int = 0,
        runtime_url: str | None = None,
        surface_id: str | None = None,
    ) -> Dict[str, Any] | None:
        with self._lock:
            self._reload_locked()
            row = self._sync_display_surface_locked(
                display_id,
                launch_mode,
                pid=pid,
                runtime_url=runtime_url,
                surface_id=surface_id,
            )
            self._dirty = True
            return dict(row) if isinstance(row, dict) else None

    def add_window_surface(
        self,
        *,
        surface_id: str | None = None,
        scene_id: str,
        display_id: str,
        runtime_url: str,
        preview_viewport: Dict[str, int] | None,
        pid: int,
        source: str = "",
        priority: int = 100,
        blend_mode: str = BLEND_MODE_STOP_LOWER,
        audio_behaviour: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        now_ms = _now_ms()
        with self._lock:
            self._reload_locked()
            self._surface_sessions = [
                existing for existing in self._surface_sessions
                if not (
                    _normalize_launch_mode(existing.get("launchMode")) == LAUNCH_MODE_WINDOWED
                    and str(existing.get("displayId") or "").strip() == str(display_id or "").strip()
                    and str(existing.get("sceneId") or "").strip() == str(scene_id or "").strip()
                )
            ]
            row = {
                "id": str(surface_id or f"surface_windowed_{uuid4().hex[:10]}"),
                "sceneId": str(scene_id or "").strip(),
                "displayId": str(display_id or "").strip(),
                "pid": max(0, int(pid or 0)),
                "launchMode": LAUNCH_MODE_WINDOWED,
                "runtimeUrl": str(runtime_url or "").strip(),
                "startedAtMs": now_ms,
                "lastSeenMs": now_ms,
                "previewViewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                "stackBehavior": STACK_BEHAVIOR_REPLACE,
                "source": str(source or "").strip(),
                "priority": int(priority),
                "blendMode": str(blend_mode or BLEND_MODE_STOP_LOWER),
                "interruptPolicy": INTERRUPT_ALLOW,
                "duplicatePolicy": DUPLICATE_ALLOW,
                "audioBehaviour": dict(audio_behaviour or {}),
            }
            self._surface_sessions.append(row)
            self._dirty = True
            return dict(row)

    def stop_display_scene(self, scene_id: str | None = None, *, display_id: str | None = None) -> Dict[str, Any]:
        with self._lock:
            self._reload_locked()
            stopped = 0
            target_display_ids: set[str] = set()
            new_sessions: List[Dict[str, Any]] = []
            for row in self._sessions:
                row_scene = str(row.get("sceneId") or "")
                row_display = str(row.get("displayId") or "")
                match = (not scene_id or row_scene == str(scene_id)) and (not display_id or row_display == str(display_id))
                if match:
                    stopped += 1
                    if row_display:
                        target_display_ids.add(row_display)
                    self._clear_trigger_for_locked(scene_id=row_scene, display_id=row_display)
                    continue
                new_sessions.append(row)
            self._sessions = new_sessions
            if scene_id or display_id:
                self._queue = [
                    row for row in self._queue
                    if not (
                        (not scene_id or str(row.get("sceneId") or "") == str(scene_id))
                        and (not display_id or str(row.get("displayId") or "") == str(display_id))
                    )
                ]
            else:
                self._queue = []
                self._sessions = []
                self._last_trigger_ms = {}
                target_display_ids.update(
                    str(row.get("displayId") or "").strip()
                    for row in self._surface_sessions
                    if _normalize_launch_mode(row.get("launchMode")) in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_FULLSCREEN)
                )
            for did in sorted({str(row.get("displayId") or "") for row in self._queue if str(row.get("displayId") or "")}):
                if any(str(row.get("displayId") or "") == did for row in self._sessions):
                    continue
                queued = next((row for row in self._queue if str(row.get("displayId") or "") == did), None)
                if queued:
                    self._queue.remove(queued)
                    self._sessions.append(queued)
                    target_display_ids.add(did)
            for did in target_display_ids:
                self._sync_display_surface_locked(did, LAUNCH_MODE_EMBEDDED)
                self._sync_display_surface_locked(did, LAUNCH_MODE_FULLSCREEN)
            self._dirty = True
            return {
                "stopped": stopped,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
            }

    def stop_surface(self, session_id: str) -> Dict[str, Any]:
        target_id = str(session_id or "").strip()
        with self._lock:
            self._reload_locked()
            target = next((dict(row) for row in self._surface_sessions if str(row.get("id") or "").strip() == target_id), None)
            if not isinstance(target, dict):
                return {"ok": False, "error": "surface_not_found"}
            launch_mode = _normalize_launch_mode(target.get("launchMode"))
            if launch_mode == LAUNCH_MODE_WINDOWED:
                self._surface_sessions = [
                    row for row in self._surface_sessions if str(row.get("id") or "").strip() != target_id
                ]
                self._clear_trigger_for_locked(
                    scene_id=str(target.get("sceneId") or ""),
                    display_id=str(target.get("displayId") or ""),
                )
            else:
                did = str(target.get("displayId") or "").strip()
                self._sessions = [
                    row for row in self._sessions
                    if str(row.get("displayId") or "").strip() != did
                ]
                self._queue = [
                    row for row in self._queue
                    if str(row.get("displayId") or "").strip() != did
                ]
                self._clear_trigger_for_locked(
                    scene_id=str(target.get("sceneId") or ""),
                    display_id=did,
                )
                self._sync_display_surface_locked(did, LAUNCH_MODE_EMBEDDED)
                self._sync_display_surface_locked(did, LAUNCH_MODE_FULLSCREEN)
            self._dirty = True
            return {
                "ok": True,
                "surface": target,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
            }

    def detach_surface(self, session_id: str) -> Dict[str, Any]:
        target_id = str(session_id or "").strip()
        if not target_id:
            return {"ok": False, "error": "missing_session_id"}
        with self._lock:
            self._reload_locked()
            target = next((dict(row) for row in self._surface_sessions if str(row.get("id") or "").strip() == target_id), None)
            if not isinstance(target, dict):
                return {"ok": False, "error": "surface_not_found"}
            mode = _normalize_launch_mode(target.get("launchMode"))
            did = str(target.get("displayId") or "").strip()
            sid = str(target.get("sceneId") or "").strip()
            self._surface_sessions = [
                row for row in self._surface_sessions if str(row.get("id") or "").strip() != target_id
            ]
            if mode == LAUNCH_MODE_EMBEDDED and did:
                self._sessions = [
                    row for row in self._sessions
                    if not (
                        str(row.get("displayId") or "").strip() == did
                        and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
                    )
                ]
            self._clear_trigger_for_locked(scene_id=sid, display_id=did)
            self._dirty = True
            return {
                "ok": True,
                "surface": target,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
            }

    def clear_all(self) -> Dict[str, Any]:
        with self._lock:
            self._reload_locked()
            self._sessions = []
            self._surface_sessions = []
            self._queue = []
            self._dirty = True
            return {
                "ok": True,
                "sessions": [],
                "surfaceSessions": [],
                "queue": [],
            }

    def detach_embedded_surface(self, display_id: str) -> Dict[str, Any]:
        did = str(display_id or "").strip()
        if not did:
            return {"ok": False, "error": "missing_display_id"}
        with self._lock:
            self._reload_locked()
            self._surface_sessions = [
                row for row in self._surface_sessions
                if not (
                    str(row.get("displayId") or "").strip() == did
                    and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
                )
            ]
            self._sessions = [
                row for row in self._sessions
                if not (
                    str(row.get("displayId") or "").strip() == did
                    and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_EMBEDDED
                )
            ]
            self._clear_trigger_for_locked(scene_id="", display_id=did)
            self._dirty = True
            return {
                "ok": True,
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
            }

    def stop_scene(self, scene_id: str | None = None, *, session_id: str | None = None, display_id: str | None = None) -> Dict[str, Any]:
        if session_id and not scene_id and not display_id:
            result = self.stop_surface(str(session_id))
            if result.get("ok"):
                result["stopped"] = 1
            return result
        return self.stop_display_scene(scene_id=scene_id, display_id=display_id)

    def complete_session(self, *, display_id: str, session_id: str | None = None, scene_id: str | None = None) -> Dict[str, Any]:
        with self._lock:
            self._reload_locked()
            target = None
            ordered = [row for row in self._sessions if str(row.get("displayId") or "") == str(display_id)]
            ordered.sort(key=lambda row: (int(row.get("priority") or 100), int(row.get("startedAtMs") or 0)))
            for row in reversed(ordered):
                if session_id and str(row.get("id") or "") != str(session_id):
                    continue
                if scene_id and str(row.get("sceneId") or "") != str(scene_id):
                    continue
                target = row
                break
            promoted = None
            if target is not None:
                self._sessions = [row for row in self._sessions if str(row.get("id") or "") != str(target.get("id") or "")]
                if not any(str(row.get("displayId") or "") == str(display_id) for row in self._sessions):
                    queued = next((row for row in self._queue if str(row.get("displayId") or "") == str(display_id)), None)
                    if queued:
                        self._queue.remove(queued)
                        self._sessions.append(queued)
                        promoted = dict(queued)
                self._sync_display_surface_locked(str(display_id), LAUNCH_MODE_EMBEDDED)
                self._sync_display_surface_locked(str(display_id), LAUNCH_MODE_FULLSCREEN)
            else:
                surface_target = None
                for row in reversed(self._surface_sessions):
                    if str(row.get("displayId") or "") != str(display_id):
                        continue
                    if session_id and str(row.get("id") or "") != str(session_id):
                        continue
                    if scene_id and str(row.get("sceneId") or "") != str(scene_id):
                        continue
                    surface_target = row
                    break
                if surface_target is None:
                    return {"ok": False, "error": "session_not_found"}
                target = surface_target
                self._surface_sessions = [row for row in self._surface_sessions if str(row.get("id") or "") != str(surface_target.get("id") or "")]
            self._dirty = True
            return {
                "ok": True,
                "completed": dict(target),
                "sessions": [dict(row) for row in self._sessions],
                "surfaceSessions": [dict(row) for row in self._surface_sessions],
                "queue": [dict(row) for row in self._queue],
                "promoted": promoted,
            }

    def mark_persisted(self) -> None:
        with self._lock:
            self._dirty = False
            self._loaded = True
            self._last_disk_mtime_ns = self._disk_mtime_ns_locked()


_RUNTIMES: Dict[str, _MediaRuntimeState] = {}
_RUNTIMES_LOCK = Lock()
_BUS_WORKERS: Dict[str, Dict[str, Any]] = {}
_BUS_WORKERS_LOCK = Lock()


def _get_runtime_state(instance_path: str | Path) -> _MediaRuntimeState:
    key = str(Path(instance_path).resolve())
    with _RUNTIMES_LOCK:
        runtime = _RUNTIMES.get(key)
        if runtime is None:
            runtime = _MediaRuntimeState(key)
            _RUNTIMES[key] = runtime
        return runtime


def _persist_runtime_snapshot(instance_path: str | Path) -> Dict[str, Any]:
    runtime = _get_runtime_state(instance_path)
    state = runtime.snapshot()
    payload = _read_json(_media_state_path(instance_path), {"engine": {"active": []}, "overlayValues": {}, "sessions": [], "queue": []})
    if not isinstance(payload, dict):
        payload = {"engine": {"active": []}, "overlayValues": {}, "sessions": [], "queue": []}
    payload["overlayValues"] = state.get("overlayValues", {})
    payload["sessions"] = state.get("sessions", [])
    payload["surfaceSessions"] = state.get("surfaceSessions", [])
    payload["queue"] = state.get("queue", [])
    payload["updatedAt"] = _utc_now_iso()
    _write_json(_media_state_path(instance_path), payload)
    runtime.mark_persisted()
    return payload


def run_media_maintenance(instance_path: str | Path) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.run_media_maintenance(instance_path)


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.process_event(instance_path, name=name, source=source, params=params)


def _media_bus_loop(*, instance_path: str, stop_evt: Event, logger: Callable[[str], None] | None = None) -> None:
    bus = get_bus()
    q = bus.subscribe()
    last_maintenance_ms = 0
    try:
        while not stop_evt.is_set():
            try:
                ev = q.get(timeout=0.5)
            except Empty:
                now_ms = _now_ms()
                if (now_ms - last_maintenance_ms) >= 1000:
                    last_maintenance_ms = now_ms
                    try:
                        run_media_maintenance(instance_path)
                    except Exception as exc:
                        if logger is not None:
                            try:
                                logger(f"media maintenance failed: {exc}")
                            except Exception:
                                pass
                continue
            try:
                process_event(instance_path, name=ev.name, source=ev.source, params=ev.params)
            except Exception as exc:
                if logger is not None:
                    try:
                        logger(f"media bus processing failed: {exc}")
                    except Exception:
                        pass
    finally:
        bus.unsubscribe(q)


def ensure_media_bus_worker(instance_path: str | Path, logger: Callable[[str], None] | None = None) -> None:
    inst = str(Path(instance_path).resolve())
    with _BUS_WORKERS_LOCK:
        existing = _BUS_WORKERS.get(inst)
        if isinstance(existing, dict):
            t = existing.get("thread")
            if isinstance(t, Thread) and t.is_alive():
                return
        stop_evt = Event()
        worker = Thread(
            target=_media_bus_loop,
            kwargs={"instance_path": inst, "stop_evt": stop_evt, "logger": logger},
            daemon=True,
            name=f"media-bus-{Path(inst).name}",
        )
        _BUS_WORKERS[inst] = {"thread": worker, "stop_evt": stop_evt}
        worker.start()


def list_media_fonts(instance_path: str | Path) -> List[Dict[str, Any]]:
    return _font_catalog(instance_path)


def upload_media_fonts(instance_path: str | Path, file_storage: Any) -> Dict[str, Any]:
    filename = str(getattr(file_storage, "filename", "") or "").strip()
    if not filename:
        return {"ok": False, "error": "missing_file_name"}
    suffix = Path(filename).suffix.lower()
    if suffix not in (".ttf", ".zip"):
        return {"ok": False, "error": "unsupported_font_upload"}

    fonts_dir = _media_fonts_dir(instance_path)
    existing = _load_custom_fonts(instance_path)
    created: List[Dict[str, Any]] = []

    def add_font_bytes(raw_name: str, payload: bytes) -> None:
        safe_name = _safe_font_name(raw_name)
        target = fonts_dir / safe_name
        if target.exists():
            target = target.with_name(f"{target.stem}_{uuid4().hex[:6]}{target.suffix}")
        target.write_bytes(payload)
        font_id = f"font_{uuid4().hex[:10]}"
        name = _font_display_name_from_filename(target.name)
        row = {
            "id": font_id,
            "name": name,
            "family": _custom_font_family(font_id),
            "filename": target.name,
            "sizeBytes": max(0, int(target.stat().st_size)),
            "createdAt": _utc_now_iso(),
            "source": "custom",
        }
        existing.append(row)
        created.append(row)

    try:
        if suffix == ".ttf":
            add_font_bytes(filename, file_storage.read())
        else:
            with zipfile.ZipFile(file_storage.stream) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    inner_name = str(info.filename or "").strip()
                    if Path(inner_name).suffix.lower() != ".ttf":
                        continue
                    with zf.open(info) as src:
                        add_font_bytes(Path(inner_name).name, src.read())
    except zipfile.BadZipFile:
        return {"ok": False, "error": "invalid_zip"}
    except Exception:
        return {"ok": False, "error": "font_upload_failed"}

    if not created:
        return {"ok": False, "error": "no_ttf_files_found"}

    _save_custom_fonts(instance_path, existing)
    return {"ok": True, "fonts": created}


def get_media_font_file(instance_path: str | Path, font_id: str) -> Dict[str, Any]:
    row = next((f for f in _load_custom_fonts(instance_path) if str(f.get("id") or "") == str(font_id)), None)
    if not isinstance(row, dict):
        return {"ok": False, "error": "font_not_found"}
    path = _media_fonts_dir(instance_path) / str(row.get("filename") or "")
    if not path.exists():
        return {"ok": False, "error": "font_not_found"}
    return {"ok": True, "path": str(path), "font": row}


def delete_media_font(instance_path: str | Path, font_id: str) -> Dict[str, Any]:
    rows = _load_custom_fonts(instance_path)
    keep: List[Dict[str, Any]] = []
    removed: Dict[str, Any] | None = None
    for row in rows:
        if removed is None and str(row.get("id") or "") == str(font_id):
            removed = row
            continue
        keep.append(row)
    if not isinstance(removed, dict):
        return {"ok": False, "error": "font_not_found"}
    path = _media_fonts_dir(instance_path) / str(removed.get("filename") or "")
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
    _save_custom_fonts(instance_path, keep)
    return {"ok": True, "font": removed}


def media_fonts_stylesheet(instance_path: str | Path, *, runtime_token: str | None = None) -> str:
    lines: List[str] = []
    for row in _load_custom_fonts(instance_path):
        font_id = str(row.get("id") or "").strip()
        family = str(row.get("family") or "").strip()
        if not font_id or not family:
            continue
        url = f"/api/media/fonts/file/{font_id}"
        if str(runtime_token or "").strip():
            url = f"{url}?{urlencode({'kiosk_token': str(runtime_token).strip()})}"
        lines.append(
            "@font-face{"
            f"font-family:'{family}';"
            f"src:url('{url}') format('truetype');"
            "font-style:normal;"
            "font-weight:400;"
            "font-display:swap;"
            "}"
        )
    return "\n".join(lines)


def _extract_godot_scene_entries_from_pack(pack_path: str | Path) -> List[str]:
    path = Path(pack_path)
    try:
        raw = path.read_bytes()
    except Exception:
        return []
    if not raw.startswith(b"GDPC"):
        return []
    entries = {
        match.decode("utf-8", errors="ignore")
        for match in re.findall(rb"res://[A-Za-z0-9_./-]+\.tscn", raw)
    }
    return sorted(entries, key=lambda item: (item.count("/"), item.lower()))


def upload_asset(instance_path: str | Path, file_storage: Any, display_name: str | None = None) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    filename = _safe_asset_name(str(getattr(file_storage, "filename", "") or "media.bin"))
    target = _media_assets_dir(instance_path) / filename
    if target.exists():
        target = target.with_name(f"{target.stem}_{uuid4().hex[:6]}{target.suffix}")
    file_storage.save(str(target))
    ext = target.suffix.lower().lstrip(".")
    kind = "godot_scene" if ext == "pck" else ("video" if _is_video_extension(ext) else "image")
    scene_entries: List[str] = []
    default_scene_entry = ""
    if kind == "godot_scene":
        scene_entries = _extract_godot_scene_entries_from_pack(target)
        default_scene_entry = scene_entries[0] if scene_entries else ""
    row = {
        "id": f"asset_{uuid4().hex[:10]}",
        "displayName": str(display_name or target.stem).strip() or target.stem,
        "filename": target.name,
        "kind": kind,
        "sizeBytes": max(0, int(target.stat().st_size)),
        "durationMs": _probe_video_duration_ms(target) if kind == "video" else 0,
        "createdAt": _utc_now_iso(),
        "sourceFormat": ext,
        "playbackFormat": ext if ext in ("ogv", "ogg", "pck") else ("ogv" if kind == "video" else ext),
        "sceneEntries": scene_entries,
        "defaultSceneEntry": default_scene_entry,
    }
    cfg_assets = [a for a in cfg.get("assets", []) if isinstance(a, dict)]
    cfg_assets.append(row)
    cfg["assets"] = cfg_assets
    save_media_config(instance_path, cfg)
    try:
        if kind == "video":
            from pinballctl.media import godot_runtime as _godot_runtime

            _godot_runtime._ensure_godot_video_derivative(instance_path, row, target)
    except Exception:
        LOGGER.exception("godot asset derivative generation failed: %s", target)
    return {"ok": True, "asset": row}


def delete_asset(instance_path: str | Path, asset_id: str) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    assets = [a for a in cfg.get("assets", []) if isinstance(a, dict)]
    keep = []
    removed = None
    for a in assets:
        if str(a.get("id") or "") == str(asset_id) and removed is None:
            removed = a
            continue
        keep.append(a)
    if not removed:
        return {"ok": False, "error": "asset_not_found"}

    file_path = _media_assets_dir(instance_path) / str(removed.get("filename") or "")
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass
    try:
        from pinballctl.media import godot_runtime as _godot_runtime

        safe_asset = _godot_runtime._safe_key(str(removed.get("id") or ""), "asset")
        cache_dir = _godot_runtime._godot_cache_assets_dir(instance_path)
        cleanup_paths = [
            _godot_runtime._video_conversion_target_path(instance_path, str(removed.get("id") or "")),
            _godot_runtime._video_conversion_lock_path(instance_path, str(removed.get("id") or "")),
            _godot_runtime._video_conversion_progress_path(instance_path, str(removed.get("id") or "")),
            _godot_runtime._video_conversion_log_path(instance_path, str(removed.get("id") or "")),
        ]
        cleanup_paths.extend(cache_dir.glob(f"{safe_asset}.*"))
        for path in cleanup_paths:
            if path.exists():
                path.unlink()
    except Exception:
        LOGGER.exception("godot asset derivative cleanup failed: %s", removed.get("id"))

    cfg["assets"] = keep
    cfg["scenes"] = [
        {
            **s,
            "layers": [
                {
                    **layer,
                    "assetId": "" if str(layer.get("assetId") or "") == str(asset_id) else str(layer.get("assetId") or ""),
                }
                for layer in (s.get("layers") if isinstance(s.get("layers"), list) else [])
                if isinstance(layer, dict)
            ],
        }
        for s in cfg.get("scenes", [])
        if isinstance(s, dict)
    ]
    save_media_config(instance_path, cfg)
    return {"ok": True}


def get_asset_file(instance_path: str | Path, asset_id: str) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    asset = next((a for a in cfg.get("assets", []) if str(a.get("id") or "") == str(asset_id)), None)
    if not asset:
        return {"ok": False, "error": "not_found"}
    path = _media_assets_dir(instance_path) / str(asset.get("filename") or "")
    if not path.exists():
        return {"ok": False, "error": "missing"}
    return {"ok": True, "path": path, "asset": asset}


def load_media_state(instance_path: str | Path, *, persist: bool = True) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.load_media_state(instance_path, persist=persist)


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    *,
    display_id: str | None = None,
    base_url: str | None = None,
    runtime_token: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    preview_viewport: Dict[str, int] | None = None,
    stack_behavior: str = DEFAULT_SCENE_STACK_BEHAVIOR,
    event_source: str = "",
    force_play: bool = False,
) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.play_scene(
        instance_path,
        scene_id,
        display_id=display_id,
        base_url=base_url,
        runtime_token=runtime_token,
        launch_mode=launch_mode,
        preview_viewport=preview_viewport,
        stack_behavior=stack_behavior,
        event_source=event_source,
        force_play=force_play,
    )


def stop_scene(instance_path: str | Path, scene_id: str | None = None, session_id: str | None = None) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.stop_scene(instance_path, scene_id=scene_id, session_id=session_id)


def set_overlay_value(instance_path: str | Path, key: str, value: Any) -> Dict[str, Any]:
    if not str(key or "").strip():
        return {"ok": False, "error": "missing_key"}
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.update_text(instance_path, str(key).strip(), value)


def complete_scene(
    instance_path: str | Path,
    *,
    display_id: str,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.complete_scene(instance_path, display_id=display_id, session_id=session_id, scene_id=scene_id)


def detach_embedded_surface(instance_path: str | Path, display_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    runtime = _get_runtime_state(instance_path)
    result = runtime.detach_embedded_surface(str(display_id or "").strip())
    if result.get("ok"):
        _persist_runtime_snapshot(instance_path)
    return result


def detach_surface(instance_path: str | Path, session_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    runtime = _get_runtime_state(instance_path)
    result = runtime.detach_surface(str(session_id or "").strip())
    if result.get("ok"):
        _persist_runtime_snapshot(instance_path)
    return result


def _asset_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(a.get("id") or ""): a
        for a in (cfg.get("assets") if isinstance(cfg.get("assets"), list) else [])
        if isinstance(a, dict) and str(a.get("id") or "")
    }


def _scene_visual_layers(scene: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = scene.get("layers") if isinstance(scene.get("layers"), list) else []
    layers = [dict(row) for row in rows if isinstance(row, dict)]
    total_layers = len(layers)
    for idx, layer in enumerate(layers):
        layer["zIndex"] = max(1, total_layers - idx)
    return layers


def _resolved_scene(scene: Dict[str, Any], assets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    visual_layers: List[Dict[str, Any]] = []
    for layer in _scene_visual_layers(scene):
        asset_id = str(layer.get("assetId") or "").strip()
        if asset_id:
            asset = assets_by_id.get(asset_id)
            if isinstance(asset, dict):
                layer["asset"] = asset
        visual_layers.append(layer)
    return {**scene, "layers": visual_layers}


def _scene_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    assets_by_id = _asset_map(cfg)
    return {
        str(s.get("id") or ""): _resolved_scene(s, assets_by_id)
        for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else [])
        if isinstance(s, dict) and str(s.get("id") or "")
    }


def _primary_media_layer(scene: Dict[str, Any]) -> Dict[str, Any] | None:
    media_layers = [
        layer for layer in _scene_visual_layers(scene)
        if str(layer.get("type") or "").strip().lower() in {"image", "video"}
        and str(layer.get("assetId") or "").strip()
    ]
    if not media_layers:
        return None
    media_layers.sort(key=lambda row: (int(row.get("zIndex") or 0), str(row.get("id") or "")))
    return dict(media_layers[-1])


def _primary_media_asset(scene: Dict[str, Any], assets_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any] | None:
    primary_layer = _primary_media_layer(scene)
    if not isinstance(primary_layer, dict):
        return None
    asset_id = str(primary_layer.get("assetId") or "").strip()
    asset = assets_by_id.get(asset_id)
    return dict(asset) if isinstance(asset, dict) else None


def _render_layers_for_display(cfg: Dict[str, Any], display_id: str, session_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes_by_id = _scene_map(cfg)
    assets_by_id = _asset_map(cfg)
    autoplay_map = _autoplay_displays(cfg)
    now_ms = _now_ms()
    rows = [row for row in session_rows if str(row.get("displayId") or "") == str(display_id)]

    def _render_order_key(row: Dict[str, Any]) -> tuple[int, int, int]:
        return (
            int(row.get("priority") or 100),
            max(0, int(row.get("launchOrder") or 0)),
            int(row.get("startedAtMs") or 0),
        )

    rows.sort(key=_render_order_key)

    if not rows:
        fallback_scene = _default_scene_for_display(cfg, display_id) if bool(autoplay_map.get(str(display_id), False)) else None
        if fallback_scene:
            asset = _primary_media_asset(fallback_scene, assets_by_id)
            if asset:
                return [{
                    "layerId": f"fallback:{display_id}:{fallback_scene.get('id')}",
                    "sessionId": "",
                    "scene": fallback_scene,
                    "asset": asset,
                    "priority": int(fallback_scene.get("priority") or 0),
                    "blendMode": BLEND_MODE_PLAY_OVER,
                    "state": "playing",
                    "fallback": True,
                    "launchMode": LAUNCH_MODE_FULLSCREEN,
                    "startedAtMs": 0,
                }]
        return []

    stop_lower_rows = [
        row for row in rows
        if str(row.get("blendMode") or "") == BLEND_MODE_STOP_LOWER
    ]
    stop_lower_cutoffs = [_render_order_key(row) for row in stop_lower_rows]
    top_stop_lower = bool(stop_lower_cutoffs)
    stop_lower_transition_active = False
    stop_lower_transition_anchor_ms = 0
    stop_lower_transition: Dict[str, Any] = {"type": TRANSITION_CUT, "durationMs": 0}
    if stop_lower_cutoffs:
        top_stop_row = max(stop_lower_rows, key=_render_order_key)
        top_stop_scene = scenes_by_id.get(str(top_stop_row.get("sceneId") or ""))
        if isinstance(top_stop_scene, dict):
            stop_lower_transition = _normalize_scene_transition(top_stop_scene.get("transition"))
        stop_lower_transition_anchor_ms = int(top_stop_row.get("startedAtMs") or 0)
        stop_lower_transition_active = (
            stop_lower_transition["durationMs"] > 0
            and stop_lower_transition["type"] != TRANSITION_CUT
            and stop_lower_transition_anchor_ms > 0
            and (now_ms - stop_lower_transition_anchor_ms) < int(stop_lower_transition["durationMs"])
        )
        cutoff = max(stop_lower_cutoffs)
        if not stop_lower_transition_active:
            rows = [row for row in rows if _render_order_key(row) >= cutoff]
    layers: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        scene = scenes_by_id.get(str(row.get("sceneId") or ""))
        if not isinstance(scene, dict):
            continue
        asset = _primary_media_asset(scene, assets_by_id)
        if not isinstance(asset, dict):
            continue
        row_order = _render_order_key(row)
        transition = _normalize_scene_transition(scene.get("transition"))
        transition_anchor_ms = int(row.get("startedAtMs") or 0)
        transition_in_active = (
            transition["durationMs"] > 0
            and transition["type"] != TRANSITION_CUT
            and transition_anchor_ms > 0
            and (now_ms - transition_anchor_ms) < int(transition["durationMs"])
        )
        paused = any(
            _render_order_key(other) > row_order
            and str(other.get("blendMode") or "") == BLEND_MODE_PAUSE_LOWER
            for other in rows
        )
        outgoing = (
            stop_lower_transition_active
            and bool(stop_lower_cutoffs)
            and row_order < max(stop_lower_cutoffs)
        )
        layer_transition = {
            "type": transition["type"],
            "durationMs": int(transition["durationMs"]),
            "phase": "in" if transition_in_active and not outgoing else ("out" if outgoing else ""),
            "anchorMs": transition_anchor_ms if transition_in_active and not outgoing else stop_lower_transition_anchor_ms if outgoing else 0,
        }
        if outgoing:
            layer_transition["type"] = str(stop_lower_transition.get("type") or TRANSITION_CUT)
            layer_transition["durationMs"] = int(stop_lower_transition.get("durationMs") or 0)
        layers.append(
            {
                "layerId": str(row.get("id") or f"layer_{idx+1}"),
                "sessionId": str(row.get("id") or ""),
                "scene": scene,
                "asset": asset,
                "priority": int(row.get("priority") or scene.get("priority") or 100),
                "blendMode": str(row.get("blendMode") or scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
                "state": "paused" if paused else "playing",
                "fallback": False,
                "launchMode": _normalize_launch_mode(row.get("launchMode")),
                "startedAtMs": int(row.get("startedAtMs") or 0),
                "transition": layer_transition,
                "audioBehaviour": dict(row.get("audioBehaviour") if isinstance(row.get("audioBehaviour"), dict) else scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}),
            }
        )

    if not top_stop_lower and bool(autoplay_map.get(str(display_id), False)):
        fallback_scene = _default_scene_for_display(cfg, display_id)
        if fallback_scene and not any(str(layer.get("scene", {}).get("id") or "") == str(fallback_scene.get("id") or "") for layer in layers):
            asset = _primary_media_asset(fallback_scene, assets_by_id)
            if asset:
                paused = any(str(layer.get("blendMode") or "") == BLEND_MODE_PAUSE_LOWER for layer in layers)
                layers.insert(
                    0,
                    {
                        "layerId": f"fallback:{display_id}:{fallback_scene.get('id')}",
                        "sessionId": "",
                        "scene": fallback_scene,
                        "asset": asset,
                        "priority": int(fallback_scene.get("priority") or 0),
                        "blendMode": BLEND_MODE_PLAY_OVER,
                        "state": "paused" if paused else "playing",
                        "fallback": True,
                        "launchMode": LAUNCH_MODE_FULLSCREEN,
                        "startedAtMs": 0,
                        "transition": {"type": TRANSITION_CUT, "durationMs": 0, "phase": "", "anchorMs": 0},
                    },
                )

    layers.sort(key=lambda row: (int(row.get("priority") or 0), int(row.get("startedAtMs") or 0)))
    for idx, layer in enumerate(layers):
        layer["renderOrder"] = idx + 1
    return layers


def _render_scene_stack_for_display(cfg: Dict[str, Any], display_id: str, session_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes_by_id = _scene_map(cfg)
    assets_by_id = _asset_map(cfg)
    autoplay_map = _autoplay_displays(cfg)
    now_ms = _now_ms()
    rows = [row for row in session_rows if str(row.get("displayId") or "") == str(display_id)]

    def _render_order_key(row: Dict[str, Any]) -> tuple[int, int, int]:
        return (
            int(row.get("priority") or 100),
            max(0, int(row.get("launchOrder") or 0)),
            int(row.get("startedAtMs") or 0),
        )

    rows.sort(key=_render_order_key)

    if not rows:
        fallback_scene = _default_scene_for_display(cfg, display_id) if bool(autoplay_map.get(str(display_id), False)) else None
        if isinstance(fallback_scene, dict):
            return [{
                "layerId": f"fallback:{display_id}:{fallback_scene.get('id')}",
                "sessionId": "",
                "scene": fallback_scene,
                "asset": _primary_media_asset(fallback_scene, assets_by_id),
                "priority": int(fallback_scene.get("priority") or 0),
                "blendMode": BLEND_MODE_PLAY_OVER,
                "state": "playing",
                "fallback": True,
                "launchMode": LAUNCH_MODE_FULLSCREEN,
                "startedAtMs": 0,
                "transition": {"type": TRANSITION_CUT, "durationMs": 0, "phase": "", "anchorMs": 0},
                "audioBehaviour": dict(fallback_scene.get("audioBehaviour") if isinstance(fallback_scene.get("audioBehaviour"), dict) else {}),
            }]
        return []

    stop_lower_rows = [
        row for row in rows
        if str(row.get("blendMode") or "") == BLEND_MODE_STOP_LOWER
    ]
    stop_lower_cutoffs = [_render_order_key(row) for row in stop_lower_rows]
    top_stop_lower = bool(stop_lower_cutoffs)
    stop_lower_transition_active = False
    stop_lower_transition_anchor_ms = 0
    stop_lower_transition: Dict[str, Any] = {"type": TRANSITION_CUT, "durationMs": 0}
    if stop_lower_cutoffs:
        top_stop_row = max(stop_lower_rows, key=_render_order_key)
        top_stop_scene = scenes_by_id.get(str(top_stop_row.get("sceneId") or ""))
        if isinstance(top_stop_scene, dict):
            stop_lower_transition = _normalize_scene_transition(top_stop_scene.get("transition"))
        stop_lower_transition_anchor_ms = int(top_stop_row.get("startedAtMs") or 0)
        stop_lower_transition_active = (
            stop_lower_transition["durationMs"] > 0
            and stop_lower_transition["type"] != TRANSITION_CUT
            and stop_lower_transition_anchor_ms > 0
            and (now_ms - stop_lower_transition_anchor_ms) < int(stop_lower_transition["durationMs"])
        )
        cutoff = max(stop_lower_cutoffs)
        if not stop_lower_transition_active:
            rows = [row for row in rows if _render_order_key(row) >= cutoff]

    stack_rows: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        scene = scenes_by_id.get(str(row.get("sceneId") or ""))
        if not isinstance(scene, dict):
            continue
        row_order = _render_order_key(row)
        transition = _normalize_scene_transition(scene.get("transition"))
        transition_anchor_ms = int(row.get("startedAtMs") or 0)
        transition_in_active = (
            transition["durationMs"] > 0
            and transition["type"] != TRANSITION_CUT
            and transition_anchor_ms > 0
            and (now_ms - transition_anchor_ms) < int(transition["durationMs"])
        )
        paused = any(
            _render_order_key(other) > row_order
            and str(other.get("blendMode") or "") == BLEND_MODE_PAUSE_LOWER
            for other in rows
        )
        outgoing = (
            stop_lower_transition_active
            and bool(stop_lower_cutoffs)
            and row_order < max(stop_lower_cutoffs)
        )
        layer_transition = {
            "type": transition["type"],
            "durationMs": int(transition["durationMs"]),
            "phase": "in" if transition_in_active and not outgoing else ("out" if outgoing else ""),
            "anchorMs": transition_anchor_ms if transition_in_active and not outgoing else stop_lower_transition_anchor_ms if outgoing else 0,
        }
        if outgoing:
            layer_transition["type"] = str(stop_lower_transition.get("type") or TRANSITION_CUT)
            layer_transition["durationMs"] = int(stop_lower_transition.get("durationMs") or 0)
        stack_rows.append(
            {
                "layerId": str(row.get("id") or f"layer_{idx+1}"),
                "sessionId": str(row.get("id") or ""),
                "scene": scene,
                "asset": _primary_media_asset(scene, assets_by_id),
                "priority": int(row.get("priority") or scene.get("priority") or 100),
                "blendMode": str(row.get("blendMode") or scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
                "state": "paused" if paused else "playing",
                "fallback": False,
                "launchMode": _normalize_launch_mode(row.get("launchMode")),
                "startedAtMs": int(row.get("startedAtMs") or 0),
                "transition": layer_transition,
                "audioBehaviour": dict(row.get("audioBehaviour") if isinstance(row.get("audioBehaviour"), dict) else scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}),
            }
        )

    if not top_stop_lower and bool(autoplay_map.get(str(display_id), False)):
        fallback_scene = _default_scene_for_display(cfg, display_id)
        if fallback_scene and not any(str(entry.get("scene", {}).get("id") or "") == str(fallback_scene.get("id") or "") for entry in stack_rows):
            paused = any(str(entry.get("blendMode") or "") == BLEND_MODE_PAUSE_LOWER for entry in stack_rows)
            stack_rows.insert(
                0,
                {
                    "layerId": f"fallback:{display_id}:{fallback_scene.get('id')}",
                    "sessionId": "",
                    "scene": fallback_scene,
                    "asset": _primary_media_asset(fallback_scene, assets_by_id),
                    "priority": int(fallback_scene.get("priority") or 0),
                    "blendMode": BLEND_MODE_PLAY_OVER,
                    "state": "paused" if paused else "playing",
                    "fallback": True,
                    "launchMode": LAUNCH_MODE_FULLSCREEN,
                    "startedAtMs": 0,
                    "transition": {"type": TRANSITION_CUT, "durationMs": 0, "phase": "", "anchorMs": 0},
                    "audioBehaviour": dict(fallback_scene.get("audioBehaviour") if isinstance(fallback_scene.get("audioBehaviour"), dict) else {}),
                },
            )

    stack_rows.sort(key=lambda row: (int(row.get("priority") or 0), int(row.get("startedAtMs") or 0)))
    for idx, row in enumerate(stack_rows):
        row["renderOrder"] = idx + 1
    return stack_rows


def _top_audio_layer_for_display(cfg: Dict[str, Any], display_id: str, session_rows: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    layers = _render_layers_for_display(cfg, display_id, session_rows)
    if not layers:
        return None
    return layers[-1] if isinstance(layers[-1], dict) else None


def _top_audio_intents_by_display(cfg: Dict[str, Any], session_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    known_ids = []
    for row in displays:
        if not isinstance(row, dict):
            continue
        did = str(row.get("id") or "").strip()
        if did and did not in known_ids:
            known_ids.append(did)
    for row in session_rows:
        if not isinstance(row, dict):
            continue
        did = str(row.get("displayId") or "").strip()
        if did and did not in known_ids:
            known_ids.append(did)
    out: Dict[str, Dict[str, Any]] = {}
    for display_id in known_ids:
        top = _top_audio_layer_for_display(cfg, display_id, session_rows)
        if not top:
            continue
        scene = top.get("scene") if isinstance(top.get("scene"), dict) else {}
        audio = top.get("audioBehaviour") if isinstance(top.get("audioBehaviour"), dict) else scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}
        out[display_id] = {
            "displayId": display_id,
            "sceneId": str(scene.get("id") or ""),
            "layerId": str(top.get("layerId") or ""),
            "priority": int(top.get("priority") or scene.get("priority") or 0),
            "blendMode": str(top.get("blendMode") or scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
            "audioBehaviour": dict(audio or {}),
            "fallback": bool(top.get("fallback")),
        }
    return out


def _emit_media_audio_intent_changes(instance_path: str | Path, cfg: Dict[str, Any], before_sessions: List[Dict[str, Any]] | None, after_sessions: List[Dict[str, Any]] | None) -> None:
    before = _top_audio_intents_by_display(cfg, _normalize_session_rows(before_sessions))
    after = _top_audio_intents_by_display(cfg, _normalize_session_rows(after_sessions))
    bus = get_bus()
    for display_id in sorted(set(before.keys()) | set(after.keys())):
        prev = before.get(display_id)
        nxt = after.get(display_id)
        prev_key = (str(prev.get("sceneId") or ""), str(prev.get("layerId") or "")) if prev else ("", "")
        next_key = (str(nxt.get("sceneId") or ""), str(nxt.get("layerId") or "")) if nxt else ("", "")
        if prev_key == next_key:
            continue
        if prev and prev_key != ("", ""):
            bus.emit(
                name=MEDIA_AUDIO_RELEASE,
                source="pi.media",
                params={
                    "displayId": display_id,
                    "sceneId": str(prev.get("sceneId") or ""),
                    "layerId": str(prev.get("layerId") or ""),
                    "priority": int(prev.get("priority") or 0),
                    "blendMode": str(prev.get("blendMode") or BLEND_MODE_STOP_LOWER),
                    "audioBehaviour": dict(prev.get("audioBehaviour") or {}),
                    "resumeOnEnd": bool((prev.get("audioBehaviour") or {}).get("resumeOnEnd", True)),
                    "fallback": bool(prev.get("fallback")),
                },
            )
        if nxt and next_key != ("", ""):
            bus.emit(
                name=MEDIA_AUDIO_APPLY,
                source="pi.media",
                params={
                    "displayId": display_id,
                    "sceneId": str(nxt.get("sceneId") or ""),
                    "layerId": str(nxt.get("layerId") or ""),
                    "priority": int(nxt.get("priority") or 0),
                    "blendMode": str(nxt.get("blendMode") or BLEND_MODE_STOP_LOWER),
                    "audioBehaviour": dict(nxt.get("audioBehaviour") or {}),
                    "resumeOnEnd": bool((nxt.get("audioBehaviour") or {}).get("resumeOnEnd", True)),
                    "fallback": bool(nxt.get("fallback")),
                },
            )


def runtime_display_payload(
    instance_path: str | Path,
    display_id: str,
    scene_id: str | None = None,
    *,
    session_id: str | None = None,
    surface_type: str | None = None,
    instance_id: str | None = None,
    surface_id: str | None = None,
) -> Dict[str, Any]:
    from pinballctl.media import godot_runtime as _godot_runtime

    return _godot_runtime.runtime_display_payload(
        instance_path,
        display_id,
        scene_id=scene_id,
        session_id=session_id,
        surface_type=surface_type,
        instance_id=instance_id,
        surface_id=surface_id,
    )


def attach_runtime_surface(instance_path: str | Path, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    del instance_path, instance_id, surface_id
    return {"ok": False, "error": "html_runtime_removed"}


def heartbeat_runtime_surface(instance_path: str | Path, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    del instance_path, instance_id, surface_id
    return {"ok": False, "error": "html_runtime_removed"}
