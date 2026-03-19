"""Pi-side audio runtime, config persistence, and event-bus playback worker."""
from __future__ import annotations

import json
import os
import platform
import re
import signal
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from queue import Empty
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
import wave

from pinballctl.events import get_bus


_CFG_LOCK = Lock()
_STATE_LOCK = Lock()
_ENGINE_LOCK = Lock()
_BUS_WORKER_LOCK = Lock()
_BUS_WORKERS: Dict[str, Dict[str, Any]] = {}
MEDIA_AUDIO_APPLY = "MEDIA_AUDIO_APPLY"
MEDIA_AUDIO_RELEASE = "MEDIA_AUDIO_RELEASE"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _pid_alive(pid: int) -> bool:
    try:
        p = int(pid or 0)
    except Exception:
        return False
    if p <= 1:
        return False
    try:
        os.kill(p, 0)
        return True
    except Exception:
        return False


def _worker_log(logger: Callable[[str], None] | None, msg: str) -> None:
    if logger is None:
        return
    try:
        logger(msg)
    except Exception:
        pass


def _audio_dir(instance_path: str | Path) -> Path:
    p = Path(instance_path) / "audio"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _assets_dir(instance_path: str | Path) -> Path:
    p = _audio_dir(instance_path) / "assets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _config_path(instance_path: str | Path) -> Path:
    return _audio_dir(instance_path) / "audio.json"


def _state_path(instance_path: str | Path) -> Path:
    return _audio_dir(instance_path) / "state.json"


def _runtime_state_path(instance_path: str | Path) -> Path:
    return _audio_dir(instance_path) / "runtime.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _to_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    if v < minimum:
        v = minimum
    if v > maximum:
        v = maximum
    return float(v)


def _to_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        v = int(value)
    except Exception:
        v = int(default)
    if v < minimum:
        v = minimum
    if v > maximum:
        v = maximum
    return int(v)


def _normalize_id(value: Any, prefix: str) -> str:
    s = str(value or "").strip()
    if not s:
        return f"{prefix}_{uuid4().hex[:10]}"
    return re.sub(r"[^a-zA-Z0-9_.:-]", "_", s)


def _sanitize_ext(name: str) -> str:
    ext = Path(name).suffix.lower().strip()
    return ext if ext.startswith(".") else ""


def _safe_asset_name(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    if not base or base.startswith("."):
        base = f"audio_{uuid4().hex[:8]}.wav"
    return base


def _friendly_name_from_filename(filename: str) -> str:
    stem = Path(str(filename or "")).stem.strip()
    if not stem:
        return "Audio"
    # Normalize separators first.
    s = re.sub(r"[_-]+", " ", stem)
    # Split common camelCase/PascalCase boundaries.
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return "Audio"
    return s.title()


def default_audio_config() -> Dict[str, Any]:
    return {
        "_version": 1,
        "updatedAt": _utc_now(),
        "settings": {
            "enabled": True,
            "masterVolume": 1.0,
            "defaultOutput": "default",
            "maxGlobalConcurrent": 24,
            "previewVolume": 0.9,
            "autoDetectOutputs": True,
            "filePolicy": {
                "allowExtensions": [".wav", ".ogg", ".mp3", ".flac", ".m4a"],
                "maxUploadMb": 64,
            },
        },
        "buses": {
            "music": {"enabled": True, "volume": 1.0, "maxConcurrent": 2},
            "sfx": {"enabled": True, "volume": 1.0, "maxConcurrent": 12},
            "voice": {"enabled": True, "volume": 1.0, "maxConcurrent": 4},
            "ambient": {"enabled": True, "volume": 0.85, "maxConcurrent": 4},
        },
        "ducking": [
            {
                "id": "duck_voice_music",
                "enabled": True,
                "whenBus": "voice",
                "duckBus": "music",
                "amount": 0.35,
                "attackMs": 80,
                "releaseMs": 220,
            }
        ],
        "assets": [],
        "cues": [],
        "mappings": [],
    }


def _normalize_asset_row(row: Dict[str, Any]) -> Dict[str, Any]:
    filename = str(row.get("filename") or "").strip()
    display_name = str(row.get("displayName") or "").strip()
    if not display_name:
        display_name = _friendly_name_from_filename(filename)
    return {
        "id": _normalize_id(row.get("id"), "asset"),
        "displayName": display_name,
        "filename": filename,
        "format": str(row.get("format") or "unknown").strip().lower() or "unknown",
        "sizeBytes": max(0, int(row.get("sizeBytes") or 0)),
        "durationMs": max(0, int(row.get("durationMs") or 0)),
        "sampleRate": max(0, int(row.get("sampleRate") or 0)),
        "channels": max(0, int(row.get("channels") or 0)),
        "createdAt": str(row.get("createdAt") or _utc_now()),
        "tags": [str(t).strip() for t in (row.get("tags") or []) if str(t).strip()],
    }


def _normalize_cue_row(row: Dict[str, Any]) -> Dict[str, Any]:
    restart = str(row.get("restartPolicy") or "layer").strip().lower()
    if restart not in ("restart", "ignore", "layer"):
        restart = "layer"
    bus = str(row.get("bus") or "sfx").strip().lower()
    if bus not in ("music", "sfx", "voice", "ambient"):
        bus = "sfx"
    return {
        "id": _normalize_id(row.get("id"), "cue"),
        "name": str(row.get("name") or "Cue").strip() or "Cue",
        "enabled": bool(row.get("enabled", True)),
        "assetId": str(row.get("assetId") or "").strip(),
        "bus": bus,
        "volume": _to_float(row.get("volume"), default=1.0, minimum=0.0, maximum=2.0),
        "loop": bool(row.get("loop", False)),
        "repeatCount": _to_int(row.get("repeatCount"), default=1, minimum=1, maximum=10000),
        "cooldownMs": _to_int(row.get("cooldownMs"), default=0, minimum=0, maximum=3_600_000),
        "maxConcurrent": _to_int(row.get("maxConcurrent"), default=3, minimum=1, maximum=64),
        "restartPolicy": restart,
        "targetOutput": str(row.get("targetOutput") or "").strip() or "default",
        "notes": str(row.get("notes") or "").strip(),
    }


def _normalize_mapping_row(row: Dict[str, Any]) -> Dict[str, Any]:
    action = str(row.get("action") or "play").strip().lower()
    if action not in ("play", "stop", "stop_all"):
        action = "play"
    match_mode = str(row.get("matchMode") or "exact").strip().lower()
    if match_mode not in ("exact", "prefix", "contains", "regex"):
        match_mode = "exact"
    source_mode = str(row.get("sourceMatchMode") or "exact").strip().lower()
    if source_mode not in ("exact", "prefix", "contains", "regex"):
        source_mode = "exact"
    return {
        "id": _normalize_id(row.get("id"), "map"),
        "enabled": bool(row.get("enabled", True)),
        "eventName": str(row.get("eventName") or "").strip().upper(),
        "matchMode": match_mode,
        "eventSource": str(row.get("eventSource") or "").strip(),
        "sourceMatchMode": source_mode,
        "action": action,
        "cueId": str(row.get("cueId") or "").strip(),
        "priority": _to_int(row.get("priority"), default=100, minimum=0, maximum=10_000),
    }


def _normalize_config(raw: Any, *, touch_updated_at: bool = False) -> Dict[str, Any]:
    out = default_audio_config()
    if not isinstance(raw, dict):
        return out

    settings = raw.get("settings") if isinstance(raw.get("settings"), dict) else {}
    out["settings"]["enabled"] = bool(settings.get("enabled", out["settings"]["enabled"]))
    out["settings"]["masterVolume"] = _to_float(settings.get("masterVolume"), 1.0, 0.0, 2.0)
    out["settings"]["defaultOutput"] = str(settings.get("defaultOutput") or "default").strip() or "default"
    out["settings"]["maxGlobalConcurrent"] = _to_int(settings.get("maxGlobalConcurrent"), 24, 1, 256)
    out["settings"]["previewVolume"] = _to_float(settings.get("previewVolume"), 0.9, 0.0, 2.0)
    out["settings"]["autoDetectOutputs"] = bool(settings.get("autoDetectOutputs", True))
    file_policy = settings.get("filePolicy") if isinstance(settings.get("filePolicy"), dict) else {}
    allow = file_policy.get("allowExtensions")
    if isinstance(allow, list):
        exts = []
        for item in allow:
            ext = _sanitize_ext(str(item))
            if ext and ext not in exts:
                exts.append(ext)
        if exts:
            out["settings"]["filePolicy"]["allowExtensions"] = exts
    out["settings"]["filePolicy"]["maxUploadMb"] = _to_int(file_policy.get("maxUploadMb"), 64, 1, 1024)

    buses = raw.get("buses") if isinstance(raw.get("buses"), dict) else {}
    for bus_name in list(out["buses"].keys()):
        row = buses.get(bus_name) if isinstance(buses.get(bus_name), dict) else {}
        out["buses"][bus_name]["enabled"] = bool(row.get("enabled", out["buses"][bus_name]["enabled"]))
        out["buses"][bus_name]["volume"] = _to_float(row.get("volume"), out["buses"][bus_name]["volume"], 0.0, 2.0)
        out["buses"][bus_name]["maxConcurrent"] = _to_int(
            row.get("maxConcurrent"), out["buses"][bus_name]["maxConcurrent"], 1, 128
        )

    ducking_rows = raw.get("ducking") if isinstance(raw.get("ducking"), list) else []
    out_ducking: List[Dict[str, Any]] = []
    for row in ducking_rows:
        if not isinstance(row, dict):
            continue
        when_bus = str(row.get("whenBus") or "").strip().lower()
        duck_bus = str(row.get("duckBus") or "").strip().lower()
        if when_bus not in out["buses"] or duck_bus not in out["buses"]:
            continue
        out_ducking.append(
            {
                "id": _normalize_id(row.get("id"), "duck"),
                "enabled": bool(row.get("enabled", True)),
                "whenBus": when_bus,
                "duckBus": duck_bus,
                "amount": _to_float(row.get("amount"), 0.3, 0.0, 0.95),
                "attackMs": _to_int(row.get("attackMs"), 80, 0, 10_000),
                "releaseMs": _to_int(row.get("releaseMs"), 220, 0, 10_000),
            }
        )
    out["ducking"] = out_ducking

    assets = raw.get("assets") if isinstance(raw.get("assets"), list) else []
    out["assets"] = [_normalize_asset_row(row) for row in assets if isinstance(row, dict)]
    cues = raw.get("cues") if isinstance(raw.get("cues"), list) else []
    out["cues"] = [_normalize_cue_row(row) for row in cues if isinstance(row, dict)]
    mappings = raw.get("mappings") if isinstance(raw.get("mappings"), list) else []
    normalized_maps = [_normalize_mapping_row(row) for row in mappings if isinstance(row, dict)]
    out["mappings"] = sorted(normalized_maps, key=lambda r: int(r.get("priority") or 100))

    out["_version"] = 1
    if touch_updated_at:
        out["updatedAt"] = _utc_now()
    else:
        out["updatedAt"] = str(raw.get("updatedAt") or _utc_now()) if isinstance(raw, dict) else _utc_now()
    return out


def _reindex_assets_from_disk(instance_path: str | Path, cfg: Dict[str, Any]) -> bool:
    assets_dir = _assets_dir(instance_path)
    current = [a for a in (cfg.get("assets") or []) if isinstance(a, dict)]
    by_filename = {
        str(a.get("filename") or "").strip(): a
        for a in current
        if str(a.get("filename") or "").strip()
    }
    allowed = {
        str(ext).lower()
        for ext in (cfg.get("settings", {}).get("filePolicy", {}).get("allowExtensions") or [])
        if str(ext).strip()
    }
    changed = False
    rows = list(current)

    for path in sorted(assets_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        filename = path.name
        if filename in by_filename:
            continue
        ext = _sanitize_ext(filename)
        if allowed and ext not in allowed:
            continue
        meta = _detect_audio_meta(path)
        try:
            created_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except Exception:
            created_at = _utc_now()
        row = _normalize_asset_row(
            {
                "id": f"asset_{uuid4().hex[:10]}",
                "displayName": _friendly_name_from_filename(filename),
                "filename": filename,
                **meta,
                "createdAt": created_at,
                "tags": [],
            }
        )
        rows.append(row)
        by_filename[filename] = row
        changed = True

    if changed:
        cfg["assets"] = rows
    return changed


def load_audio_config(instance_path: str | Path) -> Dict[str, Any]:
    with _CFG_LOCK:
        raw = _read_json(_config_path(instance_path), default_audio_config())
        cfg = _normalize_config(raw, touch_updated_at=False)
        reindexed = _reindex_assets_from_disk(instance_path, cfg)
        if reindexed or not isinstance(raw, dict) or raw != cfg:
            _write_json(_config_path(instance_path), cfg)
        return cfg


def save_audio_config(instance_path: str | Path, config: Dict[str, Any]) -> Dict[str, Any]:
    with _CFG_LOCK:
        cfg = _normalize_config(config, touch_updated_at=True)
        _write_json(_config_path(instance_path), cfg)
        return cfg


@dataclass
class PlaybackHandle:
    playback_id: str
    cue_id: str
    bus: str
    event_name: str
    source: str
    preview: bool
    started_at_ms: int
    target_output: str
    volume: float
    start_offset_ms: int
    start_iteration: int
    stop_evt: Event
    thread: Thread
    process: Optional[subprocess.Popen] = None


class AudioEngine:
    def __init__(self, instance_path: str | Path) -> None:
        self.instance_path = str(Path(instance_path).resolve())
        self._lock = Lock()
        self._active: Dict[str, PlaybackHandle] = {}
        self._cue_index: Dict[str, set[str]] = {}
        self._cooldowns: Dict[str, float] = {}
        self._last_error: str = ""
        self._devices_cache_at = 0.0
        self._devices_cache: List[Dict[str, Any]] = []
        self._mac_switch_lock = Lock()
        self._runtime_path = _runtime_state_path(self.instance_path)
        self._orphan_seen_at: Dict[int, float] = {}
        self._mac_last_output: str = ""
        self._media_audio_intents: Dict[str, Dict[str, Any]] = {}

    def _media_intent_effects_unlocked(self) -> Dict[str, Any]:
        paused: set[str] = set()
        ducked: Dict[str, float] = {}
        for row in self._media_audio_intents.values():
            if not isinstance(row, dict):
                continue
            audio = row.get("audioBehaviour") if isinstance(row.get("audioBehaviour"), dict) else {}
            for bus in audio.get("pause") if isinstance(audio.get("pause"), list) else []:
                val = str(bus or "").strip().lower()
                if val in ("music", "sfx", "voice", "ambient"):
                    paused.add(val)
            for bus in audio.get("duck") if isinstance(audio.get("duck"), list) else []:
                val = str(bus or "").strip().lower()
                if val in ("music", "sfx", "voice", "ambient"):
                    ducked[val] = max(float(ducked.get(val, 1.0)), 0.35)
        return {"pausedBuses": sorted(paused), "duckedBuses": ducked}

    def set_media_audio_intent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        display_id = str((payload or {}).get("displayId") or "").strip()
        scene_id = str((payload or {}).get("sceneId") or "").strip()
        if not display_id or not scene_id:
            return {"ok": False, "error": "invalid_media_audio_intent"}
        key = f"{display_id}:{scene_id}"
        with self._lock:
            self._media_audio_intents[key] = {
                "displayId": display_id,
                "sceneId": scene_id,
                "layerId": str((payload or {}).get("layerId") or "").strip(),
                "priority": int((payload or {}).get("priority") or 0),
                "blendMode": str((payload or {}).get("blendMode") or "").strip().upper(),
                "audioBehaviour": dict((payload or {}).get("audioBehaviour") if isinstance((payload or {}).get("audioBehaviour"), dict) else {}),
                "resumeOnEnd": bool((payload or {}).get("resumeOnEnd", True)),
            }
            effects = self._media_intent_effects_unlocked()
            handles = [h for h in self._active.values() if h.bus in set(effects["pausedBuses"])]
        for h in handles:
            self._stop_handle(h)
        return {"ok": True, **effects}

    def release_media_audio_intent(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        display_id = str((payload or {}).get("displayId") or "").strip()
        scene_id = str((payload or {}).get("sceneId") or "").strip()
        if not display_id or not scene_id:
            return {"ok": False, "error": "invalid_media_audio_intent"}
        key = f"{display_id}:{scene_id}"
        with self._lock:
            self._media_audio_intents.pop(key, None)
            effects = self._media_intent_effects_unlocked()
        return {"ok": True, **effects}

    def _backend_name(self, *, low_latency: bool = False) -> str:
        if platform.system().lower() == "darwin" and low_latency and shutil.which("afplay"):
            return "afplay"
        if shutil.which("ffplay"):
            return "ffplay"
        if platform.system().lower() == "darwin" and shutil.which("afplay"):
            return "afplay"
        if shutil.which("paplay"):
            return "paplay"
        if shutil.which("aplay"):
            return "aplay"
        return "none"

    def _list_devices_macos(self) -> List[Dict[str, Any]]:
        out = [{"id": "default", "name": "Default Output", "backend": self._backend_name(), "default": True}]
        cmd = shutil.which("SwitchAudioSource")
        if not cmd:
            return out
        try:
            proc = subprocess.run(
                [cmd, "-a", "-t", "output"],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            cur = subprocess.run(
                [cmd, "-c", "-t", "output"],
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            current = (cur.stdout or "").strip()
            for line in (proc.stdout or "").splitlines():
                name = line.strip()
                if not name:
                    continue
                out.append(
                    {
                        "id": name,
                        "name": name,
                        "backend": self._backend_name(),
                        "default": bool(current and current == name),
                    }
                )
        except Exception:
            pass
        return out

    def _list_devices_linux(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = [{"id": "default", "name": "Default Output", "backend": self._backend_name(), "default": True}]
        if shutil.which("pactl"):
            try:
                proc = subprocess.run(
                    ["pactl", "-f", "json", "list", "sinks"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=False,
                )
                sinks = json.loads(proc.stdout or "[]")
                if isinstance(sinks, list):
                    for sink in sinks:
                        if not isinstance(sink, dict):
                            continue
                        sid = str(sink.get("name") or "").strip()
                        if not sid:
                            continue
                        desc = str(sink.get("description") or sid).strip()
                        out.append({"id": sid, "name": desc, "backend": self._backend_name(), "default": False})
            except Exception:
                pass
        elif shutil.which("aplay"):
            try:
                proc = subprocess.run(["aplay", "-L"], capture_output=True, text=True, timeout=3, check=False)
                for line in (proc.stdout or "").splitlines():
                    if not line or line[0].isspace() or line.startswith("null"):
                        continue
                    sid = line.split()[0].strip()
                    if sid:
                        out.append({"id": sid, "name": sid, "backend": self._backend_name(), "default": False})
            except Exception:
                pass
        return out

    def list_devices(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        with self._lock:
            now = time.monotonic()
            if not force_refresh and self._devices_cache and (now - self._devices_cache_at) < 5.0:
                return list(self._devices_cache)
            system = platform.system().lower()
            if system == "darwin":
                devices = self._list_devices_macos()
            elif system == "linux":
                devices = self._list_devices_linux()
            else:
                devices = [{"id": "default", "name": "Default Output", "backend": self._backend_name(), "default": True}]
            dedup: Dict[str, Dict[str, Any]] = {}
            for d in devices:
                did = str(d.get("id") or "").strip()
                if did:
                    dedup[did] = d
            out = list(dedup.values())
            if not out:
                out = [{"id": "default", "name": "Default Output", "backend": self._backend_name(), "default": True}]
            self._devices_cache = out
            self._devices_cache_at = now
            return list(out)

    def _asset_path(self, filename: str) -> Path:
        return _assets_dir(self.instance_path) / filename

    def _has_active_on_bus(self, bus: str) -> bool:
        for handle in self._active.values():
            if handle.bus == bus and not handle.stop_evt.is_set():
                return True
        return False

    def _effective_volume(self, cfg: Dict[str, Any], cue: Dict[str, Any]) -> float:
        v = _to_float(cfg.get("settings", {}).get("masterVolume"), 1.0, 0.0, 2.0)
        bus = str(cue.get("bus") or "sfx")
        v *= _to_float((cfg.get("buses", {}).get(bus) or {}).get("volume"), 1.0, 0.0, 2.0)
        v *= _to_float(cue.get("volume"), 1.0, 0.0, 2.0)
        for row in cfg.get("ducking") or []:
            if not isinstance(row, dict) or not row.get("enabled", True):
                continue
            when_bus = str(row.get("whenBus") or "")
            duck_bus = str(row.get("duckBus") or "")
            if duck_bus != bus:
                continue
            if self._has_active_on_bus(when_bus):
                v *= max(0.0, 1.0 - _to_float(row.get("amount"), 0.3, 0.0, 0.95))
        with self._lock:
            effects = self._media_intent_effects_unlocked()
        if bus in set(effects.get("pausedBuses") or []):
            return 0.0
        duck_amount = float((effects.get("duckedBuses") or {}).get(bus, 0.0) or 0.0)
        if duck_amount > 0:
            v *= max(0.0, 1.0 - min(0.95, duck_amount))
        return _to_float(v, 1.0, 0.0, 2.0)

    def _player_cmd(
        self,
        file_path: Path,
        volume: float,
        device_id: str,
        *,
        start_offset_ms: int = 0,
        low_latency: bool = False,
    ) -> List[str]:
        backend = self._backend_name(low_latency=low_latency and start_offset_ms <= 0)
        seek_sec = max(0.0, float(max(0, int(start_offset_ms))) / 1000.0)
        if backend == "ffplay":
            cmd = [
                "ffplay",
                "-nodisp",
                "-autoexit",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                "-probesize",
                "32",
                "-analyzeduration",
                "0",
                "-loglevel",
                "quiet",
            ]
            if seek_sec > 0:
                cmd += ["-ss", f"{seek_sec:.3f}"]
            cmd += [
                "-volume",
                str(int(round(_to_float(volume, 1.0, 0.0, 2.0) * 100))),
                str(file_path),
            ]
            return cmd
        if backend == "afplay":
            return ["afplay", "-v", f"{_to_float(volume, 1.0, 0.0, 2.0):.3f}", str(file_path)]
        if backend == "paplay":
            cmd = ["paplay", "--volume", str(int(_to_float(volume, 1.0, 0.0, 2.0) * 65536))]
            if device_id and device_id != "default":
                cmd += ["--device", device_id]
            cmd.append(str(file_path))
            return cmd
        if backend == "aplay":
            cmd = ["aplay"]
            if device_id and device_id != "default":
                cmd += ["-D", device_id]
            cmd.append(str(file_path))
            return cmd
        return []

    def _switch_output_macos(self, target_output: str) -> bool:
        if platform.system().lower() != "darwin":
            return True
        target = str(target_output or "").strip()
        if not target or target == "default":
            return True
        if self._mac_last_output and self._mac_last_output == target:
            return True
        cmd = shutil.which("SwitchAudioSource")
        if not cmd:
            self._last_error = "switchaudiosource_missing"
            return False
        with self._mac_switch_lock:
            try:
                proc = subprocess.run(
                    [cmd, "-s", target, "-t", "output"],
                    capture_output=True,
                    text=True,
                    timeout=2.5,
                    check=False,
                )
                if proc.returncode != 0:
                    self._last_error = f"output_switch_failed:{target}"
                    return False
                self._mac_last_output = target
                return True
            except Exception as exc:
                self._last_error = f"output_switch_error:{exc}"
                return False

    def _register_handle(self, handle: PlaybackHandle) -> None:
        with self._lock:
            self._active[handle.playback_id] = handle
            self._cue_index.setdefault(handle.cue_id, set()).add(handle.playback_id)
        self._persist_runtime_snapshot()

    def _unregister_handle(self, playback_id: str) -> None:
        with self._lock:
            handle = self._active.pop(playback_id, None)
            if not handle:
                self._persist_runtime_snapshot()
                return
            ids = self._cue_index.get(handle.cue_id)
            if isinstance(ids, set):
                ids.discard(playback_id)
                if not ids:
                    self._cue_index.pop(handle.cue_id, None)
        self._persist_runtime_snapshot()

    def _stop_handle(self, handle: PlaybackHandle) -> None:
        handle.stop_evt.set()
        proc = handle.process
        self._terminate_process(proc)

    def _terminate_process(self, proc: Optional[subprocess.Popen], *, timeout_s: float = 0.35) -> None:
        if not proc:
            return
        try:
            if proc.poll() is not None:
                return
        except Exception:
            return
        # Terminate the full process group if available (ffplay/afplay can spawn children).
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        try:
            proc.wait(timeout=max(0.05, float(timeout_s)))
            return
        except Exception:
            pass
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        try:
            proc.wait(timeout=0.25)
        except Exception:
            pass

    def _reap_orphan_players(self) -> int:
        with self._lock:
            tracked = {
                int(h.process.pid)
                for h in self._active.values()
                if h.process is not None and getattr(h.process, "pid", None)
            }
        orphans = self._scan_instance_player_processes(exclude_pids=tracked)
        killed = 0
        for row in orphans:
            try:
                self._kill_pid(int(row.get("pid") or 0))
                killed += 1
            except Exception:
                continue
        return killed

    def _scan_instance_player_processes(self, *, exclude_pids: set[int] | None = None) -> List[Dict[str, Any]]:
        backend = self._backend_name()
        if backend not in ("ffplay", "afplay", "paplay", "aplay"):
            return []
        assets_root = str(_assets_dir(self.instance_path).resolve())
        out: List[Dict[str, Any]] = []
        skip = set(exclude_pids or set())
        try:
            proc = subprocess.run(
                ["ps", "-ax", "-o", "pid=,command="],
                capture_output=True,
                text=True,
                timeout=2.0,
                check=False,
            )
            lines = (proc.stdout or "").splitlines()
        except Exception:
            return []
        me = os.getpid()
        for line in lines:
            row = str(line or "").strip()
            if not row:
                continue
            parts = row.split(None, 1)
            if len(parts) != 2:
                continue
            pid_s, cmd = parts
            try:
                pid = int(pid_s)
            except Exception:
                continue
            if pid <= 1 or pid == me or pid in skip:
                continue
            cmd_l = cmd.lower()
            if assets_root.lower() not in cmd_l:
                continue
            if not any(player in cmd_l for player in ("ffplay", "afplay", "paplay", "aplay")):
                continue
            out.append({"pid": pid, "command": cmd})
        return out

    def _kill_pid(self, pid: int) -> bool:
        if pid <= 1:
            return False
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                return False
        time.sleep(0.08)
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        return True

    def stop_playback(self, playback_id: str) -> bool:
        with self._lock:
            handle = self._active.get(str(playback_id or "").strip())
        if not handle:
            return False
        self._stop_handle(handle)
        return True

    def stop_pid(self, pid: int) -> bool:
        pid_i = int(pid or 0)
        if pid_i <= 1:
            return False
        with self._lock:
            handles = list(self._active.values())
        for h in handles:
            p = h.process
            if p is not None and int(getattr(p, "pid", 0) or 0) == pid_i:
                self._stop_handle(h)
                return True
        return self._kill_pid(pid_i)

    def orphan_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            tracked = {
                int(h.process.pid)
                for h in self._active.values()
                if h.process is not None and getattr(h.process, "pid", None)
            }
        rows = self._scan_instance_player_processes(exclude_pids=tracked)
        now = time.monotonic()
        seen_now = {int(r.get("pid") or 0) for r in rows if int(r.get("pid") or 0) > 0}
        with self._lock:
            for pid in seen_now:
                self._orphan_seen_at.setdefault(pid, now)
            # prune old entries for processes no longer present
            for pid in list(self._orphan_seen_at.keys()):
                if pid not in seen_now:
                    self._orphan_seen_at.pop(pid, None)
        return [
            {
                "playbackId": f"orphan:{int(r.get('pid') or 0)}",
                "cueId": "",
                "bus": "orphan",
                "eventName": "ORPHAN",
                "source": "orphan",
                "preview": False,
                "startedAtMs": 0,
                "targetOutput": "unknown",
                "volume": 0,
                "pid": int(r.get("pid") or 0),
                "orphan": True,
                "command": str(r.get("command") or ""),
            }
            for r in rows
            if int(r.get("pid") or 0) > 0
            and (now - float(self._orphan_seen_at.get(int(r.get("pid") or 0), now))) >= 0.8
        ]

    def _wait_for_playback_ids_stopped(self, playback_ids: List[str], timeout_ms: int = 400) -> None:
        if not playback_ids:
            return
        deadline = time.monotonic() + (max(1, int(timeout_ms)) / 1000.0)
        pending = {str(pid) for pid in playback_ids if str(pid)}
        while pending and time.monotonic() < deadline:
            with self._lock:
                active_ids = set(self._active.keys())
            pending = {pid for pid in pending if pid in active_ids}
            if pending:
                time.sleep(0.02)

    def stop(self, cue_id: str | None = None, preview_only: bool = False) -> int:
        with self._lock:
            handles = list(self._active.values())
        target_ids: List[str] = []
        stop_count = 0
        for h in handles:
            if cue_id and h.cue_id != cue_id:
                continue
            if preview_only and not h.preview:
                continue
            target_ids.append(str(h.playback_id))
            self._stop_handle(h)
            stop_count += 1
        if target_ids:
            self._wait_for_playback_ids_stopped(target_ids, timeout_ms=900)
        # Extra safety: if any backend process was orphaned, reap it so audio cannot continue silently.
        stop_count += self._reap_orphan_players()
        return stop_count

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return self._snapshot_unlocked()

    def _snapshot_unlocked(self) -> Dict[str, Any]:
        active = []
        for h in self._active.values():
            p = h.process
            pid = int(getattr(p, "pid", 0) or 0) if p is not None else 0
            alive = bool(p is not None and p.poll() is None)
            active.append(
                {
                    "playbackId": h.playback_id,
                    "cueId": h.cue_id,
                    "bus": h.bus,
                    "eventName": h.event_name,
                    "source": h.source,
                    "preview": h.preview,
                    "startedAtMs": h.started_at_ms,
                    "targetOutput": h.target_output,
                    "volume": h.volume,
                    "pid": pid,
                    "alive": alive,
                    "orphan": False,
                }
            )
        return {
            "backend": self._backend_name(),
            "active": active,
            "lastError": self._last_error,
            "mediaAudioIntents": [dict(row) for row in self._media_audio_intents.values()],
            "mediaAudioEffects": self._media_intent_effects_unlocked(),
        }

    def _persist_runtime_snapshot(self) -> None:
        try:
            with self._lock:
                snap = self._snapshot_unlocked()
            payload = {
                "updatedAt": _utc_now(),
                "engine": snap,
            }
            _write_json(self._runtime_path, payload)
        except Exception:
            pass

    def _play_loop(
        self,
        *,
        handle: PlaybackHandle,
        file_path: Path,
        repeat_count: int,
        loop: bool,
    ) -> None:
        try:
            n = max(0, int(handle.start_iteration or 0))
            first_start_offset_ms = max(0, int(handle.start_offset_ms or 0))
            first_launch = True
            if not self._switch_output_macos(handle.target_output):
                return
            while not handle.stop_evt.is_set():
                if not loop and n >= repeat_count:
                    break
                if handle.stop_evt.is_set():
                    break
                cmd = self._player_cmd(
                    file_path,
                    handle.volume,
                    handle.target_output,
                    start_offset_ms=first_start_offset_ms if first_launch else 0,
                    low_latency=not handle.preview,
                )
                if not cmd:
                    self._last_error = "no_audio_backend"
                    break
                if handle.stop_evt.is_set():
                    break
                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    handle.process = proc
                except Exception as exc:
                    self._last_error = f"spawn_failed:{exc}"
                    break
                while not handle.stop_evt.is_set():
                    rc = proc.poll()
                    if rc is not None:
                        break
                    time.sleep(0.02)
                if handle.stop_evt.is_set():
                    self._terminate_process(proc)
                else:
                    # If a player was externally terminated (e.g., runtime orphan kill), do not respawn.
                    try:
                        rc_final = proc.poll()
                    except Exception:
                        rc_final = None
                    if rc_final not in (None, 0):
                        self._last_error = f"player_exited:{rc_final}"
                        break
                n += 1
                first_launch = False
                if loop:
                    continue
        finally:
            self._unregister_handle(handle.playback_id)

    def play(self, cfg: Dict[str, Any], cue: Dict[str, Any], *, event_name: str, source: str, preview: bool = False) -> Dict[str, Any]:
        if not cfg.get("settings", {}).get("enabled", True):
            return {"ok": False, "error": "audio_disabled"}
        if not cue.get("enabled", True):
            return {"ok": False, "error": "cue_disabled"}

        cue_id = str(cue.get("id") or "").strip()
        asset_id = str(cue.get("assetId") or "").strip()
        if not cue_id or not asset_id:
            return {"ok": False, "error": "invalid_cue"}

        asset_map = {str(a.get("id")): a for a in (cfg.get("assets") or []) if isinstance(a, dict)}
        asset = asset_map.get(asset_id)
        if not asset:
            return {"ok": False, "error": "asset_not_found"}

        file_path = self._asset_path(str(asset.get("filename") or ""))
        if not file_path.exists():
            return {"ok": False, "error": "asset_missing"}

        cooldown_ms = _to_int(cue.get("cooldownMs"), 0, 0, 3_600_000)
        now_mono = time.monotonic()
        bus = str(cue.get("bus") or "sfx")
        bus_cfg = (cfg.get("buses", {}) or {}).get(bus) or {}
        if not bus_cfg.get("enabled", True):
            return {"ok": False, "error": "bus_disabled"}
        with self._lock:
            effects = self._media_intent_effects_unlocked()
        if bus in set(effects.get("pausedBuses") or []):
            return {"ok": False, "error": "bus_paused_by_media"}

        cue_max = _to_int(cue.get("maxConcurrent"), 3, 1, 64)
        restart_policy = str(cue.get("restartPolicy") or "layer").strip().lower()
        if restart_policy not in ("restart", "ignore", "layer"):
            restart_policy = "layer"

        repeat_count = _to_int(cue.get("repeatCount"), 1, 1, 10_000)
        loop = bool(cue.get("loop", False))
        start_offset_ms = _to_int(cue.get("_seekMs"), 0, 0, 7_200_000)
        start_iteration = 0
        logical_seek_ms = start_offset_ms
        asset_duration_ms = _to_int(asset.get("durationMs"), 0, 0, 7_200_000)
        if asset_duration_ms > 0:
            if loop:
                start_offset_ms = start_offset_ms % asset_duration_ms
                logical_seek_ms = start_offset_ms
            else:
                total_ms = max(1, repeat_count * asset_duration_ms)
                clamped_seek = min(start_offset_ms, total_ms - 1)
                start_iteration = min(repeat_count - 1, clamped_seek // asset_duration_ms)
                start_offset_ms = clamped_seek % asset_duration_ms
                logical_seek_ms = (start_iteration * asset_duration_ms) + start_offset_ms
        target_output = str(cue.get("targetOutput") or cfg.get("settings", {}).get("defaultOutput") or "default")
        if platform.system().lower() == "darwin":
            with self._lock:
                active_targets = {str(h.target_output or "default") for h in self._active.values()}
            explicit_active = {t for t in active_targets if t and t != "default"}
            # On macOS, allow "default" cues to follow the currently active explicit output.
            # This keeps SFX and music layered when one cue is pinned to a named device.
            if target_output == "default":
                pref_default = str(cfg.get("settings", {}).get("defaultOutput") or "default").strip() or "default"
                if len(explicit_active) == 1:
                    target_output = next(iter(explicit_active))
                elif pref_default != "default":
                    target_output = pref_default

            if target_output != "default" and not shutil.which("SwitchAudioSource"):
                return {"ok": False, "error": "switchaudiosource_missing"}

            # macOS output routing is global. Avoid simultaneous conflicting explicit targets.
            if target_output != "default":
                for t in explicit_active:
                    if t != target_output:
                        return {"ok": False, "error": "mac_global_output_conflict"}

        volume = self._effective_volume(cfg, cue)
        if preview:
            volume = _to_float(cfg.get("settings", {}).get("previewVolume"), 0.9, 0.0, 2.0)

        stop_evt = Event()
        playback_id = f"play_{uuid4().hex[:12]}"
        handle = PlaybackHandle(
            playback_id=playback_id,
            cue_id=cue_id,
            bus=bus,
            event_name=event_name,
            source=source,
            preview=preview,
            started_at_ms=_now_ms() - max(0, int(logical_seek_ms)),
            target_output=target_output,
            volume=volume,
            start_offset_ms=start_offset_ms,
            start_iteration=start_iteration,
            stop_evt=stop_evt,
            thread=Thread(target=lambda: None),
        )

        # Admission is two-phase to avoid races under parallel rule worker dispatch.
        # We first evaluate limits (and stop conflicting instances for restart policy),
        # then re-evaluate + reserve a slot atomically before launching the player thread.
        ids_to_stop: List[str] = []
        with self._lock:
            next_allowed = self._cooldowns.get(cue_id, 0.0)
            if cooldown_ms > 0 and now_mono < next_allowed:
                return {"ok": False, "error": "cooldown"}
            active_global = len(self._active)
            if active_global >= _to_int(cfg.get("settings", {}).get("maxGlobalConcurrent"), 24, 1, 256):
                return {"ok": False, "error": "max_global_concurrency"}
            bus_active = sum(1 for h in self._active.values() if h.bus == bus)
            if bus_active >= _to_int(bus_cfg.get("maxConcurrent"), 8, 1, 128):
                return {"ok": False, "error": "max_bus_concurrency"}
            cue_active_ids = list(self._cue_index.get(cue_id, set()))
            if restart_policy == "ignore" and cue_active_ids:
                return {"ok": False, "error": "already_playing"}
            if restart_policy == "restart" and len(cue_active_ids) >= cue_max:
                ids_to_stop = list(cue_active_ids)
            elif restart_policy == "layer" and len(cue_active_ids) >= cue_max:
                return {"ok": False, "error": "max_cue_concurrency"}

        if ids_to_stop:
            with self._lock:
                handles_to_stop = [self._active.get(pid) for pid in ids_to_stop]
            for h in handles_to_stop:
                if h:
                    self._stop_handle(h)
            # Avoid overlapping processes when the old instance has not exited yet.
            self._wait_for_playback_ids_stopped(ids_to_stop)
        run_thread = Thread(
            target=self._play_loop,
            kwargs={
                "handle": handle,
                "file_path": file_path,
                "repeat_count": repeat_count,
                "loop": loop,
            },
            daemon=True,
            name=f"audio-play-{cue_id}",
        )
        handle.thread = run_thread

        with self._lock:
            # Re-check limits just before reservation to make this path race-safe.
            active_global = len(self._active)
            if active_global >= _to_int(cfg.get("settings", {}).get("maxGlobalConcurrent"), 24, 1, 256):
                return {"ok": False, "error": "max_global_concurrency"}
            bus_active = sum(1 for h in self._active.values() if h.bus == bus)
            if bus_active >= _to_int(bus_cfg.get("maxConcurrent"), 8, 1, 128):
                return {"ok": False, "error": "max_bus_concurrency"}
            cue_active_ids = list(self._cue_index.get(cue_id, set()))
            if restart_policy == "ignore" and cue_active_ids:
                return {"ok": False, "error": "already_playing"}
            if len(cue_active_ids) >= cue_max:
                if restart_policy == "layer":
                    return {"ok": False, "error": "max_cue_concurrency"}
                if restart_policy == "restart":
                    # A concurrent caller has already reserved/started one.
                    return {"ok": False, "error": "max_cue_concurrency"}
            self._active[handle.playback_id] = handle
            self._cue_index.setdefault(handle.cue_id, set()).add(handle.playback_id)
            if cooldown_ms > 0:
                self._cooldowns[cue_id] = now_mono + (cooldown_ms / 1000.0)
        self._persist_runtime_snapshot()
        run_thread.start()
        return {"ok": True, "playbackId": playback_id}


_ENGINES: Dict[str, AudioEngine] = {}


def _get_engine(instance_path: str | Path) -> AudioEngine:
    inst = str(Path(instance_path).resolve())
    with _ENGINE_LOCK:
        eng = _ENGINES.get(inst)
        if eng is None:
            eng = AudioEngine(inst)
            _ENGINES[inst] = eng
        return eng


def _detect_audio_meta(path: Path) -> Dict[str, Any]:
    ext = path.suffix.lower().lstrip(".")
    out = {
        "format": ext or "unknown",
        "durationMs": 0,
        "sampleRate": 0,
        "channels": 0,
        "sizeBytes": int(path.stat().st_size) if path.exists() else 0,
    }
    if ext == "wav":
        try:
            with wave.open(str(path), "rb") as wf:
                rate = int(wf.getframerate() or 0)
                channels = int(wf.getnchannels() or 0)
                frames = int(wf.getnframes() or 0)
            out["sampleRate"] = rate
            out["channels"] = channels
            if rate > 0:
                out["durationMs"] = int((frames / rate) * 1000)
            return out
        except Exception:
            return out

    if shutil.which("ffprobe"):
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-print_format",
                    "json",
                    "-show_streams",
                    "-show_format",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            doc = json.loads(proc.stdout or "{}")
            streams = doc.get("streams") if isinstance(doc, dict) else []
            if isinstance(streams, list):
                for s in streams:
                    if not isinstance(s, dict):
                        continue
                    if str(s.get("codec_type") or "") != "audio":
                        continue
                    out["sampleRate"] = int(float(s.get("sample_rate") or 0))
                    out["channels"] = int(s.get("channels") or 0)
                    duration = s.get("duration")
                    if duration is not None:
                        out["durationMs"] = int(float(duration) * 1000)
                    break
            if out["durationMs"] <= 0:
                fmt = doc.get("format") if isinstance(doc, dict) and isinstance(doc.get("format"), dict) else {}
                if fmt.get("duration") is not None:
                    out["durationMs"] = int(float(fmt.get("duration")) * 1000)
        except Exception:
            pass
    return out


def upload_asset(instance_path: str | Path, file_storage: Any, display_name: str | None = None) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    filename = _safe_asset_name(str(getattr(file_storage, "filename", "") or "audio.wav"))
    ext = _sanitize_ext(filename)
    allowed = [str(x).lower() for x in (cfg.get("settings", {}).get("filePolicy", {}).get("allowExtensions") or [])]
    if ext not in allowed:
        return {"ok": False, "error": "unsupported_extension", "allowed": allowed}

    target = _assets_dir(instance_path) / filename
    # Avoid collisions and preserve prior uploads.
    if target.exists():
        target = target.with_name(f"{target.stem}_{uuid4().hex[:6]}{target.suffix}")

    file_storage.save(str(target))
    size_mb = target.stat().st_size / (1024.0 * 1024.0)
    max_mb = _to_int(cfg.get("settings", {}).get("filePolicy", {}).get("maxUploadMb"), 64, 1, 1024)
    if size_mb > max_mb:
        try:
            target.unlink(missing_ok=True)
        except Exception:
            pass
        return {"ok": False, "error": "file_too_large", "maxUploadMb": max_mb}

    meta = _detect_audio_meta(target)
    row = _normalize_asset_row(
        {
            "id": f"asset_{uuid4().hex[:10]}",
            "displayName": str(display_name or "").strip(),
            "filename": target.name,
            **meta,
            "createdAt": _utc_now(),
            "tags": [],
        }
    )

    assets = [a for a in (cfg.get("assets") or []) if isinstance(a, dict)]
    assets.append(row)
    cfg["assets"] = assets
    save_audio_config(instance_path, cfg)
    return {"ok": True, "asset": row}


def delete_asset(instance_path: str | Path, asset_id: str) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    assets = [a for a in (cfg.get("assets") or []) if isinstance(a, dict)]
    remove = None
    keep: List[Dict[str, Any]] = []
    for row in assets:
        if str(row.get("id") or "") == asset_id and remove is None:
            remove = row
            continue
        keep.append(row)
    if remove is None:
        return {"ok": False, "error": "asset_not_found"}

    in_use = [c for c in (cfg.get("cues") or []) if isinstance(c, dict) and str(c.get("assetId") or "") == asset_id]
    if in_use:
        return {"ok": False, "error": "asset_in_use", "cueIds": [str(c.get("id") or "") for c in in_use]}

    cfg["assets"] = keep
    save_audio_config(instance_path, cfg)
    try:
        (_assets_dir(instance_path) / str(remove.get("filename") or "")).unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


def get_asset_file(instance_path: str | Path, asset_id: str) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    asset = next((a for a in (cfg.get("assets") or []) if isinstance(a, dict) and str(a.get("id") or "") == asset_id), None)
    if asset is None:
        return {"ok": False, "error": "asset_not_found"}
    filename = str(asset.get("filename") or "").strip()
    if not filename:
        return {"ok": False, "error": "asset_missing"}
    path = _assets_dir(instance_path) / filename
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "asset_missing"}
    return {"ok": True, "path": path, "asset": asset}


def _match_text(value: str, pattern: str, mode: str) -> bool:
    if mode == "exact":
        return value == pattern
    if mode == "prefix":
        return value.startswith(pattern)
    if mode == "contains":
        return pattern in value
    if mode == "regex":
        try:
            return bool(re.search(pattern, value))
        except re.error:
            return False
    return False


def process_event(instance_path: str | Path, *, name: str, source: str | None, params: Dict[str, Any] | None = None) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    if not cfg.get("settings", {}).get("enabled", True):
        return {"ok": True, "processed": False, "reason": "audio_disabled"}

    event_name = str(name or "").strip().upper()
    event_source = str(source or "").strip()
    payload = params if isinstance(params, dict) else {}
    eng = _get_engine(instance_path)

    if event_name == MEDIA_AUDIO_APPLY:
        res = eng.set_media_audio_intent(payload)
        state = {
            "updatedAt": _utc_now(),
            "lastEvent": {"name": event_name, "source": event_source, "params": payload, "atMs": _now_ms()},
            "actions": [{"ok": bool(res.get("ok")), "type": "media_audio_apply", **res}],
            "engine": eng.snapshot(),
        }
        with _STATE_LOCK:
            _write_json(_state_path(instance_path), state)
        return {"ok": True, "processed": bool(res.get("ok")), "actions": state["actions"]}

    if event_name == MEDIA_AUDIO_RELEASE:
        res = eng.release_media_audio_intent(payload)
        state = {
            "updatedAt": _utc_now(),
            "lastEvent": {"name": event_name, "source": event_source, "params": payload, "atMs": _now_ms()},
            "actions": [{"ok": bool(res.get("ok")), "type": "media_audio_release", **res}],
            "engine": eng.snapshot(),
        }
        with _STATE_LOCK:
            _write_json(_state_path(instance_path), state)
        return {"ok": True, "processed": bool(res.get("ok")), "actions": state["actions"]}

    mappings = [m for m in (cfg.get("mappings") or []) if isinstance(m, dict) and m.get("enabled", True)]
    mappings.sort(key=lambda m: int(m.get("priority") or 100))
    cues = {str(c.get("id") or ""): c for c in (cfg.get("cues") or []) if isinstance(c, dict)}
    actions: List[Dict[str, Any]] = []

    for m in mappings:
        m_name = str(m.get("eventName") or "").strip().upper()
        m_mode = str(m.get("matchMode") or "exact").strip().lower()
        if not m_name or not _match_text(event_name, m_name, m_mode):
            continue

        m_source = str(m.get("eventSource") or "").strip()
        if m_source:
            src_mode = str(m.get("sourceMatchMode") or "exact").strip().lower()
            if not _match_text(event_source, m_source, src_mode):
                continue

        action = str(m.get("action") or "play").strip().lower()
        cue_id = str(m.get("cueId") or "").strip()
        if action == "play":
            cue = cues.get(cue_id)
            if cue is None:
                actions.append({"mappingId": m.get("id"), "ok": False, "error": "cue_not_found"})
                continue
            res = eng.play(cfg, cue, event_name=event_name, source=event_source, preview=False)
            actions.append({"mappingId": m.get("id"), **res})
        elif action == "stop":
            stopped = eng.stop(cue_id=cue_id or None)
            actions.append({"mappingId": m.get("id"), "ok": True, "stopped": stopped})
        elif action == "stop_all":
            stopped = eng.stop(cue_id=None)
            actions.append({"mappingId": m.get("id"), "ok": True, "stopped": stopped})

    state = {
        "updatedAt": _utc_now(),
        "lastEvent": {
            "name": event_name,
            "source": event_source,
            "params": params or {},
            "atMs": _now_ms(),
        },
        "actions": actions,
        "engine": eng.snapshot(),
    }
    with _STATE_LOCK:
        _write_json(_state_path(instance_path), state)
    return {"ok": True, "processed": bool(actions), "actions": actions}


def load_audio_state(instance_path: str | Path) -> Dict[str, Any]:
    eng = _get_engine(instance_path)
    state = _read_json(_state_path(instance_path), {"updatedAt": _utc_now(), "actions": [], "lastEvent": None})
    if not isinstance(state, dict):
        state = {"updatedAt": _utc_now(), "actions": [], "lastEvent": None}
    persisted = _read_json(_runtime_state_path(instance_path), {"engine": {"active": []}})
    persisted_engine = persisted.get("engine") if isinstance(persisted, dict) and isinstance(persisted.get("engine"), dict) else {}
    persisted_active = persisted_engine.get("active") if isinstance(persisted_engine.get("active"), list) else []
    local_engine = eng.snapshot()
    local_active = local_engine.get("active") if isinstance(local_engine.get("active"), list) else []

    merged: Dict[str, Dict[str, Any]] = {}
    for row in persisted_active:
        if not isinstance(row, dict):
            continue
        pid = int(row.get("pid") or 0) if str(row.get("pid") or "").strip() else 0
        # Keep only live persisted entries; this avoids stale rows from old crashes.
        if pid > 0 and not _pid_alive(pid):
            continue
        key = str(row.get("playbackId") or f"{row.get('cueId')}:{row.get('startedAtMs')}")
        merged[key] = row
    for row in local_active:
        if isinstance(row, dict):
            key = str(row.get("playbackId") or f"{row.get('cueId')}:{row.get('startedAtMs')}")
            merged[key] = row
    for row in eng.orphan_entries():
        if isinstance(row, dict):
            key = str(row.get("playbackId") or f"orphan:{row.get('pid')}")
            merged[key] = row

    state["engine"] = {
        "backend": str(local_engine.get("backend") or persisted_engine.get("backend") or "none"),
        "lastError": str(local_engine.get("lastError") or persisted_engine.get("lastError") or ""),
        "active": list(merged.values()),
    }
    return state


def list_output_devices(instance_path: str | Path, force_refresh: bool = False) -> List[Dict[str, Any]]:
    eng = _get_engine(instance_path)
    return eng.list_devices(force_refresh=force_refresh)


def detect_audio_tooling() -> Dict[str, Any]:
    system = platform.system().lower()
    tools: List[Dict[str, Any]] = []
    notes: List[str] = []

    def _add(name: str, required: bool, purpose: str, install_cmd: str) -> None:
        tools.append(
            {
                "name": name,
                "installed": bool(shutil.which(name)),
                "required": required,
                "purpose": purpose,
                "installCommand": install_cmd,
            }
        )

    if system == "darwin":
        _add("ffplay", True, "Primary playback backend with broad codec support", "brew install ffmpeg")
        _add("SwitchAudioSource", True, "Enumerate and target named macOS output devices", "brew install switchaudio-osx")
        _add("afplay", False, "Fallback playback backend", "Included with macOS")
        notes.append("Speaker targeting on macOS requires SwitchAudioSource for named output discovery.")
        notes.append("macOS routing is global per host; simultaneous different target outputs are not supported.")
    elif system == "linux":
        _add("ffplay", True, "Primary playback backend with broad codec support", "sudo apt-get install -y ffmpeg")
        _add("pactl", True, "Enumerate and target PulseAudio/PipeWire sinks", "sudo apt-get install -y pulseaudio-utils")
        _add("aplay", False, "ALSA fallback playback/device listing", "sudo apt-get install -y alsa-utils")
        notes.append("On Raspberry Pi, install ffmpeg + pulseaudio-utils for reliable speaker targeting.")
    else:
        _add("ffplay", True, "Primary playback backend", "Install ffmpeg for your OS package manager")
        notes.append("Unsupported OS for advanced output enumeration; default output remains available.")

    missing_required = [t["name"] for t in tools if t.get("required") and not t.get("installed")]
    return {
        "platform": system,
        "tools": tools,
        "readyForTargetedOutputs": len(missing_required) == 0,
        "missingRequired": missing_required,
        "notes": notes,
    }


def get_output_environment(instance_path: str | Path, force_refresh: bool = False) -> Dict[str, Any]:
    eng = _get_engine(instance_path)
    return {
        "platform": platform.system().lower(),
        "backend": eng._backend_name(),  # internal backend pick
        "devices": eng.list_devices(force_refresh=force_refresh),
        "tooling": detect_audio_tooling(),
    }


def play_cue(
    instance_path: str | Path,
    cue_id: str,
    *,
    preview: bool = False,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    cue = next((c for c in (cfg.get("cues") or []) if isinstance(c, dict) and str(c.get("id") or "") == cue_id), None)
    if cue is None:
        return {"ok": False, "error": "cue_not_found"}
    cue_play = dict(cue)
    if isinstance(overrides, dict):
        cue_play.update({k: v for k, v in overrides.items() if k})
    eng = _get_engine(instance_path)
    return eng.play(cfg, cue_play, event_name="AUDIO_PREVIEW" if preview else "AUDIO_MANUAL", source="pi.audio", preview=preview)


def preview_asset(instance_path: str | Path, asset_id: str) -> Dict[str, Any]:
    cfg = load_audio_config(instance_path)
    asset = next((a for a in (cfg.get("assets") or []) if isinstance(a, dict) and str(a.get("id") or "") == asset_id), None)
    if asset is None:
        return {"ok": False, "error": "asset_not_found"}
    cue = {
        "id": f"preview_asset_{asset_id}",
        "name": f"Preview {str(asset.get('displayName') or asset_id)}",
        "enabled": True,
        "assetId": asset_id,
        "bus": "sfx",
        "volume": 1.0,
        "loop": False,
        "repeatCount": 1,
        "cooldownMs": 0,
        "maxConcurrent": 1,
        "restartPolicy": "restart",
        "targetOutput": str(cfg.get("settings", {}).get("defaultOutput") or "default"),
        "notes": "temporary preview cue",
    }
    eng = _get_engine(instance_path)
    return eng.play(cfg, cue, event_name="AUDIO_ASSET_PREVIEW", source="pi.audio", preview=True)


def preview_cue(instance_path: str | Path, cue: Dict[str, Any], *, seek_ms: int = 0) -> Dict[str, Any]:
    if not isinstance(cue, dict):
        return {"ok": False, "error": "invalid_cue"}
    cfg = load_audio_config(instance_path)
    normalized = _normalize_cue_row(cue)
    normalized["enabled"] = True
    normalized["_seekMs"] = _to_int(seek_ms, 0, 0, 7_200_000)
    eng = _get_engine(instance_path)
    return eng.play(cfg, normalized, event_name="AUDIO_CUE_PREVIEW", source="pi.audio", preview=True)


def stop_cue(instance_path: str | Path, cue_id: str | None = None, *, preview_only: bool = False) -> Dict[str, Any]:
    eng = _get_engine(instance_path)
    stopped = eng.stop(cue_id=cue_id, preview_only=preview_only)
    return {"ok": True, "stopped": stopped}


def stop_runtime_entry(instance_path: str | Path, *, playback_id: str | None = None, pid: int | None = None) -> Dict[str, Any]:
    eng = _get_engine(instance_path)
    stopped = 0
    if playback_id:
        pb = str(playback_id).strip()
        if pb.startswith("orphan:"):
            try:
                opid = int(pb.split(":", 1)[1])
            except Exception:
                opid = 0
            if opid > 0 and eng.stop_pid(opid):
                stopped += 1
        elif eng.stop_playback(pb):
            stopped += 1
    if pid is not None:
        try:
            p = int(pid)
        except Exception:
            p = 0
        if p > 0 and eng.stop_pid(p):
            stopped += 1
    if stopped <= 0:
        return {"ok": False, "error": "not_found", "stopped": 0}
    return {"ok": True, "stopped": stopped}


def _audio_bus_loop(*, instance_path: str, stop_evt: Event, logger: Callable[[str], None] | None = None) -> None:
    bus = get_bus()
    q = bus.subscribe()
    try:
        while not stop_evt.is_set():
            try:
                ev = q.get(timeout=0.5)
            except Empty:
                continue
            try:
                process_event(instance_path, name=ev.name, source=ev.source, params=ev.params)
            except Exception as exc:
                _worker_log(logger, f"audio bus processing failed: {exc}")
    finally:
        bus.unsubscribe(q)


def ensure_audio_bus_worker(instance_path: str | Path, logger: Callable[[str], None] | None = None) -> None:
    inst = str(Path(instance_path).resolve())
    with _BUS_WORKER_LOCK:
        existing = _BUS_WORKERS.get(inst)
        if isinstance(existing, dict):
            t = existing.get("thread")
            if isinstance(t, Thread) and t.is_alive():
                return
        stop_evt = Event()
        worker = Thread(
            target=_audio_bus_loop,
            kwargs={"instance_path": inst, "stop_evt": stop_evt, "logger": logger},
            daemon=True,
            name=f"audio-bus-{Path(inst).name}",
        )
        _BUS_WORKERS[inst] = {"thread": worker, "stop_evt": stop_evt}
        worker.start()
    _worker_log(logger, f"audio bus worker started instance={inst}")
