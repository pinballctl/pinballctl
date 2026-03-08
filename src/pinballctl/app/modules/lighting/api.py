"""Lighting scenes API: fixtures, scene authoring, compile, sync."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from flask import current_app, jsonify, request

from pinballctl.app.sync_state import update_sync_state
from pinballctl.bridge.state import enqueue_command, is_headless_mode, queue_blob_put, read_state as read_bridge_state
from pinballctl.lighting.patterns import list_pattern_specs, merge_params_with_defaults, normalize_pattern_name
from pinballctl.lighting.runtime import play_scene_rpc, scene_status, stop_scene_rpc
from pinballctl.ops.lighting_blob import build_lighting_pd_bytes, compile_lighting_timeline, compile_lighting_timeline_data

from . import api_bp


_MARKER_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MARKER_SHAPES = {
    "circle",
    "square",
    "triangle",
    "hexagon",
    "star",
    "arrow",
    "rectangle",
    "pill",
}


def _store_dir() -> Path:
    p = Path(current_app.instance_path) / "lighting"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _lighting_json_path() -> Path:
    return _store_dir() / "lighting.json"


def _lighting_pd_path() -> Path:
    return _store_dir() / "lighting.pd"


def _lighting_meta_path() -> Path:
    return _store_dir() / "lighting_meta.json"


def _lighting_compiled_path() -> Path:
    return _store_dir() / "lighting.compiled.json"


def _mapping_path() -> Path:
    return Path(current_app.instance_path) / "hardware" / "mapping.json"


def _layout_path() -> Path:
    return Path(current_app.instance_path) / "playfield" / "layout.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _default_config() -> Dict[str, Any]:
    return {
        "_version": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "fixtures": {},
        "scenes": [],
        "ui": {
            "showLayoutGuides": True,
        },
    }


def _load_config() -> Dict[str, Any]:
    data = _read_json(_lighting_json_path(), _default_config())
    if not isinstance(data, dict):
        data = _default_config()
    data.setdefault("_version", 1)
    data.setdefault("updatedAt", datetime.now(timezone.utc).isoformat())
    data.setdefault("fixtures", {})
    data.setdefault("scenes", [])
    data.setdefault("ui", {"showLayoutGuides": True})
    if not isinstance(data["fixtures"], dict):
        data["fixtures"] = {}
    if not isinstance(data["scenes"], list):
        data["scenes"] = []
    if not isinstance(data["ui"], dict):
        data["ui"] = {"showLayoutGuides": True}
    data["ui"]["showLayoutGuides"] = bool(data["ui"].get("showLayoutGuides", True))
    try:
        data = _remap_config_ids(data, _load_mapping_data())
    except Exception:
        pass
    return data


def _normalize_duration(duration: Any) -> Dict[str, Any]:
    if not isinstance(duration, dict):
        return {"value": 5, "unit": "seconds"}
    value = duration.get("value", 5)
    unit = str(duration.get("unit", "seconds")).strip().lower()
    if unit not in ("seconds", "minutes", "frames"):
        unit = "seconds"
    try:
        value = float(value)
    except Exception:
        value = 5
    if unit == "frames":
        value = max(1, int(round(value)))
    elif value < 0:
        value = 0
    return {"value": value, "unit": unit}


def _clamp01(value: Any, default: float = 1.0) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return float(v)


def _normalize_marker_shape(value: Any) -> str:
    s = str(value or "circle").strip().lower()
    return s if s in _MARKER_SHAPES else "circle"


def _normalize_marker_size_px(value: Any, default: float) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    if v < 4:
        return 4.0
    if v > 200:
        return 200.0
    return float(v)


def _normalize_marker_rotation_deg(value: Any) -> float:
    try:
        v = float(value)
    except Exception:
        v = 0.0
    if v < -180:
        return -180.0
    if v > 180:
        return 180.0
    return float(v)


def _normalize_point_visuals(raw: Any, default_size_px: float = 8.0) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for row in raw:
        if not isinstance(row, dict):
            out.append({})
            continue
        out.append(
            {
                "shape": _normalize_marker_shape(row.get("shape")),
                "sizePx": _normalize_marker_size_px(row.get("sizePx"), default_size_px),
                "rotationDeg": _normalize_marker_rotation_deg(row.get("rotationDeg")),
            }
        )
    return out


def _normalize_scene(scene: Dict[str, Any], idx: int) -> Dict[str, Any]:
    sid = str(scene.get("id") or f"scene_{idx+1}")
    title = str(scene.get("title") or sid).strip()
    if not title:
        title = sid
    pattern = normalize_pattern_name(scene.get("pattern") or "solid")
    end_behavior = str(scene.get("endBehavior") or "stop").strip().lower()
    if end_behavior not in ("stop", "repeat", "bounce"):
        end_behavior = "stop"
    blend_mode = str(scene.get("blendMode") or "overlay").strip().lower()
    if blend_mode not in ("overlay", "pause_lower", "stop_lower"):
        blend_mode = "overlay"
    cast_mask = str(scene.get("castMask") or "cast").strip().lower()
    if cast_mask not in ("cast", "all"):
        cast_mask = "cast"
    try:
        priority = int(scene.get("priority", 0))
    except Exception:
        priority = 0
    if priority < -100:
        priority = -100
    if priority > 100:
        priority = 100
    cast = [str(x) for x in (scene.get("cast") or []) if isinstance(x, str) and x.strip()]
    params = merge_params_with_defaults(pattern, scene.get("params") if isinstance(scene.get("params"), dict) else {})
    if "brightness" in params:
        params["brightness"] = _clamp01(params.get("brightness"), default=1.0)
    if pattern == "custom":
        tween = str(params.get("tween") or "hold").strip().lower()
        if tween not in ("hold", "linear"):
            tween = "hold"
        params["tween"] = tween
    timeline_raw = scene.get("timeline") if isinstance(scene.get("timeline"), list) else []
    markers_raw = scene.get("markers") if isinstance(scene.get("markers"), list) else []
    timeline: List[Dict[str, Any]] = []
    markers: List[Dict[str, Any]] = []
    for frame in timeline_raw:
        if not isinstance(frame, dict):
            continue
        try:
            at_ms = int(frame.get("atMs", 0))
        except Exception:
            at_ms = 0
        if at_ms < 0:
            at_ms = 0
        entry = {
            "atMs": at_ms,
            "fixtureId": str(frame.get("fixtureId") or "").strip(),
            "pixelIndex": None,
            "color": str(frame.get("color") or "#ffffff"),
            "intensity": float(frame.get("intensity", 1.0)) if isinstance(frame.get("intensity"), (int, float)) else 1.0,
            "brightness": _clamp01(frame.get("brightness", 1.0), default=1.0),
            "tween": "hold",
        }
        tween = str(frame.get("tween") or "hold").strip().lower()
        if tween in ("hold", "linear"):
            entry["tween"] = tween
        px_idx = frame.get("pixelIndex")
        if isinstance(px_idx, (int, float)):
            px_idx_int = int(px_idx)
            if px_idx_int >= 0:
                entry["pixelIndex"] = px_idx_int
        timeline.append(entry)
    seen_tags: set[str] = set()
    seen_times: set[int] = set()
    for marker in markers_raw:
        if not isinstance(marker, dict):
            continue
        try:
            at_ms = int(marker.get("atMs", 0))
        except Exception:
            at_ms = 0
        if at_ms < 0:
            at_ms = 0
        tag = str(marker.get("tag") or "").strip().lower()
        if not tag or not _MARKER_TAG_RE.match(tag):
            continue
        if tag in seen_tags:
            continue
        if at_ms in seen_times:
            continue
        seen_tags.add(tag)
        seen_times.add(at_ms)
        markers.append({"atMs": at_ms, "tag": tag})
    timeline.sort(key=lambda x: x["atMs"])
    markers.sort(key=lambda x: x["atMs"])
    return {
        "id": sid,
        "title": title,
        "duration": _normalize_duration(scene.get("duration")),
        "endBehavior": end_behavior,
        "priority": priority,
        "blendMode": blend_mode,
        "castMask": cast_mask,
        "pattern": pattern,
        "cast": cast,
        "params": params,
        "timeline": timeline,
        "markers": markers,
    }


def _normalize_fixtures_map(fixtures: Any) -> Dict[str, Dict[str, Any]]:
    def norm_color(raw: Any) -> str:
        s = str(raw or "").strip()
        if len(s) == 7 and s.startswith("#"):
            hex_part = s[1:]
            if all(c in "0123456789abcdefABCDEF" for c in hex_part):
                return f"#{hex_part.lower()}"
        return "#60a5fa"

    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(fixtures, dict):
        return out
    for fid, cfg in fixtures.items():
        if not isinstance(fid, str) or not isinstance(cfg, dict):
            continue
        layout_mode = str(cfg.get("layoutMode") or "line").strip().lower()
        if layout_mode not in ("line", "manual"):
            layout_mode = "line"
        pixel_count = cfg.get("pixelCount")
        if isinstance(pixel_count, (int, float)):
            pixel_count = int(pixel_count)
        else:
            pixel_count = None
        if pixel_count is not None and pixel_count < 1:
            pixel_count = 1
        length_px = cfg.get("lengthPx")
        if isinstance(length_px, (int, float)):
            length_px = float(length_px)
            if length_px < 1:
                length_px = 1.0
        else:
            length_px = None
        line = cfg.get("line") if isinstance(cfg.get("line"), dict) else {}
        points = cfg.get("points") if isinstance(cfg.get("points"), list) else []
        default_marker_size = 8.0 if (pixel_count is None or pixel_count > 1) else 14.0
        point_visuals = _normalize_point_visuals(cfg.get("pointVisuals"), default_size_px=default_marker_size)
        norm_points: List[Dict[str, float]] = []
        for p in points:
            if not isinstance(p, dict):
                continue
            try:
                x = float(p.get("x", 0.5))
                y = float(p.get("y", 0.5))
            except Exception:
                continue
            norm_points.append({"x": x, "y": y})
        out[fid] = {
            "pixelCount": pixel_count,
            "fixedColor": norm_color(cfg.get("fixedColor")),
            "layoutMode": layout_mode,
            "markerShape": _normalize_marker_shape(cfg.get("markerShape")),
            "markerSizePx": _normalize_marker_size_px(cfg.get("markerSizePx"), default_marker_size),
            "markerRotationDeg": _normalize_marker_rotation_deg(cfg.get("markerRotationDeg")),
            "lengthPx": length_px,
            "line": {
                "x1": float(line.get("x1", 0.4)) if isinstance(line.get("x1"), (int, float)) else 0.4,
                "y1": float(line.get("y1", 0.5)) if isinstance(line.get("y1"), (int, float)) else 0.5,
                "x2": float(line.get("x2", 0.6)) if isinstance(line.get("x2"), (int, float)) else 0.6,
                "y2": float(line.get("y2", 0.5)) if isinstance(line.get("y2"), (int, float)) else 0.5,
            },
            "points": norm_points,
            "pointVisuals": point_visuals,
        }
    return out


def _extract_mapping_data(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw.get("data") or {}
    if isinstance(raw, dict):
        return raw
    return {}


def _load_mapping_data() -> Dict[str, Any]:
    return _extract_mapping_data(_read_json(_mapping_path(), {}))


def _uid_tail(uid: str) -> str:
    parts = str(uid or "").split("__")
    if len(parts) < 4:
        return str(uid or "")
    return "__".join(parts[-3:])


def _canonical_id_by_tail(mapping: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not isinstance(mapping, dict):
        return out
    for raw_id in mapping.keys():
        if not isinstance(raw_id, str):
            continue
        tail = _uid_tail(raw_id)
        if tail and tail not in out:
            out[tail] = raw_id
    return out


def _canonicalize_id(raw_id: Any, by_tail: Dict[str, str]) -> str:
    sid = str(raw_id or "").strip()
    if not sid:
        return ""
    return by_tail.get(_uid_tail(sid), sid)


def _remap_config_ids(cfg: Dict[str, Any], mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Remap lighting ids to current controller ids using BOARD__TYPE__CHAN tails."""
    if not isinstance(cfg, dict):
        return cfg
    by_tail = _canonical_id_by_tail(mapping)
    if not by_tail:
        return cfg

    fixtures = cfg.get("fixtures")
    if isinstance(fixtures, dict):
        remapped_fixtures: Dict[str, Any] = {}
        for raw_id, row in fixtures.items():
            if not isinstance(raw_id, str):
                continue
            dst_id = _canonicalize_id(raw_id, by_tail)
            if dst_id in remapped_fixtures:
                if isinstance(remapped_fixtures[dst_id], dict) and isinstance(row, dict):
                    merged = dict(remapped_fixtures[dst_id])
                    for k, v in row.items():
                        if k not in merged:
                            merged[k] = v
                    remapped_fixtures[dst_id] = merged
                continue
            remapped_fixtures[dst_id] = row
        cfg["fixtures"] = remapped_fixtures

    scenes = cfg.get("scenes")
    if isinstance(scenes, list):
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            cast = scene.get("cast")
            if isinstance(cast, list):
                seen: set[str] = set()
                out_cast: List[str] = []
                for item in cast:
                    sid = _canonicalize_id(item, by_tail)
                    if not sid or sid in seen:
                        continue
                    seen.add(sid)
                    out_cast.append(sid)
                scene["cast"] = out_cast
            timeline = scene.get("timeline")
            if isinstance(timeline, list):
                for frame in timeline:
                    if isinstance(frame, dict) and "fixtureId" in frame:
                        frame["fixtureId"] = _canonicalize_id(frame.get("fixtureId"), by_tail)
    return cfg


def _save_mapping_data(data: Dict[str, Any]) -> None:
    payload = {
        "_version": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    _write_json(_mapping_path(), payload)


def _load_playfield_layout() -> Dict[str, Any]:
    data = _read_json(_layout_path(), {})
    if not isinstance(data, dict):
        return {}
    return data


def _playfield_layout_elements(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = layout.get("elements") if isinstance(layout.get("elements"), list) else []
    out: List[Dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        out.append(
            {
                "id": str(row.get("id") or "").strip(),
                "type": str(row.get("type") or "").strip(),
                "icon": str(row.get("icon") or "").strip(),
                "color": str(row.get("color") or "").strip(),
                "size": str(row.get("size") or "m").strip().lower(),
                "scale": float(row.get("scale")) if isinstance(row.get("scale"), (int, float)) else 1.0,
                "rotation": float(row.get("rotation")) if isinstance(row.get("rotation"), (int, float)) else 0.0,
                "nx": float(row.get("nx")) if isinstance(row.get("nx"), (int, float)) else None,
                "ny": float(row.get("ny")) if isinstance(row.get("ny"), (int, float)) else None,
                "x": float(row.get("x")) if isinstance(row.get("x"), (int, float)) else None,
                "y": float(row.get("y")) if isinstance(row.get("y"), (int, float)) else None,
            }
        )
    return out


def _playfield_options(layout: Dict[str, Any]) -> Dict[str, Any]:
    opts = layout.get("options") if isinstance(layout.get("options"), dict) else {}
    width = opts.get("width", 700)
    height = opts.get("height", 1400)
    if not isinstance(width, (int, float)) or width <= 0:
        width = 700
    if not isinstance(height, (int, float)) or height <= 0:
        height = 1400
    out: Dict[str, Any] = {
        "width": float(width),
        "height": float(height),
        "ratio": float(width) / float(height),
    }
    playfield = layout.get("playfield") if isinstance(layout.get("playfield"), dict) else {}
    name = str(playfield.get("name") or "").strip()
    if name:
        p = Path(current_app.instance_path) / "playfield" / name
        if p.exists() and p.is_file():
            stamp = str(playfield.get("updatedAt") or "").strip() or str(int(p.stat().st_mtime))
            safe_stamp = re.sub(r"[^0-9A-Za-zT:_\\-\\.]+", "", stamp)
            out["playfieldImageUrl"] = f"/api/playfield/image?v={safe_stamp}"
            fit = str(playfield.get("fit") or "").strip().lower()
            pos = str(playfield.get("position") or "").strip().lower()
            out["playfieldFit"] = fit if fit in ("cover", "contain", "exact") else "cover"
            out["playfieldPosition"] = pos if pos in (
                "center", "top", "bottom", "left", "right",
                "top left", "top right", "bottom left", "bottom right",
            ) else "center"
            try:
                opacity = float(playfield.get("opacity", 1.0))
            except Exception:
                opacity = 1.0
            if opacity < 0:
                opacity = 0.0
            if opacity > 1:
                opacity = 1.0
            out["playfieldOpacity"] = float(opacity)
    return out


def _fixture_type_from_function(fn: str) -> str:
    f = (fn or "").strip().lower()
    if f == "rgb strip":
        return "rgb_strip"
    if f == "rgb led":
        return "rgb_led"
    return "led"


def _resolve_fixtures(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    try:
        mapping = _load_mapping_data()
    except Exception:
        mapping = {}
    layout = _load_playfield_layout()
    fixture_cfg = config.get("fixtures") if isinstance(config.get("fixtures"), dict) else {}

    emu_by_hardware: Dict[str, Dict[str, Any]] = {}
    emu_by_tail: Dict[str, Dict[str, Any]] = {}
    for el in layout.get("elements") if isinstance(layout.get("elements"), list) else []:
        if not isinstance(el, dict):
            continue
        hw = el.get("hardwareId")
        if isinstance(hw, str) and hw:
            emu_by_hardware[hw] = el
            tail = _uid_tail(hw)
            if tail and tail not in emu_by_tail:
                emu_by_tail[tail] = el

    fixtures: List[Dict[str, Any]] = []
    for fid, row in mapping.items():
        if not isinstance(row, dict):
            continue
        function = str(row.get("function") or "").strip()
        if function not in ("LED", "RGB Strip", "RGB LED"):
            continue
        user = fixture_cfg.get(fid) if isinstance(fixture_cfg.get(fid), dict) else {}
        pixel_count = row.get("pixelCount")
        if isinstance(pixel_count, (int, float)):
            pixel_count = int(pixel_count)
        elif isinstance(user.get("pixelCount"), (int, float)):
            pixel_count = int(user.get("pixelCount"))
        else:
            pixel_count = 1
        if pixel_count < 1:
            pixel_count = 1

        layout_mode = str(user.get("layoutMode") or "line").strip().lower()
        if layout_mode not in ("line", "manual"):
            layout_mode = "line"
        fixed_color = str(user.get("fixedColor") or "#60a5fa").strip()
        if not (len(fixed_color) == 7 and fixed_color.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in fixed_color[1:])):
            fixed_color = "#60a5fa"
        else:
            fixed_color = fixed_color.lower()

        emu = emu_by_hardware.get(fid) or emu_by_tail.get(_uid_tail(fid), {}) or {}
        ex = emu.get("nx")
        ey = emu.get("ny")
        if not isinstance(ex, (int, float)):
            ex = 0.5
        if not isinstance(ey, (int, float)):
            ey = 0.5
        default_line = {"x1": max(0.0, ex - 0.12), "y1": ey, "x2": min(1.0, ex + 0.12), "y2": ey}
        line = user.get("line") if isinstance(user.get("line"), dict) else default_line
        points = user.get("points") if isinstance(user.get("points"), list) else []
        default_marker_size = 8.0 if _fixture_type_from_function(function) == "rgb_strip" else 14.0
        point_visuals = _normalize_point_visuals(user.get("pointVisuals"), default_size_px=default_marker_size)
        length_px = user.get("lengthPx")
        if isinstance(length_px, (int, float)):
            length_px = float(length_px)
            if length_px < 1:
                length_px = 1.0
        else:
            length_px = None

        fixtures.append(
            {
                "id": fid,
                "title": str(row.get("friendly") or fid),
                "function": function,
                "type": _fixture_type_from_function(function),
                "pixelCount": pixel_count,
                "fixedColor": fixed_color,
                "layoutMode": layout_mode,
                "markerShape": _normalize_marker_shape(user.get("markerShape")),
                "markerSizePx": _normalize_marker_size_px(user.get("markerSizePx"), default_marker_size),
                "markerRotationDeg": _normalize_marker_rotation_deg(user.get("markerRotationDeg")),
                "lengthPx": length_px,
                "line": {
                    "x1": float(line.get("x1", default_line["x1"])) if isinstance(line.get("x1"), (int, float)) else default_line["x1"],
                    "y1": float(line.get("y1", default_line["y1"])) if isinstance(line.get("y1"), (int, float)) else default_line["y1"],
                    "x2": float(line.get("x2", default_line["x2"])) if isinstance(line.get("x2"), (int, float)) else default_line["x2"],
                    "y2": float(line.get("y2", default_line["y2"])) if isinstance(line.get("y2"), (int, float)) else default_line["y2"],
                },
                "points": points,
                "pointVisuals": point_visuals,
            }
        )
    fixtures.sort(key=lambda f: (f["type"], f["title"].lower()))
    return fixtures


def _normalize_config_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_fixtures = payload.get("fixtures")
    raw_scenes = payload.get("scenes")
    raw_ui = payload.get("ui")
    ui: Dict[str, Any] = {
        "showLayoutGuides": True,
    }
    if isinstance(raw_ui, dict):
        ui["showLayoutGuides"] = bool(raw_ui.get("showLayoutGuides", True))
    scenes: List[Dict[str, Any]] = []
    if isinstance(raw_scenes, list):
        for idx, scene in enumerate(raw_scenes):
            if isinstance(scene, dict):
                scenes.append(_normalize_scene(scene, idx))
    out = {
        "_version": 1,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "fixtures": _normalize_fixtures_map(raw_fixtures),
        "scenes": scenes,
        "ui": ui,
    }
    fixtures_out = out["fixtures"] if isinstance(out.get("fixtures"), dict) else {}

    # Materialize fixture defaults for all mapped lighting-capable hardware rows so
    # compiler/export has a complete fixture universe (not only user-overridden rows).
    try:
        mapping = _load_mapping_data()
    except Exception:
        mapping = {}
    lighting_functions = {"LED", "RGB Strip", "RGB LED"}
    allowed_fixture_ids: set[str] = set()
    if isinstance(mapping, dict):
        for fid, row in mapping.items():
            if not isinstance(fid, str) or not isinstance(row, dict):
                continue
            function = str(row.get("function") or "").strip()
            if function in lighting_functions:
                allowed_fixture_ids.add(fid)

        # Drop persisted fixture rows for non-lighting hardware IDs.
        for fid in list(fixtures_out.keys()):
            if fid not in allowed_fixture_ids:
                fixtures_out.pop(fid, None)

        ids = sorted(allowed_fixture_ids)
        total = max(1, len(ids))
        for idx, fid in enumerate(ids):
            if fid in fixtures_out:
                continue
            row = mapping.get(fid) if isinstance(mapping.get(fid), dict) else {}
            function = str(row.get("function") or "").strip()
            if function not in lighting_functions:
                continue
            ftype = _fixture_type_from_function(function)
            pixel_count = 1
            if ftype == "rgb_strip":
                p = row.get("pixelCount")
                if isinstance(p, (int, float)) and int(p) > 0:
                    pixel_count = int(p)
            y = (idx + 1) / (total + 1)
            fixtures_out[fid] = {
                "pixelCount": pixel_count,
                "fixedColor": "#60a5fa",
                "layoutMode": "line",
                "markerShape": "circle",
                "markerSizePx": 8.0 if pixel_count > 1 else 14.0,
                "markerRotationDeg": 0.0,
                "line": {
                    "x1": 0.10,
                    "y1": y,
                    "x2": 0.40 if pixel_count > 1 else 0.10,
                    "y2": y,
                },
                "points": [],
                "pointVisuals": [],
            }

    # Ensure scene casts always have a backing fixture record (fallback if unknown).
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for fid in scene.get("cast", []) if isinstance(scene.get("cast"), list) else []:
            if not isinstance(fid, str) or not fid.strip() or fid in fixtures_out:
                continue
            fixtures_out[fid] = {
                "pixelCount": 1,
                "fixedColor": "#60a5fa",
                "layoutMode": "line",
                "markerShape": "circle",
                "markerSizePx": 14.0,
                "markerRotationDeg": 0.0,
                "line": {"x1": 0.10, "y1": 0.50, "x2": 0.10, "y2": 0.50},
                "points": [],
                "pointVisuals": [],
            }

    out["fixtures"] = fixtures_out
    out = _remap_config_ids(out, mapping)
    return out


def _persist_config(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = _normalize_config_payload(payload)
    _write_json(_lighting_json_path(), out)
    return out


def _write_lighting_meta(blob: bytes) -> Dict[str, Any]:
    sha = hashlib.sha256(blob).hexdigest()
    meta = {
        "sha256": sha,
        "size": len(blob),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(_lighting_meta_path(), meta)
    return meta


def _compile_lighting_outputs() -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Compile and persist both inspectable timeline JSON and lighting.pd."""
    compiled = compile_lighting_timeline(_lighting_json_path())
    _write_json(_lighting_compiled_path(), compiled)
    blob = build_lighting_pd_bytes(_lighting_json_path())
    _lighting_pd_path().write_bytes(blob)
    meta = _write_lighting_meta(blob)
    return compiled, meta


@api_bp.get("/state")
def api_lighting_state():
    cfg = _load_config()
    layout = _load_playfield_layout()
    fixtures = _resolve_fixtures(cfg)
    return jsonify(
        {
            "ok": True,
            "config": cfg,
            "fixtures": fixtures,
            "playfield": _playfield_options(layout),
            "layoutElements": _playfield_layout_elements(layout),
        }
    )


@api_bp.get("/patterns")
def api_lighting_patterns():
    return jsonify({"ok": True, "patterns": list_pattern_specs()})


@api_bp.post("/save")
def api_lighting_save():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400
    cfg = _persist_config(body)

    # Mirror physical truth for RGB strip pixel count into hardware mapping.
    mapping = _load_mapping_data()
    changed = False
    for fid, fcfg in cfg.get("fixtures", {}).items():
        row = mapping.get(fid)
        if not isinstance(row, dict):
            continue
        if str(row.get("function") or "").strip() != "RGB Strip":
            continue
        pcount = fcfg.get("pixelCount")
        if isinstance(pcount, (int, float)):
            pcount = int(pcount)
            if pcount > 0 and row.get("pixelCount") != pcount:
                row["pixelCount"] = pcount
                changed = True
    if changed:
        _save_mapping_data(mapping)

    try:
        compiled, meta = _compile_lighting_outputs()
    except Exception as exc:
        current_app.logger.exception("Failed to compile lighting.pd")
        return jsonify({"ok": False, "error": "compile_failed", "detail": str(exc)}), 500

    return jsonify(
        {
            "ok": True,
            "config": cfg,
            "meta": meta,
            "compiledPath": str(_lighting_compiled_path()),
            "compiled": {"schema": compiled.get("schema"), "sceneCount": len(compiled.get("scenes", []))},
        }
    )


@api_bp.post("/compile")
def api_lighting_compile():
    cfg = _load_config()
    try:
        compiled, meta = _compile_lighting_outputs()
    except Exception as exc:
        current_app.logger.exception("Failed to compile lighting.pd")
        return jsonify({"ok": False, "error": "compile_failed", "detail": str(exc)}), 500
    return jsonify(
        {
            "ok": True,
            "meta": meta,
            "sceneCount": len(cfg.get("scenes", [])),
            "compiledPath": str(_lighting_compiled_path()),
            "compiled": {"schema": compiled.get("schema"), "sceneCount": len(compiled.get("scenes", []))},
        }
    )


@api_bp.get("/compiled")
def api_lighting_compiled():
    compiled = _read_json(_lighting_compiled_path(), None)
    if not isinstance(compiled, dict):
        return jsonify({"ok": False, "error": "compiled_not_found"}), 404
    return jsonify({"ok": True, "compiled": compiled})


@api_bp.post("/preview/frames")
def api_lighting_preview_frames():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"ok": False, "error": "invalid_payload"}), 400
    scene_id = str(body.get("sceneId") or "").strip()
    if not scene_id:
        return jsonify({"ok": False, "error": "scene_required"}), 400

    cfg_raw = body.get("config")
    cfg = _normalize_config_payload(cfg_raw) if isinstance(cfg_raw, dict) else _normalize_config_payload(_load_config())
    try:
        compiled = compile_lighting_timeline_data(cfg)
    except Exception as exc:
        current_app.logger.exception("Failed to compile preview frames")
        return jsonify({"ok": False, "error": "compile_failed", "detail": str(exc)}), 500

    scene = None
    for row in compiled.get("scenes", []):
        if isinstance(row, dict) and str(row.get("id") or "") == scene_id:
            scene = row
            break
    if not isinstance(scene, dict):
        return jsonify({"ok": False, "error": "scene_not_found"}), 404

    return jsonify(
        {
            "ok": True,
            "preview": {
                "schema": compiled.get("schema"),
                "builtAt": compiled.get("builtAt"),
                "fixtures": compiled.get("fixtures") if isinstance(compiled.get("fixtures"), list) else [],
                "scene": scene,
            },
        }
    )


@api_bp.post("/sync")
def api_lighting_sync():
    st = read_bridge_state()
    if not st.get("connected") or not st.get("port"):
        return jsonify(
            {
                "ok": False,
                "error": "bridge_not_connected",
                "bridge": {"connected": st.get("connected"), "port": st.get("port")},
            }
        ), 409
    # Always compile before sync so ESP receives the latest timeline payload
    # shape produced by the current PI compiler/runtime.
    try:
        _compile_lighting_outputs()
    except Exception as exc:
        return jsonify({"ok": False, "error": "compile_failed", "detail": str(exc)}), 500
    # Preflight LittleFS capacity: upload writes to .upload first, then renames.
    # If free bytes are obviously too low, fail early with a clear message.
    try:
        pd_size = int(_lighting_pd_path().stat().st_size)
    except Exception:
        pd_size = 0
    fs_status = st.get("fs_status") if isinstance(st, dict) else {}
    if isinstance(fs_status, dict) and bool(fs_status.get("mounted")):
        try:
            free_bytes = int(fs_status.get("free", 0) or 0)
        except Exception:
            free_bytes = 0
        # Small safety margin for filesystem metadata overhead.
        required_bytes = max(0, pd_size) + 32768
        if free_bytes > 0 and required_bytes > 0 and free_bytes < required_bytes:
            return jsonify(
                {
                    "ok": False,
                    "error": "insufficient_fs_space",
                    "detail": "Not enough ESP LittleFS free space for lighting upload.",
                    "fileBytes": pd_size,
                    "freeBytes": free_bytes,
                    "requiredBytes": required_bytes,
                }
            ), 409
    enqueue_error: Exception | None = None
    for attempt in range(3):
        try:
            queue_blob_put("lighting", str(_lighting_pd_path()), "/cfg/lighting.pd")
            enqueue_error = None
            break
        except Exception as exc:
            enqueue_error = exc
            if attempt < 2:
                time.sleep(0.15)
    if enqueue_error is not None:
        return jsonify({"ok": False, "error": "bridge_enqueue_failed", "detail": str(enqueue_error)}), 503
    return jsonify({"ok": True, "queued": True, "path": "/cfg/lighting.pd"})


@api_bp.get("/sync/status")
def api_lighting_sync_status():
    st = read_bridge_state()
    status = st.get("blob_status") or {}
    blob_at = st.get("blob_at")
    if (
        isinstance(status, dict)
        and status.get("state") == "begin"
        and status.get("blobType") == "lighting"
        and isinstance(blob_at, (int, float))
    ):
        age_s = max(0, int(datetime.now(timezone.utc).timestamp() - float(blob_at)))
        # Large lighting blobs can take longer to upload/apply on slower links.
        # Avoid false "stuck" errors for valid long-running transfers.
        if age_s > 180:
            status = {
                "state": "error",
                "blobType": "lighting",
                "error": "stuck_begin",
                "ageSeconds": age_s,
            }
    if status.get("state") == "done" and status.get("ok") and status.get("blobType") == "lighting":
        try:
            path = _lighting_pd_path()
            if path.exists():
                sha = hashlib.sha256(path.read_bytes()).hexdigest()
                update_sync_state(current_app.instance_path, "lighting", sha)
        except Exception:
            current_app.logger.exception("Failed to update lighting sync state")
    progress = None
    if isinstance(status, dict) and status.get("blobType") == "lighting":
        try:
            size = int(status.get("size", 0) or 0)
        except Exception:
            size = 0
        try:
            sent = int(status.get("sent", 0) or 0)
        except Exception:
            sent = 0
        try:
            acked = int(status.get("acked", 0) or 0)
        except Exception:
            acked = 0
        if size > 0:
            tx = max(0, min(size, sent))
            rx = max(0, min(size, acked))
            progress = {
                "size": size,
                "sent": tx,
                "acked": rx,
                "txPercent": int((tx * 100) / size),
                "ackPercent": int((rx * 100) / size),
            }
    return jsonify(
        {
            "ok": True,
            "bridge": {"connected": bool(st.get("connected")), "port": st.get("port")},
            "blob_status": status,
            "blob_at": blob_at,
            "progress": progress,
        }
    )


@api_bp.post("/preview/play")
def api_lighting_preview_play():
    body = request.get_json(silent=True) or {}
    scene_id = str(body.get("sceneId") or "").strip()
    if not scene_id:
        return jsonify({"ok": False, "error": "scene_required"}), 400
    result = play_scene_rpc(current_app.instance_path, scene_id=scene_id, source="pi.lighting.preview", timeout_s=4.5)
    if not bool(result.get("ok", False)):
        reason = str(result.get("reason") or "play_failed")
        bridge = read_bridge_state() if callable(read_bridge_state) else {}
        blob_status = bridge.get("blob_status") if isinstance(bridge, dict) else {}
        lighting_status = bridge.get("lighting_status") if isinstance(bridge, dict) else {}
        lighting_at = 0.0
        if isinstance(bridge, dict):
            try:
                lighting_at = float(bridge.get("lighting_at") or 0.0)
            except Exception:
                lighting_at = 0.0
        now_ts = datetime.now(timezone.utc).timestamp()
        lighting_status_fresh = lighting_at > 0.0 and (now_ts - lighting_at) <= 20.0
        if reason in ("no_response", "rpc_error"):
            if isinstance(blob_status, dict):
                blob_state = str(blob_status.get("state") or "")
                blob_type = str(blob_status.get("blobType") or "")
                if blob_type == "lighting" and blob_state in ("begin", "await_ready", "await_result", "await_manifest"):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "sync_in_progress",
                                "sceneId": str(result.get("sceneId") or scene_id),
                            }
                        ),
                        409,
                    )
            if lighting_status_fresh and isinstance(lighting_status, dict):
                st = str(lighting_status.get("status") or "").strip().lower()
                if st in ("error", "skipped", "missing"):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "runtime_not_loaded",
                                "sceneId": str(result.get("sceneId") or scene_id),
                                "status": st,
                                "bootReason": str(lighting_status.get("reason") or ""),
                                "failures": int(lighting_status.get("failures") or 0),
                            }
                        ),
                        503,
                    )
        if reason == "not_loaded":
            if lighting_status_fresh and isinstance(lighting_status, dict):
                st = str(lighting_status.get("status") or "").strip().lower()
                boot_reason = str(lighting_status.get("reason") or "").strip().lower()
                if st == "skipped" and boot_reason == "guarded":
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "runtime_guarded",
                                "sceneId": str(result.get("sceneId") or scene_id),
                                "status": st,
                                "bootReason": boot_reason,
                                "failures": int(lighting_status.get("failures") or 0),
                            }
                        ),
                        503,
                    )
                if st in ("error", "missing"):
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "error": "runtime_not_loaded",
                                "sceneId": str(result.get("sceneId") or scene_id),
                                "status": st,
                                "bootReason": boot_reason,
                                "failures": int(lighting_status.get("failures") or 0),
                            }
                        ),
                        503,
                    )
            return jsonify({"ok": False, "error": "not_loaded", "sceneId": str(result.get("sceneId") or scene_id)}), 503
        status = 404 if reason == "unknown_scene" else 503
        return jsonify({"ok": False, "error": reason, "sceneId": str(result.get("sceneId") or scene_id)}), status
    return jsonify({"ok": True, "sceneId": str(result.get("sceneId") or scene_id)})


@api_bp.post("/preview/stop")
def api_lighting_preview_stop():
    body = request.get_json(silent=True) or {}
    scene_id = str(body.get("sceneId") or "").strip()
    result = stop_scene_rpc(scene_id=scene_id or "*", source="pi.lighting.preview", timeout_s=1.8)
    if not bool(result.get("ok", False)):
        reason = str(result.get("reason") or "stop_failed")
        return jsonify({"ok": False, "error": reason, "sceneId": str(result.get("sceneId") or scene_id or "*")}), 503
    return jsonify({"ok": True, "sceneId": str(result.get("sceneId") or scene_id or "*")})


@api_bp.get("/preview/esp-state")
def api_lighting_preview_esp_state():
    st = scene_status(timeout_s=1.5)
    bridge = read_bridge_state() if callable(read_bridge_state) else {}
    esp_connected = bool(bridge.get("connected")) if isinstance(bridge, dict) else False
    return jsonify(
        {
            "ok": bool(st.get("ok", False)),
            "playing": bool(st.get("playing", False)),
            "sceneId": str(st.get("sceneId") or ""),
            "reason": str(st.get("reason") or ""),
            "espConnected": esp_connected,
            "headless": bool(is_headless_mode()),
            "activeSceneCount": int(st.get("activeSceneCount") or 0),
            "overridesActive": int(st.get("overridesActive") or 0),
            "activeScenes": st.get("activeScenes") if isinstance(st.get("activeScenes"), list) else [],
        }
    )


@api_bp.get("/runtime/status")
def api_lighting_runtime_status():
    st = scene_status(timeout_s=1.5)
    bridge = read_bridge_state() if callable(read_bridge_state) else {}
    esp_connected = bool(bridge.get("connected")) if isinstance(bridge, dict) else False
    active_scenes = st.get("activeScenes") if isinstance(st.get("activeScenes"), list) else []
    return jsonify(
        {
            "ok": True,
            "headless": bool(is_headless_mode()),
            "espConnected": esp_connected,
            "bridge": {"connected": esp_connected, "port": bridge.get("port") if isinstance(bridge, dict) else None},
            "scene": {
                "ok": bool(st.get("ok", False)),
                "playing": bool(st.get("playing", False)),
                "sceneId": str(st.get("sceneId") or ""),
                "reason": str(st.get("reason") or ""),
                "activeSceneCount": int(st.get("activeSceneCount") or len(active_scenes)),
                "overridesActive": int(st.get("overridesActive") or 0),
                "activeScenes": active_scenes,
            },
        }
    )


@api_bp.post("/fixtures/layout")
def api_lighting_fixtures_layout():
    """Persist fixture layout overrides without editing scenes."""
    body = request.get_json(silent=True) or {}
    fixtures = body.get("fixtures")
    if not isinstance(fixtures, dict):
        return jsonify({"ok": False, "error": "fixtures must be object"}), 400
    cfg = _load_config()
    cfg["fixtures"] = _normalize_fixtures_map(fixtures)
    cfg["updatedAt"] = datetime.now(timezone.utc).isoformat()
    _write_json(_lighting_json_path(), cfg)
    return jsonify({"ok": True})
