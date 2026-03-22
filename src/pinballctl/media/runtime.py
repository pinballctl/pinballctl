"""Media runtime: config persistence, display detection, and Chromium scene playback."""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
import signal
import subprocess
import time
import zipfile
from queue import Empty
from urllib.parse import urlencode, urlparse, parse_qs
from dataclasses import dataclass
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
BLEND_MODE_PLAY_OVER = "PLAY_OVER"
BLEND_MODE_PAUSE_LOWER = "PAUSE_LOWER"
BLEND_MODE_STOP_LOWER = "STOP_LOWER"
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


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _format_elapsed_mmss(total_ms: int) -> str:
    secs = max(0, int(total_ms // 1000))
    mm = secs // 60
    ss = secs % 60
    return f"{mm:02d}:{ss:02d}"


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


def _media_profiles_dir(instance_path: str | Path) -> Path:
    p = _media_dir(instance_path) / "chromium_profiles"
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


def _is_pid_alive(pid: int) -> bool:
    if int(pid or 0) <= 0:
        return False
    # Treat zombie/defunct processes as dead so runtime rows are cleaned up.
    try:
        stat_proc = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(int(pid))],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if stat_proc.returncode == 0:
            stat_txt = str(stat_proc.stdout or "").strip().upper()
            if "Z" in stat_txt:
                return False
    except Exception:
        pass
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


def _list_media_process_commands(instance_path: str | Path) -> List[tuple[int, str]]:
    out: List[tuple[int, str]] = []
    profiles_dir = str(_media_profiles_dir(instance_path)).replace("\\", "/")
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
        if proc.returncode != 0:
            return out
        for raw in str(proc.stdout or "").splitlines():
            line = str(raw or "").strip()
            if not line:
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            try:
                pid = int(parts[0])
            except Exception:
                continue
            cmd = parts[1].strip()
            cmd_norm = cmd.replace("\\", "/")
            if (profiles_dir and profiles_dir in cmd_norm) or ("/media/runtime/display/" in cmd_norm and "--app=" in cmd_norm):
                out.append((pid, cmd))
    except Exception:
        return []
    return out


def _surface_process_alive(instance_path: str | Path, surface_row: Dict[str, Any]) -> bool:
    pid = max(0, int(float(surface_row.get("pid") or 0)))
    if pid > 0 and _is_pid_alive(pid) and _is_managed_media_pid(instance_path, pid):
        return True
    sid = str(surface_row.get("id") or "").strip()
    runtime_url = str(surface_row.get("runtimeUrl") or "").strip()
    for _, cmd in _list_media_process_commands(instance_path):
        if sid and f"sessionId={sid}" in cmd:
            return True
        if runtime_url and runtime_url in cmd:
            return True
    return False


def _stop_pid(pid: int) -> bool:
    target = int(pid or 0)
    if target <= 0:
        return False
    stopped = False
    try:
        os.killpg(os.getpgid(target), signal.SIGTERM)
        stopped = True
    except Exception:
        try:
            os.kill(target, signal.SIGTERM)
            stopped = True
        except Exception:
            pass
    time.sleep(0.25)
    if _is_pid_alive(target):
        # On macOS, prefer non-destructive stop behavior to avoid Chrome crash dialogs.
        if platform.system().lower() == "darwin":
            deadline = time.time() + 1.5
            while time.time() < deadline and _is_pid_alive(target):
                time.sleep(0.1)
            return stopped
        try:
            os.killpg(os.getpgid(target), signal.SIGKILL)
            stopped = True
        except Exception:
            try:
                os.kill(target, signal.SIGKILL)
                stopped = True
            except Exception:
                pass
    return stopped


def _is_managed_media_pid(instance_path: str | Path, pid: int) -> bool:
    """True only for browser processes launched by pinballctl media runtime."""
    target = int(pid or 0)
    if target <= 0:
        return False
    # Inspect process argv using /proc on Linux; fallback to `ps` on macOS/other.
    cmdline = ""
    proc_cmd = Path(f"/proc/{target}/cmdline")
    try:
        if proc_cmd.exists():
            raw = proc_cmd.read_bytes()
            cmdline = raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
    except Exception:
        cmdline = ""
    if not cmdline:
        try:
            proc = subprocess.run(
                ["ps", "-o", "command=", "-p", str(target)],
                capture_output=True,
                text=True,
                timeout=0.5,
                check=False,
            )
            if proc.returncode == 0:
                cmdline = str(proc.stdout or "").strip()
        except Exception:
            cmdline = ""
    if not cmdline:
        return False

    profiles_dir = str(_media_profiles_dir(instance_path)).replace("\\", "/")
    cmdline_norm = cmdline.replace("\\", "/")
    # Require either explicit pinballctl media profile usage OR explicit media runtime URL.
    if profiles_dir and profiles_dir in cmdline_norm:
        return True
    if "/media/runtime/display/" in cmdline_norm and "--app=" in cmdline_norm:
        return True
    return False


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
            "renderer": "chromium",
            "previewScale": 0.35,
            "windowScale": 0.25,
            "defaultDisplayRole": "backbox",
            "defaultScenesByDisplay": {},
            "autoplayByDisplay": {},
            "runtimePollMs": 150,
        },
        "displays": _default_displays(),
        "assets": [],
        "overlays": [],
        "scenes": [],
    }


def _normalize_layer(layer: Dict[str, Any], idx: int) -> Dict[str, Any]:
    typ = str(layer.get("type") or "text").strip().lower()
    if typ == "badge":
        typ = "text"
    if typ == "frame":
        typ = "image"
    if typ not in ("text", "image"):
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
        "zIndex": max(0, min(9999, idx + 1)),
        "assetId": str(layer.get("assetId") or "").strip(),
        "fit": str(layer.get("fit") or "contain").strip().lower() if str(layer.get("fit") or "").strip().lower() in ("cover", "contain", "fill", "none", "scale-down") else "contain",
    }
    if typ != "text":
        out["textEffects"] = []
    return out


def _normalize_overlay(overlay: Dict[str, Any], idx: int) -> Dict[str, Any]:
    layers_in = overlay.get("layers") if isinstance(overlay.get("layers"), list) else []
    normalized_layers = [_normalize_layer(layer, i) for i, layer in enumerate(layers_in) if isinstance(layer, dict)]
    if not normalized_layers:
        legacy_keys = {
            "type", "text", "valueKey", "textAlign", "textEffects", "xPct", "yPct", "wPct", "hPct",
            "rotateDeg", "scale", "opacity", "color", "bgColor", "fontSizePx", "fontFamily", "assetId", "fit",
        }
        if any(key in overlay for key in legacy_keys):
            normalized_layers = [_normalize_layer(overlay, 0)]
    return {
        "id": str(overlay.get("id") or f"overlay_{idx+1}").strip() or f"overlay_{idx+1}",
        "name": str(overlay.get("name") or f"Overlay {idx+1}").strip() or f"Overlay {idx+1}",
        "previewAssetId": str(overlay.get("previewAssetId") or "").strip(),
        "layers": normalized_layers,
    }


def _normalize_overlay_ref(ref: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return {
        "overlayId": str(ref.get("overlayId") or ref.get("id") or f"overlay_{idx+1}").strip() or f"overlay_{idx+1}",
        "active": bool(ref.get("active", True)),
    }


def _normalize_scene(scene: Dict[str, Any], idx: int) -> Dict[str, Any]:
    overlay_refs = scene.get("overlayRefs") if isinstance(scene.get("overlayRefs"), list) else []
    screens_in = scene.get("screens") if isinstance(scene.get("screens"), list) else []
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
    def _audio_types(rows: Any) -> List[str]:
        allowed = {"music", "sfx", "voice", "ambient"}
        out: List[str] = []
        if isinstance(rows, list):
            for raw in rows:
                val = str(raw or "").strip().lower()
                if val in allowed and val not in out:
                    out.append(val)
        return out
    return {
        "id": str(scene.get("id") or f"scene_{idx+1}").strip() or f"scene_{idx+1}",
        "name": str(scene.get("name") or f"Scene {idx+1}").strip() or f"Scene {idx+1}",
        "screens": screens,
        "baseAssetId": str(scene.get("baseAssetId") or "").strip(),
        "priority": int(float(scene.get("priority") or 100)),
        "blendMode": blend_mode,
        "loop": bool(scene.get("loop", True)),
        "mute": bool(scene.get("mute", True)),
        "interruptPolicy": interrupt_policy,
        "duplicatePolicy": duplicate_policy,
        "cooldownMs": max(0, int(float(scene.get("cooldownMs") or 0))),
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
        "overlayRefs": [_normalize_overlay_ref(ref, i) for i, ref in enumerate(overlay_refs) if isinstance(ref, dict)],
    }


def normalize_media_config(cfg: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = cfg if isinstance(cfg, dict) else {}
    defaults = _default_config()
    settings_in = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    displays_in = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    assets_in = cfg.get("assets") if isinstance(cfg.get("assets"), list) else []
    overlays_in = cfg.get("overlays") if isinstance(cfg.get("overlays"), list) else []
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
    migrated_overlays: List[Dict[str, Any]] = []
    migrated_overlay_ids: set[str] = set()

    def _take_overlay_id(raw_overlay: Dict[str, Any], idx: int) -> str:
        base = str(raw_overlay.get("id") or f"overlay_{idx+1}").strip() or f"overlay_{idx+1}"
        candidate = base
        suffix = 2
        while candidate in migrated_overlay_ids:
            candidate = f"{base}_{suffix}"
            suffix += 1
        migrated_overlay_ids.add(candidate)
        return candidate

    out = {
        "settings": {
            "enabled": bool(settings_in.get("enabled", defaults["settings"]["enabled"])),
            "renderer": "chromium",
            "previewScale": max(0.1, min(1.0, float(settings_in.get("previewScale", defaults["settings"]["previewScale"])))),
            "windowScale": max(0.05, min(1.0, float(settings_in.get("windowScale", defaults["settings"]["windowScale"])))),
            "defaultDisplayRole": str(settings_in.get("defaultDisplayRole") or defaults["settings"]["defaultDisplayRole"]).strip() or "backbox",
            "defaultScenesByDisplay": default_scenes_by_display,
            "autoplayByDisplay": autoplay_by_display,
            "runtimePollMs": max(40, min(5000, int(float(settings_in.get("runtimePollMs") or defaults["settings"]["runtimePollMs"])))),
        },
        "displays": [],
        "assets": [],
        "overlays": [],
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
        out["assets"].append(
            {
                "id": aid,
                "displayName": str(a.get("displayName") or Path(filename).stem).strip() or Path(filename).stem,
                "filename": filename,
                "kind": str(a.get("kind") or ("video" if ext in ("mp4", "mkv", "webm", "mov", "m4v") else "image")).strip().lower(),
                "sizeBytes": max(0, int(float(a.get("sizeBytes") or 0))),
                "durationMs": max(0, int(float(a.get("durationMs") or 0))),
                "createdAt": str(a.get("createdAt") or _utc_now_iso()),
            }
        )

    for i, ov in enumerate(overlays_in):
        if not isinstance(ov, dict):
            continue
        normalized_overlay = _normalize_overlay(ov, i)
        overlay_id = str(normalized_overlay.get("id") or "").strip()
        if not overlay_id or overlay_id in migrated_overlay_ids:
            overlay_id = _take_overlay_id(normalized_overlay, i)
            normalized_overlay["id"] = overlay_id
        else:
            migrated_overlay_ids.add(overlay_id)
        out["overlays"].append(normalized_overlay)

    for i, s in enumerate(scenes_in):
        if not isinstance(s, dict):
            continue
        scene_in = dict(s)
        if not isinstance(scene_in.get("overlayRefs"), list):
            inline_overlays = scene_in.get("overlays") if isinstance(scene_in.get("overlays"), list) else []
            refs: List[Dict[str, Any]] = []
            for j, ov in enumerate(inline_overlays):
                if not isinstance(ov, dict):
                    continue
                normalized_overlay = _normalize_overlay(ov, j)
                overlay_id = _take_overlay_id(normalized_overlay, len(out["overlays"]) + len(migrated_overlays))
                normalized_overlay["id"] = overlay_id
                migrated_overlays.append(normalized_overlay)
                refs.append({"overlayId": overlay_id, "active": True})
            scene_in["overlayRefs"] = refs
        out["scenes"].append(_normalize_scene(scene_in, i))
    if migrated_overlays:
        out["overlays"].extend(migrated_overlays)
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
    return normalized


def save_media_config(instance_path: str | Path, cfg: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_media_config(cfg)
    _write_json(_media_config_path(instance_path), normalized)
    return normalized


def _detect_displays_screeninfo() -> List[Dict[str, Any]]:
    try:
        from screeninfo import get_monitors  # type: ignore
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for i, m in enumerate(get_monitors()):
        out.append(
            {
                "id": f"display_{i+1}",
                "name": f"Display {i+1}",
                "width": int(getattr(m, "width", 1920) or 1920),
                "height": int(getattr(m, "height", 1080) or 1080),
                "x": int(getattr(m, "x", 0) or 0),
                "y": int(getattr(m, "y", 0) or 0),
                "role": "backbox" if i == 0 else f"aux_{i+1}",
                "enabled": True,
                "screenIndex": i + 1,
            }
        )
    return out


def _detect_displays_xrandr() -> List[Dict[str, Any]]:
    if not shutil.which("xrandr"):
        return []
    try:
        proc = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=2, check=False)
        lines = (proc.stdout or "").splitlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    idx = 1
    for line in lines:
        if " connected " not in line:
            continue
        m = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", line)
        if not m:
            continue
        name = line.split(" connected ", 1)[0].strip() or f"Display {idx}"
        out.append(
            {
                "id": f"display_{idx}",
                "name": name,
                "width": int(m.group(1)),
                "height": int(m.group(2)),
                "x": int(m.group(3)),
                "y": int(m.group(4)),
                "role": "backbox" if idx == 1 else f"aux_{idx}",
                "enabled": True,
                "screenIndex": idx,
            }
        )
        idx += 1
    return out


def _detect_displays_system_profiler() -> List[Dict[str, Any]]:
    if platform.system().lower() != "darwin" or not shutil.which("system_profiler"):
        return []
    try:
        proc = subprocess.run(
            ["system_profiler", "SPDisplaysDataType"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
        lines = (proc.stdout or "").splitlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    idx = 1
    x_cursor = 0
    for line in lines:
        m = re.search(r"Resolution:\s*(\d+)\s*x\s*(\d+)", line)
        if not m:
            continue
        width = int(m.group(1))
        height = int(m.group(2))
        out.append(
            {
                "id": f"display_{idx}",
                "name": f"Display {idx}",
                "width": width,
                "height": height,
                "x": x_cursor,
                "y": 0,
                "role": "backbox" if idx == 1 else f"aux_{idx}",
                "enabled": True,
                "screenIndex": idx,
            }
        )
        x_cursor += max(320, width)
        idx += 1
    return out


def detect_displays() -> List[Dict[str, Any]]:
    for fn in (_detect_displays_screeninfo, _detect_displays_xrandr, _detect_displays_system_profiler):
        rows = fn()
        if rows:
            return rows
    return _default_displays()


def _find_browser_cmd() -> List[str]:
    env_bin = str(os.environ.get("PINBALLCTL_MEDIA_BROWSER") or "").strip()
    if env_bin:
        return [env_bin]

    for candidate in ("chromium-browser", "chromium", "google-chrome", "google-chrome-stable"):
        path = shutil.which(candidate)
        if path:
            return [path]

    if platform.system().lower() == "darwin":
        mac_bins = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for p in mac_bins:
            if Path(p).exists():
                return [p]

    return []


def _media_base_url() -> str:
    env = str(os.environ.get("PINBALLCTL_MEDIA_BASE_URL") or "").strip()
    if env:
        return env.rstrip("/")
    return "http://127.0.0.1:8888"


def _detect_media_tooling() -> Dict[str, Any]:
    host = platform.system().lower()
    tools: List[Dict[str, Any]] = []
    notes: List[str] = []

    def add_tool(name: str, *, required: bool, purpose: str, install_command: str) -> None:
        installed = bool(shutil.which(name))
        tools.append(
            {
                "name": name,
                "installed": installed,
                "required": required,
                "purpose": purpose,
                "installCommand": install_command,
            }
        )

    if host == "darwin":
        chrome_installed = bool(_find_browser_cmd())
        tools.append(
            {
                "name": "chromium-or-chrome",
                "installed": chrome_installed,
                "required": True,
                "purpose": "Runtime renderer (kiosk output windows).",
                "installCommand": "brew install --cask google-chrome",
            }
        )
        add_tool(
            "system_profiler",
            required=False,
            purpose="Display detection metadata for auto screen sizing.",
            install_command="(included with macOS)",
        )
        notes.append("For development on macOS, Google Chrome works as the kiosk renderer.")
    elif host == "linux":
        browser_installed = bool(_find_browser_cmd())
        tools.append(
            {
                "name": "chromium-browser",
                "installed": browser_installed,
                "required": True,
                "purpose": "Runtime renderer (kiosk output windows).",
                "installCommand": "sudo apt-get install chromium-browser",
            }
        )
        add_tool(
            "xrandr",
            required=False,
            purpose="Display detection on X11 (recommended on Raspberry Pi).",
            install_command="sudo apt-get install x11-xserver-utils",
        )
        notes.append("On Raspberry Pi OS, Chromium + xrandr gives reliable multi-display detection.")
    else:
        tools.append(
            {
                "name": "chromium-or-chrome",
                "installed": bool(_find_browser_cmd()),
                "required": True,
                "purpose": "Runtime renderer (kiosk output windows).",
                "installCommand": "Install Chromium or Google Chrome and add to PATH.",
            }
        )
        notes.append("Unsupported OS for automatic install hints; Chromium still works if available in PATH.")

    missing_required = [str(t.get("name") or "") for t in tools if t.get("required") and not t.get("installed")]
    return {
        "os": platform.system(),
        "tools": tools,
        "missingRequired": missing_required,
        "notes": notes,
    }


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
    browser_cmd = _find_browser_cmd()
    font_catalog = _font_catalog(instance_path)
    return {
        "renderer": {
            "name": "chromium",
            "chromiumFound": bool(browser_cmd),
            "binary": browser_cmd[0] if browser_cmd else "",
            "platform": platform.system(),
        },
        "tooling": _detect_media_tooling(),
        "displays": detect_displays(),
        "fonts": [str(row.get("family") or row.get("name") or "").strip() for row in font_catalog if str(row.get("family") or row.get("name") or "").strip()],
        "fontCatalog": font_catalog,
    }


@dataclass
class _SceneHandle:
    scene_id: str
    display_id: str
    pid: int
    started_at_ms: int
    runtime_url: str
    launch_mode: str
    preview_viewport: Dict[str, int] | None
    process: subprocess.Popen[Any]


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
            stale_fullscreen_displays: set[str] = set()
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
                if mode == LAUNCH_MODE_WINDOWED:
                    if not _surface_process_alive(self.instance_path, row):
                        self._clear_trigger_for_locked(
                            scene_id=str(row.get("sceneId") or ""),
                            display_id=str(row.get("displayId") or ""),
                        )
                        continue
                    kept_surfaces.append(row)
                    continue
                if _surface_process_alive(self.instance_path, row):
                    kept_surfaces.append(row)
                    continue
                if mode == LAUNCH_MODE_FULLSCREEN:
                    stale_fullscreen_displays.add(str(row.get("displayId") or "").strip())
                    self._clear_trigger_for_locked(
                        scene_id=str(row.get("sceneId") or ""),
                        display_id=str(row.get("displayId") or ""),
                    )
            self._surface_sessions = kept_surfaces
            if stale_fullscreen_displays:
                self._sessions = [
                    row for row in self._sessions
                    if not (
                        str(row.get("displayId") or "").strip() in stale_fullscreen_displays
                        and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_FULLSCREEN
                    )
                ]
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
                or (
                    max(0, int(float(row.get("pid") or 0))) > 0
                    and (
                        max(0, int(float(row.get("pid") or 0))) in live_pids
                        or _is_pid_alive(max(0, int(float(row.get("pid") or 0))))
                    )
                )
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


class _ChromiumEngine:
    def __init__(self, instance_path: str | Path):
        self.instance_path = str(Path(instance_path).resolve())
        self._lock = Lock()
        self._active: Dict[str, _SceneHandle] = {}

    def _cleanup_dead(self) -> None:
        dead = []
        for key, h in self._active.items():
            if h.process.poll() is not None:
                dead.append(key)
        for k in dead:
            self._active.pop(k, None)

    def _stop_handle(self, h: _SceneHandle) -> None:
        p = h.process
        try:
            if p.poll() is None:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except Exception:
            try:
                p.terminate()
            except Exception:
                pass
        # Avoid hard-kill on macOS to prevent "quit unexpectedly" crash dialogs.
        deadline = time.time() + (2.0 if platform.system().lower() == "darwin" else 0.3)
        while time.time() < deadline and p.poll() is None:
            time.sleep(0.05)
        if p.poll() is None and platform.system().lower() != "darwin":
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

    def _resolve_display(self, cfg: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
        targets = _scene_targets(scene)
        display_key = str(targets[0] if targets else "").strip()
        display = next(
            (
                d
                for d in cfg.get("displays", [])
                if str(d.get("id") or "") == display_key or str(d.get("role") or "") == display_key
            ),
            None,
        )
        if display:
            return display
        displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
        if displays:
            return displays[0]
        return _default_displays()[0]

    def _effective_display(self, cfg: Dict[str, Any], display: Dict[str, Any]) -> Dict[str, Any]:
        """Return display coordinates for launch placement."""
        out = dict(display or {})
        rows = [d for d in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(d, dict)]
        if len(rows) <= 1:
            return out

        # Some host APIs report every display at (0,0). Distinguish true mirrored
        # layouts from ambiguous coordinates so screen-targeted placement still works.
        try:
            x0 = int(float(rows[0].get("x") or 0))
            y0 = int(float(rows[0].get("y") or 0))
            same_origin = all(
                int(float(d.get("x") or 0)) == x0 and int(float(d.get("y") or 0)) == y0
                for d in rows
            )
            w0 = max(64, int(float(rows[0].get("width") or 1920)))
            h0 = max(64, int(float(rows[0].get("height") or 1080)))
            same_size = all(
                max(64, int(float(d.get("width") or 1920))) == w0
                and max(64, int(float(d.get("height") or 1080))) == h0
                for d in rows
            )
        except Exception:
            same_origin = False
            same_size = False

        if not same_origin:
            return out

        if same_size:
            # Likely mirrored outputs; keep one effective origin.
            out["x"] = x0
            out["y"] = y0
            return out

        # Ambiguous coordinates with non-mirrored sizes: synthesize a stable
        # left-to-right virtual layout so fullscreen placement honors screen targeting.
        def _sort_key(d: Dict[str, Any]) -> tuple[int, int, str]:
            try:
                si = int(float(d.get("screenIndex") or 0))
            except Exception:
                si = 0
            sid = str(d.get("id") or "")
            rid = str(d.get("role") or "")
            return (0 if si > 0 else 1, si if si > 0 else 0, f"{si}:{sid}:{rid}")

        ordered = sorted(rows, key=_sort_key)
        virtual_x = 0
        virtual_by_id: Dict[str, int] = {}
        virtual_by_role: Dict[str, int] = {}
        for d in ordered:
            did = str(d.get("id") or "").strip()
            role = str(d.get("role") or "").strip()
            if did:
                virtual_by_id[did] = virtual_x
            if role:
                virtual_by_role[role] = virtual_x
            dw = max(64, int(float(d.get("width") or 1920)))
            virtual_x += max(320, dw)

        key_id = str(out.get("id") or "").strip()
        key_role = str(out.get("role") or "").strip()
        if key_id in virtual_by_id:
            out["x"] = virtual_by_id[key_id]
        elif key_role in virtual_by_role:
            out["x"] = virtual_by_role[key_role]
        else:
            out["x"] = x0
        out["y"] = y0
        return out

    def _runtime_url_for_display(
        self,
        display_id: str,
        base_url: str | None = None,
        *,
        runtime_token: str | None = None,
        scene_id: str | None = None,
    ) -> str:
        root = (base_url or _media_base_url()).rstrip("/")
        base = f"{root}/media/runtime/display/{display_id}"
        qs: Dict[str, str] = {}
        if runtime_token:
            qs["kiosk_token"] = str(runtime_token)
        if scene_id:
            qs["sceneId"] = str(scene_id)
        if not qs:
            return base
        return f"{base}?{urlencode(qs)}"

    def _launch_for_display(
        self,
        display: Dict[str, Any],
        runtime_url: str,
        *,
        launch_mode: str,
        window_scale: float,
    ) -> Dict[str, Any]:
        browser_cmd = _find_browser_cmd()
        if not browser_cmd:
            return {"ok": False, "error": "chromium_not_found"}

        display_id = str(display.get("id") or "display_1")
        x = int(float(display.get("x") or 0))
        y = int(float(display.get("y") or 0))
        mode = _normalize_launch_mode(launch_mode)
        profile_suffix = "kiosk" if mode == LAUNCH_MODE_FULLSCREEN else "windowed"
        profile_key = ""
        if mode == LAUNCH_MODE_WINDOWED:
            try:
                qs = parse_qs(urlparse(str(runtime_url or "")).query or "")
                profile_key = str((qs.get("instanceId") or [""])[0] or "").strip()
            except Exception:
                profile_key = ""
        profile_name = f"{display_id}_{profile_suffix}_{profile_key}" if profile_key else f"{display_id}_{profile_suffix}"
        profile_dir = _media_profiles_dir(self.instance_path) / profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)

        cmd = browser_cmd + [
            "--no-first-run",
            "--disable-session-crashed-bubble",
            "--disable-infobars",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling",
            f"--user-data-dir={profile_dir}",
        ]
        if mode == LAUNCH_MODE_WINDOWED:
            display_w = max(64, int(float(display.get("width") or 1920)))
            display_h = max(64, int(float(display.get("height") or 1080)))
            scale = max(0.05, min(1.0, float(window_scale or 0.25)))
            window_w = max(320, int(round(display_w * scale)))
            ratio = display_h / max(1, display_w)
            window_h = max(180, int(round(window_w * ratio)))
            cmd.extend(
                [
                    "--new-window",
                    f"--window-position={x + 48},{y + 48}",
                    f"--window-size={window_w},{window_h}",
                    f"--app={runtime_url}",
                ]
            )
        else:
            cmd.extend(
                [
                    f"--window-position={x},{y}",
                    "--start-fullscreen",
                    "--kiosk",
                    f"--app={runtime_url}",
                ]
            )

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as exc:
            return {"ok": False, "error": f"spawn_failed:{exc}"}
        return {"ok": True, "process": proc}

    def set_display_scene(
        self,
        display_id: str,
        scene_id: str,
        *,
        preview_viewport: Dict[str, int] | None = None,
    ) -> None:
        with self._lock:
            self._cleanup_dead()
            for h in self._active.values():
                if h.display_id != str(display_id):
                    continue
                if h.launch_mode != LAUNCH_MODE_FULLSCREEN:
                    continue
                if h.process.poll() is not None:
                    continue
                h.scene_id = str(scene_id)
                h.preview_viewport = preview_viewport
                break

    def play_scene(
        self,
        cfg: Dict[str, Any],
        scene_id: str,
        *,
        base_url: str | None = None,
        runtime_token: str | None = None,
        launch_mode: str = LAUNCH_MODE_FULLSCREEN,
        preview_viewport: Dict[str, int] | None = None,
        forced_display: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        scene = next((s for s in cfg.get("scenes", []) if str(s.get("id") or "") == str(scene_id)), None)
        if not scene:
            return {"ok": False, "error": "scene_not_found"}

        asset_id = str(scene.get("baseAssetId") or "").strip()
        if not asset_id:
            return {"ok": False, "error": "scene_asset_missing"}
        asset = next((a for a in cfg.get("assets", []) if str(a.get("id") or "") == asset_id), None)
        if not asset:
            return {"ok": False, "error": "asset_not_found"}
        file_path = _media_assets_dir(self.instance_path) / str(asset.get("filename") or "")
        if not file_path.exists():
            return {"ok": False, "error": "asset_file_missing"}

        display = forced_display if isinstance(forced_display, dict) else self._resolve_display(cfg, scene)
        display = self._effective_display(cfg, display)
        display_id = str(display.get("id") or "display_1")
        mode = _normalize_launch_mode(launch_mode)
        runtime_url = self._runtime_url_for_display(
            display_id,
            base_url=base_url,
            runtime_token=runtime_token,
            scene_id=str(scene.get("id") or scene_id) if mode == LAUNCH_MODE_WINDOWED else None,
        )
        settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
        window_scale = max(
            0.05,
            min(
                1.0,
                float(
                    settings.get("windowScale")
                    or settings.get("previewScale")
                    or 0.25
                ),
            ),
        )

        with self._lock:
            self._cleanup_dead()
            if mode == LAUNCH_MODE_FULLSCREEN:
                fullscreen_handles = [
                    h
                    for h in self._active.values()
                    if h.display_id == display_id and h.launch_mode == LAUNCH_MODE_FULLSCREEN and h.process.poll() is None
                ]
                if fullscreen_handles:
                    existing = fullscreen_handles[0]
                    for stale in fullscreen_handles[1:]:
                        self._stop_handle(stale)
                        self._active.pop(f"{stale.display_id}:{stale.pid}", None)
                    # If runtime URL changed (for example refreshed/added kiosk token),
                    # relaunch this display process so polling uses the new URL.
                    if str(existing.runtime_url or "") == str(runtime_url):
                        existing.scene_id = str(scene.get("id") or scene_id)
                        existing.preview_viewport = preview_viewport
                        return {
                            "ok": True,
                            "sceneId": existing.scene_id,
                            "displayId": display_id,
                            "pid": existing.pid,
                            "reused": True,
                            "renderer": "chromium",
                            "runtimeUrl": runtime_url,
                            "launchMode": mode,
                        }
                    self._stop_handle(existing)
                    self._active.pop(f"{existing.display_id}:{existing.pid}", None)

            launched = self._launch_for_display(
                display,
                runtime_url,
                launch_mode=mode,
                window_scale=window_scale,
            )
            if not launched.get("ok"):
                return launched
            proc = launched["process"]
            handle = _SceneHandle(
                scene_id=str(scene.get("id") or scene_id),
                display_id=display_id,
                pid=int(proc.pid or 0),
                started_at_ms=_now_ms(),
                runtime_url=runtime_url,
                launch_mode=mode,
                preview_viewport=preview_viewport,
                process=proc,
            )
            self._active[f"{handle.display_id}:{handle.pid}"] = handle
            return {
                "ok": True,
                "sceneId": handle.scene_id,
                "displayId": display_id,
                "pid": handle.pid,
                "reused": False,
                "renderer": "chromium",
                "runtimeUrl": runtime_url,
                "launchMode": mode,
            }

    def stop_scene(self, scene_id: str | None = None) -> Dict[str, Any]:
        stopped = 0
        with self._lock:
            self._cleanup_dead()
            targets = []
            for _, h in self._active.items():
                if scene_id and h.scene_id != scene_id:
                    continue
                targets.append(h)
            for h in targets:
                self._stop_handle(h)
                self._active.pop(f"{h.display_id}:{h.pid}", None)
                stopped += 1
        return {"ok": True, "stopped": stopped}

    def stop_display(self, display_id: str) -> int:
        stopped = 0
        with self._lock:
            self._cleanup_dead()
            targets = [
                h for h in self._active.values()
                if h.display_id == str(display_id)
            ]
            for h in targets:
                self._stop_handle(h)
                self._active.pop(f"{h.display_id}:{h.pid}", None)
                stopped += 1
        return stopped

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_dead()
            active = [
                {
                    "sceneId": h.scene_id,
                    "displayId": h.display_id,
                    "pid": h.pid,
                    "startedAtMs": h.started_at_ms,
                    "runtimeUrl": h.runtime_url,
                    "launchMode": h.launch_mode,
                    "previewViewport": h.preview_viewport,
                }
                for h in self._active.values()
            ]
        return {"backend": "chromium", "active": active}


_ENGINES: Dict[str, _ChromiumEngine] = {}
_ENGINES_LOCK = Lock()
_RUNTIMES: Dict[str, _MediaRuntimeState] = {}
_RUNTIMES_LOCK = Lock()
_BUS_WORKERS: Dict[str, Dict[str, Any]] = {}
_BUS_WORKERS_LOCK = Lock()


def _get_engine(instance_path: str | Path) -> _ChromiumEngine:
    key = str(Path(instance_path).resolve())
    with _ENGINES_LOCK:
        eng = _ENGINES.get(key)
        if eng is None:
            eng = _ChromiumEngine(key)
            _ENGINES[key] = eng
        return eng


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
    runtime = _get_runtime_state(instance_path)
    result = runtime.sweep_dead_surfaces()
    if int(result.get("removed") or 0) > 0:
        _persist_runtime_snapshot(instance_path)
    return result


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    event_name = str(name or "").strip().upper()
    payload = params if isinstance(params, dict) else {}
    runtime = _get_runtime_state(instance_path)

    if event_name == "SCORING_EVAL":
        updates: Dict[str, Any] = {}
        if "score" in payload:
            try:
                updates["score"] = f"{max(0, int(float(payload.get('score') or 0))):08d}"
            except Exception:
                pass
        if updates:
            runtime.set_overlay_values(updates)
            _persist_runtime_snapshot(instance_path)
        return {"ok": True, "processed": bool(updates), "updates": updates}

    if event_name == "SCORE_CHANGED":
        updates = {}
        if "score" in payload:
            try:
                updates["score"] = f"{max(0, int(float(payload.get('score') or 0))):08d}"
            except Exception:
                pass
        if updates:
            runtime.set_overlay_values(updates)
            _persist_runtime_snapshot(instance_path)
        return {"ok": True, "processed": bool(updates), "updates": updates}

    if event_name == "MEDIA_SET_OVERLAY":
        key = str(payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "missing_key"}
        overlay_values = runtime.set_overlay_value(key, payload.get("value"))
        _persist_runtime_snapshot(instance_path)
        return {"ok": True, "processed": True, "overlayValues": overlay_values}

    if event_name == "MEDIA_SCENE_PLAY":
        scene_id = str(payload.get("sceneId") or "").strip()
        if not scene_id:
            return {"ok": False, "error": "missing_scene_id"}
        launch_mode = str(payload.get("launchMode") or LAUNCH_MODE_EMBEDDED).strip().lower() or LAUNCH_MODE_EMBEDDED
        stack_behavior = str(payload.get("stackBehavior") or DEFAULT_SCENE_STACK_BEHAVIOR).strip().lower() or DEFAULT_SCENE_STACK_BEHAVIOR
        preview_viewport = payload.get("previewViewport") if isinstance(payload.get("previewViewport"), dict) else None
        return play_scene(
            instance_path,
            scene_id=scene_id,
            base_url=str(payload.get("baseUrl") or "").strip() or None,
            runtime_token=str(payload.get("runtimeToken") or "").strip() or None,
            launch_mode=launch_mode,
            preview_viewport=preview_viewport,
            stack_behavior=stack_behavior,
            event_source=str(source or "").strip(),
        )

    if event_name == "MEDIA_SCENE_STOP":
        scene_id = str(payload.get("sceneId") or "").strip() or None
        session_id = str(payload.get("sessionId") or "").strip() or None
        return stop_scene(instance_path, scene_id=scene_id, session_id=session_id)

    if event_name == "MEDIA_STOP_ALL":
        return stop_scene(instance_path, scene_id=None)

    if event_name == "MEDIA_SCENE_COMPLETE":
        display_id = str(payload.get("displayId") or "").strip()
        if not display_id:
            return {"ok": False, "error": "missing_display_id"}
        session_id = str(payload.get("sessionId") or "").strip() or None
        scene_id = str(payload.get("sceneId") or "").strip() or None
        return complete_scene(instance_path, display_id=display_id, session_id=session_id, scene_id=scene_id)

    return {"ok": True, "processed": False}


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


def upload_asset(instance_path: str | Path, file_storage: Any, display_name: str | None = None) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    filename = _safe_asset_name(str(getattr(file_storage, "filename", "") or "media.bin"))
    target = _media_assets_dir(instance_path) / filename
    if target.exists():
        target = target.with_name(f"{target.stem}_{uuid4().hex[:6]}{target.suffix}")
    file_storage.save(str(target))
    ext = target.suffix.lower().lstrip(".")
    kind = "video" if ext in ("mp4", "mkv", "webm", "mov", "m4v") else "image"
    row = {
        "id": f"asset_{uuid4().hex[:10]}",
        "displayName": str(display_name or target.stem).strip() or target.stem,
        "filename": target.name,
        "kind": kind,
        "sizeBytes": max(0, int(target.stat().st_size)),
        "durationMs": 0,
        "createdAt": _utc_now_iso(),
    }
    cfg_assets = [a for a in cfg.get("assets", []) if isinstance(a, dict)]
    cfg_assets.append(row)
    cfg["assets"] = cfg_assets
    save_media_config(instance_path, cfg)
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

    cfg["assets"] = keep
    cfg["overlays"] = [
        {
            **ov,
            "previewAssetId": "" if str(ov.get("previewAssetId") or "") == str(asset_id) else str(ov.get("previewAssetId") or ""),
            "layers": [
                {
                    **layer,
                    "assetId": "" if str(layer.get("assetId") or "") == str(asset_id) else str(layer.get("assetId") or ""),
                }
                for layer in (ov.get("layers") if isinstance(ov.get("layers"), list) else [])
                if isinstance(layer, dict)
            ],
        }
        for ov in cfg.get("overlays", [])
        if isinstance(ov, dict)
    ]
    cfg["scenes"] = [
        {
            **s,
            "baseAssetId": "" if str(s.get("baseAssetId") or "") == str(asset_id) else str(s.get("baseAssetId") or ""),
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
    ensure_media_bus_worker(instance_path)
    runtime = _get_runtime_state(instance_path)
    runtime_state = runtime.snapshot()
    session_rows = _normalize_session_rows(runtime_state.get("sessions"))
    surface_rows = _normalize_session_rows(runtime_state.get("surfaceSessions"))
    merged_surfaces = list(surface_rows)
    merged_active = [
        {
            "sceneId": str(row.get("sceneId") or ""),
            "displayId": str(row.get("displayId") or ""),
            "pid": max(0, int(row.get("pid") or 0)),
            "startedAtMs": max(0, int(float(row.get("startedAtMs") or 0))),
            "runtimeUrl": str(row.get("runtimeUrl") or ""),
            "launchMode": _normalize_launch_mode(row.get("launchMode")),
            "previewViewport": row.get("previewViewport") if isinstance(row.get("previewViewport"), dict) else None,
        }
        for row in merged_surfaces
    ]
    overlay_values = runtime_state.get("overlayValues") if isinstance(runtime_state.get("overlayValues"), dict) else {}
    merged_overlay_values = _default_overlay_values()
    merged_overlay_values.update(overlay_values)
    state = {
        "updatedAt": _utc_now_iso(),
        "engine": {"backend": "chromium", "active": merged_active},
        "sessions": session_rows,
        "surfaceSessions": merged_surfaces,
        "queue": _normalize_session_rows(runtime_state.get("queue")),
        "overlayValues": merged_overlay_values,
    }
    if persist:
        _write_json(_media_state_path(instance_path), state)
    return state


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    *,
    base_url: str | None = None,
    runtime_token: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    preview_viewport: Dict[str, int] | None = None,
    stack_behavior: str = DEFAULT_SCENE_STACK_BEHAVIOR,
    event_source: str = "",
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    before_state = load_media_state(instance_path, persist=False)
    mode = _normalize_launch_mode(launch_mode)
    scenes = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []
    scene = next((s for s in scenes if str(s.get("id") or "") == str(scene_id)), None)
    if not isinstance(scene, dict):
        return {"ok": False, "error": "scene_not_found"}

    eng = _get_engine(instance_path)
    runtime = _get_runtime_state(instance_path)
    blend_mode = str(scene.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper()
    if stack_behavior == STACK_BEHAVIOR_INTERRUPT:
        blend_mode = BLEND_MODE_PAUSE_LOWER
    elif stack_behavior == STACK_BEHAVIOR_REPLACE:
        blend_mode = BLEND_MODE_STOP_LOWER if mode != LAUNCH_MODE_EMBEDDED else BLEND_MODE_STOP_LOWER
    interrupt_policy = str(scene.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper()
    duplicate_policy = str(scene.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper()
    cooldown_ms = max(0, int(float(scene.get("cooldownMs") or 0)))
    priority = int(scene.get("priority") or 100)
    audio_behaviour = scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}
    queue_cfg = scene.get("queue") if isinstance(scene.get("queue"), dict) else {}
    queue_enabled = bool(queue_cfg.get("enabled", interrupt_policy == INTERRUPT_QUEUE))
    queue_max_length = max(0, int(float(queue_cfg.get("maxLength") or 8)))
    queue_dedupe = bool(queue_cfg.get("dedupe", True))
    target_displays = [eng._effective_display(cfg, d) for d in _resolve_scene_displays(cfg, scene)]
    results: List[Dict[str, Any]] = []

    if mode == LAUNCH_MODE_EMBEDDED:
        for display in target_displays:
            display_id = str(display.get("id") or "display_1")
            runtime_url = eng._runtime_url_for_display(
                display_id,
                base_url=base_url,
                runtime_token=runtime_token,
                scene_id=str(scene.get("id") or scene_id),
            )
            session = runtime.play_display_scene(
                scene_id=str(scene.get("id") or scene_id),
                display_id=display_id,
                launch_mode=LAUNCH_MODE_EMBEDDED,
                runtime_url=runtime_url,
                preview_viewport=preview_viewport,
                stack_behavior=stack_behavior,
                source=event_source,
                priority=priority,
                blend_mode=blend_mode,
                interrupt_policy=interrupt_policy,
                duplicate_policy=duplicate_policy,
                cooldown_ms=cooldown_ms,
                audio_behaviour=audio_behaviour,
                queue_enabled=queue_enabled,
                queue_max_length=queue_max_length,
                queue_dedupe=queue_dedupe,
            )
            surface = runtime.upsert_display_surface(
                display_id=display_id,
                launch_mode=LAUNCH_MODE_EMBEDDED,
                pid=0,
                runtime_url=runtime_url,
            )
            results.append({**session, "surfaceId": str((surface or {}).get("id") or "")})
        _persist_runtime_snapshot(instance_path)
        after_state = load_media_state(instance_path)
        _emit_media_audio_intent_changes(
            instance_path,
            cfg,
            before_state.get("sessions") if isinstance(before_state, dict) else [],
            after_state.get("sessions") if isinstance(after_state, dict) else [],
        )
        first = results[0] if results else {"sceneId": str(scene.get("id") or scene_id), "displayId": "display_1"}
        return {
            "ok": True,
            "sceneId": first["sceneId"],
            "displayId": first["displayId"],
            "displayIds": [str(row.get("displayId") or "") for row in results],
            "pid": 0,
            "reused": any(bool(row.get("reused")) for row in results),
            "queued": any(bool(row.get("queued")) for row in results),
            "dropped": any(bool(row.get("dropped")) for row in results),
            "renderer": "embedded",
            "runtimeUrl": str(first.get("runtimeUrl") or ""),
            "launchMode": LAUNCH_MODE_EMBEDDED,
            "blendMode": blend_mode,
        }

    for display in target_displays:
        display_id = str(display.get("id") or "display_1")
        window_surface_id = f"surface_windowed_{uuid4().hex[:10]}" if mode == LAUNCH_MODE_WINDOWED else ""
        fullscreen_surface_id = f"surface_fullscreen_{display_id}" if mode == LAUNCH_MODE_FULLSCREEN else ""
        runtime_url = eng._runtime_url_for_display(
            display_id,
            base_url=base_url,
            runtime_token=runtime_token,
            scene_id=str(scene.get("id") or scene_id) if mode == LAUNCH_MODE_WINDOWED else None,
        )
        if mode == LAUNCH_MODE_WINDOWED and window_surface_id:
            runtime_url = f"{runtime_url}&sessionId={window_surface_id}" if "?" in runtime_url else f"{runtime_url}?sessionId={window_surface_id}"
        if mode == LAUNCH_MODE_FULLSCREEN and fullscreen_surface_id:
            runtime_url = f"{runtime_url}&sessionId={fullscreen_surface_id}" if "?" in runtime_url else f"{runtime_url}?sessionId={fullscreen_surface_id}"
        if mode == LAUNCH_MODE_FULLSCREEN:
            state_result = runtime.play_display_scene(
                scene_id=str(scene.get("id") or scene_id),
                display_id=display_id,
                launch_mode=mode,
                runtime_url=runtime_url,
                preview_viewport=preview_viewport,
                stack_behavior=stack_behavior,
                source=event_source,
                priority=priority,
                blend_mode=blend_mode,
                interrupt_policy=interrupt_policy,
                duplicate_policy=duplicate_policy,
                cooldown_ms=cooldown_ms,
                audio_behaviour=audio_behaviour,
                queue_enabled=queue_enabled,
                queue_max_length=queue_max_length,
                queue_dedupe=queue_dedupe,
            )
            if bool(state_result.get("queued")) or bool(state_result.get("dropped")):
                results.append(state_result)
                continue
            existing_surface = next(
                (
                    row for row in runtime.surface_rows()
                    if str(row.get("displayId") or "") == display_id
                    and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_FULLSCREEN
                    and max(0, int(row.get("pid") or 0)) > 0
                    and _is_pid_alive(max(0, int(row.get("pid") or 0)))
                ),
                None,
            )
            if isinstance(existing_surface, dict):
                eng.set_display_scene(display_id, str(state_result.get("sceneId") or scene_id), preview_viewport=preview_viewport)
                surface = runtime.upsert_display_surface(
                    display_id=display_id,
                    launch_mode=LAUNCH_MODE_FULLSCREEN,
                    pid=max(0, int(existing_surface.get("pid") or 0)),
                    runtime_url=runtime_url,
                    surface_id=fullscreen_surface_id,
                )
                results.append({**state_result, "ok": True, "pid": max(0, int((surface or {}).get("pid") or 0)), "reused": True, "renderer": "chromium", "runtimeUrl": runtime_url, "launchMode": mode, "surfaceId": str((surface or {}).get("id") or "")})
                continue
            result = eng.play_scene(
                cfg,
                scene_id,
                base_url=base_url,
                runtime_token=runtime_token,
                launch_mode=mode,
                preview_viewport=preview_viewport,
                forced_display=display,
            )
            if not result.get("ok"):
                return result
            surface = runtime.upsert_display_surface(
                display_id=display_id,
                launch_mode=LAUNCH_MODE_FULLSCREEN,
                pid=max(0, int(result.get("pid") or 0)),
                runtime_url=runtime_url,
                surface_id=fullscreen_surface_id,
            )
            eng.set_display_scene(display_id, str(state_result.get("sceneId") or scene_id), preview_viewport=preview_viewport)
            results.append({**state_result, **result, "displayId": display_id, "surfaceId": str((surface or {}).get("id") or "")})
            continue

        result = eng.play_scene(
            cfg,
            scene_id,
            base_url=base_url,
            runtime_token=runtime_token,
            launch_mode=mode,
            preview_viewport=preview_viewport,
            forced_display=display,
        )
        if not result.get("ok"):
            return result
        if mode == LAUNCH_MODE_WINDOWED:
            existing_windowed = [
                row for row in runtime.surface_rows()
                if _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_WINDOWED
                and str(row.get("displayId") or "") == display_id
                and str(row.get("sceneId") or "") == str(scene.get("id") or scene_id)
                and max(0, int(row.get("pid") or 0)) != max(0, int(result.get("pid") or 0))
            ]
            for stale in existing_windowed:
                stale_pid = max(0, int(stale.get("pid") or 0))
                if stale_pid > 0 and _is_managed_media_pid(instance_path, stale_pid):
                    _stop_pid(stale_pid)
        surface = runtime.add_window_surface(
            surface_id=window_surface_id,
            scene_id=str(scene.get("id") or scene_id),
            display_id=display_id,
            runtime_url=runtime_url,
            preview_viewport=preview_viewport,
            pid=max(0, int(result.get("pid") or 0)),
            source=event_source,
            priority=priority,
            blend_mode=blend_mode,
            audio_behaviour=audio_behaviour,
        )
        results.append({**surface, **result, "displayId": display_id, "surfaceId": str(surface.get("id") or "")})

    _persist_runtime_snapshot(instance_path)
    after_state = load_media_state(instance_path)
    _emit_media_audio_intent_changes(
        instance_path,
        cfg,
        before_state.get("sessions") if isinstance(before_state, dict) else [],
        after_state.get("sessions") if isinstance(after_state, dict) else [],
    )
    first = results[0] if results else {"displayId": "display_1", "sceneId": str(scene.get("id") or scene_id)}
    return {
        "ok": True,
        "sceneId": str(first.get("sceneId") or scene_id),
        "displayId": str(first.get("displayId") or "display_1"),
        "displayIds": [str(row.get("displayId") or "") for row in results],
        "pid": int(first.get("pid") or 0),
        "reused": any(bool(row.get("reused")) for row in results),
        "queued": any(bool(row.get("queued")) for row in results),
        "dropped": any(bool(row.get("dropped")) for row in results),
        "renderer": "chromium" if mode != LAUNCH_MODE_EMBEDDED else "embedded",
        "runtimeUrl": str(first.get("runtimeUrl") or ""),
        "launchMode": mode,
        "blendMode": blend_mode,
        "results": results,
    }


def stop_scene(instance_path: str | Path, scene_id: str | None = None, session_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    eng = _get_engine(instance_path)
    runtime = _get_runtime_state(instance_path)
    before = runtime.snapshot()
    before_surfaces = _normalize_session_rows(before.get("surfaceSessions"))
    target_surface = next((row for row in before_surfaces if session_id and str(row.get("id") or "") == str(session_id)), None)
    before_top = _top_session_by_display(_normalize_session_rows(before.get("sessions")))
    if session_id and isinstance(target_surface, dict):
        stop_info = runtime.stop_surface(str(session_id))
    else:
        stop_info = runtime.stop_display_scene(scene_id=scene_id)
    after_top = _top_session_by_display(_normalize_session_rows(stop_info.get("sessions")))

    stopped_runtime = int(stop_info.get("stopped") or (1 if stop_info.get("ok") and session_id else 0))
    stopped_processes = 0
    changed_displays = set(before_top.keys()) | set(after_top.keys())
    for display_id in changed_displays:
        prev = before_top.get(display_id)
        nxt = after_top.get(display_id)
        if nxt:
            if _normalize_launch_mode(nxt.get("launchMode")) == LAUNCH_MODE_FULLSCREEN:
                eng.set_display_scene(
                    display_id,
                    str(nxt.get("sceneId") or ""),
                    preview_viewport=nxt.get("previewViewport") if isinstance(nxt.get("previewViewport"), dict) else None,
                )
            continue
        stopped_processes += eng.stop_display(display_id)

    if isinstance(target_surface, dict):
        target_pid = max(0, int(target_surface.get("pid") or 0))
        if target_pid > 0 and _is_managed_media_pid(instance_path, target_pid):
            if _stop_pid(target_pid):
                stopped_processes += 1
    elif not scene_id and not session_id:
        for surface in before_surfaces:
            pid = max(0, int(surface.get("pid") or 0))
            if pid <= 0:
                continue
            if _is_managed_media_pid(instance_path, pid):
                if _stop_pid(pid):
                    stopped_processes += 1
        runtime.clear_all()
    elif scene_id:
        for surface in before_surfaces:
            if str(surface.get("sceneId") or "") != str(scene_id):
                continue
            pid = max(0, int(surface.get("pid") or 0))
            if pid > 0 and _is_managed_media_pid(instance_path, pid):
                if _stop_pid(pid):
                    stopped_processes += 1

    after_state = load_media_state(instance_path)
    _emit_media_audio_intent_changes(
        instance_path,
        cfg,
        before.get("sessions") if isinstance(before, dict) else [],
        after_state.get("sessions") if isinstance(after_state, dict) else [],
    )
    return {"ok": True, "stopped": stopped_runtime + stopped_processes}


def set_overlay_value(instance_path: str | Path, key: str, value: Any) -> Dict[str, Any]:
    if not str(key or "").strip():
        return {"ok": False, "error": "missing_key"}
    ensure_media_bus_worker(instance_path)
    runtime = _get_runtime_state(instance_path)
    overlay_values = runtime.set_overlay_value(str(key).strip(), value)
    _persist_runtime_snapshot(instance_path)
    return {"ok": True, "overlayValues": overlay_values}


def complete_scene(
    instance_path: str | Path,
    *,
    display_id: str,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    runtime = _get_runtime_state(instance_path)
    eng = _get_engine(instance_path)
    before = runtime.snapshot()
    before_top = _top_session_by_display(_normalize_session_rows(before.get("sessions")))
    result = runtime.complete_session(display_id=str(display_id or "").strip(), session_id=session_id, scene_id=scene_id)
    if not result.get("ok"):
        return result
    after_top = _top_session_by_display(_normalize_session_rows(result.get("sessions")))
    did = str(display_id or "").strip()
    nxt = after_top.get(did)
    if nxt and _normalize_launch_mode(nxt.get("launchMode")) == LAUNCH_MODE_FULLSCREEN:
        eng.set_display_scene(
            did,
            str(nxt.get("sceneId") or ""),
            preview_viewport=nxt.get("previewViewport") if isinstance(nxt.get("previewViewport"), dict) else None,
        )
    elif before_top.get(did) and not nxt:
        eng.stop_display(did)
    _persist_runtime_snapshot(instance_path)
    after_state = load_media_state(instance_path)
    _emit_media_audio_intent_changes(
        instance_path,
        cfg,
        before.get("sessions") if isinstance(before, dict) else [],
        after_state.get("sessions") if isinstance(after_state, dict) else [],
    )
    return {"ok": True, "completed": result.get("completed"), "promoted": result.get("promoted")}


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


def _overlay_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(ov.get("id") or ""): ov
        for ov in (cfg.get("overlays") if isinstance(cfg.get("overlays"), list) else [])
        if isinstance(ov, dict) and str(ov.get("id") or "")
    }


def _resolved_scene(scene: Dict[str, Any], overlays_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    refs = scene.get("overlayRefs") if isinstance(scene.get("overlayRefs"), list) else []
    layers: List[Dict[str, Any]] = []
    for overlay_idx, ref in enumerate(refs):
        if not isinstance(ref, dict) or not bool(ref.get("active", True)):
            continue
        overlay_id = str(ref.get("overlayId") or "").strip()
        overlay = overlays_by_id.get(overlay_id)
        if not isinstance(overlay, dict):
            continue
        overlay_layers = overlay.get("layers") if isinstance(overlay.get("layers"), list) else []
        for layer_idx, layer in enumerate(overlay_layers):
            if not isinstance(layer, dict):
                continue
            resolved = dict(layer)
            resolved["id"] = str(layer.get("id") or f"{overlay_id}_layer_{layer_idx+1}")
            resolved["name"] = str(layer.get("name") or f"Layer {layer_idx+1}")
            resolved["overlayId"] = overlay_id
            resolved["overlayName"] = str(overlay.get("name") or overlay_id)
            layers.append(resolved)
    total = len(layers)
    for idx, resolved in enumerate(layers):
        resolved["zIndex"] = total - idx
    return {**scene, "overlays": layers}


def _scene_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    overlays_by_id = _overlay_map(cfg)
    return {
        str(s.get("id") or ""): _resolved_scene(s, overlays_by_id)
        for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else [])
        if isinstance(s, dict) and str(s.get("id") or "")
    }


def _render_layers_for_display(cfg: Dict[str, Any], display_id: str, session_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    scenes_by_id = _scene_map(cfg)
    assets_by_id = _asset_map(cfg)
    autoplay_map = _autoplay_displays(cfg)
    rows = [row for row in session_rows if str(row.get("displayId") or "") == str(display_id)]
    rows.sort(key=lambda row: (int(row.get("priority") or 100), int(row.get("startedAtMs") or 0)))

    # Latest row wins for equal priority.
    deduped: List[Dict[str, Any]] = []
    seen_priorities: set[int] = set()
    for row in reversed(rows):
        prio = int(row.get("priority") or 100)
        if prio in seen_priorities:
            continue
        seen_priorities.add(prio)
        deduped.append(row)
    deduped.reverse()

    if not deduped:
        fallback_scene = _default_scene_for_display(cfg, display_id) if bool(autoplay_map.get(str(display_id), False)) else None
        if fallback_scene:
            asset = assets_by_id.get(str(fallback_scene.get("baseAssetId") or ""))
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

    stop_lower_priorities = [
        int(row.get("priority") or 100)
        for row in deduped
        if str(row.get("blendMode") or "") == BLEND_MODE_STOP_LOWER
    ]
    top_stop_lower = bool(stop_lower_priorities)
    if stop_lower_priorities:
        cutoff = max(stop_lower_priorities)
        deduped = [row for row in deduped if int(row.get("priority") or 100) >= cutoff]
    layers: List[Dict[str, Any]] = []
    for idx, row in enumerate(deduped):
        scene = scenes_by_id.get(str(row.get("sceneId") or ""))
        if not isinstance(scene, dict):
            continue
        asset = assets_by_id.get(str(scene.get("baseAssetId") or ""))
        if not isinstance(asset, dict):
            continue
        paused = any(
            int(other.get("priority") or 100) > int(row.get("priority") or 100)
            and str(other.get("blendMode") or "") == BLEND_MODE_PAUSE_LOWER
            for other in deduped
        )
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
                "audioBehaviour": dict(row.get("audioBehaviour") if isinstance(row.get("audioBehaviour"), dict) else scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {}),
            }
        )

    if not top_stop_lower and bool(autoplay_map.get(str(display_id), False)):
        fallback_scene = _default_scene_for_display(cfg, display_id)
        if fallback_scene and not any(str(layer.get("scene", {}).get("id") or "") == str(fallback_scene.get("id") or "") for layer in layers):
            asset = assets_by_id.get(str(fallback_scene.get("baseAssetId") or ""))
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
                    },
                )

    layers.sort(key=lambda row: (int(row.get("priority") or 0), int(row.get("startedAtMs") or 0)))
    for idx, layer in enumerate(layers):
        layer["renderOrder"] = idx + 1
    return layers


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
) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    runtime = _get_runtime_state(instance_path)
    displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    display = next((d for d in displays if str(d.get("id") or "") == str(display_id)), None)
    if not display:
        display = next((d for d in displays if str(d.get("role") or "") == str(display_id)), None)
    if not display:
        display = displays[0] if displays else _default_displays()[0]

    resolved_display_id = str(display.get("id") or "display_1")
    requested_scene_id = str(scene_id or "").strip()
    persist_heartbeat = False
    surface_key = str(surface_type or "").strip().lower()
    if str(session_id or "").strip():
        persist_heartbeat = runtime.touch_surface(str(session_id).strip())
    elif surface_key == "embedded":
        # Embedded surfaces are lifecycle-driven by explicit leave events.
        persist_heartbeat = False
    if persist_heartbeat:
        _persist_runtime_snapshot(instance_path)
    state = load_media_state(instance_path, persist=False)

    active_rows = state.get("engine", {}).get("active", []) if isinstance(state.get("engine"), dict) else []
    session_rows = _normalize_session_rows(state.get("sessions"))
    surface_rows = _normalize_session_rows(state.get("surfaceSessions"))
    top_sessions = _top_session_by_display(session_rows)
    render_rows = session_rows
    requested_surface = None
    if requested_scene_id:
        requested_surface = next(
            (
                row for row in surface_rows
                if str(row.get("displayId") or "") == resolved_display_id
                and str(row.get("sceneId") or "") == requested_scene_id
                and _normalize_launch_mode(row.get("launchMode")) == LAUNCH_MODE_WINDOWED
            ),
            None,
        )
        if isinstance(requested_surface, dict):
            render_rows = [requested_surface]
        else:
            render_rows = [
                row for row in session_rows
                if str(row.get("displayId") or "") == resolved_display_id
                and str(row.get("sceneId") or "") == requested_scene_id
            ] or session_rows
    # Runtime URLs that carry sceneId (windowed surfaces) should render that scene
    # independently from the shared display session stack.
    if requested_scene_id:
        scenes = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []
        forced_scene = next((s for s in scenes if str(s.get("id") or "") == requested_scene_id), None)
        if isinstance(forced_scene, dict):
            render_rows = [
                {
                    "id": str((requested_surface or {}).get("id") or f"surface_windowed_forced_{resolved_display_id}"),
                    "sceneId": requested_scene_id,
                    "displayId": resolved_display_id,
                    "pid": max(0, int((requested_surface or {}).get("pid") or 0)),
                    "launchMode": LAUNCH_MODE_WINDOWED,
                    "runtimeUrl": str((requested_surface or {}).get("runtimeUrl") or ""),
                    "startedAtMs": max(0, int(float((requested_surface or {}).get("startedAtMs") or _now_ms()))),
                    "previewViewport": (requested_surface or {}).get("previewViewport") if isinstance((requested_surface or {}).get("previewViewport"), dict) else None,
                    "stackBehavior": STACK_BEHAVIOR_REPLACE,
                    "source": str((requested_surface or {}).get("source") or "runtime.window"),
                    "priority": int(forced_scene.get("priority") or 100),
                    "blendMode": str(forced_scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
                    "interruptPolicy": str(forced_scene.get("interruptPolicy") or INTERRUPT_ALLOW),
                    "duplicatePolicy": str(forced_scene.get("duplicatePolicy") or DUPLICATE_ALLOW),
                    "audioBehaviour": dict(forced_scene.get("audioBehaviour") if isinstance(forced_scene.get("audioBehaviour"), dict) else {}),
                }
            ]
    layers = _render_layers_for_display(cfg, resolved_display_id, render_rows)
    active = None
    if requested_scene_id:
        active = next(
            (
                a
                for a in active_rows
                if str(a.get("displayId") or "") == resolved_display_id and str(a.get("sceneId") or "") == requested_scene_id
            ),
            None,
        )
    if not active:
        session = top_sessions.get(resolved_display_id)
        if session:
            active = {
                "sceneId": str(session.get("sceneId") or ""),
                "displayId": resolved_display_id,
                "pid": 0 if _normalize_launch_mode(session.get("launchMode")) == LAUNCH_MODE_EMBEDDED else "",
                "startedAtMs": max(0, int(float(session.get("startedAtMs") or 0))),
                "runtimeUrl": str(session.get("runtimeUrl") or ""),
                "launchMode": _normalize_launch_mode(session.get("launchMode")),
                "previewViewport": session.get("previewViewport") if isinstance(session.get("previewViewport"), dict) else None,
            }
    if not active:
        active = next(
            (
                a
                for a in active_rows
                if str(a.get("displayId") or "") == resolved_display_id
                and _normalize_launch_mode(a.get("launchMode")) == LAUNCH_MODE_FULLSCREEN
            ),
            None,
        )
    if not active:
        active = next((a for a in active_rows if str(a.get("displayId") or "") == resolved_display_id), None)

    effective_scene_id = requested_scene_id or (str(active.get("sceneId") or "").strip() if isinstance(active, dict) else "")
    scenes = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []
    scene = next((s for s in scenes if str(s.get("id") or "") == effective_scene_id), None)

    asset = None
    if isinstance(scene, dict):
        base_asset_id = str(scene.get("baseAssetId") or "").strip()
        assets = cfg.get("assets") if isinstance(cfg.get("assets"), list) else []
        asset = next((a for a in assets if str(a.get("id") or "") == base_asset_id), None)
    if layers:
        top_layer = layers[-1]
        scene = top_layer.get("scene") if isinstance(top_layer.get("scene"), dict) else scene
        asset = top_layer.get("asset") if isinstance(top_layer.get("asset"), dict) else asset
        if not active:
            active = {
                "sceneId": str(top_layer.get("scene", {}).get("id") or ""),
                "displayId": resolved_display_id,
                "pid": 0 if _normalize_launch_mode(top_layer.get("launchMode")) == LAUNCH_MODE_EMBEDDED else "",
                "startedAtMs": int(top_layer.get("startedAtMs") or 0),
                "runtimeUrl": "",
                "launchMode": _normalize_launch_mode(top_layer.get("launchMode")),
            }

    overlay_values = state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else {}
    merged_overlay_values: Dict[str, Any] = dict(overlay_values)
    scoring_state = _load_scoring_state_nonblocking(instance_path)
    game_active = False
    if isinstance(scoring_state, dict):
        score_val = int(float(scoring_state.get("score") or 0))
        merged_overlay_values["score"] = f"{max(0, score_val):08d}"

        game = scoring_state.get("game") if isinstance(scoring_state.get("game"), dict) else {}
        started_ms = int(float(game.get("startedAtMs") or 0)) if isinstance(game, dict) else 0
        ended_ms = int(float(game.get("endedAtMs") or 0)) if isinstance(game, dict) else 0
        game_active = bool(game.get("active")) if isinstance(game, dict) else False
        now_ms = _now_ms()
        if started_ms > 0:
            elapsed_ms = (now_ms - started_ms) if game_active else max(0, ended_ms - started_ms)
        else:
            elapsed_ms = 0
        merged_overlay_values["game_elapsed_time"] = _format_elapsed_mmss(elapsed_ms)

        merged_overlay_values["player"] = str(scoring_state.get("player") or merged_overlay_values.get("player") or "1")
        merged_overlay_values["ball"] = str(scoring_state.get("ball") or merged_overlay_values.get("ball") or "1")
        merged_overlay_values["credit"] = str(scoring_state.get("credit") or merged_overlay_values.get("credit") or "0")
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    configured_poll_ms = max(40, int(float(settings.get("runtimePollMs") or 150)))
    runtime_poll_ms = min(configured_poll_ms, 80) if game_active else configured_poll_ms

    return {
        "ok": True,
        "renderer": "chromium",
        "updatedAt": state.get("updatedAt") or _utc_now_iso(),
        "display": display,
        "active": active,
        "scene": scene,
        "asset": asset,
        "layers": layers,
        "overlayValues": merged_overlay_values,
        "settings": {
            "runtimePollMs": runtime_poll_ms,
        },
    }


# =============================
# Runtime V2: single registry
# =============================

INSTANCE_STATE_STARTING = "starting"
INSTANCE_STATE_RUNNING = "running"
INSTANCE_STATE_STOPPING = "stopping"
INSTANCE_STATE_STOPPED = "stopped"
INSTANCE_STATE_CRASHED = "crashed"
INSTANCE_STATE_ORPHANED = "orphaned"
DESIRED_PRESENT = "present"
DESIRED_ABSENT = "absent"
SURFACE_HEARTBEAT_TIMEOUT_MS = 30000
STOPPED_RETENTION_MS = 60000


class _SceneInstanceRegistry:
    def __init__(self, instance_path: str | Path):
        self.instance_path = str(Path(instance_path).resolve())
        self._lock = Lock()
        self._loaded = False
        self._dirty = False
        self._instances: Dict[str, Dict[str, Any]] = {}
        self._display_stacks: Dict[str, List[str]] = {}
        self._overlay_values: Dict[str, Any] = _default_overlay_values()
        self._last_disk_mtime_ns = -1

    def _disk_mtime_ns_locked(self) -> int:
        path = _media_state_path(self.instance_path)
        try:
            return int(path.stat().st_mtime_ns)
        except Exception:
            return -1

    def _normalize_instance(self, raw: Dict[str, Any]) -> Dict[str, Any] | None:
        instance_id = str(raw.get("instance_id") or raw.get("id") or "").strip()
        scene_id = str(raw.get("scene_id") or raw.get("sceneId") or "").strip()
        display_id = str(raw.get("display_id") or raw.get("displayId") or "").strip()
        mode = _normalize_launch_mode(raw.get("mode") or raw.get("launchMode"))
        if not instance_id or not scene_id or not display_id:
            return None
        state = str(raw.get("state") or INSTANCE_STATE_STARTING).strip().lower()
        if state not in (
            INSTANCE_STATE_STARTING,
            INSTANCE_STATE_RUNNING,
            INSTANCE_STATE_STOPPING,
            INSTANCE_STATE_STOPPED,
            INSTANCE_STATE_CRASHED,
            INSTANCE_STATE_ORPHANED,
        ):
            state = INSTANCE_STATE_STARTING
        desired_state = str(raw.get("desired_state") or raw.get("desiredState") or DESIRED_PRESENT).strip().lower()
        if desired_state not in (DESIRED_PRESENT, DESIRED_ABSENT):
            desired_state = DESIRED_PRESENT
        created_at = max(0, int(float(raw.get("created_at") or raw.get("createdAt") or _now_ms())))
        updated_at = max(0, int(float(raw.get("updated_at") or raw.get("updatedAt") or created_at)))
        process = raw.get("process") if isinstance(raw.get("process"), dict) else {}
        surface = raw.get("surface") if isinstance(raw.get("surface"), dict) else {}
        render = raw.get("render") if isinstance(raw.get("render"), dict) else {}
        control = raw.get("control") if isinstance(raw.get("control"), dict) else {}
        out = {
            "instance_id": instance_id,
            "scene_id": scene_id,
            "display_id": display_id,
            "mode": mode,
            "state": state,
            "desired_state": desired_state,
            "created_at": created_at,
            "updated_at": updated_at,
            "generation": max(1, int(float(raw.get("generation") or 1))),
            "runtime_url": str(raw.get("runtime_url") or raw.get("runtimeUrl") or "").strip(),
            "preview_viewport": render.get("previewViewport") if isinstance(render.get("previewViewport"), dict) else (raw.get("previewViewport") if isinstance(raw.get("previewViewport"), dict) else None),
            "source": str(raw.get("source") or "").strip(),
            "priority": int(float(raw.get("priority") or 100)),
            "blend_mode": str(raw.get("blend_mode") or raw.get("blendMode") or BLEND_MODE_STOP_LOWER).strip().upper(),
            "interrupt_policy": str(raw.get("interrupt_policy") or raw.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper(),
            "duplicate_policy": str(raw.get("duplicate_policy") or raw.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper(),
            "audio_behaviour": dict(raw.get("audio_behaviour") if isinstance(raw.get("audio_behaviour"), dict) else raw.get("audioBehaviour") if isinstance(raw.get("audioBehaviour"), dict) else {}),
            "process": {
                "pid": max(0, int(float(process.get("pid") or raw.get("pid") or 0))),
                "started_at": max(0, int(float(process.get("started_at") or process.get("startedAt") or created_at))),
                "exit_code": process.get("exit_code", process.get("exitCode")),
                "last_seen_at": max(0, int(float(process.get("last_seen_at") or process.get("lastSeenAt") or updated_at))),
            },
            "surface": {
                "attached": bool(surface.get("attached", False)),
                "surface_id": str(surface.get("surface_id") or surface.get("surfaceId") or "").strip(),
                "attached_at": max(0, int(float(surface.get("attached_at") or surface.get("attachedAt") or 0))),
                "last_heartbeat_at": max(0, int(float(surface.get("last_heartbeat_at") or surface.get("lastHeartbeatAt") or 0))),
            },
            "render": {
                "z_index": int(float(render.get("z_index") or render.get("zIndex") or 0)),
                "visible": bool(render.get("visible", True)),
                "overlay": dict(render.get("overlay") if isinstance(render.get("overlay"), dict) else {}),
                "previewViewport": render.get("previewViewport") if isinstance(render.get("previewViewport"), dict) else (raw.get("previewViewport") if isinstance(raw.get("previewViewport"), dict) else None),
            },
            "control": {
                "stop_requested_at": max(0, int(float(control.get("stop_requested_at") or control.get("stopRequestedAt") or 0))),
                "stop_reason": str(control.get("stop_reason") or control.get("stopReason") or "").strip(),
            },
        }
        return out

    def _load_locked(self) -> None:
        if self._loaded and self._disk_mtime_ns_locked() <= self._last_disk_mtime_ns and not self._dirty:
            return
        payload = _read_json(_media_state_path(self.instance_path), {})
        if not isinstance(payload, dict):
            payload = {}
        self._overlay_values = _default_overlay_values()
        if isinstance(payload.get("overlayValues"), dict):
            self._overlay_values.update(payload.get("overlayValues"))
        runtime_v2 = payload.get("runtimeV2") if isinstance(payload.get("runtimeV2"), dict) else {}
        raw_instances = runtime_v2.get("instances") if isinstance(runtime_v2.get("instances"), list) else []
        inst: Dict[str, Dict[str, Any]] = {}
        for row in raw_instances:
            if not isinstance(row, dict):
                continue
            normalized = self._normalize_instance(row)
            if isinstance(normalized, dict):
                inst[str(normalized.get("instance_id") or "")] = normalized
        self._instances = inst
        stacks_in = runtime_v2.get("displayStates") if isinstance(runtime_v2.get("displayStates"), dict) else {}
        stacks_out: Dict[str, List[str]] = {}
        for did, row in stacks_in.items():
            display_id = str(did or "").strip()
            if not display_id:
                continue
            stack = row.get("stack") if isinstance(row, dict) and isinstance(row.get("stack"), list) else []
            stacks_out[display_id] = [str(x or "").strip() for x in stack if str(x or "").strip() in self._instances]
        self._display_stacks = stacks_out
        self._loaded = True
        self._dirty = False
        self._last_disk_mtime_ns = self._disk_mtime_ns_locked()

    def _persist_locked(self) -> None:
        payload = _read_json(_media_state_path(self.instance_path), {})
        if not isinstance(payload, dict):
            payload = {}
        payload["overlayValues"] = dict(self._overlay_values)
        payload["runtimeV2"] = {
            "instances": [dict(v) for v in sorted(self._instances.values(), key=lambda r: int(r.get("created_at") or 0))],
            "displayStates": {did: {"display_id": did, "stack": list(stack)} for did, stack in self._display_stacks.items()},
        }
        payload["updatedAt"] = _utc_now_iso()
        _write_json(_media_state_path(self.instance_path), payload)
        self._dirty = False
        self._last_disk_mtime_ns = self._disk_mtime_ns_locked()

    def _mark_updated_locked(self, inst: Dict[str, Any]) -> None:
        inst["updated_at"] = _now_ms()
        inst["generation"] = max(1, int(inst.get("generation") or 1)) + 1

    def _state_transition_locked(self, inst: Dict[str, Any], nxt: str) -> None:
        cur = str(inst.get("state") or "")
        allowed = {
            INSTANCE_STATE_STARTING: {INSTANCE_STATE_RUNNING, INSTANCE_STATE_CRASHED, INSTANCE_STATE_STOPPING},
            INSTANCE_STATE_RUNNING: {INSTANCE_STATE_STOPPING, INSTANCE_STATE_CRASHED, INSTANCE_STATE_ORPHANED},
            INSTANCE_STATE_STOPPING: {INSTANCE_STATE_STOPPED, INSTANCE_STATE_ORPHANED, INSTANCE_STATE_CRASHED},
            INSTANCE_STATE_ORPHANED: {INSTANCE_STATE_STOPPED},
        }
        if cur == nxt:
            return
        if cur in allowed and nxt in allowed[cur]:
            inst["state"] = nxt
            self._mark_updated_locked(inst)
            self._dirty = True

    def _instance_rows_locked(self) -> List[Dict[str, Any]]:
        rows = list(self._instances.values())
        rows.sort(key=lambda r: int(r.get("created_at") or 0), reverse=True)
        return [dict(r) for r in rows]

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            self._load_locked()
            return {
                "overlayValues": dict(self._overlay_values),
                "instances": self._instance_rows_locked(),
                "displayStates": {did: {"display_id": did, "stack": list(stack)} for did, stack in self._display_stacks.items()},
            }

    def _active_instance_locked(self, inst: Dict[str, Any]) -> bool:
        if str(inst.get("desired_state") or DESIRED_PRESENT) != DESIRED_PRESENT:
            return False
        return str(inst.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)

    def _remove_from_stack_locked(self, instance_id: str) -> None:
        iid = str(instance_id or "").strip()
        if not iid:
            return
        for did, stack in list(self._display_stacks.items()):
            if iid in stack:
                self._display_stacks[did] = [x for x in stack if x != iid]
                self._dirty = True

    def _request_stop_locked(self, inst: Dict[str, Any], reason: str) -> None:
        inst["desired_state"] = DESIRED_ABSENT
        inst["control"]["stop_requested_at"] = _now_ms()
        inst["control"]["stop_reason"] = str(reason or "").strip()
        cur = str(inst.get("state") or "")
        if cur in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING):
            self._state_transition_locked(inst, INSTANCE_STATE_STOPPING)
        self._remove_from_stack_locked(str(inst.get("instance_id") or ""))
        self._dirty = True

    def set_overlay_values(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        clean_updates = {str(k).strip(): v for k, v in updates.items() if str(k).strip()} if isinstance(updates, dict) else {}
        with self._lock:
            self._load_locked()
            self._overlay_values.update(clean_updates)
            self._dirty = True
            self._persist_locked()
            return dict(self._overlay_values)

    def set_overlay_value(self, key: str, value: Any) -> Dict[str, Any]:
        return self.set_overlay_values({str(key or "").strip(): value})

    def create_instance(
        self,
        *,
        instance_id: str,
        scene_id: str,
        display_id: str,
        mode: str,
        runtime_url: str,
        preview_viewport: Dict[str, int] | None,
        source: str,
        priority: int,
        blend_mode: str,
        interrupt_policy: str,
        duplicate_policy: str,
        audio_behaviour: Dict[str, Any] | None,
        pid: int = 0,
        stack_behavior: str = STACK_BEHAVIOR_REPLACE,
    ) -> Dict[str, Any]:
        now_ms = _now_ms()
        with self._lock:
            self._load_locked()
            if str(mode) in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_FULLSCREEN):
                stack = list(self._display_stacks.get(display_id, []))
                if _normalize_stack_behavior(stack_behavior) == STACK_BEHAVIOR_REPLACE:
                    for iid in stack:
                        inst = self._instances.get(iid)
                        if isinstance(inst, dict):
                            self._request_stop_locked(inst, "replaced")
                    stack = []
                stack.append(instance_id)
                self._display_stacks[display_id] = stack
            inst = {
                "instance_id": instance_id,
                "scene_id": scene_id,
                "display_id": display_id,
                "mode": _normalize_launch_mode(mode),
                "state": INSTANCE_STATE_RUNNING if max(0, int(pid or 0)) > 0 else INSTANCE_STATE_STARTING,
                "desired_state": DESIRED_PRESENT,
                "created_at": now_ms,
                "updated_at": now_ms,
                "generation": 1,
                "runtime_url": str(runtime_url or "").strip(),
                "preview_viewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                "source": str(source or "").strip(),
                "priority": int(priority),
                "blend_mode": str(blend_mode or BLEND_MODE_STOP_LOWER).strip().upper(),
                "interrupt_policy": str(interrupt_policy or INTERRUPT_NO_INTERRUPT).strip().upper(),
                "duplicate_policy": str(duplicate_policy or DUPLICATE_DROP_IF_PLAYING).strip().upper(),
                "audio_behaviour": dict(audio_behaviour or {}),
                "process": {
                    "pid": max(0, int(pid or 0)),
                    "started_at": now_ms,
                    "exit_code": None,
                    "last_seen_at": now_ms,
                },
                "surface": {
                    "attached": False,
                    "surface_id": "",
                    "attached_at": 0,
                    "last_heartbeat_at": 0,
                },
                "render": {
                    "z_index": 0,
                    "visible": True,
                    "overlay": {},
                    "previewViewport": preview_viewport if isinstance(preview_viewport, dict) else None,
                },
                "control": {
                    "stop_requested_at": 0,
                    "stop_reason": "",
                },
            }
            self._instances[instance_id] = inst
            self._dirty = True
            self._persist_locked()
            return dict(inst)

    def attach_surface(self, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        now_ms = _now_ms()
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict):
                return {"ok": False, "error": "instance_not_found"}
            inst["surface"]["attached"] = True
            inst["surface"]["surface_id"] = str(surface_id or iid).strip() or iid
            inst["surface"]["attached_at"] = now_ms
            inst["surface"]["last_heartbeat_at"] = now_ms
            if str(inst.get("state") or "") == INSTANCE_STATE_STARTING:
                self._state_transition_locked(inst, INSTANCE_STATE_RUNNING)
            self._mark_updated_locked(inst)
            self._dirty = True
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def heartbeat(self, *, instance_id: str) -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        now_ms = _now_ms()
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict):
                return {"ok": False, "error": "instance_not_found"}
            inst["surface"]["attached"] = True
            inst["surface"]["last_heartbeat_at"] = now_ms
            if str(inst.get("state") or "") == INSTANCE_STATE_STARTING:
                self._state_transition_locked(inst, INSTANCE_STATE_RUNNING)
            self._mark_updated_locked(inst)
            self._dirty = True
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def detach_surface(self, *, instance_id: str, reason: str = "surface_leave") -> Dict[str, Any]:
        iid = str(instance_id or "").strip()
        if not iid:
            return {"ok": False, "error": "missing_instance_id"}
        with self._lock:
            self._load_locked()
            inst = self._instances.get(iid)
            if not isinstance(inst, dict):
                return {"ok": False, "error": "instance_not_found"}
            inst["surface"]["attached"] = False
            self._request_stop_locked(inst, reason)
            self._persist_locked()
            return {"ok": True, "instance": dict(inst)}

    def detach_embedded_by_display(self, display_id: str) -> Dict[str, Any]:
        did = str(display_id or "").strip()
        if not did:
            return {"ok": False, "error": "missing_display_id"}
        count = 0
        with self._lock:
            self._load_locked()
            for inst in self._instances.values():
                if str(inst.get("display_id") or "") != did:
                    continue
                if _normalize_launch_mode(inst.get("mode")) != LAUNCH_MODE_EMBEDDED:
                    continue
                self._request_stop_locked(inst, "embedded_leave")
                count += 1
            self._persist_locked()
            return {"ok": True, "stopped": count}

    def request_stop(self, *, scene_id: str | None = None, instance_id: str | None = None) -> Dict[str, Any]:
        sid = str(scene_id or "").strip()
        iid = str(instance_id or "").strip()
        stopped = 0
        with self._lock:
            self._load_locked()
            if iid:
                inst = self._instances.get(iid)
                if isinstance(inst, dict):
                    self._request_stop_locked(inst, "stop_request")
                    stopped += 1
            elif sid:
                for inst in self._instances.values():
                    if str(inst.get("scene_id") or "") != sid:
                        continue
                    if str(inst.get("desired_state") or "") == DESIRED_ABSENT:
                        continue
                    self._request_stop_locked(inst, "scene_stop")
                    stopped += 1
            else:
                for inst in self._instances.values():
                    if str(inst.get("desired_state") or "") == DESIRED_ABSENT:
                        continue
                    self._request_stop_locked(inst, "stop_all")
                    stopped += 1
            self._persist_locked()
            return {"ok": True, "stopped": stopped}

    def complete(self, *, display_id: str, instance_id: str | None = None, scene_id: str | None = None) -> Dict[str, Any]:
        did = str(display_id or "").strip()
        iid = str(instance_id or "").strip()
        sid = str(scene_id or "").strip()
        with self._lock:
            self._load_locked()
            target: Dict[str, Any] | None = None
            stack = list(self._display_stacks.get(did, []))
            for candidate_id in reversed(stack):
                inst = self._instances.get(candidate_id)
                if not isinstance(inst, dict):
                    continue
                if iid and str(inst.get("instance_id") or "") != iid:
                    continue
                if sid and str(inst.get("scene_id") or "") != sid:
                    continue
                if not self._active_instance_locked(inst):
                    continue
                target = inst
                break
            if not isinstance(target, dict):
                return {"ok": False, "error": "instance_not_found"}
            self._request_stop_locked(target, "complete")
            self._persist_locked()
            return {"ok": True, "completed": dict(target)}

    def reconcile(self, *, cfg: Dict[str, Any]) -> Dict[str, Any]:
        now_ms = _now_ms()
        removed = 0
        changed = 0
        with self._lock:
            self._load_locked()
            for inst in list(self._instances.values()):
                state = str(inst.get("state") or "")
                desired_state = str(inst.get("desired_state") or DESIRED_PRESENT)
                pid = max(0, int(((inst.get("process") or {}).get("pid") or 0)))
                mode = _normalize_launch_mode(inst.get("mode"))
                hb = max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0)))
                stale_hb = hb > 0 and (now_ms - hb) > SURFACE_HEARTBEAT_TIMEOUT_MS

                if pid > 0:
                    alive = _is_pid_alive(pid)
                    age_ms = now_ms - max(0, int(inst.get("created_at") or 0))
                    if mode == LAUNCH_MODE_WINDOWED and (hb <= 0 and age_ms > SURFACE_HEARTBEAT_TIMEOUT_MS or stale_hb):
                        inst["desired_state"] = DESIRED_ABSENT
                        if state in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING):
                            self._state_transition_locked(inst, INSTANCE_STATE_STOPPING)
                    if alive:
                        inst["process"]["last_seen_at"] = now_ms
                    if desired_state == DESIRED_ABSENT:
                        if state in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING):
                            self._state_transition_locked(inst, INSTANCE_STATE_STOPPING)
                        if alive:
                            _stop_pid(pid)
                            alive = _is_pid_alive(pid)
                        if not alive:
                            inst["process"]["exit_code"] = 0
                            self._state_transition_locked(inst, INSTANCE_STATE_STOPPED)
                    else:
                        if state == INSTANCE_STATE_STARTING and alive:
                            self._state_transition_locked(inst, INSTANCE_STATE_RUNNING)
                        if state in (INSTANCE_STATE_RUNNING, INSTANCE_STATE_STARTING) and not alive:
                            self._state_transition_locked(inst, INSTANCE_STATE_CRASHED)
                    if stale_hb and mode in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_FULLSCREEN, LAUNCH_MODE_WINDOWED):
                        inst["surface"]["attached"] = False
                else:
                    if desired_state == DESIRED_ABSENT:
                        if state in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING):
                            self._state_transition_locked(inst, INSTANCE_STATE_STOPPING)
                        if state == INSTANCE_STATE_STOPPING and (hb <= 0 or stale_hb):
                            self._state_transition_locked(inst, INSTANCE_STATE_STOPPED)
                    else:
                        if state == INSTANCE_STATE_STARTING and (hb > 0 or mode == LAUNCH_MODE_EMBEDDED):
                            self._state_transition_locked(inst, INSTANCE_STATE_RUNNING)
                        # Embedded instances are explicit-lifecycle controlled:
                        # do not auto-stop on heartbeat loss/background throttling.
                        if mode != LAUNCH_MODE_EMBEDDED and state == INSTANCE_STATE_RUNNING and stale_hb:
                            self._state_transition_locked(inst, INSTANCE_STATE_ORPHANED)
                    if mode != LAUNCH_MODE_EMBEDDED and state == INSTANCE_STATE_ORPHANED and (hb <= 0 or stale_hb):
                        self._state_transition_locked(inst, INSTANCE_STATE_STOPPED)

                if str(inst.get("state") or "") in (INSTANCE_STATE_STOPPED, INSTANCE_STATE_CRASHED):
                    age_ms = now_ms - max(0, int(inst.get("updated_at") or inst.get("created_at") or 0))
                    if age_ms > STOPPED_RETENTION_MS:
                        iid = str(inst.get("instance_id") or "")
                        self._remove_from_stack_locked(iid)
                        self._instances.pop(iid, None)
                        removed += 1
                        self._dirty = True
                        continue
                changed += 1

            # Stack hygiene: keep only active present fullscreen/embedded instances.
            for did, stack in list(self._display_stacks.items()):
                cleaned: List[str] = []
                for iid in stack:
                    inst = self._instances.get(iid)
                    if not isinstance(inst, dict):
                        continue
                    if not self._active_instance_locked(inst):
                        continue
                    if _normalize_launch_mode(inst.get("mode")) == LAUNCH_MODE_WINDOWED:
                        continue
                    cleaned.append(iid)
                self._display_stacks[did] = cleaned

            if self._dirty:
                self._persist_locked()
            return {"ok": True, "removed": removed, "checked": changed}


_REG_V2: Dict[str, _SceneInstanceRegistry] = {}
_REG_V2_LOCK = Lock()
_PLAY_QUEUE_HINTS: Dict[str, Dict[str, int]] = {}
_PLAY_QUEUE_HINTS_LOCK = Lock()


def _get_registry(instance_path: str | Path) -> _SceneInstanceRegistry:
    key = str(Path(instance_path).resolve())
    with _REG_V2_LOCK:
        reg = _REG_V2.get(key)
        if reg is None:
            reg = _SceneInstanceRegistry(key)
            _REG_V2[key] = reg
        return reg


def list_runtime_instances(instance_path: str | Path) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    snap = reg.snapshot()
    return {"ok": True, "instances": snap.get("instances", []), "displayStates": snap.get("displayStates", {})}


def attach_runtime_surface(instance_path: str | Path, *, instance_id: str, surface_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    return reg.attach_surface(instance_id=str(instance_id or "").strip(), surface_id=surface_id)


def heartbeat_runtime_surface(instance_path: str | Path, *, instance_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    return reg.heartbeat(instance_id=str(instance_id or "").strip())


def load_media_state(instance_path: str | Path, *, persist: bool = True) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    snap = reg.snapshot()
    instances = [row for row in (snap.get("instances") if isinstance(snap.get("instances"), list) else []) if isinstance(row, dict)]
    display_states = snap.get("displayStates") if isinstance(snap.get("displayStates"), dict) else {}

    by_id = {str(row.get("instance_id") or ""): row for row in instances if str(row.get("instance_id") or "")}
    sessions: List[Dict[str, Any]] = []
    for did, state in display_states.items():
        stack = state.get("stack") if isinstance(state, dict) and isinstance(state.get("stack"), list) else []
        for iid in stack:
            inst = by_id.get(str(iid or ""))
            if not isinstance(inst, dict):
                continue
            if str(inst.get("desired_state") or "") != DESIRED_PRESENT:
                continue
            if str(inst.get("state") or "") not in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING):
                continue
            sessions.append(
                {
                    "id": str(inst.get("instance_id") or ""),
                    "sceneId": str(inst.get("scene_id") or ""),
                    "displayId": str(inst.get("display_id") or ""),
                    "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
                    "startedAtMs": max(0, int(inst.get("created_at") or 0)),
                    "runtimeUrl": str(inst.get("runtime_url") or ""),
                    "launchMode": _normalize_launch_mode(inst.get("mode")),
                    "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
                    "priority": int(inst.get("priority") or 100),
                    "blendMode": str(inst.get("blend_mode") or BLEND_MODE_STOP_LOWER),
                    "audioBehaviour": dict(inst.get("audio_behaviour") if isinstance(inst.get("audio_behaviour"), dict) else {}),
                }
            )

    surface_rows = [
        {
            "id": str(inst.get("instance_id") or ""),
            "sceneId": str(inst.get("scene_id") or ""),
            "displayId": str(inst.get("display_id") or ""),
            "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
            "startedAtMs": max(0, int(inst.get("created_at") or 0)),
            "runtimeUrl": str(inst.get("runtime_url") or ""),
            "launchMode": _normalize_launch_mode(inst.get("mode")),
            "lastSeenMs": max(0, int(((inst.get("surface") or {}).get("last_heartbeat_at") or 0)),
            ),
            "state": str(inst.get("state") or ""),
            "desiredState": str(inst.get("desired_state") or ""),
            "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
        }
        for inst in instances
        if str(inst.get("desired_state") or "") == DESIRED_PRESENT
        and str(inst.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
    ]

    active_rows = [
        {
            "sceneId": str(inst.get("scene_id") or ""),
            "displayId": str(inst.get("display_id") or ""),
            "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
            "startedAtMs": max(0, int(inst.get("created_at") or 0)),
            "runtimeUrl": str(inst.get("runtime_url") or ""),
            "launchMode": _normalize_launch_mode(inst.get("mode")),
            "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
        }
        for inst in instances
        if max(0, int(((inst.get("process") or {}).get("pid") or 0))) > 0
        and str(inst.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
    ]

    state = {
        "updatedAt": _utc_now_iso(),
        "engine": {"backend": "chromium", "active": active_rows},
        "sessions": sessions,
        "surfaceSessions": surface_rows,
        "instances": instances,
        "displayStates": display_states,
        "queue": [],
        "overlayValues": snap.get("overlayValues") if isinstance(snap.get("overlayValues"), dict) else _default_overlay_values(),
    }
    if persist:
        _write_json(_media_state_path(instance_path), state)
    return state


def run_media_maintenance(instance_path: str | Path) -> Dict[str, Any]:
    reg = _get_registry(instance_path)
    cfg = load_media_config(instance_path)
    return reg.reconcile(cfg=cfg)


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    *,
    base_url: str | None = None,
    runtime_token: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    preview_viewport: Dict[str, int] | None = None,
    stack_behavior: str = DEFAULT_SCENE_STACK_BEHAVIOR,
    event_source: str = "",
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    cfg = load_media_config(instance_path)
    reg = _get_registry(instance_path)
    eng = _get_engine(instance_path)
    mode = _normalize_launch_mode(launch_mode)
    scene = next((s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if str(s.get("id") or "") == str(scene_id)), None)
    if not isinstance(scene, dict):
        return {"ok": False, "error": "scene_not_found"}
    interrupt_policy = str(scene.get("interruptPolicy") or INTERRUPT_NO_INTERRUPT).strip().upper()
    duplicate_policy = str(scene.get("duplicatePolicy") or DUPLICATE_DROP_IF_PLAYING).strip().upper()
    queue_cfg = scene.get("queue") if isinstance(scene.get("queue"), dict) else {}
    queue_enabled = bool(queue_cfg.get("enabled", interrupt_policy == INTERRUPT_QUEUE))
    queue_max_length = max(0, int(float(queue_cfg.get("maxLength") or 8)))
    queue_dedupe = bool(queue_cfg.get("dedupe", True))

    results: List[Dict[str, Any]] = []
    targets = _resolve_scene_displays(cfg, scene)
    base_root = (base_url or _media_base_url()).rstrip("/")
    snap = reg.snapshot()
    active_instances = [
        row for row in (snap.get("instances") if isinstance(snap.get("instances"), list) else [])
        if isinstance(row, dict)
        and str(row.get("desired_state") or "") == DESIRED_PRESENT
        and str(row.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
    ]
    for display in targets:
        did = str(display.get("id") or "display_1")
        existing_same = [
            row for row in active_instances
            if str(row.get("display_id") or "") == did
            and str(row.get("scene_id") or "") == str(scene.get("id") or scene_id)
            and _normalize_launch_mode(row.get("mode")) == mode
        ]
        if duplicate_policy == DUPLICATE_COALESCE and existing_same:
            first = existing_same[0]
            results.append(
                {
                    "ok": True,
                    "reused": True,
                    "sceneId": str(first.get("scene_id") or ""),
                    "displayId": did,
                    "instanceId": str(first.get("instance_id") or ""),
                    "id": str(first.get("instance_id") or ""),
                    "pid": max(0, int(((first.get("process") or {}).get("pid") or 0))),
                    "runtimeUrl": str(first.get("runtime_url") or ""),
                    "launchMode": mode,
                }
            )
            continue
        if interrupt_policy == INTERRUPT_QUEUE and existing_same and queue_enabled:
            queue_key = f"{str(Path(instance_path).resolve())}:{did}:{mode}:{str(scene.get('id') or scene_id)}"
            with _PLAY_QUEUE_HINTS_LOCK:
                qmap = _PLAY_QUEUE_HINTS.setdefault(str(Path(instance_path).resolve()), {})
                depth = max(0, int(qmap.get(queue_key) or 0))
                if queue_dedupe and depth > 0:
                    results.append({"ok": True, "queued": True, "sceneId": str(scene.get("id") or scene_id), "displayId": did, "queueDepth": depth})
                    continue
                if depth >= queue_max_length:
                    results.append({"ok": True, "dropped": True, "sceneId": str(scene.get("id") or scene_id), "displayId": did, "queueDepth": depth})
                    continue
                qmap[queue_key] = depth + 1
                results.append({"ok": True, "queued": True, "sceneId": str(scene.get("id") or scene_id), "displayId": did, "queueDepth": depth + 1})
            continue
        iid = f"inst_{uuid4().hex[:12]}"
        query = {"instanceId": iid, "surface": mode}
        if mode in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
            query["sceneId"] = str(scene.get("id") or scene_id)
        if runtime_token:
            query["kiosk_token"] = str(runtime_token)
        runtime_url = f"{base_root}/media/runtime/display/{did}?{urlencode(query)}"
        pid = 0
        if mode in (LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
            effective = eng._effective_display(cfg, display)
            launched = eng._launch_for_display(
                effective,
                runtime_url,
                launch_mode=mode,
                window_scale=max(0.05, min(1.0, float(((cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}).get("windowScale") or 0.25)))),
            )
            if not launched.get("ok"):
                return launched
            proc = launched.get("process")
            pid = max(0, int(getattr(proc, "pid", 0) or 0))
            if pid > 0 and proc is not None:
                handle = _SceneHandle(
                    scene_id=str(scene.get("id") or scene_id),
                    display_id=did,
                    pid=pid,
                    started_at_ms=_now_ms(),
                    runtime_url=runtime_url,
                    launch_mode=mode,
                    preview_viewport=preview_viewport,
                    process=proc,
                )
                with eng._lock:
                    eng._active[f"{did}:{pid}"] = handle
        inst = reg.create_instance(
            instance_id=iid,
            scene_id=str(scene.get("id") or scene_id),
            display_id=did,
            mode=mode,
            runtime_url=runtime_url,
            preview_viewport=preview_viewport,
            source=str(event_source or "").strip(),
            priority=int(scene.get("priority") or 100),
            blend_mode=str(scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
            interrupt_policy=interrupt_policy,
            duplicate_policy=duplicate_policy,
            audio_behaviour=scene.get("audioBehaviour") if isinstance(scene.get("audioBehaviour"), dict) else {},
            pid=pid,
            stack_behavior=stack_behavior,
        )
        results.append(
            {
                "ok": True,
                "id": str(inst.get("instance_id") or ""),
                "instanceId": str(inst.get("instance_id") or ""),
                "sceneId": str(inst.get("scene_id") or ""),
                "displayId": str(inst.get("display_id") or ""),
                "pid": max(0, int(((inst.get("process") or {}).get("pid") or 0))),
                "runtimeUrl": str(inst.get("runtime_url") or ""),
                "launchMode": mode,
                "state": str(inst.get("state") or ""),
                "surfaceId": str(inst.get("instance_id") or ""),
            }
        )

    run_media_maintenance(instance_path)
    return {
        "ok": True,
        "sceneId": str(scene.get("id") or scene_id),
        "displayIds": [str(row.get("displayId") or "") for row in results],
        "results": results,
        "reused": any(bool(row.get("reused")) for row in results),
        "queued": any(bool(row.get("queued")) for row in results),
        "dropped": any(bool(row.get("dropped")) for row in results),
        "instanceId": str(results[0].get("instanceId") or "") if results else "",
        "displayId": str(results[0].get("displayId") or "") if results else "",
        "runtimeUrl": str(results[0].get("runtimeUrl") or "") if results else "",
        "pid": int(results[0].get("pid") or 0) if results else 0,
        "launchMode": mode,
    }


def stop_scene(instance_path: str | Path, scene_id: str | None = None, session_id: str | None = None) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    res = reg.request_stop(scene_id=scene_id, instance_id=session_id)
    inst_key = str(Path(instance_path).resolve())
    with _PLAY_QUEUE_HINTS_LOCK:
        if scene_id:
            qmap = _PLAY_QUEUE_HINTS.get(inst_key, {})
            prefix = f"{inst_key}:"
            for key in list(qmap.keys()):
                if key.startswith(prefix) and key.endswith(f":{scene_id}"):
                    qmap.pop(key, None)
        elif session_id:
            pass
        else:
            _PLAY_QUEUE_HINTS.pop(inst_key, None)
    run_media_maintenance(instance_path)
    return {"ok": True, "stopped": int(res.get("stopped") or 0)}


def complete_scene(
    instance_path: str | Path,
    *,
    display_id: str,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    res = reg.complete(display_id=str(display_id or "").strip(), instance_id=session_id, scene_id=scene_id)
    run_media_maintenance(instance_path)
    return res


def detach_embedded_surface(instance_path: str | Path, display_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    res = reg.detach_embedded_by_display(str(display_id or "").strip())
    run_media_maintenance(instance_path)
    return res


def detach_surface(instance_path: str | Path, session_id: str) -> Dict[str, Any]:
    ensure_media_bus_worker(instance_path)
    reg = _get_registry(instance_path)
    res = reg.detach_surface(instance_id=str(session_id or "").strip())
    run_media_maintenance(instance_path)
    return res


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    event_name = str(name or "").strip().upper()
    payload = params if isinstance(params, dict) else {}
    reg = _get_registry(instance_path)

    if event_name in ("SCORING_EVAL", "SCORE_CHANGED"):
        updates: Dict[str, Any] = {}
        if "score" in payload:
            try:
                updates["score"] = f"{max(0, int(float(payload.get('score') or 0))):08d}"
            except Exception:
                pass
        if updates:
            reg.set_overlay_values(updates)
        return {"ok": True, "processed": bool(updates), "updates": updates}

    if event_name == "MEDIA_SET_OVERLAY":
        key = str(payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "missing_key"}
        overlay_values = reg.set_overlay_value(key, payload.get("value"))
        return {"ok": True, "processed": True, "overlayValues": overlay_values}

    if event_name == "MEDIA_SCENE_PLAY":
        scene_id = str(payload.get("sceneId") or "").strip()
        if not scene_id:
            return {"ok": False, "error": "missing_scene_id"}
        return play_scene(
            instance_path,
            scene_id=scene_id,
            base_url=str(payload.get("baseUrl") or "").strip() or None,
            runtime_token=str(payload.get("runtimeToken") or "").strip() or None,
            launch_mode=str(payload.get("launchMode") or LAUNCH_MODE_EMBEDDED).strip().lower() or LAUNCH_MODE_EMBEDDED,
            preview_viewport=payload.get("previewViewport") if isinstance(payload.get("previewViewport"), dict) else None,
            stack_behavior=str(payload.get("stackBehavior") or DEFAULT_SCENE_STACK_BEHAVIOR).strip().lower() or DEFAULT_SCENE_STACK_BEHAVIOR,
            event_source=str(source or "").strip(),
        )

    if event_name == "MEDIA_SCENE_STOP":
        scene_id = str(payload.get("sceneId") or "").strip() or None
        session_id = str(payload.get("sessionId") or "").strip() or None
        return stop_scene(instance_path, scene_id=scene_id, session_id=session_id)

    if event_name == "MEDIA_STOP_ALL":
        return stop_scene(instance_path, scene_id=None, session_id=None)

    if event_name == "MEDIA_SCENE_COMPLETE":
        display_id = str(payload.get("displayId") or "").strip()
        if not display_id:
            return {"ok": False, "error": "missing_display_id"}
        return complete_scene(
            instance_path,
            display_id=display_id,
            session_id=str(payload.get("sessionId") or "").strip() or None,
            scene_id=str(payload.get("sceneId") or "").strip() or None,
        )

    return {"ok": True, "processed": False}


def runtime_display_payload(
    instance_path: str | Path,
    display_id: str,
    scene_id: str | None = None,
    *,
    session_id: str | None = None,
    surface_type: str | None = None,
    instance_id: str | None = None,
) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    req_instance_id = str(instance_id or session_id or "").strip()
    if req_instance_id:
        try:
            _get_registry(instance_path).heartbeat(instance_id=req_instance_id)
        except Exception:
            pass
    state = load_media_state(instance_path, persist=False)
    displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    display = next((d for d in displays if str(d.get("id") or "") == str(display_id)), None)
    if not display:
        display = next((d for d in displays if str(d.get("role") or "") == str(display_id)), None)
    if not display:
        display = displays[0] if displays else _default_displays()[0]
    resolved_display_id = str(display.get("id") or "display_1")

    req_scene_id = str(scene_id or "").strip()
    surface_key = str(surface_type or "").strip().lower()
    instances = [row for row in (state.get("instances") if isinstance(state.get("instances"), list) else []) if isinstance(row, dict)]
    by_id = {str(row.get("instance_id") or ""): row for row in instances if str(row.get("instance_id") or "")}
    display_states = state.get("displayStates") if isinstance(state.get("displayStates"), dict) else {}
    stack = display_states.get(resolved_display_id, {}).get("stack") if isinstance(display_states.get(resolved_display_id), dict) else []
    stack = stack if isinstance(stack, list) else []
    render_display_id = resolved_display_id

    selected_rows: List[Dict[str, Any]] = []
    if req_instance_id and req_instance_id in by_id:
        row = by_id[req_instance_id]
        row_mode = _normalize_launch_mode(row.get("mode"))
        if surface_key in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN) and row_mode != surface_key:
            selected_rows = []
        else:
            selected_rows = [row]
            render_display_id = str(selected_rows[0].get("display_id") or resolved_display_id).strip() or resolved_display_id
    elif req_scene_id:
        selected_rows = [
            row for row in instances
            if str(row.get("display_id") or "") == resolved_display_id
            and str(row.get("scene_id") or "") == req_scene_id
            and str(row.get("desired_state") or "") == DESIRED_PRESENT
            and (surface_key not in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN) or _normalize_launch_mode(row.get("mode")) == surface_key)
            and str(row.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
        ]
        if not selected_rows:
            forced_scene = next((s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if str(s.get("id") or "") == req_scene_id), None)
            if isinstance(forced_scene, dict):
                selected_rows = [
                    {
                        "instance_id": f"virtual_{resolved_display_id}_{req_scene_id}",
                        "scene_id": req_scene_id,
                        "display_id": resolved_display_id,
                        "mode": LAUNCH_MODE_WINDOWED,
                        "state": INSTANCE_STATE_RUNNING,
                        "desired_state": DESIRED_PRESENT,
                        "created_at": _now_ms(),
                        "priority": int(forced_scene.get("priority") or 100),
                        "blend_mode": str(forced_scene.get("blendMode") or BLEND_MODE_STOP_LOWER),
                        "audio_behaviour": dict(forced_scene.get("audioBehaviour") if isinstance(forced_scene.get("audioBehaviour"), dict) else {}),
                    }
                ]
    else:
        for iid in stack:
            inst = by_id.get(str(iid or ""))
            if not isinstance(inst, dict):
                continue
            if surface_key == LAUNCH_MODE_EMBEDDED and _normalize_launch_mode(inst.get("mode")) != LAUNCH_MODE_EMBEDDED:
                continue
            if surface_key == LAUNCH_MODE_FULLSCREEN and _normalize_launch_mode(inst.get("mode")) != LAUNCH_MODE_FULLSCREEN:
                continue
            if str(inst.get("desired_state") or "") != DESIRED_PRESENT:
                continue
            if str(inst.get("state") or "") not in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING):
                continue
            selected_rows.append(inst)

    if not selected_rows and str(surface_type or "").strip().lower() == LAUNCH_MODE_WINDOWED and not req_instance_id:
        candidates = [
            row for row in instances
            if str(row.get("display_id") or "") == resolved_display_id
            and _normalize_launch_mode(row.get("mode")) == LAUNCH_MODE_WINDOWED
            and str(row.get("desired_state") or "") == DESIRED_PRESENT
            and str(row.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
        ]
        candidates.sort(key=lambda r: int(r.get("created_at") or 0), reverse=True)
        if candidates:
            selected_rows = [candidates[0]]
            render_display_id = str(candidates[0].get("display_id") or resolved_display_id).strip() or resolved_display_id
    if not selected_rows and str(surface_type or "").strip().lower() == LAUNCH_MODE_FULLSCREEN and not req_instance_id:
        candidates = [
            row for row in instances
            if str(row.get("display_id") or "") == resolved_display_id
            and _normalize_launch_mode(row.get("mode")) == LAUNCH_MODE_FULLSCREEN
            and str(row.get("desired_state") or "") == DESIRED_PRESENT
            and str(row.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
        ]
        candidates.sort(key=lambda r: int(r.get("created_at") or 0), reverse=True)
        if candidates:
            selected_rows = [candidates[0]]
            render_display_id = str(candidates[0].get("display_id") or resolved_display_id).strip() or resolved_display_id
    if not selected_rows and req_instance_id:
        any_mode = [
            row for row in instances
            if str(row.get("instance_id") or "") == req_instance_id
            and (surface_key not in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN) or _normalize_launch_mode(row.get("mode")) == surface_key)
        ]
        if any_mode:
            selected_rows = [any_mode[0]]
            render_display_id = str(any_mode[0].get("display_id") or resolved_display_id).strip() or resolved_display_id
    if not selected_rows and not req_instance_id and surface_key not in (LAUNCH_MODE_EMBEDDED, LAUNCH_MODE_WINDOWED, LAUNCH_MODE_FULLSCREEN):
        candidates = [
            row for row in instances
            if str(row.get("display_id") or "") == resolved_display_id
            and str(row.get("desired_state") or "") == DESIRED_PRESENT
            and str(row.get("state") or "") in (INSTANCE_STATE_STARTING, INSTANCE_STATE_RUNNING, INSTANCE_STATE_STOPPING)
        ]
        candidates.sort(key=lambda r: int(r.get("created_at") or 0), reverse=True)
        if candidates:
            selected_rows = [candidates[0]]
            render_display_id = str(candidates[0].get("display_id") or resolved_display_id).strip() or resolved_display_id

    session_rows = [
        {
            "id": str(inst.get("instance_id") or ""),
            "sceneId": str(inst.get("scene_id") or ""),
            "displayId": str(inst.get("display_id") or ""),
            "startedAtMs": max(0, int(inst.get("created_at") or 0)),
            "launchMode": _normalize_launch_mode(inst.get("mode")),
            "runtimeUrl": str(inst.get("runtime_url") or ""),
            "priority": int(inst.get("priority") or 100),
            "blendMode": str(inst.get("blend_mode") or BLEND_MODE_STOP_LOWER),
            "audioBehaviour": dict(inst.get("audio_behaviour") if isinstance(inst.get("audio_behaviour"), dict) else {}),
            "previewViewport": inst.get("preview_viewport") if isinstance(inst.get("preview_viewport"), dict) else None,
        }
        for inst in selected_rows
    ]
    layers = _render_layers_for_display(cfg, render_display_id, session_rows)
    top = layers[-1] if layers else None
    scene = top.get("scene") if isinstance(top, dict) and isinstance(top.get("scene"), dict) else None
    asset = top.get("asset") if isinstance(top, dict) and isinstance(top.get("asset"), dict) else None
    active = None
    if isinstance(top, dict):
        active = {
            "instanceId": str((top.get("sessionId") or "") or ""),
            "sessionId": str((top.get("sessionId") or "") or ""),
            "sceneId": str((top.get("scene") or {}).get("id") or ""),
            "displayId": render_display_id,
            "pid": 0,
            "startedAtMs": int(top.get("startedAtMs") or 0),
            "runtimeUrl": str((selected_rows[-1].get("runtime_url") if selected_rows else "") or ""),
            "launchMode": _normalize_launch_mode(top.get("launchMode")),
        }

    overlay_values = state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else {}
    merged_overlay_values: Dict[str, Any] = dict(overlay_values)
    scoring_state = _load_scoring_state_nonblocking(instance_path)
    game_active = False
    if isinstance(scoring_state, dict):
        score_val = int(float(scoring_state.get("score") or 0))
        merged_overlay_values["score"] = f"{max(0, score_val):08d}"
        game = scoring_state.get("game") if isinstance(scoring_state.get("game"), dict) else {}
        started_ms = int(float(game.get("startedAtMs") or 0)) if isinstance(game, dict) else 0
        ended_ms = int(float(game.get("endedAtMs") or 0)) if isinstance(game, dict) else 0
        game_active = bool(game.get("active")) if isinstance(game, dict) else False
        now_ms = _now_ms()
        elapsed_ms = (now_ms - started_ms) if (started_ms > 0 and game_active) else (max(0, ended_ms - started_ms) if started_ms > 0 else 0)
        merged_overlay_values["game_elapsed_time"] = _format_elapsed_mmss(elapsed_ms)
        merged_overlay_values["player"] = str(scoring_state.get("player") or merged_overlay_values.get("player") or "1")
        merged_overlay_values["ball"] = str(scoring_state.get("ball") or merged_overlay_values.get("ball") or "1")
        merged_overlay_values["credit"] = str(scoring_state.get("credit") or merged_overlay_values.get("credit") or "0")

    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    configured_poll_ms = max(40, int(float(settings.get("runtimePollMs") or 150)))
    runtime_poll_ms = min(configured_poll_ms, 80) if game_active else configured_poll_ms
    return {
        "ok": True,
        "renderer": "chromium",
        "updatedAt": state.get("updatedAt") or _utc_now_iso(),
        "display": display,
        "active": active,
        "scene": scene,
        "asset": asset,
        "layers": layers,
        "overlayValues": merged_overlay_values,
        "settings": {"runtimePollMs": runtime_poll_ms},
    }


# Isolated runtime implementation. These re-exported names intentionally
# override the older in-file runtime path above.
from pinballctl.media.runtime_isolated import (  # noqa: E402
    attach_runtime_surface,
    complete_scene,
    detach_embedded_surface,
    detach_surface,
    heartbeat_runtime_surface,
    list_runtime_instances,
    load_media_state,
    play_scene,
    process_event,
    run_media_maintenance,
    runtime_display_payload,
    stop_scene,
)
