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
from urllib.parse import urlencode
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List
from uuid import uuid4

LAUNCH_MODE_FULLSCREEN = "fullscreen"
LAUNCH_MODE_WINDOWED = "windowed"
LAUNCH_MODE_EMBEDDED = "embedded"


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


def _media_config_path(instance_path: str | Path) -> Path:
    return _media_dir(instance_path) / "media.json"


def _media_state_path(instance_path: str | Path) -> Path:
    return _media_dir(instance_path) / "media_state.json"


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
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False
    return True


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
    time.sleep(0.08)
    if _is_pid_alive(target):
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
            "runtimePollMs": 150,
        },
        "displays": _default_displays(),
        "assets": [],
        "scenes": [],
    }


def _normalize_overlay(overlay: Dict[str, Any], idx: int) -> Dict[str, Any]:
    typ = str(overlay.get("type") or "text").strip().lower()
    if typ == "badge":
        typ = "text"
    if typ not in ("text", "image", "frame"):
        typ = "text"
    bg_raw = str(overlay.get("bgColor") or "transparent").strip()
    text_align = str(overlay.get("textAlign") or "center").strip().lower()
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
    text_effects_in = overlay.get("textEffects")
    text_effects: List[str] = []
    if isinstance(text_effects_in, list):
        for raw in text_effects_in:
            eff = str(raw or "").strip().lower()
            if eff in effects_allowed and eff not in text_effects:
                text_effects.append(eff)
    out = {
        "id": str(overlay.get("id") or f"overlay_{idx+1}").strip() or f"overlay_{idx+1}",
        "name": str(overlay.get("name") or f"Overlay {idx+1}").strip() or f"Overlay {idx+1}",
        "type": typ,
        "text": str(overlay.get("text") or "").strip(),
        "valueKey": str(overlay.get("valueKey") or "").strip(),
        "textAlign": text_align,
        "textEffects": text_effects,
        "xPct": max(0.0, min(100.0, float(overlay.get("xPct") or 0.0))),
        "yPct": max(0.0, min(100.0, float(overlay.get("yPct") or 0.0))),
        "wPct": max(0.0, min(100.0, float(overlay.get("wPct") or 20.0))),
        "hPct": max(0.0, min(100.0, float(overlay.get("hPct") or 8.0))),
        "rotateDeg": float(overlay.get("rotateDeg") or 0.0),
        "scale": max(0.1, min(8.0, float(overlay.get("scale") or 1.0))),
        "opacity": max(0.0, min(1.0, float(overlay.get("opacity") or 1.0))),
        "color": str(overlay.get("color") or "#ffffff").strip() or "#ffffff",
        "bgColor": bg_raw if bg_raw else "transparent",
        "fontSizePx": max(8, min(256, int(float(overlay.get("fontSizePx") or 28)))),
        "fontFamily": str(overlay.get("fontFamily") or "").strip()[:160],
        "zIndex": max(0, min(9999, int(float(overlay.get("zIndex") or (idx + 1))))),
        "assetId": str(overlay.get("assetId") or "").strip(),
        "fit": str(overlay.get("fit") or "contain").strip().lower() if str(overlay.get("fit") or "").strip().lower() in ("cover", "contain", "fill", "none", "scale-down") else "contain",
    }
    if typ == "frame":
        out["text"] = ""
        out["valueKey"] = ""
        out["textAlign"] = "center"
        out["textEffects"] = []
        out["xPct"] = 0.0
        out["yPct"] = 0.0
        out["wPct"] = 100.0
        out["hPct"] = 100.0
        out["rotateDeg"] = 0.0
        out["scale"] = 1.0
        out["color"] = "#ffffff"
        out["bgColor"] = "transparent"
        out["fontSizePx"] = 24
        out["fontFamily"] = ""
    return out


def _normalize_scene(scene: Dict[str, Any], idx: int) -> Dict[str, Any]:
    overlays = scene.get("overlays") if isinstance(scene.get("overlays"), list) else []
    target = str(scene.get("targetDisplay") or "").strip()
    return {
        "id": str(scene.get("id") or f"scene_{idx+1}").strip() or f"scene_{idx+1}",
        "name": str(scene.get("name") or f"Scene {idx+1}").strip() or f"Scene {idx+1}",
        "targetDisplay": target or "backbox",
        "baseAssetId": str(scene.get("baseAssetId") or "").strip(),
        "loop": bool(scene.get("loop", True)),
        "mute": bool(scene.get("mute", True)),
        "overlays": [_normalize_overlay(ov, i) for i, ov in enumerate(overlays) if isinstance(ov, dict)],
    }


def normalize_media_config(cfg: Dict[str, Any] | None) -> Dict[str, Any]:
    cfg = cfg if isinstance(cfg, dict) else {}
    defaults = _default_config()
    settings_in = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    displays_in = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    assets_in = cfg.get("assets") if isinstance(cfg.get("assets"), list) else []
    scenes_in = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []

    out = {
        "settings": {
            "enabled": bool(settings_in.get("enabled", defaults["settings"]["enabled"])),
            "renderer": "chromium",
            "previewScale": max(0.1, min(1.0, float(settings_in.get("previewScale", defaults["settings"]["previewScale"])))),
            "windowScale": max(0.05, min(1.0, float(settings_in.get("windowScale", defaults["settings"]["windowScale"])))),
            "defaultDisplayRole": str(settings_in.get("defaultDisplayRole") or defaults["settings"]["defaultDisplayRole"]).strip() or "backbox",
            "runtimePollMs": max(40, min(5000, int(float(settings_in.get("runtimePollMs") or defaults["settings"]["runtimePollMs"])))),
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


def get_media_environment() -> Dict[str, Any]:
    browser_cmd = _find_browser_cmd()
    return {
        "renderer": {
            "name": "chromium",
            "chromiumFound": bool(browser_cmd),
            "binary": browser_cmd[0] if browser_cmd else "",
            "platform": platform.system(),
        },
        "tooling": _detect_media_tooling(),
        "displays": detect_displays(),
        "fonts": _detect_system_fonts(),
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
        time.sleep(0.08)
        try:
            if p.poll() is None:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass

    def _resolve_display(self, cfg: Dict[str, Any], scene: Dict[str, Any]) -> Dict[str, Any]:
        display_key = str(scene.get("targetDisplay") or "").strip()
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
        # layouts from ambiguous coordinates so targetDisplay can still work.
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
        # left-to-right virtual layout so fullscreen placement honors targetDisplay.
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
        profile_dir = _media_profiles_dir(self.instance_path) / f"{display_id}_{profile_suffix}"
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

    def play_scene(
        self,
        cfg: Dict[str, Any],
        scene_id: str,
        *,
        base_url: str | None = None,
        runtime_token: str | None = None,
        launch_mode: str = LAUNCH_MODE_FULLSCREEN,
        preview_viewport: Dict[str, int] | None = None,
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

        display = self._resolve_display(cfg, scene)
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


def _get_engine(instance_path: str | Path) -> _ChromiumEngine:
    key = str(Path(instance_path).resolve())
    with _ENGINES_LOCK:
        eng = _ENGINES.get(key)
        if eng is None:
            eng = _ChromiumEngine(key)
            _ENGINES[key] = eng
        return eng


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
    cfg["scenes"] = [
        {
            **s,
            "baseAssetId": "" if str(s.get("baseAssetId") or "") == str(asset_id) else str(s.get("baseAssetId") or ""),
            "overlays": [
                {**ov, "assetId": "" if str(ov.get("assetId") or "") == str(asset_id) else str(ov.get("assetId") or "")}
                for ov in (s.get("overlays") if isinstance(s.get("overlays"), list) else [])
                if isinstance(ov, dict)
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
    persisted = _read_json(_media_state_path(instance_path), {"engine": {"active": []}, "overlayValues": {}})
    eng = _get_engine(instance_path)
    live = eng.snapshot()
    persisted_active = _normalize_active_rows(
        persisted.get("engine", {}).get("active", []) if isinstance(persisted.get("engine"), dict) else []
    )
    live_active = _normalize_active_rows(live.get("active", []))

    # Keep cross-worker state stable:
    # - start from persisted active rows that still have a running PID
    # - keep embedded rows (pid=0) as virtual active sessions for in-app previews
    # - overlay/replace with local live rows for any PID this worker owns
    active_by_pid: Dict[int, Dict[str, Any]] = {}
    embedded_by_display: Dict[str, Dict[str, Any]] = {}
    for row in persisted_active:
        pid = int(row.get("pid") or 0)
        launch_mode = _normalize_launch_mode(row.get("launchMode"))
        if launch_mode == LAUNCH_MODE_EMBEDDED:
            display_id = str(row.get("displayId") or "").strip()
            scene_id = str(row.get("sceneId") or "").strip()
            if display_id and scene_id:
                embedded_by_display[display_id] = row
            continue
        if pid > 0 and _is_pid_alive(pid):
            active_by_pid[pid] = row
    for row in live_active:
        pid = int(row.get("pid") or 0)
        if pid > 0:
            active_by_pid[pid] = row
    merged_active = list(active_by_pid.values())
    live_display_ids = {str(row.get("displayId") or "").strip() for row in merged_active if str(row.get("displayId") or "").strip()}
    for display_id, row in embedded_by_display.items():
        if display_id in live_display_ids:
            continue
        merged_active.append(row)
    overlay_values = persisted.get("overlayValues") if isinstance(persisted.get("overlayValues"), dict) else {}
    merged_overlay_values = _default_overlay_values()
    merged_overlay_values.update(overlay_values)
    state = {
        "updatedAt": _utc_now_iso(),
        "engine": {"backend": "chromium", "active": merged_active},
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
) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    mode = _normalize_launch_mode(launch_mode)
    if mode == LAUNCH_MODE_EMBEDDED:
        scenes = cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []
        scene = next((s for s in scenes if str(s.get("id") or "") == str(scene_id)), None)
        if not isinstance(scene, dict):
            return {"ok": False, "error": "scene_not_found"}
        displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
        display = next(
            (
                d
                for d in displays
                if str(d.get("id") or "") == str(scene.get("targetDisplay") or "").strip()
                or str(d.get("role") or "") == str(scene.get("targetDisplay") or "").strip()
            ),
            None,
        )
        if not isinstance(display, dict):
            display = displays[0] if displays else _default_displays()[0]
        display_id = str(display.get("id") or "display_1")
        runtime_url = _ChromiumEngine(instance_path)._runtime_url_for_display(
            display_id,
            base_url=base_url,
            runtime_token=runtime_token,
            scene_id=str(scene.get("id") or scene_id),
        )
        state = _read_json(_media_state_path(instance_path), {"engine": {"active": []}, "overlayValues": {}})
        active_rows = _normalize_active_rows(state.get("engine", {}).get("active", []) if isinstance(state.get("engine"), dict) else [])
        active_rows = [row for row in active_rows if str(row.get("displayId") or "") != display_id]
        active_rows.append(
            {
                "sceneId": str(scene.get("id") or scene_id),
                "displayId": display_id,
                "pid": 0,
                "startedAtMs": _now_ms(),
                "runtimeUrl": runtime_url,
                "launchMode": LAUNCH_MODE_EMBEDDED,
                "previewViewport": preview_viewport if isinstance(preview_viewport, dict) else None,
            }
        )
        state["engine"] = {"backend": "chromium", "active": active_rows}
        state["updatedAt"] = _utc_now_iso()
        _write_json(_media_state_path(instance_path), state)
        load_media_state(instance_path)
        return {
            "ok": True,
            "sceneId": str(scene.get("id") or scene_id),
            "displayId": display_id,
            "pid": 0,
            "reused": False,
            "renderer": "embedded",
            "runtimeUrl": runtime_url,
            "launchMode": LAUNCH_MODE_EMBEDDED,
        }

    eng = _get_engine(instance_path)
    result = eng.play_scene(
        cfg,
        scene_id,
        base_url=base_url,
        runtime_token=runtime_token,
        launch_mode=mode,
        preview_viewport=preview_viewport,
    )
    load_media_state(instance_path)
    return result


def stop_scene(instance_path: str | Path, scene_id: str | None = None) -> Dict[str, Any]:
    eng = _get_engine(instance_path)
    result = eng.stop_scene(scene_id=scene_id)

    # Fallback for multi-worker deployments where this worker does not hold
    # the local subprocess handle but persisted state has active PIDs.
    state = _read_json(_media_state_path(instance_path), {"engine": {"active": []}, "overlayValues": {}})
    active_rows = _normalize_active_rows(state.get("engine", {}).get("active", []) if isinstance(state.get("engine"), dict) else [])
    stopped_pids: set[int] = set()
    stopped_embedded = 0
    kept_rows: List[Dict[str, Any]] = []
    for row in active_rows:
        pid = int(row.get("pid") or 0)
        row_scene = str(row.get("sceneId") or "")
        runtime_url = str(row.get("runtimeUrl") or "").strip()
        launch_mode = _normalize_launch_mode(row.get("launchMode"))
        match = not scene_id or row_scene == str(scene_id)
        if launch_mode == LAUNCH_MODE_EMBEDDED:
            if match:
                stopped_embedded += 1
            else:
                kept_rows.append(row)
            continue
        if not match:
            if _is_pid_alive(pid):
                kept_rows.append(row)
            continue
        # Safety guard: never kill arbitrary browser PIDs; only stop
        # processes that match pinballctl-managed media runtime launches.
        if not _is_managed_media_pid(instance_path, pid):
            if _is_pid_alive(pid):
                kept_rows.append(row)
            continue
        if runtime_url and "/media/runtime/display/" not in runtime_url:
            if _is_pid_alive(pid):
                kept_rows.append(row)
            continue
        if _stop_pid(pid):
            stopped_pids.add(pid)
            continue
        if _is_pid_alive(pid):
            kept_rows.append(row)

    if stopped_pids or stopped_embedded:
        result["stopped"] = int(result.get("stopped") or 0) + len(stopped_pids) + stopped_embedded

    state["engine"] = {"backend": "chromium", "active": kept_rows}
    state["updatedAt"] = _utc_now_iso()
    _write_json(_media_state_path(instance_path), state)
    load_media_state(instance_path)
    return result


def set_overlay_value(instance_path: str | Path, key: str, value: Any) -> Dict[str, Any]:
    if not str(key or "").strip():
        return {"ok": False, "error": "missing_key"}
    state = _read_json(_media_state_path(instance_path), {"engine": {"active": []}, "overlayValues": {}})
    overlay_values = state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else {}
    if not overlay_values:
        overlay_values = _default_overlay_values()
    overlay_values[str(key).strip()] = value
    state["overlayValues"] = overlay_values
    state["updatedAt"] = _utc_now_iso()
    _write_json(_media_state_path(instance_path), state)
    return {"ok": True, "overlayValues": overlay_values}


def runtime_display_payload(instance_path: str | Path, display_id: str, scene_id: str | None = None) -> Dict[str, Any]:
    cfg = load_media_config(instance_path)
    state = load_media_state(instance_path, persist=False)

    displays = cfg.get("displays") if isinstance(cfg.get("displays"), list) else []
    display = next((d for d in displays if str(d.get("id") or "") == str(display_id)), None)
    if not display:
        display = next((d for d in displays if str(d.get("role") or "") == str(display_id)), None)
    if not display:
        display = displays[0] if displays else _default_displays()[0]

    resolved_display_id = str(display.get("id") or "display_1")
    active_rows = state.get("engine", {}).get("active", []) if isinstance(state.get("engine"), dict) else []
    requested_scene_id = str(scene_id or "").strip()
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
        "overlayValues": merged_overlay_values,
        "settings": {
            "runtimePollMs": runtime_poll_ms,
        },
    }
