"""Accelerometer runtime + calibration API."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from flask import current_app, jsonify

from pinballctl.bridge.state import is_headless_mode, read_state as read_bridge_state, rpc_command as bridge_rpc_command
from pinballctl.app.modules.hardware.api import _build_accelerometer_configs

from . import api_bp


def _mapping_path() -> Path:
    return Path(current_app.instance_path) / "hardware" / "mapping.json"


def _store_dir() -> Path:
    p = Path(current_app.instance_path) / "accelerometer"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _calibration_path() -> Path:
    return _store_dir() / "calibration.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _load_mapping_data() -> Dict[str, Any]:
    raw = _read_json(_mapping_path(), {})
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    if isinstance(raw, dict):
        return raw
    return {}


def _accel_configs() -> List[Dict[str, Any]]:
    return _build_accelerometer_configs(_load_mapping_data())


def _load_calibration() -> Dict[str, Any]:
    raw = _read_json(_calibration_path(), {})
    if not isinstance(raw, dict):
        return {"entries": [], "updatedAt": ""}
    entries = raw.get("entries")
    if not isinstance(entries, list):
        entries = []
    raw["entries"] = [e for e in entries if isinstance(e, dict)]
    raw.setdefault("updatedAt", "")
    return raw


def _query_accel_status(timeout_s: float = 2.5) -> Tuple[Dict[str, Any] | None, str | None]:
    req_id = uuid4().hex
    try:
        payload = bridge_rpc_command({"cmd": "ACCEL_STATUS_QUERY", "reqId": req_id}, match_t="ACCEL_STATUS", timeout_s=timeout_s)
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "no_response"
    if payload.get("ok") is False:
        return None, str(payload.get("reason") or payload.get("error") or "status_error")
    return payload, None


def _sync_accel_config(timeout_s: float = 4.0) -> Tuple[bool, str | None, int]:
    configs = _accel_configs()
    req_id = uuid4().hex
    try:
        resp = bridge_rpc_command({"cmd": "SET_ACCEL_CONFIG", "configs": configs, "reqId": req_id}, match_t="ACCEL_CONFIG", timeout_s=timeout_s)
    except Exception as exc:
        return False, str(exc), len(configs)
    if not isinstance(resp, dict):
        return False, "no_response", len(configs)
    if resp.get("ok") is not True:
        return False, str(resp.get("reason") or resp.get("error") or "apply_failed"), len(configs)
    try:
        applied = int(resp.get("count", 0) or 0)
    except Exception:
        applied = 0
    if configs and applied <= 0:
        return False, "applied_zero_configs", len(configs)
    return True, None, len(configs)


def _angles_from_vector(x: float, y: float, z: float) -> Tuple[float, float]:
    # Pitch/roll estimate in degrees from gravity vector.
    pitch = math.degrees(math.atan2(x, math.sqrt((y * y) + (z * z))))
    roll = math.degrees(math.atan2(y, z if abs(z) > 1e-6 else (1e-6 if y >= 0 else -1e-6)))
    return pitch, roll


def _enrich_status(status: Dict[str, Any], configs: List[Dict[str, Any]]) -> Dict[str, Any]:
    sensors = status.get("sensors") if isinstance(status, dict) else []
    if not isinstance(sensors, list):
        sensors = []
    by_source = {str(c.get("source") or ""): c for c in configs if isinstance(c, dict)}
    enriched: List[Dict[str, Any]] = []
    level_warn = False
    total_tilt = 0
    total_lift = 0
    max_abs_pitch = 0.0
    max_abs_roll = 0.0
    for s in sensors:
        if not isinstance(s, dict):
            continue
        source = str(s.get("source") or "").strip()
        cfg = by_source.get(source, {})
        try:
            ax = float(s.get("ax", 0.0))
            ay = float(s.get("ay", 0.0))
            az = float(s.get("az", 1.0))
        except Exception:
            ax, ay, az = 0.0, 0.0, 1.0
        try:
            bx = float(s.get("baselineX", cfg.get("baselineX", 0.0)))
            by = float(s.get("baselineY", cfg.get("baselineY", 0.0)))
            bz = float(s.get("baselineZ", cfg.get("baselineZ", 1.0)))
        except Exception:
            bx, by, bz = 0.0, 0.0, 1.0
        pitch, roll = _angles_from_vector(ax, ay, az)
        base_pitch, base_roll = _angles_from_vector(bx, by, bz)
        level_pitch = pitch - base_pitch
        level_roll = roll - base_roll
        max_abs_pitch = max(max_abs_pitch, abs(level_pitch))
        max_abs_roll = max(max_abs_roll, abs(level_roll))
        if abs(level_pitch) > 2.5 or abs(level_roll) > 2.5:
            level_warn = True
        tilt_count = int(s.get("tiltCount", 0) or 0)
        lift_count = int(s.get("liftCount", 0) or 0)
        total_tilt += tilt_count
        total_lift += lift_count
        item = dict(s)
        item["componentId"] = str(cfg.get("componentId") or "")
        item["levelPitchDeg"] = round(level_pitch, 2)
        item["levelRollDeg"] = round(level_roll, 2)
        item["isLevel"] = abs(level_pitch) <= 2.5 and abs(level_roll) <= 2.5
        enriched.append(item)
    return {
        "sensors": enriched,
        "summary": {
            "sensorCount": len(enriched),
            "levelWarning": level_warn,
            "maxAbsPitchDeg": round(max_abs_pitch, 2),
            "maxAbsRollDeg": round(max_abs_roll, 2),
            "tiltCount": total_tilt,
            "liftCount": total_lift,
        },
    }


@api_bp.get("/runtime")
def accel_runtime():
    global _last_auto_bootstrap_attempt
    bridge = read_bridge_state() or {}
    connected = bool(bridge.get("connected"))
    headless = bool(is_headless_mode())
    configs = _accel_configs()
    calibration = _load_calibration()
    payload: Dict[str, Any] = {
        "ok": True,
        "bridge": {
            "connected": connected,
            "headless": headless,
            "port": bridge.get("port"),
        },
        "configs": configs,
        "calibration": calibration,
        "status": None,
        "error": "",
    }
    if not connected:
        return jsonify(payload)
    status, err = _query_accel_status()
    if err:
        payload["error"] = err
        return jsonify(payload)
    # First-use bootstrap: if ESP has no accel runtime yet but mapping contains
    # valid accelerometer configs, push defaults automatically.
    try:
      configured = int(status.get("configured", 0) or 0) if isinstance(status, dict) else 0
    except Exception:
      configured = 0
    now_ts = datetime.now(timezone.utc).timestamp()
    if configured <= 0 and configs and (now_ts - _last_auto_bootstrap_attempt) >= _AUTO_BOOTSTRAP_COOLDOWN_S:
        _last_auto_bootstrap_attempt = now_ts
        synced, sync_err, _count = _sync_accel_config(timeout_s=4.0)
        if synced:
            status2, err2 = _query_accel_status(timeout_s=2.5)
            if not err2 and isinstance(status2, dict):
                status = status2
                payload["autoBootstrapped"] = True
        elif sync_err:
            payload["error"] = sync_err
    payload["status"] = status
    payload["derived"] = _enrich_status(status or {}, configs)
    return jsonify(payload)


@api_bp.post("/calibrate/save")
def accel_calibrate_save():
    status, err = _query_accel_status(timeout_s=3.0)
    if err:
        return jsonify({"ok": False, "error": err}), 409
    configs = _accel_configs()
    by_source = {str(c.get("source") or ""): c for c in configs if isinstance(c, dict)}
    sensors = status.get("sensors") if isinstance(status, dict) else []
    if not isinstance(sensors, list):
        sensors = []
    saved_at = datetime.now(timezone.utc).isoformat()
    entries: List[Dict[str, Any]] = []
    for sensor in sensors:
        if not isinstance(sensor, dict):
            continue
        source = str(sensor.get("source") or "").strip()
        if not source:
            continue
        cfg = by_source.get(source, {})
        try:
            bx = float(sensor.get("ax", 0.0))
            by = float(sensor.get("ay", 0.0))
            bz = float(sensor.get("az", 1.0))
        except Exception:
            continue
        mag = math.sqrt((bx * bx) + (by * by) + (bz * bz))
        if mag <= 0.001:
            continue
        entries.append(
            {
                "componentId": str(cfg.get("componentId") or ""),
                "source": source,
                "baselineX": bx / mag,
                "baselineY": by / mag,
                "baselineZ": bz / mag,
                "savedAt": saved_at,
            }
        )
    _write_json(_calibration_path(), {"updatedAt": saved_at, "entries": entries})
    ok, sync_err, count = _sync_accel_config()
    if not ok:
        return jsonify({"ok": False, "error": sync_err or "sync_failed", "saved": len(entries), "configCount": count}), 409
    return jsonify({"ok": True, "saved": len(entries), "configCount": count, "updatedAt": saved_at})


@api_bp.post("/sync")
def accel_sync():
    ok, err, count = _sync_accel_config()
    if not ok:
        return jsonify({"ok": False, "error": err or "sync_failed", "configCount": count}), 409
    return jsonify({"ok": True, "configCount": count})
_AUTO_BOOTSTRAP_COOLDOWN_S = 10.0
_last_auto_bootstrap_attempt = 0.0
