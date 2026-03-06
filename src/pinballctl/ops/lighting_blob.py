"""Build and decode lighting scene blobs (lighting.pd)."""
from __future__ import annotations

import gzip
import hashlib
import json
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pinballctl.lighting.patterns import build_pattern_op, expand_pattern_op, normalize_pattern_name
from pinballctl.lighting.pattern_runtime import PatternRuntime

@dataclass(frozen=True)
class LightingBlobResult:
    payload_len: int
    payload_sha256: str
    output_path: Path


@dataclass(frozen=True)
class LightingBundle:
    schema: int
    built_at: int
    scenes: List[Dict[str, Any]]
    fixtures: Dict[str, Dict[str, Any]]


def _instance_dir() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "src":
            inst = p / "instance"
            inst.mkdir(parents=True, exist_ok=True)
            return inst
    inst = Path.cwd() / "src" / "instance"
    inst.mkdir(parents=True, exist_ok=True)
    return inst


def _default_paths() -> Tuple[Path, Path]:
    inst = _instance_dir() / "lighting"
    inst.mkdir(parents=True, exist_ok=True)
    return inst / "lighting.json", inst / "lighting.pd"


def _canonical_json_bytes(data: Any) -> bytes:
    payload_json = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
    return payload_json.encode("utf-8")


def _to_ms(duration: Dict[str, Any] | None) -> int:
    if not isinstance(duration, dict):
        return 1000
    frame_ms = 500
    value = duration.get("value", 1)
    unit = str(duration.get("unit", "seconds")).strip().lower()
    try:
        v = float(value)
    except Exception:
        v = 1.0
    if v < 0:
        v = 0
    if unit.startswith("frame"):
        return max(1, int(round(v))) * frame_ms
    if unit.startswith("min"):
        return int(v * 60_000)
    return int(v * 1_000)


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


def _compile_scene(scene: Dict[str, Any], scene_id: int) -> Dict[str, Any]:
    sid = str(scene.get("id") or f"scene_{scene_id}")
    title = str(scene.get("title") or sid)
    cast = [str(x) for x in (scene.get("cast") or []) if isinstance(x, str) and x.strip()]
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
    duration_ms = _to_ms(scene.get("duration"))
    params = scene.get("params") if isinstance(scene.get("params"), dict) else {}
    brightness = _clamp01(params.get("brightness", 1.0), default=1.0)
    timeline = scene.get("timeline") if isinstance(scene.get("timeline"), list) else []
    markers_raw = scene.get("markers") if isinstance(scene.get("markers"), list) else []
    markers: List[Dict[str, Any]] = []
    linear: List[Dict[str, Any]] = []

    # Deterministic baseline: every scene starts by clearing output state.
    # Scene ops at tMs=0 are then applied on top of this baseline.
    linear.append({"tMs": 0, "op": "CLEAR", "target": "*"})

    if pattern == "custom":
        for keyframe in timeline:
            if not isinstance(keyframe, dict):
                continue
            at_ms = keyframe.get("atMs", 0)
            try:
                at_ms = int(at_ms)
            except Exception:
                at_ms = 0
            if at_ms < 0:
                at_ms = 0
            target = keyframe.get("fixtureId")
            pixel_index = keyframe.get("pixelIndex")
            color = keyframe.get("color", "#000000")
            intensity = keyframe.get("intensity", 1.0)
            op = {
                "tMs": at_ms,
                "op": "SET",
                "target": str(target) if target else "*",
                "color": str(color),
                "intensity": float(intensity) if isinstance(intensity, (int, float)) else 1.0,
                "brightness": _clamp01(keyframe.get("brightness", 1.0), default=1.0),
                "tween": str(keyframe.get("tween", "hold")).strip().lower() if isinstance(keyframe.get("tween"), str) else "hold",
            }
            if op["tween"] not in ("hold", "linear"):
                op["tween"] = "hold"
            if isinstance(pixel_index, (int, float)) and int(pixel_index) >= 0:
                op["pixelIndex"] = int(pixel_index)
            linear.append(op)
    else:
        op = build_pattern_op(pattern, params, brightness)
        if not isinstance(op, dict):
            op = build_pattern_op("solid", params, brightness)
        if isinstance(op, dict):
            if "target" not in op:
                op["target"] = "*"
            op["tMs"] = 0
            linear.append(op)

    linear.sort(key=lambda x: int(x.get("tMs", 0)))
    seen_tags: set[str] = set()
    seen_times: set[int] = set()
    for marker in markers_raw:
        if not isinstance(marker, dict):
            continue
        tag = str(marker.get("tag") or "").strip().lower()
        if not tag:
            continue
        try:
            at_ms = int(marker.get("atMs", 0))
        except Exception:
            at_ms = 0
        if at_ms < 0:
            at_ms = 0
        if tag in seen_tags or at_ms in seen_times:
            continue
        seen_tags.add(tag)
        seen_times.add(at_ms)
        markers.append({"tMs": at_ms, "tag": tag})
    markers.sort(key=lambda x: int(x.get("tMs", 0)))
    scene_tween = str(params.get("tween", "hold")).strip().lower() if pattern == "custom" else "hold"
    if scene_tween not in ("hold", "linear"):
        scene_tween = "hold"
    return {
        "id": sid,
        "title": title,
        "durationMs": duration_ms,
        "endBehavior": end_behavior,
        "priority": priority,
        "blendMode": blend_mode,
        "castMask": cast_mask,
        "cast": cast,
        "pattern": pattern,
        "brightness": brightness,
        "tween": scene_tween,
        "ops": linear,
        "markers": markers,
    }


def _compile_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    fixtures = data.get("fixtures") if isinstance(data.get("fixtures"), dict) else {}
    scenes_raw = data.get("scenes") if isinstance(data.get("scenes"), list) else []
    scenes = [_compile_scene(scene, idx) for idx, scene in enumerate(scenes_raw) if isinstance(scene, dict)]
    return {
        "schema": 1,
        "builtAt": int(time.time()),
        "fixtures": fixtures,
        "scenes": scenes,
    }


def _timeline_view(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip compiled payload to an inspectable timeline-only JSON view."""
    fixtures_in = payload.get("fixtures") if isinstance(payload.get("fixtures"), dict) else {}
    fixtures_out: List[Dict[str, Any]] = []
    for fid, row in fixtures_in.items():
        if not isinstance(fid, str) or not isinstance(row, dict):
            continue
        fixtures_out.append(
            {
                "id": fid,
                "type": str(row.get("type") or ""),
                "pixelCount": int(row.get("pixelCount", 1)) if isinstance(row.get("pixelCount"), (int, float)) else 1,
            }
        )
    fixtures_out.sort(key=lambda r: r["id"])

    runtime = PatternRuntime(fixtures_in)
    scenes_in = payload.get("scenes") if isinstance(payload.get("scenes"), list) else []
    scenes_out: List[Dict[str, Any]] = []

    for scene in scenes_in:
        if not isinstance(scene, dict):
            continue
        duration_ms = int(scene.get("durationMs", 0)) if isinstance(scene.get("durationMs"), (int, float)) else 0
        ops = scene.get("ops") if isinstance(scene.get("ops"), list) else []
        frames: Dict[int, List[Dict[str, Any]]] = {}

        for op in ops:
            if not isinstance(op, dict):
                continue
            try:
                t_ms = int(op.get("tMs", 0))
            except Exception:
                t_ms = 0
            if t_ms < 0:
                t_ms = 0

            op_name = str(op.get("op") or "").strip().upper()
            target = str(op.get("target") or "*").strip() or "*"

            expanded = expand_pattern_op(op_name, runtime, scene, op, duration_ms, t_ms)
            if expanded:
                for t_key, change_list in expanded.items():
                    frames.setdefault(t_key, []).extend(change_list)
                continue

            if op_name == "CLEAR":
                change = {"target": target, "off": True}
            else:
                change = {"target": target}
                if isinstance(op.get("pixelIndex"), (int, float)):
                    px = int(op.get("pixelIndex"))
                    if px >= 0:
                        change["pixelIndex"] = px
                if isinstance(op.get("color"), str):
                    change["color"] = str(op.get("color"))
                if isinstance(op.get("brightness"), (int, float)):
                    change["brightness"] = float(op.get("brightness"))
                if isinstance(op.get("intensity"), (int, float)):
                    change["intensity"] = float(op.get("intensity"))
                if op_name not in ("SET", "SOLID"):
                    change["effect"] = op_name.lower()
                    params: Dict[str, Any] = {}
                    for k, v in op.items():
                        if k in {"tMs", "op", "target", "pixelIndex", "color", "brightness", "intensity"}:
                            continue
                        params[k] = v
                    if params:
                        change["params"] = params

            frames.setdefault(t_ms, []).append(change)

        sorted_times = sorted(frames.keys())
        frame_list = [{"frame": idx, "atMs": int(t), "changes": frames[t]} for idx, t in enumerate(sorted_times)]
        scenes_out.append(
            {
                "id": str(scene.get("id") or ""),
                "name": str(scene.get("title") or scene.get("id") or ""),
                "priority": int(scene.get("priority", 0)) if isinstance(scene.get("priority"), (int, float)) else 0,
                "blendMode": str(scene.get("blendMode") or "overlay"),
                "endBehavior": str(scene.get("endBehavior") or "stop"),
                "durationMs": duration_ms,
                "frameCount": len(frame_list),
                "frames": frame_list,
            }
        )

    return {
        "schema": int(payload.get("schema", 1)) if isinstance(payload.get("schema"), (int, float)) else 1,
        "builtAt": int(payload.get("builtAt", 0)) if isinstance(payload.get("builtAt"), (int, float)) else 0,
        "fixtures": fixtures_out,
        "scenes": scenes_out,
    }

def compile_lighting_timeline(lighting_json_path: Path) -> Dict[str, Any]:
    """Compile lighting.json into an inspectable timeline-only JSON payload."""
    if not lighting_json_path.exists():
        raise FileNotFoundError(f"missing lighting.json at {lighting_json_path}")
    raw = json.loads(lighting_json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid lighting payload")
    return compile_lighting_timeline_data(raw)


def compile_lighting_timeline_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Compile in-memory lighting payload into inspectable timeline JSON."""
    if not isinstance(raw, dict):
        raise ValueError("invalid lighting payload")
    compiled = _compile_payload(raw)
    return _timeline_view(compiled)


def build_lighting_pd_bytes(lighting_json_path: Path) -> bytes:
    if not lighting_json_path.exists():
        raise FileNotFoundError(f"missing lighting.json at {lighting_json_path}")
    raw = json.loads(lighting_json_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid lighting payload")
    timeline_payload = compile_lighting_timeline_data(raw)
    scenes_raw = timeline_payload.get("scenes") if isinstance(timeline_payload.get("scenes"), list) else []
    fixtures_raw = timeline_payload.get("fixtures") if isinstance(timeline_payload.get("fixtures"), list) else []
    rgb_target_hints: set[str] = set()
    for scene in scenes_raw:
        if not isinstance(scene, dict):
            continue
        frames = scene.get("frames") if isinstance(scene.get("frames"), list) else []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            changes = frame.get("changes") if isinstance(frame.get("changes"), list) else []
            for ch in changes:
                if not isinstance(ch, dict):
                    continue
                tgt = str(ch.get("target") or "").strip()
                if not tgt or tgt == "*":
                    continue
                if "pixelIndex" in ch:
                    rgb_target_hints.add(tgt)

    fixture_index: Dict[str, int] = {}
    fixture_rows: List[Tuple[str, int, int]] = []
    for row in fixtures_raw:
        if not isinstance(row, dict):
            continue
        fid = str(row.get("id") or "").strip()
        if not fid or fid in fixture_index:
            continue
        pcount = int(row.get("pixelCount", 1)) if isinstance(row.get("pixelCount"), (int, float)) else 1
        if pcount < 1:
            pcount = 1
        ftype = str(row.get("type") or "").strip().lower()
        is_rgb = 1 if (ftype == "rgb_strip" or "rgb" in ftype or pcount > 1 or fid in rgb_target_hints) else 0
        fixture_index[fid] = len(fixture_rows)
        fixture_rows.append((fid, pcount, is_rgb))

    def _ensure_fixture(fid: str) -> int:
        key = str(fid or "").strip()
        if key == "*" or not key:
            return -1
        idx = fixture_index.get(key)
        if idx is not None:
            return idx
        idx = len(fixture_rows)
        fixture_index[key] = idx
        fixture_rows.append((key, 1, 0))
        return idx

    # Pre-scan scene changes so fixture table includes every referenced target
    # before we emit the fixture section. This keeps fixture indexes stable.
    for scene in scenes_raw:
        if not isinstance(scene, dict):
            continue
        frames = scene.get("frames") if isinstance(scene.get("frames"), list) else []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            changes = frame.get("changes") if isinstance(frame.get("changes"), list) else []
            for ch in changes:
                if not isinstance(ch, dict):
                    continue
                tgt = str(ch.get("target") or "*").strip() or "*"
                _ensure_fixture(tgt)

    payload = bytearray()
    payload.extend(b"LPD2")

    payload.extend(struct.pack("<H", len(fixture_rows)))
    for fid, pcount, is_rgb in fixture_rows:
        b = fid.encode("utf-8")
        if len(b) > 65535:
            raise ValueError("fixture id too long")
        payload.extend(struct.pack("<H", len(b)))
        payload.extend(b)
        payload.extend(struct.pack("<H", int(pcount)))
        payload.extend(struct.pack("<B", int(1 if is_rgb else 0)))

    scene_rows = [s for s in scenes_raw if isinstance(s, dict) and str(s.get("id") or "").strip()]
    payload.extend(struct.pack("<H", len(scene_rows)))
    scene_priority_rows: List[Tuple[str, int]] = []
    for scene in scene_rows:
        sid = str(scene.get("id") or "").strip()
        sid_b = sid.encode("utf-8")
        if len(sid_b) > 65535:
            raise ValueError("scene id too long")
        payload.extend(struct.pack("<H", len(sid_b)))
        payload.extend(sid_b)

        end_behavior = str(scene.get("endBehavior") or "stop").strip().lower()
        end_code = 1 if end_behavior == "repeat" else (2 if end_behavior == "bounce" else 0)
        payload.extend(struct.pack("<B", end_code))
        priority = int(scene.get("priority", 0)) if isinstance(scene.get("priority"), (int, float)) else 0
        if priority < -32768:
            priority = -32768
        if priority > 32767:
            priority = 32767
        payload.extend(struct.pack("<h", int(priority)))
        scene_priority_rows.append((sid, priority))
        blend_mode = str(scene.get("blendMode") or "overlay").strip().lower()
        if blend_mode == "stop_lower":
            blend_code = 1
        elif blend_mode == "pause_lower":
            blend_code = 2
        else:
            blend_code = 0
        payload.extend(struct.pack("<B", blend_code))

        duration_ms = int(scene.get("durationMs", 0)) if isinstance(scene.get("durationMs"), (int, float)) else 0
        if duration_ms < 0:
            duration_ms = 0
        payload.extend(struct.pack("<I", duration_ms))

        frames = scene.get("frames") if isinstance(scene.get("frames"), list) else []
        payload.extend(struct.pack("<I", len(frames)))
        for frame in frames:
            if not isinstance(frame, dict):
                payload.extend(struct.pack("<IH", 0, 0))
                continue
            at_ms = int(frame.get("atMs", 0)) if isinstance(frame.get("atMs"), (int, float)) else 0
            if at_ms < 0:
                at_ms = 0
            changes = frame.get("changes") if isinstance(frame.get("changes"), list) else []
            payload.extend(struct.pack("<IH", at_ms, len(changes)))
            for ch in changes:
                if not isinstance(ch, dict):
                    payload.extend(struct.pack("<HhB", 0xFFFF, -1, 0x01))
                    continue
                tgt = str(ch.get("target") or "*").strip() or "*"
                fi = _ensure_fixture(tgt)
                fi_encoded = 0xFFFF if fi < 0 else fi
                px = int(ch.get("pixelIndex")) if isinstance(ch.get("pixelIndex"), (int, float)) else -1
                if px < -1:
                    px = -1
                flags = 0
                if bool(ch.get("off", False)):
                    flags |= 0x01
                color = ch.get("color")
                if isinstance(color, str) and color.strip():
                    flags |= 0x02
                brightness = ch.get("brightness")
                if isinstance(brightness, (int, float)):
                    flags |= 0x04
                intensity = ch.get("intensity")
                if isinstance(intensity, (int, float)):
                    flags |= 0x08
                payload.extend(struct.pack("<HhB", fi_encoded, px, flags))
                if flags & 0x02:
                    c = str(color).strip().lstrip("#")
                    if len(c) == 3:
                        c = "".join(x * 2 for x in c)
                    if len(c) != 6:
                        c = "ffffff"
                    try:
                        r = int(c[0:2], 16)
                        g = int(c[2:4], 16)
                        b = int(c[4:6], 16)
                    except Exception:
                        r = g = b = 255
                    payload.extend(struct.pack("<BBB", r, g, b))
                if flags & 0x04:
                    bv = max(0.0, min(1.0, float(brightness)))
                    payload.extend(struct.pack("<B", int(round(bv * 255.0))))
                if flags & 0x08:
                    iv = max(0.0, min(1.0, float(intensity)))
                    payload.extend(struct.pack("<B", int(round(iv * 255.0))))

    # Optional metadata trailer kept outside scene stream for runtime compatibility.
    payload.extend(b"PRI1")
    payload.extend(struct.pack("<H", len(scene_priority_rows)))
    for sid, priority in scene_priority_rows:
        sid_b = sid.encode("utf-8")
        if len(sid_b) > 65535:
            raise ValueError("scene id too long")
        payload.extend(struct.pack("<H", len(sid_b)))
        payload.extend(sid_b)
        payload.extend(struct.pack("<h", int(priority)))

    payload_bytes = bytes(payload)
    sha = hashlib.sha256(payload_bytes).digest()
    header = struct.pack("<4sHHI32s", b"PLT1", 4, 0, len(payload_bytes), sha)
    return header + payload_bytes


def build_lighting_pd(lighting_json_path: Path | None = None, output_path: Path | None = None) -> LightingBlobResult:
    if lighting_json_path is None or output_path is None:
        default_src, default_out = _default_paths()
        lighting_json_path = lighting_json_path or default_src
        output_path = output_path or default_out
    blob = build_lighting_pd_bytes(lighting_json_path)
    payload_len = struct.unpack("<I", blob[8:12])[0]
    sha = blob[12:44].hex()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(blob)
    return LightingBlobResult(payload_len=payload_len, payload_sha256=sha, output_path=output_path)


def decode_lighting_pd_bytes(blob: bytes) -> LightingBundle:
    if len(blob) < 44:
        raise ValueError("lighting.pd too small")
    magic, version, flags, payload_len, sha = struct.unpack("<4sHHI32s", blob[:44])
    if magic != b"PLT1":
        raise ValueError("lighting.pd bad magic")
    if version not in (2, 3, 4):
        raise ValueError("lighting.pd bad version")
    if len(blob) != 44 + payload_len:
        raise ValueError("lighting.pd size mismatch")
    payload = blob[44:]
    if hashlib.sha256(payload).digest() != sha:
        raise ValueError("lighting.pd sha mismatch")
    if flags & 0x1:
        payload = gzip.decompress(payload)
    if len(payload) < 4 or payload[:4] != b"LPD2":
        raise ValueError("lighting.pd bad payload magic")
    off = 4

    def _u8() -> int:
        nonlocal off
        if off + 1 > len(payload):
            raise ValueError("lighting.pd truncated")
        v = payload[off]
        off += 1
        return int(v)

    def _u16() -> int:
        nonlocal off
        if off + 2 > len(payload):
            raise ValueError("lighting.pd truncated")
        v = struct.unpack_from("<H", payload, off)[0]
        off += 2
        return int(v)

    def _i16() -> int:
        nonlocal off
        if off + 2 > len(payload):
            raise ValueError("lighting.pd truncated")
        v = struct.unpack_from("<h", payload, off)[0]
        off += 2
        return int(v)

    def _u32() -> int:
        nonlocal off
        if off + 4 > len(payload):
            raise ValueError("lighting.pd truncated")
        v = struct.unpack_from("<I", payload, off)[0]
        off += 4
        return int(v)

    def _str() -> str:
        nonlocal off
        n = _u16()
        if off + n > len(payload):
            raise ValueError("lighting.pd truncated")
        b = payload[off:off + n]
        off += n
        return b.decode("utf-8", errors="replace")

    fixture_count = _u16()
    fixtures_by_idx: List[Dict[str, Any]] = []
    fixtures: Dict[str, Dict[str, Any]] = {}
    for _ in range(fixture_count):
        fid = _str().strip()
        pcount = _u16()
        kind = _u8()
        row = {"id": fid, "pixelCount": pcount, "type": "rgb_strip" if kind == 1 else "led"}
        fixtures_by_idx.append(row)
        if fid:
            fixtures[fid] = dict(row)

    scene_count = _u16()
    scenes: List[Dict[str, Any]] = []
    for _ in range(scene_count):
        sid = _str().strip()
        end_code = _u8()
        priority = _i16() if version >= 3 else 0
        blend_code = _u8() if version >= 4 else 0
        duration_ms = _u32()
        frame_count = _u32()
        frames: List[Dict[str, Any]] = []
        for _ in range(frame_count):
            at_ms = _u32()
            change_count = _u16()
            changes: List[Dict[str, Any]] = []
            for _ in range(change_count):
                fi = _u16()
                px = _i16()
                flags = _u8()
                out: Dict[str, Any] = {"target": "*"}
                if fi != 0xFFFF and fi < len(fixtures_by_idx):
                    out["target"] = str(fixtures_by_idx[fi].get("id") or "*")
                if px >= 0:
                    out["pixelIndex"] = px
                if flags & 0x01:
                    out["off"] = True
                if flags & 0x02:
                    r = _u8()
                    g = _u8()
                    b = _u8()
                    out["color"] = f"#{r:02x}{g:02x}{b:02x}"
                if flags & 0x04:
                    out["brightness"] = _u8() / 255.0
                if flags & 0x08:
                    out["intensity"] = _u8() / 255.0
                changes.append(out)
            frames.append({"atMs": at_ms, "changes": changes})
        scenes.append(
            {
                "id": sid,
                "name": sid,
                "priority": priority,
                "blendMode": "stop_lower" if blend_code == 1 else ("pause_lower" if blend_code == 2 else "overlay"),
                "endBehavior": "repeat" if end_code == 1 else ("bounce" if end_code == 2 else "stop"),
                "durationMs": duration_ms,
                "frameCount": len(frames),
                "frames": frames,
            }
        )

    if off + 6 <= len(payload) and payload[off:off + 4] == b"PRI1":
        off += 4
        row_count = _u16()
        prio_by_scene: Dict[str, int] = {}
        for _ in range(row_count):
            sid = _str().strip()
            prio_by_scene[sid] = _i16()
        for scene in scenes:
            sid = str(scene.get("id") or "")
            if sid in prio_by_scene:
                scene["priority"] = int(prio_by_scene[sid])

    return LightingBundle(schema=2, built_at=0, scenes=scenes, fixtures=fixtures)
