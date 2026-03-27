"""Godot-backed media runtime for pinballctl.

This module keeps the authored media config in pinballctl while delegating
rendering and runtime control to one or more external Godot 4 processes.
"""
from __future__ import annotations

import json
import logging
import os
import platform
import re
import shlex
import shutil
import signal
import socket
import subprocess
import time
import importlib
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

LOGGER = logging.getLogger(__name__)

LAUNCH_MODE_FULLSCREEN = "fullscreen"
LAUNCH_MODE_WINDOWED = "windowed"
LAUNCH_MODE_EMBEDDED = "embedded"
STATE_STOPPED = "stopped"
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_CRASHED = "crashed"
_WS_CONNECT = None
_WS_IMPORT_ATTEMPTED = False
_DAEMON_ENV = "PINBALLCTL_GODOT_DAEMON"
_VIDEO_PROFILE_TAG = "hq1"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _running_under_gunicorn() -> bool:
    server_software = str(os.environ.get("SERVER_SOFTWARE") or "").lower()
    if "gunicorn" in server_software:
        return True
    return any("gunicorn" in str(arg).lower() for arg in os.sys.argv[:4])


def _in_daemon_process() -> bool:
    return str(os.environ.get(_DAEMON_ENV) or "").strip() == "1"


def _get_ws_connect():
    global _WS_CONNECT, _WS_IMPORT_ATTEMPTED
    if _WS_IMPORT_ATTEMPTED:
        return _WS_CONNECT
    _WS_IMPORT_ATTEMPTED = True
    try:
        client_mod = importlib.import_module("websockets.sync.client")
        _WS_CONNECT = getattr(client_mod, "connect", None)
    except Exception:
        _WS_CONNECT = None
    return _WS_CONNECT


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


def _default_overlay_values() -> Dict[str, Any]:
    return {
        "player": "1",
        "score": "00000000",
        "ball": "1",
        "credit": "0",
        "game_elapsed_time": "00:00",
    }


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


def _normalize_launch_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode == LAUNCH_MODE_WINDOWED:
        return LAUNCH_MODE_WINDOWED
    if mode == LAUNCH_MODE_EMBEDDED:
        return LAUNCH_MODE_EMBEDDED
    return LAUNCH_MODE_FULLSCREEN


def _media_dir(instance_path: str | Path) -> Path:
    path = Path(instance_path) / "media"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _media_config_path(instance_path: str | Path) -> Path:
    return _media_dir(instance_path) / "media.json"


def _media_assets_dir(instance_path: str | Path) -> Path:
    path = _media_dir(instance_path) / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_base_dir(instance_path: str | Path) -> Path:
    path = _media_dir(instance_path) / "godot"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_instances_dir(instance_path: str | Path) -> Path:
    path = _godot_base_dir(instance_path) / "instances"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_runtime_dir(instance_path: str | Path, runtime_id: str | None = None) -> Path:
    safe_runtime = _safe_key(str(runtime_id or "display_1"), "runtime")
    path = _godot_instances_dir(instance_path) / safe_runtime
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_runtime_state_path(instance_path: str | Path, runtime_id: str | None = None) -> Path:
    return _godot_runtime_dir(instance_path, runtime_id) / "runtime_state.json"


def _godot_scene_registry_path(instance_path: str | Path) -> Path:
    return _godot_base_dir(instance_path) / "scene_registry.json"


def _godot_scene_upload_dir(instance_path: str | Path) -> Path:
    path = _godot_base_dir(instance_path) / "scenes"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_log_dir(instance_path: str | Path, runtime_id: str | None = None) -> Path:
    path = _godot_runtime_dir(instance_path, runtime_id) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_cache_dir(instance_path: str | Path) -> Path:
    path = _godot_base_dir(instance_path) / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _godot_cache_assets_dir(instance_path: str | Path) -> Path:
    path = _godot_cache_dir(instance_path) / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def godot_daemon_socket_path(instance_path: str | Path) -> Path:
    return _godot_base_dir(instance_path) / "daemon.sock"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _godot_project_path() -> Path:
    return _project_root() / "src" / "godot"


def _configured_displays(cfg: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    cfg = cfg if isinstance(cfg, dict) else {}
    displays = [row for row in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(row, dict)]
    return displays or _default_displays()


def _runtime_targets(instance_path: str | Path) -> List[Dict[str, Any]]:
    cfg = _load_media_config(instance_path)
    displays = _configured_displays(cfg)
    targets: List[Dict[str, Any]] = []
    for idx, row in enumerate(displays):
        if not bool(row.get("enabled", True)):
            continue
        display_id = str(row.get("id") or f"display_{idx+1}").strip() or f"display_{idx+1}"
        role = str(row.get("role") or "").strip()
        label = str(row.get("name") or role or display_id).strip() or display_id
        targets.append(
            {
                "id": display_id,
                "name": label,
                "displayId": display_id,
                "role": role or display_id,
                "screenIndex": max(1, int(float(row.get("screenIndex") or idx + 1))),
                "width": max(64, int(float(row.get("width") or 1920))),
                "height": max(64, int(float(row.get("height") or 1080))),
                "x": int(float(row.get("x") or 0)),
                "y": int(float(row.get("y") or 0)),
            }
        )
    if not targets:
        row = _default_displays()[0]
        targets.append(
            {
                "id": str(row.get("id") or "display_1"),
                "name": str(row.get("name") or "Primary Display"),
                "displayId": str(row.get("id") or "display_1"),
                "role": str(row.get("role") or "backbox"),
                "screenIndex": 1,
                "width": 1920,
                "height": 1080,
                "x": 0,
                "y": 0,
            }
        )
    return targets


def _effective_displays(instance_path: str | Path, cfg: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    cfg = cfg if isinstance(cfg, dict) else _load_media_config(instance_path)
    configured = _configured_displays(cfg)
    live_rows = _detect_displays_local()
    if not live_rows:
        return configured if configured else _default_displays()

    merged: List[Dict[str, Any]] = []
    total = max(len(configured), len(live_rows))
    for idx in range(total):
        cfg_row = configured[idx] if idx < len(configured) and isinstance(configured[idx], dict) else {}
        live_row = live_rows[idx] if idx < len(live_rows) and isinstance(live_rows[idx], dict) else {}
        if not cfg_row and not live_row:
            continue
        did = str(cfg_row.get("id") or live_row.get("id") or f"display_{idx+1}").strip() or f"display_{idx+1}"
        merged.append(
            {
                "id": did,
                "name": str(cfg_row.get("name") or live_row.get("name") or did).strip() or did,
                "width": max(64, int(float(live_row.get("width") or cfg_row.get("width") or 1920))),
                "height": max(64, int(float(live_row.get("height") or cfg_row.get("height") or 1080))),
                "x": int(float(live_row.get("x") or cfg_row.get("x") or 0)),
                "y": int(float(live_row.get("y") or cfg_row.get("y") or 0)),
                "role": str(cfg_row.get("role") or live_row.get("role") or ("backbox" if idx == 0 else f"aux_{idx+1}")).strip() or ("backbox" if idx == 0 else f"aux_{idx+1}"),
                "enabled": bool(cfg_row.get("enabled", live_row.get("enabled", True))),
                "screenIndex": max(1, int(float(live_row.get("screenIndex") or cfg_row.get("screenIndex") or (idx + 1)))),
            }
        )
    return merged or configured


def _detect_displays_local() -> List[Dict[str, Any]]:
    for fn in (_detect_displays_screeninfo_local, _detect_displays_xrandr_local, _detect_displays_swift_local, _detect_displays_system_profiler_local):
        rows = fn()
        if rows:
            return rows
    return []


def _detect_displays_screeninfo_local() -> List[Dict[str, Any]]:
    if platform.system().lower() == "darwin":
        return []
    try:
        from screeninfo import get_monitors  # type: ignore
    except Exception:
        return []
    monitors = list(get_monitors())
    if not monitors:
        return []
    monitors.sort(key=lambda m: (0 if bool(getattr(m, "is_primary", False)) else 1, int(getattr(m, "x", 0) or 0), int(getattr(m, "y", 0) or 0)))
    out: List[Dict[str, Any]] = []
    for idx, mon in enumerate(monitors, start=1):
        out.append(
            {
                "id": f"display_{idx}",
                "name": f"Display {idx}",
                "width": int(getattr(mon, "width", 1920) or 1920),
                "height": int(getattr(mon, "height", 1080) or 1080),
                "x": int(getattr(mon, "x", 0) or 0),
                "y": int(getattr(mon, "y", 0) or 0),
                "role": "backbox" if idx == 1 else f"aux_{idx}",
                "enabled": True,
                "screenIndex": idx,
            }
        )
    return out


def _detect_displays_xrandr_local() -> List[Dict[str, Any]]:
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
        out.append(
            {
                "id": f"display_{idx}",
                "name": f"Display {idx}",
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


def _detect_displays_swift_local() -> List[Dict[str, Any]]:
    if platform.system().lower() != "darwin" or not shutil.which("swift"):
        return []
    script = """
import AppKit
let screens = NSScreen.screens
for (idx, screen) in screens.enumerated() {
    let frame = screen.frame
    let isPrimary = screen == NSScreen.main
    print("\\(idx + 1)|\\(Int(frame.origin.x))|\\(Int(frame.origin.y))|\\(Int(frame.size.width))|\\(Int(frame.size.height))|\\(isPrimary ? 1 : 0)")
}
"""
    try:
        proc = subprocess.run(
            ["swift", "-e", script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        lines = (proc.stdout or "").splitlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for raw in lines:
        parts = [str(part or "").strip() for part in str(raw or "").split("|")]
        if len(parts) != 6:
            continue
        try:
            idx = int(parts[0])
            x = int(parts[1])
            y = int(parts[2])
            width = int(parts[3])
            height = int(parts[4])
            is_primary = parts[5] == "1"
        except Exception:
            continue
        out.append(
            {
                "id": f"display_{idx}",
                "name": f"Display {idx}",
                "width": width,
                "height": height,
                "x": x,
                "y": y,
                "role": "backbox" if idx == 1 else f"aux_{idx}",
                "enabled": True,
                "screenIndex": idx,
                "isPrimary": is_primary,
            }
        )
    return out


def _detect_displays_system_profiler_local() -> List[Dict[str, Any]]:
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


def _default_runtime_id(instance_path: str | Path) -> str:
    targets = _runtime_targets(instance_path)
    return str(((targets[0] if targets else {}).get("id")) or "display_1")


def _resolve_runtime_id(instance_path: str | Path, runtime_id: str | None = None, display_id: str | None = None) -> str:
    requested = str(runtime_id or display_id or "").strip()
    targets = _runtime_targets(instance_path)
    if requested:
        for row in targets:
            if str(row.get("id") or "") == requested or str(row.get("displayId") or "") == requested:
                return str(row.get("id") or requested)
        return _safe_key(requested, "runtime")
    return _default_runtime_id(instance_path)


def _runtime_target(instance_path: str | Path, runtime_id: str | None = None, display_id: str | None = None) -> Dict[str, Any]:
    resolved = _resolve_runtime_id(instance_path, runtime_id, display_id)
    for row in _runtime_targets(instance_path):
        if str(row.get("id") or "") == resolved:
            return row
    return {
        "id": resolved,
        "name": resolved,
        "displayId": str(display_id or resolved or "display_1"),
        "role": resolved,
        "screenIndex": 1,
        "width": 1920,
        "height": 1080,
        "x": 0,
        "y": 0,
    }


def _preferred_port(instance_path: str | Path, runtime_id: str, fallback: int) -> int:
    targets = _runtime_targets(instance_path)
    ids = [str(row.get("id") or "") for row in targets]
    try:
        offset = max(0, ids.index(str(runtime_id)))
    except ValueError:
        offset = 0
    return max(1024, min(65535, int(fallback or 17342) + offset))


def _default_state(instance_path: str | Path, runtime_id: str | None = None) -> Dict[str, Any]:
    target = _runtime_target(instance_path, runtime_id)
    return {
        "updatedAt": _utc_now_iso(),
        "runtimeId": str(target.get("id") or _default_runtime_id(instance_path)),
        "target": target,
        "process": {
            "pid": 0,
            "startedAtMs": 0,
            "exitCode": None,
            "binary": "",
        },
        "runtime": {
            "state": STATE_STOPPED,
            "health": "offline",
            "wsUrl": "",
            "port": 17342,
            "autoRestart": True,
            "projectPath": str(_godot_project_path()),
        },
        "display": {
            "displayId": str(target.get("displayId") or "display_1"),
            "mode": LAUNCH_MODE_FULLSCREEN,
            "monitor": max(1, int(target.get("screenIndex") or 1)),
            "fullscreen": True,
            "borderless": True,
            "width": int(target.get("width") or 1920),
            "height": int(target.get("height") or 1080),
            "x": 0,
            "y": 0,
            "scale": 1.0,
        },
        "scene": {
            "current": "",
            "available": ["no_scene", "attract", "gameplay", "results"],
        },
        "playback": {
            "status": "stopped",
            "mediaKey": "",
            "loop": False,
            "positionMs": 0,
        },
        "overlayValues": _default_overlay_values(),
        "overlayVisibility": {},
        "knownScenes": [],
        "lastCommand": None,
        "lastLaunch": {
            "sceneId": "",
            "displayId": str(target.get("displayId") or "display_1"),
            "launchMode": LAUNCH_MODE_FULLSCREEN,
            "reason": "",
        },
    }


def _load_media_config(instance_path: str | Path) -> Dict[str, Any]:
    raw = _read_json(_media_config_path(instance_path), {})
    if not isinstance(raw, dict):
        return {}
    return raw


def _scene_label(instance_path: str | Path, scene_key: str | None) -> str:
    key = str(scene_key or "").strip()
    if not key:
        return "No scene loaded"
    if key == "no_scene":
        return "No scene loaded"
    cfg = _load_media_config(instance_path)
    authored = _scene_by_id(cfg, key)
    if isinstance(authored, dict):
        return str(authored.get("name") or key).strip() or key
    dynamic = next((row for row in _scene_catalog(instance_path) if str(row.get("key") or "") == key), None)
    if isinstance(dynamic, dict):
        return str(dynamic.get("name") or dynamic.get("filename") or key).strip() or key
    builtin = {
        "attract": "Attract Mode",
        "gameplay": "Gameplay",
        "results": "Results",
    }
    return str(builtin.get(key) or key)


def _load_state(instance_path: str | Path, runtime_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _default_state(instance_path, resolved_runtime)
    raw = _read_json(_godot_runtime_state_path(instance_path, resolved_runtime), {})
    if isinstance(raw, dict):
        for key, value in raw.items():
            if isinstance(state.get(key), dict) and isinstance(value, dict):
                state[key].update(value)
            else:
                state[key] = value
    state["runtimeId"] = resolved_runtime
    state["target"] = _runtime_target(instance_path, resolved_runtime)
    return state


def _save_state(instance_path: str | Path, state: Dict[str, Any], runtime_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id or str(state.get("runtimeId") or ""))
    state["runtimeId"] = resolved_runtime
    state["target"] = _runtime_target(instance_path, resolved_runtime)
    state["updatedAt"] = _utc_now_iso()
    _write_json(_godot_runtime_state_path(instance_path, resolved_runtime), state)
    return state


def _renderer_enabled(instance_path: str | Path) -> bool:
    del instance_path
    return True


def renderer_enabled(instance_path: str | Path) -> bool:
    return _renderer_enabled(instance_path)


def _godot_settings(instance_path: str | Path) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    godot = settings.get("godot") if isinstance(settings.get("godot"), dict) else {}
    return godot


def _pick_port(preferred: int) -> int:
    port = max(1024, min(65535, int(preferred or 17342)))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])


def _pid_alive(pid: int) -> bool:
    p = int(pid or 0)
    if p <= 1:
        return False
    try:
        os.kill(p, 0)
        return True
    except Exception:
        return False


def _command_line_for_pid(pid: int) -> str:
    target = int(pid or 0)
    if target <= 1:
        return ""
    try:
        proc = subprocess.run(
            ["ps", "-o", "command=", "-p", str(target)],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if proc.returncode == 0:
            return str(proc.stdout or "").strip()
    except Exception:
        return ""
    return ""


def _godot_pid_alive(instance_path: str | Path, runtime_id: str | None, pid: int) -> bool:
    target = int(pid or 0)
    if target <= 1 or not _pid_alive(target):
        return False
    cmdline = _command_line_for_pid(target)
    if not cmdline:
        return False
    project_path = str(_godot_project_path())
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    return (
        project_path in cmdline
        and "--runtime-id" in cmdline
        and resolved_runtime in cmdline
        and ("godot" in cmdline.lower())
    )


def _kill_pid(pid: int) -> None:
    target = int(pid or 0)
    if target <= 1:
        return
    try:
        os.killpg(os.getpgid(target), signal.SIGTERM)
    except Exception:
        try:
            os.kill(target, signal.SIGTERM)
        except Exception:
            pass
    deadline = time.time() + 1.5
    while time.time() < deadline and _pid_alive(target):
        time.sleep(0.1)
    if _pid_alive(target):
        try:
            os.killpg(os.getpgid(target), signal.SIGKILL)
        except Exception:
            try:
                os.kill(target, signal.SIGKILL)
            except Exception:
                pass


def _daemon_rpc(instance_path: str | Path, op: str, payload: Dict[str, Any] | None = None, *, timeout: float = 5.0) -> Dict[str, Any]:
    sock_path = godot_daemon_socket_path(instance_path)
    if not sock_path.exists():
        return {"ok": False, "error": "godot_daemon_unavailable"}
    req = {"op": str(op), "payload": payload or {}}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(str(sock_path))
            s.sendall((json.dumps(req, separators=(",", ":")) + "\n").encode("utf-8"))
            raw = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                raw += chunk
                if b"\n" in raw:
                    raw = raw.split(b"\n", 1)[0]
                    break
    except Exception as exc:
        return {"ok": False, "error": "godot_daemon_unavailable", "detail": str(exc)}
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return {"ok": False, "error": "invalid_daemon_response"}
    return data if isinstance(data, dict) else {"ok": False, "error": "invalid_daemon_response"}


def _daemon_or_local(instance_path: str | Path, op: str, payload: Dict[str, Any], local_fn):
    if _in_daemon_process():
        return local_fn()
    rpc_timeout = 15.0 if op in {"launch_runtime", "restart_runtime", "stop_runtime"} or (op == "send_runtime_command" and bool(payload.get("auto_launch"))) else 5.0
    daemon_res = _daemon_rpc(instance_path, op, payload, timeout=rpc_timeout)
    if daemon_res.get("ok"):
        return daemon_res
    if daemon_res.get("error") != "godot_daemon_unavailable" and not (_running_under_gunicorn() and op in {"launch_runtime", "restart_runtime", "stop_runtime", "send_runtime_command"}):
        return daemon_res
    if _running_under_gunicorn() and op in {"launch_runtime", "restart_runtime", "stop_runtime", "send_runtime_command"}:
        return daemon_res
    return local_fn()


def _safe_name(raw_name: str, *, fallback_ext: str = "") -> str:
    base = Path(raw_name or "").name
    safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in base).strip("._")
    if not safe:
        safe = f"file_{uuid4().hex[:10]}{fallback_ext}"
    if fallback_ext and not safe.lower().endswith(fallback_ext.lower()):
        safe = f"{Path(safe).stem}{fallback_ext}"
    return safe


def _safe_key(raw_key: str, prefix: str) -> str:
    base = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(raw_key or "").strip()).strip("._")
    return base or f"{prefix}_{uuid4().hex[:8]}"


def _resolve_binary(instance_path: str | Path) -> str:
    settings = _godot_settings(instance_path)
    for candidate in (
        str(os.environ.get("PINBALLCTL_GODOT_BIN") or "").strip(),
        str(settings.get("binary") or "").strip(),
        shutil.which("godot4"),
        shutil.which("godot"),
    ):
        if candidate:
            return candidate
    return ""


def _resolve_ffmpeg_binary() -> str:
    return str(shutil.which("ffmpeg") or "").strip()


def _video_conversion_target_path(instance_path: str | Path, asset_id: str) -> Path:
    return _godot_cache_assets_dir(instance_path) / f"{_safe_key(asset_id, 'asset')}.{_VIDEO_PROFILE_TAG}.ogv"


def _video_conversion_lock_path(instance_path: str | Path, asset_id: str) -> Path:
    return _video_conversion_target_path(instance_path, asset_id).with_suffix(".lock")


def _video_conversion_progress_path(instance_path: str | Path, asset_id: str) -> Path:
    return _godot_cache_assets_dir(instance_path) / f"{_safe_key(asset_id, 'asset')}.{_VIDEO_PROFILE_TAG}.progress"


def _video_conversion_log_path(instance_path: str | Path, asset_id: str) -> Path:
    return _godot_cache_assets_dir(instance_path) / f"{_safe_key(asset_id, 'asset')}.{_VIDEO_PROFILE_TAG}.ffmpeg.log"


def _probe_duration_ms(path: Path) -> int:
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


def _read_progress_pct(progress_path: Path, duration_ms: int) -> int:
    if duration_ms <= 0 or not progress_path.exists():
        return 0
    try:
        out_time_ms = 0
        out_time_us = 0
        progress_complete = False
        for raw in progress_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = str(raw or "").strip()
            if line.startswith("out_time_ms="):
                out_time_ms = max(out_time_ms, int(float(line.split("=", 1)[1] or 0)))
            elif line.startswith("out_time_us="):
                out_time_us = max(out_time_us, int(float(line.split("=", 1)[1] or 0)))
            elif line == "progress=end":
                progress_complete = True
        progress_ms = 0
        if out_time_us > 0:
            progress_ms = int(out_time_us / 1000)
        elif out_time_ms > 0:
            # ffmpeg's progress output can report this field as microseconds in practice.
            progress_ms = int(out_time_ms / 1000) if out_time_ms > (duration_ms * 10) else out_time_ms
        if progress_ms <= 0:
            return 100 if progress_complete else 0
        pct = max(0, min(100, int((progress_ms / float(duration_ms)) * 100.0)))
        if progress_complete:
            return 100
        return pct
    except Exception:
        return 0


def get_asset_conversion_status(instance_path: str | Path, asset: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(asset, dict):
        return {
            "status": "unknown",
            "ready": False,
            "progressPct": 0,
            "originalFormat": "",
            "playbackFormat": "",
        }
    filename = str(asset.get("filename") or "").strip()
    kind = str(asset.get("kind") or "").strip().lower()
    asset_id = str(asset.get("id") or Path(filename).stem or "").strip()
    source_path = (_media_assets_dir(instance_path) / filename).resolve() if filename else None
    original_format = source_path.suffix.lower().lstrip(".") if source_path else ""
    direct_playable = kind != "video" or original_format in {"ogv", "ogg"}
    playback_format = original_format if direct_playable else "ogv"
    base = {
        "status": "ready" if direct_playable else "queued",
        "ready": bool(direct_playable),
        "progressPct": 100 if direct_playable else 0,
        "originalFormat": original_format,
        "playbackFormat": playback_format,
        "sourceFilename": filename,
        "derivedFilename": "",
        "updatedAt": _utc_now_iso(),
    }
    if not source_path or not source_path.exists():
        base.update({"status": "missing", "ready": False, "progressPct": 0})
        return base
    if kind != "video":
        return base
    if direct_playable:
        return base

    target_path = _video_conversion_target_path(instance_path, asset_id)
    lock_path = _video_conversion_lock_path(instance_path, asset_id)
    progress_path = _video_conversion_progress_path(instance_path, asset_id)
    base["derivedFilename"] = target_path.name
    duration_ms = max(0, int(float(asset.get("durationMs") or 0)))
    if duration_ms <= 0:
        duration_ms = _probe_duration_ms(source_path)
    try:
        source_mtime = source_path.stat().st_mtime
    except Exception:
        source_mtime = 0.0
    if target_path.exists():
        try:
            if target_path.stat().st_size > 0 and target_path.stat().st_mtime >= source_mtime:
                base.update({"status": "converted", "ready": True, "progressPct": 100})
                return base
        except Exception:
            pass

    if lock_path.exists():
        lock_info = _read_json(lock_path, {})
        lock_pid = 0
        tmp_path = None
        if isinstance(lock_info, dict):
            try:
                lock_pid = int(lock_info.get("pid") or 0)
            except Exception:
                lock_pid = 0
            tmp_raw = str(lock_info.get("tmp") or "").strip()
            if tmp_raw:
                tmp_path = Path(tmp_raw)
        pct = _read_progress_pct(progress_path, duration_ms)
        if lock_pid > 0 and _pid_alive(lock_pid):
            state = "queued"
            if pct >= 100:
                state = "finalizing"
            elif pct > 0:
                state = "converting"
            base.update({"status": state, "ready": False, "progressPct": pct})
            return base
        try:
            lock_path.unlink()
        except Exception:
            pass
        if tmp_path is not None:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
        try:
            if progress_path.exists():
                progress_path.unlink()
            stale_tmp = target_path.with_suffix(".tmp.ogv")
            if stale_tmp.exists():
                stale_tmp.unlink()
        except Exception:
            pass
    if target_path.exists():
        base.update({"status": "outdated", "ready": False, "progressPct": 0})
    else:
        base.update({"status": "queued", "ready": False, "progressPct": 0})
    return base


def _state_to_display(instance_path: str | Path, state: Dict[str, Any], cfg: Dict[str, Any], requested_display_id: str | None) -> Dict[str, Any]:
    displays = _effective_displays(instance_path, cfg)
    state_display = state.get("display") if isinstance(state.get("display"), dict) else {}
    last_launch = state.get("lastLaunch") if isinstance(state.get("lastLaunch"), dict) else {}
    target = str(requested_display_id or "").strip()
    selected = None
    if target:
        selected = next(
            (
                row for row in displays
                if str(row.get("id") or "").strip() == target or str(row.get("role") or "").strip() == target
            ),
            None,
        )
    if not isinstance(selected, dict):
        selected = next((row for row in displays if str(row.get("id") or "").strip() == str((state.get("display") or {}).get("displayId") or "").strip()), None)
    if not isinstance(selected, dict):
        selected = displays[0]
    mode = _normalize_launch_mode(state_display.get("mode"))
    selected_display_id = str(selected.get("id") or "display_1")
    stored_x = int(state_display.get("x") or 0)
    stored_y = int(state_display.get("y") or 0)
    stored_windowed_geometry = (
        mode == LAUNCH_MODE_WINDOWED
        and _normalize_launch_mode(last_launch.get("launchMode")) == LAUNCH_MODE_WINDOWED
        and str(last_launch.get("displayId") or "").strip() == selected_display_id
        and (stored_x != int(selected.get("x") or 0) or stored_y != int(selected.get("y") or 0))
    )
    payload = {
        "displayId": selected_display_id,
        "mode": mode,
        "monitor": max(1, int(state_display.get("monitor") or selected.get("screenIndex") or 1)),
        "fullscreen": bool(state_display.get("fullscreen", True)),
        "borderless": bool(state_display.get("borderless", True)),
        "width": max(1, int(state_display.get("width") or selected.get("width") or 1920)),
        "height": max(1, int(state_display.get("height") or selected.get("height") or 1080)),
        "x": stored_x if stored_windowed_geometry else 0,
        "y": stored_y if stored_windowed_geometry else 0,
        "originX": int(selected.get("x") or 0),
        "originY": int(selected.get("y") or 0),
        "displayWidth": max(1, int(selected.get("width") or 1920)),
        "displayHeight": max(1, int(selected.get("height") or 1080)),
        "scale": float(state_display.get("scale") or 1.0),
        "name": str(selected.get("name") or selected.get("id") or "Display"),
    }
    return _normalize_display_payload(payload)


def _normalize_display_payload(display: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(display or {})
    mode = _normalize_launch_mode(payload.get("mode"))
    payload["mode"] = mode
    payload["fullscreen"] = mode != LAUNCH_MODE_WINDOWED
    if mode == LAUNCH_MODE_WINDOWED:
        payload["borderless"] = False
        payload["width"] = min(max(640, int(payload.get("width") or 1600)), 1920)
        payload["height"] = min(max(480, int(payload.get("height") or 900)), 1080)
    else:
        payload["borderless"] = bool(payload.get("borderless", True))
    return payload


def _same_display_runtime(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    left = _normalize_display_payload(a)
    right = _normalize_display_payload(b)
    keys = ("displayId", "mode", "monitor", "borderless", "width", "height", "x", "y", "scale")
    for key in keys:
        if left.get(key) != right.get(key):
            return False
    return True


def _preserve_windowed_geometry(current_display: Dict[str, Any], next_display: Dict[str, Any]) -> Dict[str, Any]:
    current = _normalize_display_payload(current_display)
    requested = _normalize_display_payload(next_display)
    if str(current.get("mode") or "").strip().lower() != LAUNCH_MODE_WINDOWED:
        return requested
    if str(requested.get("mode") or "").strip().lower() != LAUNCH_MODE_WINDOWED:
        return requested
    if str(current.get("displayId") or "").strip() != str(requested.get("displayId") or "").strip():
        return requested
    if int(current.get("monitor") or 1) != int(requested.get("monitor") or 1):
        return requested
    requested["x"] = int(current.get("x") or 0)
    requested["y"] = int(current.get("y") or 0)
    requested["width"] = int(current.get("width") or requested.get("width") or 1600)
    requested["height"] = int(current.get("height") or requested.get("height") or 900)
    return requested


def _scene_catalog(instance_path: str | Path) -> List[Dict[str, Any]]:
    raw = _read_json(_godot_scene_registry_path(instance_path), [])
    rows = raw if isinstance(raw, list) else []
    return [row for row in rows if isinstance(row, dict)]


def list_uploaded_scenes(instance_path: str | Path) -> Dict[str, Any]:
    rows = _scene_catalog(instance_path)
    return {"ok": True, "scenes": rows}


def upload_dynamic_scene(instance_path: str | Path, file_storage: Any, *, scene_key: str | None = None) -> Dict[str, Any]:
    filename = _safe_name(getattr(file_storage, "filename", "") or "scene.pck")
    ext = Path(filename).suffix.lower()
    if ext not in (".tscn", ".pck"):
        return {"ok": False, "error": "unsupported_scene_type"}
    key = _safe_key(scene_key or Path(filename).stem, "scene")
    target = _godot_scene_upload_dir(instance_path) / filename
    file_storage.save(target)
    rows = [row for row in _scene_catalog(instance_path) if str(row.get("key") or "") != key]
    row = {
        "key": key,
        "filename": filename,
        "path": str(target),
        "type": ext.lstrip("."),
        "uploadedAt": _utc_now_iso(),
    }
    rows.append(row)
    _write_json(_godot_scene_registry_path(instance_path), rows)
    return {"ok": True, "scene": row}


def _scene_by_id(cfg: Dict[str, Any], scene_id: str) -> Dict[str, Any] | None:
    return next(
        (
            row for row in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else [])
            if isinstance(row, dict) and str(row.get("id") or "") == str(scene_id)
        ),
        None,
    )


def _asset_by_key(cfg: Dict[str, Any], key: str) -> Dict[str, Any] | None:
    target = str(key or "").strip()
    return next(
        (
            row for row in (cfg.get("assets") if isinstance(cfg.get("assets"), list) else [])
            if isinstance(row, dict) and (
                str(row.get("id") or "") == target
                or str(row.get("key") or "") == target
            )
        ),
        None,
    )


def _asset_payload(instance_path: str | Path, asset: Dict[str, Any] | None) -> Dict[str, Any]:
    if not isinstance(asset, dict):
        return {}
    filename = str(asset.get("filename") or "").strip()
    source_path = (_media_assets_dir(instance_path) / filename).resolve() if filename else None
    playable_path, derivative_ready = _godot_playable_asset_path(instance_path, asset)
    playable_ext = playable_path.suffix.lower().lstrip(".") if playable_path else ""
    playable_kind = str(asset.get("kind") or "").strip().lower()
    if playable_kind == "video" and derivative_ready and playable_ext in {"ogv", "ogg"}:
        playable_kind = "video"
    elif playable_kind == "video":
        playable_kind = "pending_video"
    return {
        "id": str(asset.get("id") or ""),
        "key": str(asset.get("id") or asset.get("key") or ""),
        "displayName": str(asset.get("displayName") or Path(filename).stem or "").strip(),
        "filename": filename,
        "kind": playable_kind,
        "path": str(playable_path) if playable_path else "",
        "sourcePath": str(source_path) if source_path else "",
        "ready": derivative_ready,
    }


def _godot_playable_asset_path(instance_path: str | Path, asset: Dict[str, Any] | None) -> tuple[Path | None, bool]:
    if not isinstance(asset, dict):
        return None, False
    filename = str(asset.get("filename") or "").strip()
    if not filename:
        return None, False
    source_path = (_media_assets_dir(instance_path) / filename).resolve()
    if not source_path.exists():
        return source_path, False
    kind = str(asset.get("kind") or "").strip().lower()
    ext = source_path.suffix.lower().lstrip(".")
    if kind != "video":
        return source_path, True
    if ext in {"ogv", "ogg"}:
        return source_path, True
    return _ensure_godot_video_derivative(instance_path, asset, source_path)


def _ensure_godot_video_derivative(instance_path: str | Path, asset: Dict[str, Any], source_path: Path) -> tuple[Path, bool]:
    asset_id = str(asset.get("id") or Path(source_path).stem).strip() or Path(source_path).stem
    target_path = _video_conversion_target_path(instance_path, asset_id)
    lock_path = _video_conversion_lock_path(instance_path, asset_id)
    progress_path = _video_conversion_progress_path(instance_path, asset_id)
    if target_path.exists():
        try:
            if target_path.stat().st_mtime >= source_path.stat().st_mtime and target_path.stat().st_size > 0:
                return target_path, True
        except Exception:
            pass
    if lock_path.exists():
        lock_info = _read_json(lock_path, {})
        lock_pid = 0
        if isinstance(lock_info, dict):
            try:
                lock_pid = int(lock_info.get("pid") or 0)
            except Exception:
                lock_pid = 0
        if lock_pid > 0 and _pid_alive(lock_pid):
            return target_path, False
        try:
            lock_path.unlink()
        except Exception:
            return target_path, False
    ffmpeg_bin = _resolve_ffmpeg_binary()
    if not ffmpeg_bin:
        LOGGER.warning("ffmpeg not found; Godot video derivative unavailable for %s", source_path)
        return source_path, False
    tmp_path = target_path.with_name(f"{target_path.stem}.{uuid4().hex}.tmp.ogv")
    try:
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return target_path, False
    try:
        command = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(source_path),
            "-progress",
            str(progress_path),
            "-nostats",
            "-vf",
            "scale=1280:-2:force_original_aspect_ratio=decrease,fps=30",
            "-c:v",
            "libtheora",
            "-q:v",
            "8",
            "-an",
            "-threads",
            "2",
            str(tmp_path),
        ]
        log_path = _video_conversion_log_path(instance_path, asset_id)
        log_handle = open(log_path, "ab")
        shell_cmd = (
            f"{' '.join(shlex.quote(part) for part in command)}"
            f"; status=$?"
            f"; if [ $status -eq 0 ]; then mv {shlex.quote(str(tmp_path))} {shlex.quote(str(target_path))}; fi"
            f"; rm -f {shlex.quote(str(lock_path))}"
            f" {shlex.quote(str(progress_path))}"
            f"; if [ $status -ne 0 ]; then rm -f {shlex.quote(str(tmp_path))}; fi"
            f"; exit $status"
        )
        proc = subprocess.Popen(
            ["/bin/sh", "-c", shell_cmd],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        log_handle.close()
        with os.fdopen(lock_fd, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "pid": proc.pid,
                    "source": str(source_path),
                    "target": str(target_path),
                    "tmp": str(tmp_path),
                    "startedAtMs": _now_ms(),
                },
                handle,
            )
        return target_path, False
    except Exception as exc:
        LOGGER.warning("ffmpeg derivative failed for %s: %s", source_path, exc)
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass
        try:
            os.close(lock_fd)
        except Exception:
            pass
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass
        return source_path, False


def _overlay_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {
        str(row.get("id") or ""): row
        for row in (cfg.get("overlays") if isinstance(cfg.get("overlays"), list) else [])
        if isinstance(row, dict) and str(row.get("id") or "").strip()
    }


def _resolved_overlay_layers(instance_path: str | Path, cfg: Dict[str, Any], scene: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not isinstance(scene, dict):
        return []
    overlay_refs = scene.get("overlayRefs") if isinstance(scene.get("overlayRefs"), list) else []
    overlays_by_id = _overlay_map(cfg)
    resolved: List[Dict[str, Any]] = []
    for overlay_idx, ref in enumerate(overlay_refs):
        if not isinstance(ref, dict) or not bool(ref.get("active", True)):
            continue
        overlay_id = str(ref.get("overlayId") or "").strip()
        overlay = overlays_by_id.get(overlay_id)
        if not isinstance(overlay, dict):
            continue
        layers = overlay.get("layers") if isinstance(overlay.get("layers"), list) else []
        for layer_idx, layer in enumerate(layers):
            if not isinstance(layer, dict):
                continue
            row = dict(layer)
            row["id"] = str(layer.get("id") or f"{overlay_id}_layer_{layer_idx+1}")
            row["overlayId"] = overlay_id
            row["overlayName"] = str(overlay.get("name") or overlay_id)
            asset = _asset_by_key(cfg, str(layer.get("assetId") or ""))
            if isinstance(asset, dict):
                row["asset"] = _asset_payload(instance_path, asset)
                row["assetPath"] = str(row["asset"].get("path") or "")
            row["zIndex"] = int(layer.get("zIndex") or (overlay_idx * 100) + layer_idx + 1)
            resolved.append(row)
    resolved.sort(key=lambda row: int(row.get("zIndex") or 0))
    return resolved


def _build_runtime_state_payload(instance_path: str | Path, runtime_id: str, scene_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    cfg = _load_media_config(instance_path)
    active_scene_id = str(scene_id or "").strip() or str(((state.get("scene") or {}).get("current")) or "").strip() or "no_scene"
    scene = _scene_by_id(cfg, active_scene_id)
    asset = _asset_by_key(cfg, str((scene or {}).get("baseAssetId") or "")) if isinstance(scene, dict) else None
    scene_payload: Dict[str, Any] = {
        "key": active_scene_id,
        "name": _scene_label(instance_path, active_scene_id),
        "path": str(((scene or {}).get("godotScenePath")) or ""),
    }
    layers: List[Dict[str, Any]] = []
    if active_scene_id != "no_scene":
        layers.append(
            {
                "layerId": f"{resolved_runtime}:{active_scene_id}:primary",
                "scene": {
                    "id": active_scene_id,
                    "name": scene_payload["name"],
                },
                "asset": _asset_payload(instance_path, asset),
                "state": str((((state.get("playback") or {}).get("status")) or "stopped")),
                "fallback": False,
            }
        )
    return {
        "scene": scene_payload,
        "layers": layers,
        "overlays": _resolved_overlay_layers(instance_path, cfg, scene),
        "overlayValues": dict(state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values()),
        "overlayVisibility": dict(state.get("overlayVisibility") if isinstance(state.get("overlayVisibility"), dict) else {}),
        "display": dict(state.get("display") if isinstance(state.get("display"), dict) else {}),
        "playback": dict(state.get("playback") if isinstance(state.get("playback"), dict) else {}),
    }


def _apply_runtime_state(instance_path: str | Path, runtime_id: str | None = None, *, scene_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    payload = _build_runtime_state_payload(instance_path, resolved_runtime, scene_id)
    return send_runtime_command(
        instance_path,
        {"cmd": "APPLY_STATE", "state": payload},
        runtime_id=resolved_runtime,
        auto_launch=True,
    )


def _runtime_ws_url(state: Dict[str, Any]) -> str:
    return str(((state.get("runtime") or {}).get("wsUrl")) or "").strip()


def _request_status(instance_path: str | Path, runtime_id: str | None = None, *, timeout: float = 1.0) -> Dict[str, Any]:
    return send_runtime_command(instance_path, {"cmd": "GET_STATUS"}, runtime_id=runtime_id, timeout=timeout, auto_launch=False)


def _send_runtime_command_impl(
    instance_path: str | Path,
    payload: Dict[str, Any],
    *,
    runtime_id: str | None = None,
    timeout: float = 2.0,
    auto_launch: bool = False,
) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id, str((((payload.get("display") if isinstance(payload.get("display"), dict) else {}) or {}).get("displayId")) or ""))
    state = _load_state(instance_path, resolved_runtime)
    if auto_launch and not _godot_pid_alive(instance_path, resolved_runtime, int(((state.get("process") or {}).get("pid")) or 0)):
        launched = launch_runtime(instance_path, runtime_id=resolved_runtime, reason="auto_launch")
        if not launched.get("ok"):
            return launched
        state = _load_state(instance_path, resolved_runtime)
    ws_url = _runtime_ws_url(state)
    if not ws_url:
        return {"ok": False, "error": "runtime_not_configured"}
    ws_connect = _get_ws_connect()
    if ws_connect is None:
        return {"ok": False, "error": "websocket_client_unavailable"}
    try:
        with ws_connect(ws_url, open_timeout=timeout, close_timeout=1.0) as ws:
            ws.send(json.dumps(payload, separators=(",", ":")))
            raw = ws.recv()
    except Exception as exc:
        LOGGER.warning("godot runtime command failed: %s", exc)
        return {"ok": False, "error": "runtime_unreachable", "detail": str(exc)}
    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "invalid_runtime_response", "raw": raw}
    if isinstance(data, dict):
        return data
    return {"ok": False, "error": "invalid_runtime_response"}


def runtime_status(
    instance_path: str | Path,
    runtime_id: str | None = None,
    *,
    probe_live: bool = True,
) -> Dict[str, Any]:
    return runtime_status_for(instance_path, runtime_id or _default_runtime_id(instance_path), probe_live=probe_live)


def runtime_status_for(
    instance_path: str | Path,
    runtime_id: str | None = None,
    *,
    probe_live: bool = True,
) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    pid = int(((state.get("process") or {}).get("pid")) or 0)
    alive = _godot_pid_alive(instance_path, resolved_runtime, pid)
    if not alive and pid > 0:
        previous_state = str(((state.get("runtime") or {}).get("state")) or "").strip().lower()
        previous_mode = str(((state.get("display") or {}).get("mode")) or "").strip().lower()
        state["process"]["pid"] = 0
        if previous_state in (STATE_STOPPED, "stopping") or previous_mode == LAUNCH_MODE_WINDOWED:
            state["runtime"]["state"] = STATE_STOPPED
            state["runtime"]["health"] = "offline"
        else:
            state["runtime"]["state"] = STATE_CRASHED
            state["runtime"]["health"] = "process_dead"
        _save_state(instance_path, state, resolved_runtime)
    status = {
        "ok": True,
        "runtimeId": resolved_runtime,
        "running": alive,
        "pid": pid if alive else 0,
        "state": str(((state.get("runtime") or {}).get("state")) or STATE_STOPPED),
        "health": str(((state.get("runtime") or {}).get("health")) or "offline"),
        "wsUrl": _runtime_ws_url(state),
        "scene": dict(state.get("scene") if isinstance(state.get("scene"), dict) else {}),
        "playback": dict(state.get("playback") if isinstance(state.get("playback"), dict) else {}),
        "display": dict(state.get("display") if isinstance(state.get("display"), dict) else {}),
        "overlayValues": dict(state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values()),
    }
    if probe_live and alive and _runtime_ws_url(state):
        probe = _request_status(instance_path, resolved_runtime, timeout=0.6)
        if probe.get("ok") and isinstance(probe.get("status"), dict):
            runtime_state = probe["status"]
            if runtime_state.get("windowVisible", True) is False:
                _kill_pid(pid)
                state["process"]["pid"] = 0
                state["runtime"]["state"] = STATE_STOPPED
                state["runtime"]["health"] = "window_closed"
                _save_state(instance_path, state, resolved_runtime)
                return {
                    "ok": True,
                    "runtimeId": resolved_runtime,
                    "running": False,
                    "pid": 0,
                    "state": STATE_STOPPED,
                    "health": "window_closed",
                    "wsUrl": _runtime_ws_url(state),
                    "scene": dict(state.get("scene") if isinstance(state.get("scene"), dict) else {}),
                    "playback": dict(state.get("playback") if isinstance(state.get("playback"), dict) else {}),
                    "display": dict(state.get("display") if isinstance(state.get("display"), dict) else {}),
                    "overlayValues": dict(state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values()),
                }
            state["runtime"]["state"] = STATE_RUNNING
            state["runtime"]["health"] = str(runtime_state.get("health") or "ok")
            if isinstance(runtime_state.get("scene"), dict):
                state["scene"].update(runtime_state.get("scene"))
            if isinstance(runtime_state.get("playback"), dict):
                state["playback"].update(runtime_state.get("playback"))
            if isinstance(runtime_state.get("display"), dict):
                state["display"].update(runtime_state.get("display"))
            if isinstance(runtime_state.get("overlayValues"), dict):
                state["overlayValues"].update(runtime_state.get("overlayValues"))
            _save_state(instance_path, state, resolved_runtime)
            status.update(
                {
                    "state": STATE_RUNNING,
                    "health": state["runtime"]["health"],
                    "scene": dict(state.get("scene") or {}),
                    "playback": dict(state.get("playback") or {}),
                    "display": dict(state.get("display") or {}),
                    "overlayValues": dict(state.get("overlayValues") or {}),
                }
            )
    return status


def _launch_runtime_impl(
    instance_path: str | Path,
    *,
    runtime_id: str | None = None,
    display_id: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    scene_id: str | None = None,
    reason: str = "manual",
) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id, display_id)
    state = _load_state(instance_path, resolved_runtime)
    requested_scene_id = (
        str(scene_id or "").strip()
        or str(((state.get("scene") or {}).get("current")) or "").strip()
        or str(((state.get("lastLaunch") or {}).get("sceneId")) or "").strip()
        or "no_scene"
    )
    pid = int(((state.get("process") or {}).get("pid")) or 0)
    if _godot_pid_alive(instance_path, resolved_runtime, pid):
        runtime_status_for(instance_path, resolved_runtime, probe_live=True)
        state = _load_state(instance_path, resolved_runtime)
        current_display = dict(state.get("display") if isinstance(state.get("display"), dict) else {})
        display_payload = _state_to_display(instance_path, state, cfg, display_id)
        display_payload["mode"] = _normalize_launch_mode(launch_mode)
        display_payload = _preserve_windowed_geometry(current_display, display_payload)
        godot_settings = _godot_settings(instance_path)
        previous_display = dict(current_display)
        state["display"] = display_payload
        state["scene"]["current"] = requested_scene_id
        state["lastLaunch"] = {
            "sceneId": requested_scene_id,
            "displayId": str(display_payload.get("displayId") or "display_1"),
            "launchMode": str(display_payload.get("mode") or LAUNCH_MODE_FULLSCREEN),
            "reason": str(reason or "manual"),
        }
        _save_state(instance_path, state, resolved_runtime)
        if not _same_display_runtime(previous_display, display_payload):
            configure_display(instance_path, runtime_id=resolved_runtime, **display_payload)
        send_runtime_command(
            instance_path,
            {"cmd": "SET_DEBUG", "enabled": bool(godot_settings.get("debugVisible", True))},
            runtime_id=resolved_runtime,
            auto_launch=False,
        )
        if requested_scene_id == "no_scene":
            _apply_runtime_state(instance_path, resolved_runtime, scene_id=requested_scene_id)
        else:
            set_scene(instance_path, requested_scene_id, runtime_id=resolved_runtime)
        return {"ok": True, "running": True, "pid": pid, "reused": True, "runtimeId": resolved_runtime, "status": runtime_status_for(instance_path, resolved_runtime)}
    binary = _resolve_binary(instance_path)
    if not binary:
        return {"ok": False, "error": "godot_binary_not_found"}
    project_path = _godot_project_path()
    if not project_path.exists():
        return {"ok": False, "error": "godot_project_missing", "path": str(project_path)}
    godot_settings = _godot_settings(instance_path)
    preferred_port = _preferred_port(instance_path, resolved_runtime, int(godot_settings.get("port") or ((state.get("runtime") or {}).get("port")) or 17342))
    port = _pick_port(preferred_port)
    ws_url = f"ws://127.0.0.1:{port}"
    display_payload = _state_to_display(instance_path, state, cfg, display_id)
    display_payload["mode"] = _normalize_launch_mode(launch_mode)
    log_path = _godot_log_dir(instance_path, resolved_runtime) / "runtime.log"
    state["process"] = {
        "pid": 0,
        "startedAtMs": _now_ms(),
        "exitCode": None,
        "binary": binary,
        "logPath": str(log_path),
    }
    state["runtime"].update(
        {
            "state": STATE_STARTING,
            "health": "booting",
            "wsUrl": ws_url,
            "port": port,
            "autoRestart": bool(godot_settings.get("autoRestart", True)),
            "projectPath": str(project_path),
        }
    )
    state["display"] = display_payload
    state["scene"]["current"] = requested_scene_id
    state["lastLaunch"] = {
        "sceneId": requested_scene_id,
        "displayId": str(display_payload.get("displayId") or "display_1"),
        "launchMode": str(display_payload.get("mode") or LAUNCH_MODE_FULLSCREEN),
        "reason": str(reason or "manual"),
    }
    _save_state(instance_path, state, resolved_runtime)
    command = [
        binary,
        "--path",
        str(project_path),
        "--",
        "--ws-port",
        str(port),
        "--instance-path",
        str(Path(instance_path).resolve()),
        "--runtime-id",
        str(resolved_runtime),
        "--scene-id",
        requested_scene_id,
        "--scene-name",
        _scene_label(instance_path, requested_scene_id),
        "--display-id",
        str(display_payload.get("displayId") or "display_1"),
        "--display-name",
        str(display_payload.get("name") or display_payload.get("displayId") or resolved_runtime),
        "--monitor",
        str(int(display_payload.get("monitor") or 1)),
        "--window-mode",
        str(display_payload.get("mode") or LAUNCH_MODE_FULLSCREEN),
        "--debug-visible",
        "1" if bool(godot_settings.get("debugVisible", True)) else "0",
        "--window-width",
        str(int(display_payload.get("width") or 1600)),
        "--window-height",
        str(int(display_payload.get("height") or 900)),
        "--window-x",
        str(int(display_payload.get("x") or 80)),
        "--window-y",
        str(int(display_payload.get("y") or 80)),
    ]
    log_handle = open(log_path, "ab")
    try:
        proc = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as exc:
        log_handle.close()
        state["runtime"]["state"] = STATE_CRASHED
        state["runtime"]["health"] = "launch_failed"
        _save_state(instance_path, state, resolved_runtime)
        return {"ok": False, "error": "launch_failed", "detail": str(exc)}
    state["process"]["pid"] = int(proc.pid or 0)
    _save_state(instance_path, state, resolved_runtime)
    deadline = time.time() + max(1.0, float(godot_settings.get("startupTimeoutSec") or 8.0))
    while time.time() < deadline:
        if not _godot_pid_alive(instance_path, resolved_runtime, int(proc.pid or 0)):
            state["runtime"]["state"] = STATE_CRASHED
            state["runtime"]["health"] = "process_exited"
            state["process"]["pid"] = 0
            _save_state(instance_path, state, resolved_runtime)
            return {"ok": False, "error": "process_exited"}
        probe = _request_status(instance_path, resolved_runtime, timeout=0.25)
        if probe.get("ok"):
            time.sleep(0.35)
            if not _godot_pid_alive(instance_path, resolved_runtime, int(proc.pid or 0)):
                state["runtime"]["state"] = STATE_CRASHED
                state["runtime"]["health"] = "process_exited"
                state["process"]["pid"] = 0
                _save_state(instance_path, state, resolved_runtime)
                return {"ok": False, "error": "process_exited"}
            state["runtime"]["state"] = STATE_RUNNING
            state["runtime"]["health"] = "ok"
            _save_state(instance_path, state, resolved_runtime)
            return {"ok": True, "running": True, "pid": int(proc.pid or 0), "reused": False, "runtimeId": resolved_runtime, "status": runtime_status_for(instance_path, resolved_runtime)}
        time.sleep(0.2)
    return {"ok": False, "error": "startup_timeout", "pid": int(proc.pid or 0), "runtimeId": resolved_runtime}


def _stop_runtime_impl(instance_path: str | Path, runtime_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    pid = int(((state.get("process") or {}).get("pid")) or 0)
    if pid <= 0 or not _godot_pid_alive(instance_path, resolved_runtime, pid):
        state["runtime"]["state"] = STATE_STOPPED
        state["runtime"]["health"] = "offline"
        state["process"]["pid"] = 0
        _save_state(instance_path, state, resolved_runtime)
        return {"ok": True, "stopped": 0, "runtimeId": resolved_runtime}
    try:
        send_runtime_command(instance_path, {"cmd": "SHUTDOWN"}, runtime_id=resolved_runtime, timeout=0.8, auto_launch=False)
    except Exception:
        pass
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass
    deadline = time.time() + 2.0
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.1)
    if _pid_alive(pid):
        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
    state["runtime"]["state"] = STATE_STOPPED
    state["runtime"]["health"] = "offline"
    state["process"]["pid"] = 0
    _save_state(instance_path, state, resolved_runtime)
    return {"ok": True, "stopped": 1, "runtimeId": resolved_runtime}


def _restart_runtime_impl(instance_path: str | Path, *, runtime_id: str | None = None, reason: str = "restart") -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    last_launch = state.get("lastLaunch") if isinstance(state.get("lastLaunch"), dict) else {}
    stop_runtime(instance_path, runtime_id=resolved_runtime)
    return launch_runtime(
        instance_path,
        runtime_id=resolved_runtime,
        display_id=str(last_launch.get("displayId") or "").strip() or None,
        launch_mode=str(last_launch.get("launchMode") or LAUNCH_MODE_FULLSCREEN),
        scene_id=str(last_launch.get("sceneId") or "").strip() or None,
        reason=reason,
    )


def _configure_display_impl(
    instance_path: str | Path,
    *,
    runtime_id: str | None = None,
    displayId: str | None = None,
    mode: str | None = None,
    monitor: int | None = None,
    fullscreen: bool | None = None,
    borderless: bool | None = None,
    width: int | None = None,
    height: int | None = None,
    x: int | None = None,
    y: int | None = None,
    scale: float | None = None,
    **_: Any,
) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id, displayId)
    state = _load_state(instance_path, resolved_runtime)
    display = state.get("display") if isinstance(state.get("display"), dict) else {}
    if displayId is not None:
        display["displayId"] = str(displayId)
    if mode is not None:
        display["mode"] = _normalize_launch_mode(mode)
    if monitor is not None:
        display["monitor"] = max(1, int(monitor))
    if fullscreen is not None:
        display["fullscreen"] = bool(fullscreen)
    if borderless is not None:
        display["borderless"] = bool(borderless)
    if width is not None:
        display["width"] = max(1, int(width))
    if height is not None:
        display["height"] = max(1, int(height))
    if x is not None:
        display["x"] = int(x)
    if y is not None:
        display["y"] = int(y)
    if scale is not None:
        display["scale"] = max(0.1, float(scale))
    display = _normalize_display_payload(display)
    state["display"] = display
    _save_state(instance_path, state, resolved_runtime)
    pid = int(((state.get("process") or {}).get("pid")) or 0)
    if pid <= 0 or not _pid_alive(pid):
        return {"ok": True, "display": display, "pending": True, "runtimeId": resolved_runtime}
    res = send_runtime_command(
        instance_path,
        {"cmd": "SET_DISPLAY", "display": display},
        runtime_id=resolved_runtime,
        timeout=1.0,
        auto_launch=False,
    )
    return res if res.get("ok") else {"ok": True, "display": display, "pending": True, "runtimeId": resolved_runtime}


def send_runtime_command(
    instance_path: str | Path,
    payload: Dict[str, Any],
    *,
    runtime_id: str | None = None,
    timeout: float = 2.0,
    auto_launch: bool = False,
) -> Dict[str, Any]:
    return _daemon_or_local(
        instance_path,
        "send_runtime_command",
        {"runtimeId": runtime_id, "payload": payload, "timeout": timeout, "auto_launch": auto_launch},
        lambda: _send_runtime_command_impl(instance_path, payload, runtime_id=runtime_id, timeout=timeout, auto_launch=auto_launch),
    )


def launch_runtime(
    instance_path: str | Path,
    *,
    runtime_id: str | None = None,
    display_id: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    scene_id: str | None = None,
    reason: str = "manual",
) -> Dict[str, Any]:
    return _daemon_or_local(
        instance_path,
        "launch_runtime",
        {"runtimeId": runtime_id, "display_id": display_id, "launch_mode": launch_mode, "scene_id": scene_id, "reason": reason},
        lambda: _launch_runtime_impl(instance_path, runtime_id=runtime_id, display_id=display_id, launch_mode=launch_mode, scene_id=scene_id, reason=reason),
    )


def stop_runtime(instance_path: str | Path, *, runtime_id: str | None = None) -> Dict[str, Any]:
    return _daemon_or_local(
        instance_path,
        "stop_runtime",
        {"runtimeId": runtime_id},
        lambda: _stop_runtime_impl(instance_path, runtime_id=runtime_id),
    )


def restart_runtime(instance_path: str | Path, *, runtime_id: str | None = None, reason: str = "restart") -> Dict[str, Any]:
    return _daemon_or_local(
        instance_path,
        "restart_runtime",
        {"runtimeId": runtime_id, "reason": reason},
        lambda: _restart_runtime_impl(instance_path, runtime_id=runtime_id, reason=reason),
    )


def configure_display(
    instance_path: str | Path,
    *,
    runtime_id: str | None = None,
    displayId: str | None = None,
    mode: str | None = None,
    monitor: int | None = None,
    fullscreen: bool | None = None,
    borderless: bool | None = None,
    width: int | None = None,
    height: int | None = None,
    x: int | None = None,
    y: int | None = None,
    scale: float | None = None,
    **extra: Any,
) -> Dict[str, Any]:
    payload = {
        "displayId": displayId,
        "mode": mode,
        "monitor": monitor,
        "fullscreen": fullscreen,
        "borderless": borderless,
        "width": width,
        "height": height,
        "x": x,
        "y": y,
        "scale": scale,
    }
    payload.update(extra)
    return _daemon_or_local(
        instance_path,
        "configure_display",
        {**payload, "runtimeId": runtime_id},
        lambda: _configure_display_impl(
            instance_path,
            runtime_id=runtime_id,
            displayId=displayId,
            mode=mode,
            monitor=monitor,
            fullscreen=fullscreen,
            borderless=borderless,
            width=width,
            height=height,
            x=x,
            y=y,
            scale=scale,
            **extra,
        ),
    )


def preload_media(instance_path: str | Path, media_keys: List[str], *, runtime_id: str | None = None) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    resolved: List[Dict[str, Any]] = []
    for key in media_keys:
        asset = _asset_by_key(cfg, key)
        if not isinstance(asset, dict):
            continue
        if str(asset.get("kind") or "").strip().lower() == "video":
            try:
                _godot_playable_asset_path(instance_path, asset)
            except Exception:
                LOGGER.exception("Failed preparing Godot video asset %s", key)
        resolved.append(
            {
                "key": str(asset.get("key") or asset.get("id") or ""),
                "path": str(_media_assets_dir(instance_path) / str(asset.get("filename") or "")),
            }
        )
    return send_runtime_command(instance_path, {"cmd": "PRELOAD_MEDIA", "media": resolved}, runtime_id=runtime_id, auto_launch=True)


def prepare_video_assets(instance_path: str | Path) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    assets = [row for row in (cfg.get("assets") if isinstance(cfg.get("assets"), list) else []) if isinstance(row, dict)]
    prepared = 0
    ready = 0
    pending = 0
    failed = 0
    for asset in assets:
        if str(asset.get("kind") or "").strip().lower() != "video":
            continue
        prepared += 1
        try:
            _path, _is_ready = _godot_playable_asset_path(instance_path, asset)
            status = get_asset_conversion_status(instance_path, asset)
            if bool(status.get("ready")):
                ready += 1
            else:
                pending += 1
        except Exception:
            failed += 1
            LOGGER.exception("Failed preparing Godot video derivative for asset %s", str(asset.get("id") or ""))
    return {
        "ok": True,
        "prepared": prepared,
        "ready": ready,
        "pending": pending,
        "failed": failed,
    }


def play_video(instance_path: str | Path, media_key: str, *, runtime_id: str | None = None, loop: bool = False) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    asset = _asset_by_key(cfg, media_key)
    if not isinstance(asset, dict):
        return {"ok": False, "error": "media_not_found"}
    path = _media_assets_dir(instance_path) / str(asset.get("filename") or "")
    if not path.exists():
        return {"ok": False, "error": "media_missing"}
    res = send_runtime_command(
        instance_path,
        {
            "cmd": "PLAY_VIDEO",
            "media": {
                "key": str(asset.get("key") or asset.get("id") or media_key),
                "path": str(path),
                "loop": bool(loop),
            },
        },
        runtime_id=runtime_id,
        auto_launch=True,
    )
    if res.get("ok"):
        resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
        state = _load_state(instance_path, resolved_runtime)
        ext = Path(str(path)).suffix.lower().lstrip(".")
        playback_status = "playing" if ext in {"ogv", "ogg"} else "displaying"
        state["playback"].update({"status": playback_status, "mediaKey": str(asset.get("id") or media_key), "loop": bool(loop), "mediaPath": str(path)})
        _save_state(instance_path, state, resolved_runtime)
    return res


def pause_video(instance_path: str | Path, *, runtime_id: str | None = None) -> Dict[str, Any]:
    res = send_runtime_command(instance_path, {"cmd": "PAUSE_VIDEO"}, runtime_id=runtime_id, auto_launch=False)
    if res.get("ok"):
        resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
        state = _load_state(instance_path, resolved_runtime)
        state["playback"]["status"] = "paused"
        _save_state(instance_path, state, resolved_runtime)
    return res


def stop_video(instance_path: str | Path, *, runtime_id: str | None = None) -> Dict[str, Any]:
    res = send_runtime_command(instance_path, {"cmd": "STOP_VIDEO"}, runtime_id=runtime_id, auto_launch=False)
    if res.get("ok"):
        resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
        state = _load_state(instance_path, resolved_runtime)
        state["playback"].update({"status": "stopped", "mediaKey": "", "loop": False, "positionMs": 0})
        _save_state(instance_path, state, resolved_runtime)
    return res


def set_scene(instance_path: str | Path, scene_key: str, *, runtime_id: str | None = None) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    authored_scene = _scene_by_id(cfg, scene_key)
    dynamic_scene = next((row for row in _scene_catalog(instance_path) if str(row.get("key") or "") == str(scene_key)), None)
    scene_payload: Dict[str, Any] = {"key": scene_key, "name": _scene_label(instance_path, scene_key)}
    if isinstance(dynamic_scene, dict):
        scene_payload["path"] = str(dynamic_scene.get("path") or "")
    elif isinstance(authored_scene, dict):
        scene_payload["path"] = str(authored_scene.get("godotScenePath") or "")
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    res = send_runtime_command(instance_path, {"cmd": "SET_SCENE", "scene": scene_payload}, runtime_id=resolved_runtime, auto_launch=True)
    if res.get("ok"):
        state = _load_state(instance_path, resolved_runtime)
        state["scene"]["current"] = str(scene_key)
        if scene_key not in state["scene"].get("available", []):
            state["scene"]["available"] = list(state["scene"].get("available", [])) + [scene_key]
        _save_state(instance_path, state, resolved_runtime)
    return res


def load_dynamic_scene(instance_path: str | Path, scene_key: str, *, runtime_id: str | None = None) -> Dict[str, Any]:
    row = next((item for item in _scene_catalog(instance_path) if str(item.get("key") or "") == str(scene_key)), None)
    if not isinstance(row, dict):
        return {"ok": False, "error": "scene_not_found"}
    return send_runtime_command(
        instance_path,
        {"cmd": "LOAD_SCENE", "scene": {"key": scene_key, "path": str(row.get("path") or ""), "type": str(row.get("type") or "")}},
        runtime_id=runtime_id,
        auto_launch=True,
    )


def show_overlay(instance_path: str | Path, overlay_id: str, *, runtime_id: str | None = None, visible: bool = True, position: Dict[str, Any] | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    visibility = state.get("overlayVisibility") if isinstance(state.get("overlayVisibility"), dict) else {}
    visibility[str(overlay_id)] = bool(visible)
    state["overlayVisibility"] = visibility
    _save_state(instance_path, state, resolved_runtime)
    if position:
        return send_runtime_command(
            instance_path,
            {"cmd": "SHOW_OVERLAY" if visible else "HIDE_OVERLAY", "overlay": {"id": str(overlay_id), "position": position}},
            runtime_id=resolved_runtime,
            auto_launch=True,
        )
    return _apply_runtime_state(instance_path, resolved_runtime)


def update_text(instance_path: str | Path, key: str, value: Any, *, runtime_id: str | None = None) -> Dict[str, Any]:
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id)
    state = _load_state(instance_path, resolved_runtime)
    overlay_values = state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values()
    overlay_values[str(key)] = value
    state["overlayValues"] = overlay_values
    _save_state(instance_path, state, resolved_runtime)
    return _apply_runtime_state(instance_path, resolved_runtime)


def get_media_environment(instance_path: str | Path) -> Dict[str, Any]:
    default_runtime = _default_runtime_id(instance_path)
    state = _load_state(instance_path, default_runtime)
    binary = _resolve_binary(instance_path)
    cfg = _load_media_config(instance_path)
    displays = _configured_displays(cfg)
    # Reuse the shared media font catalog so the editor sees the same
    # system/custom fonts regardless of which renderer is active.
    from pinballctl.media.runtime import list_media_fonts

    font_catalog = list_media_fonts(instance_path)
    return {
        "renderer": {
            "name": "godot",
            "godotFound": bool(binary),
            "binary": binary,
            "projectPath": str(_godot_project_path()),
            "wsUrl": _runtime_ws_url(state),
        },
        "tooling": {"websocketClientAvailable": _get_ws_connect() is not None},
        "runtimeTargets": _runtime_targets(instance_path),
        "displays": displays,
        "fonts": [
            str(row.get("family") or row.get("name") or "").strip()
            for row in font_catalog
            if str(row.get("family") or row.get("name") or "").strip()
        ],
        "fontCatalog": font_catalog,
        "runtime": runtime_status_for(instance_path, default_runtime, probe_live=False),
        "dynamicScenes": _scene_catalog(instance_path),
    }


def list_runtime_instances(instance_path: str | Path) -> Dict[str, Any]:
    instances: List[Dict[str, Any]] = []
    outputs: List[Dict[str, Any]] = []
    sessions: List[Dict[str, Any]] = []
    display_states: Dict[str, Dict[str, Any]] = {}
    for idx, target in enumerate(_runtime_targets(instance_path)):
        runtime_id = str(target.get("id") or "")
        state = _load_state(instance_path, runtime_id)
        status = runtime_status_for(instance_path, runtime_id, probe_live=False)
        if not status.get("running"):
            continue
        display_id = str(((state.get("display") or {}).get("displayId")) or str(target.get("displayId") or runtime_id))
        mode = str(((state.get("display") or {}).get("mode")) or LAUNCH_MODE_FULLSCREEN)
        scene_id = str(((state.get("scene") or {}).get("current")) or "")
        created_at = int(((state.get("process") or {}).get("startedAtMs")) or 0)
        instance = {
            "instance_id": runtime_id,
            "instanceId": runtime_id,
            "runtime_id": runtime_id,
            "runtimeId": runtime_id,
            "scene_id": scene_id,
            "sceneId": scene_id,
            "display_id": display_id,
            "displayId": display_id,
            "mode": mode,
            "state": STATE_RUNNING,
            "desired_state": "present",
            "created_at": created_at,
            "updated_at": _now_ms(),
            "runtime_url": _runtime_ws_url(state),
            "priority": 100,
            "launch_order": idx + 1,
            "process": {"pid": int(status.get("pid") or 0)},
        }
        output = {
            "id": runtime_id,
            "outputId": runtime_id,
            "runtimeId": runtime_id,
            "instanceId": runtime_id,
            "sceneId": scene_id,
            "createdAtMs": created_at,
            "priority": 100,
            "launchOrder": idx + 1,
            "type": mode,
            "target": {"displayId": display_id, "containerId": ""},
            "displayId": display_id,
            "state": STATE_RUNNING,
            "desiredState": "present",
            "lastFrameTime": _now_ms(),
            "lastSeenMs": _now_ms(),
            "runtimeUrl": _runtime_ws_url(state),
            "pid": int(status.get("pid") or 0),
            "previewViewport": None,
        }
        session = {
            "id": runtime_id,
            "runtimeId": runtime_id,
            "instanceId": runtime_id,
            "sceneId": scene_id,
            "state": STATE_RUNNING,
            "createdAtMs": created_at,
            "updatedAtMs": _now_ms(),
            "health": str(status.get("health") or "ok"),
            "outputIds": [runtime_id],
            "outputs": [output],
        }
        display_state = display_states.setdefault(display_id, {"display_id": display_id, "embedded": [], "fullscreen": []})
        (display_state["embedded"] if mode == LAUNCH_MODE_EMBEDDED else display_state["fullscreen"]).append(runtime_id)
        instances.append(instance)
        outputs.append(output)
        sessions.append(session)
    return {
        "ok": True,
        "runtimeTargets": _runtime_targets(instance_path),
        "runtimeSessions": sessions,
        "outputEndpoints": outputs,
        "instances": instances,
        "displayStates": display_states,
    }


def load_media_state(instance_path: str | Path, *, persist: bool = True) -> Dict[str, Any]:
    runtime_sessions = list_runtime_instances(instance_path)
    default_runtime = _default_runtime_id(instance_path)
    state = _load_state(instance_path, default_runtime)
    target_ids = [str(row.get("id") or "") for row in _runtime_targets(instance_path)]
    state_by_runtime = {runtime_id: _load_state(instance_path, runtime_id) for runtime_id in target_ids}
    statuses = [runtime_status_for(instance_path, runtime_id, probe_live=False) for runtime_id in target_ids]
    active = [
        {
            "runtimeId": str(status.get("runtimeId") or ""),
            "sceneId": str((((state_by_runtime.get(str(status.get("runtimeId") or ""), {}).get("scene")) or {}).get("current")) or ""),
            "displayId": str((((state_by_runtime.get(str(status.get("runtimeId") or ""), {}).get("display")) or {}).get("displayId")) or ""),
            "pid": int(status.get("pid") or 0),
            "startedAtMs": int((((state_by_runtime.get(str(status.get("runtimeId") or ""), {}).get("process")) or {}).get("startedAtMs")) or 0),
            "runtimeUrl": str(status.get("wsUrl") or ""),
            "launchMode": str((((state_by_runtime.get(str(status.get("runtimeId") or ""), {}).get("display")) or {}).get("mode")) or LAUNCH_MODE_FULLSCREEN),
            "previewViewport": None,
        }
        for status in statuses if status.get("running")
    ]
    overlay_values = {
        runtime_id: dict(state_by_runtime.get(runtime_id, {}).get("overlayValues") if isinstance(state_by_runtime.get(runtime_id, {}).get("overlayValues"), dict) else _default_overlay_values())
        for runtime_id in target_ids
    }
    payload = {
        "updatedAt": _utc_now_iso(),
        "engine": {"backend": "godot", "active": active},
        "sessions": runtime_sessions.get("outputEndpoints", []),
        "runtimeSessions": runtime_sessions.get("runtimeSessions", []),
        "outputEndpoints": runtime_sessions.get("outputEndpoints", []),
        "surfaceSessions": runtime_sessions.get("outputEndpoints", []),
        "instances": runtime_sessions.get("instances", []),
        "displayStates": runtime_sessions.get("displayStates", {}),
        "queue": [],
        "overlayValues": overlay_values,
        "godot": {
            "defaultRuntimeId": default_runtime,
            "targets": _runtime_targets(instance_path),
            "instances": state_by_runtime,
            "selected": state,
        },
    }
    if persist:
        for runtime_id, runtime_state in state_by_runtime.items():
            _save_state(instance_path, runtime_state, runtime_id)
    return payload


def play_scene(
    instance_path: str | Path,
    scene_id: str,
    *,
    runtime_id: str | None = None,
    display_id: str | None = None,
    launch_mode: str = LAUNCH_MODE_FULLSCREEN,
    **_: Any,
) -> Dict[str, Any]:
    cfg = _load_media_config(instance_path)
    scene = _scene_by_id(cfg, scene_id)
    if not isinstance(scene, dict):
        return {"ok": False, "error": "scene_not_found"}
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id, display_id)
    launched = launch_runtime(instance_path, runtime_id=resolved_runtime, display_id=display_id or resolved_runtime, launch_mode=launch_mode, scene_id=scene_id, reason="play_scene")
    if not launched.get("ok"):
        return launched
    resolved_display = str(display_id or "").strip() or str(((launched.get("status") or {}).get("display") or {}).get("displayId") or "display_1")
    state = _load_state(instance_path, resolved_runtime)
    state["scene"]["current"] = scene_id
    available = state["scene"].get("available") if isinstance(state.get("scene"), dict) and isinstance(state["scene"].get("available"), list) else []
    if scene_id not in available:
        state["scene"]["available"] = list(available) + [scene_id]
    state["playback"].update(
        {
            "status": "displaying" if str(scene.get("baseAssetId") or "").strip() else "stopped",
            "mediaKey": str(scene.get("baseAssetId") or ""),
            "loop": bool(scene.get("loop")),
            "positionMs": 0,
        }
    )
    _save_state(instance_path, state, resolved_runtime)
    applied = _apply_runtime_state(instance_path, resolved_runtime, scene_id=scene_id)
    if not applied.get("ok"):
        return applied
    return {
        "ok": True,
        "sceneId": scene_id,
        "displayId": resolved_display,
        "displayIds": [resolved_display],
        "pid": int(((launched.get("status") or {}).get("pid")) or launched.get("pid") or 0),
        "renderer": "godot",
        "runtimeUrl": _runtime_ws_url(_load_state(instance_path, resolved_runtime)),
        "launchMode": _normalize_launch_mode(launch_mode),
        "instanceId": resolved_runtime,
        "runtimeId": resolved_runtime,
        "results": [{"sceneId": scene_id, "displayId": resolved_display, "runtimeId": resolved_runtime}],
    }


def stop_scene(
    instance_path: str | Path,
    scene_id: str | None = None,
    session_id: str | None = None,
    *,
    display_id: str | None = None,
    launch_mode: str | None = None,
) -> Dict[str, Any]:
    del launch_mode
    resolved_runtime = _resolve_runtime_id(instance_path, runtime_id=session_id, display_id=display_id)
    if resolved_runtime:
        return stop_runtime(instance_path, runtime_id=resolved_runtime)
    if scene_id:
        state = _load_state(instance_path, _default_runtime_id(instance_path))
        state["scene"]["current"] = "no_scene"
        state["playback"].update({"status": "stopped", "mediaKey": "", "loop": False, "positionMs": 0})
        _save_state(instance_path, state, _default_runtime_id(instance_path))
        _apply_runtime_state(instance_path, _default_runtime_id(instance_path), scene_id="no_scene")
        return {"ok": True, "stopped": 1}
    return stop_runtime(instance_path)


def complete_scene(
    instance_path: str | Path,
    *,
    display_id: str,
    session_id: str | None = None,
    scene_id: str | None = None,
) -> Dict[str, Any]:
    del session_id, scene_id
    resolved_runtime = _resolve_runtime_id(instance_path, display_id=display_id)
    stop_video(instance_path, runtime_id=resolved_runtime)
    return {"ok": True, "completed": {"runtimeId": resolved_runtime}}


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
    del session_id, surface_type, surface_id
    cfg = _load_media_config(instance_path)
    resolved_runtime = _resolve_runtime_id(instance_path, instance_id, display_id)
    state = _load_state(instance_path, resolved_runtime)
    status = runtime_status_for(instance_path, resolved_runtime)
    requested_scene_id = str(scene_id or "").strip() or str(((state.get("scene") or {}).get("current")) or "")
    authored_scene = _scene_by_id(cfg, requested_scene_id) if requested_scene_id else None
    asset = None
    if isinstance(authored_scene, dict):
        asset = _asset_by_key(cfg, str(authored_scene.get("baseAssetId") or ""))
    displays = [row for row in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(row, dict)] or _default_displays()
    display = next((row for row in displays if str(row.get("id") or "") == str(display_id)), None) or displays[0]
    layers = []
    if isinstance(authored_scene, dict):
        layers.append(
            {
                "id": "godot-layer-primary",
                "scene": authored_scene,
                "asset": asset,
                "state": str(((state.get("playback") or {}).get("status")) or "stopped"),
                "launchMode": str(((state.get("display") or {}).get("mode")) or LAUNCH_MODE_FULLSCREEN),
                "startedAtMs": int(((state.get("process") or {}).get("startedAtMs")) or 0),
            }
        )
    return {
        "ok": True,
        "renderer": "godot",
        "updatedAt": _utc_now_iso(),
        "display": display,
        "runtimeId": resolved_runtime,
        "active": {
            "sceneId": requested_scene_id,
            "displayId": str(display.get("id") or "display_1"),
            "pid": int(status.get("pid") or 0),
            "startedAtMs": int(((state.get("process") or {}).get("startedAtMs")) or 0),
            "runtimeUrl": _runtime_ws_url(state),
            "launchMode": str(((state.get("display") or {}).get("mode")) or LAUNCH_MODE_FULLSCREEN),
            "runtimeId": resolved_runtime,
        }
        if status.get("running")
        else None,
        "scene": authored_scene,
        "asset": asset,
        "layers": layers,
        "overlayValues": dict(state.get("overlayValues") if isinstance(state.get("overlayValues"), dict) else _default_overlay_values()),
        "settings": {"runtimePollMs": 100},
    }


def run_media_maintenance(instance_path: str | Path) -> Dict[str, Any]:
    removed = 0
    restarted = 0
    running = 0
    for target in _runtime_targets(instance_path):
        runtime_id = str(target.get("id") or "")
        state = _load_state(instance_path, runtime_id)
        pid = int(((state.get("process") or {}).get("pid")) or 0)
        alive = _pid_alive(pid)
        if alive:
            running += 1
            continue
        auto_restart = bool(((state.get("runtime") or {}).get("autoRestart")) if isinstance(state.get("runtime"), dict) else True)
        if pid > 0:
            state["runtime"]["state"] = STATE_CRASHED
            state["runtime"]["health"] = "process_dead"
            _save_state(instance_path, state, runtime_id)
            removed += 1
        if auto_restart and pid > 0:
            relaunched = restart_runtime(instance_path, runtime_id=runtime_id, reason="maintenance_restart")
            if relaunched.get("ok"):
                restarted += 1
    return {"ok": True, "removed": removed, "restarted": restarted, "running": running}


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    del source
    event_name = str(name or "").strip().upper()
    payload = params if isinstance(params, dict) else {}
    if event_name in ("SCORING_EVAL", "SCORE_CHANGED"):
        score = payload.get("score")
        if score is not None:
            try:
                return update_text(instance_path, "score", f"{max(0, int(float(score))):08d}")
            except Exception:
                return {"ok": False, "error": "invalid_score"}
        return {"ok": True, "processed": False}
    if event_name == "MEDIA_SET_OVERLAY":
        key = str(payload.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "missing_key"}
        return update_text(instance_path, key, payload.get("value"))
    if event_name == "MEDIA_SCENE_PLAY":
        return play_scene(
            instance_path,
            str(payload.get("sceneId") or "").strip(),
            display_id=str(payload.get("displayId") or "").strip() or None,
            launch_mode=str(payload.get("launchMode") or LAUNCH_MODE_FULLSCREEN),
        )
    if event_name == "MEDIA_SCENE_STOP":
        return stop_scene(
            instance_path,
            scene_id=str(payload.get("sceneId") or "").strip() or None,
            session_id=str(payload.get("sessionId") or "").strip() or None,
            display_id=str(payload.get("displayId") or "").strip() or None,
            launch_mode=str(payload.get("launchMode") or "").strip() or None,
        )
    if event_name == "MEDIA_STOP_ALL":
        return stop_runtime(instance_path)
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
