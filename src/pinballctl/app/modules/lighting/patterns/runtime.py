from __future__ import annotations

import colorsys
import math
import random
from typing import Any, Dict, List


class PatternRuntime:
    def __init__(self, fixtures: Dict[str, Dict[str, Any]]) -> None:
        self.fixtures = fixtures if isinstance(fixtures, dict) else {}

    def clamp01(self, value: Any, default: float = 1.0) -> float:
        try:
            v = float(value)
        except Exception:
            v = float(default)
        if v < 0:
            return 0.0
        if v > 1:
            return 1.0
        return float(v)

    def as_bool(self, value: Any, default: bool = False) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        s = str(value).strip().lower()
        if s in ("1", "true", "yes", "on"):
            return True
        if s in ("0", "false", "no", "off"):
            return False
        return default

    def hex_from_hsv(self, h: float, s: float, v: float) -> str:
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, self.clamp01(s, 1.0), self.clamp01(v, 1.0))
        return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"

    def hex_from_heat(self, v: float) -> str:
        t = self.clamp01(v, 0.0)
        if t < 0.33:
            r = int(round((t / 0.33) * 255)); g = 0; b = 0
        elif t < 0.66:
            r = 255; g = int(round(((t - 0.33) / 0.33) * 200)); b = 0
        else:
            r = 255; g = 200 + int(round(((t - 0.66) / 0.34) * 55)); b = int(round(((t - 0.66) / 0.34) * 180))
        return f"#{max(0, min(255, r)):02x}{max(0, min(255, g)):02x}{max(0, min(255, b)):02x}"

    def scene_targets(self, scene: Dict[str, Any]) -> List[str]:
        cast = [str(x) for x in (scene.get("cast") or []) if isinstance(x, str) and x.strip()]
        cast_mask = str(scene.get("castMask") or "cast").strip().lower()
        if cast_mask == "all":
            return sorted(self.fixtures.keys())
        out = [fid for fid in cast if fid in self.fixtures]
        return out

    def resolve_targets(self, scene: Dict[str, Any], target: str) -> List[str]:
        if target and target != "*" and target in self.fixtures:
            return [target]
        return self.scene_targets(scene)

    def fixture_pixels(self, fid: str) -> List[Dict[str, Any]]:
        row = self.fixtures.get(fid, {}) if isinstance(self.fixtures.get(fid), dict) else {}
        raw_count = row.get("pixelCount", 1)
        px_total = int(raw_count) if isinstance(raw_count, (int, float)) else 1
        if px_total < 1:
            px_total = 1
        points = row.get("points") if isinstance(row.get("points"), list) else []
        line = row.get("line") if isinstance(row.get("line"), dict) else {}
        x1 = float(line.get("x1", 0.0)) if isinstance(line.get("x1"), (int, float)) else 0.0
        y1 = float(line.get("y1", 0.0)) if isinstance(line.get("y1"), (int, float)) else 0.0
        x2 = float(line.get("x2", 1.0)) if isinstance(line.get("x2"), (int, float)) else 1.0
        y2 = float(line.get("y2", 0.0)) if isinstance(line.get("y2"), (int, float)) else 0.0
        out: List[Dict[str, Any]] = []
        for px in range(px_total):
            t = 0.0 if px_total <= 1 else float(px) / float(px_total - 1)
            if px < len(points) and isinstance(points[px], dict):
                pt = points[px]
                x = float(pt.get("x", t)) if isinstance(pt.get("x"), (int, float)) else t
                y = float(pt.get("y", 0.5)) if isinstance(pt.get("y"), (int, float)) else 0.5
            else:
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
            out.append({
                "target": fid,
                "pixelIndex": None if px_total == 1 else px,
                "pixelCount": px_total,
                "pixelPos": 0.0 if px_total == 1 else float(px) / float(px_total),
                "x": x,
                "y": y,
            })
        return out

    def pixels_for_targets(self, targets: List[str]) -> List[Dict[str, Any]]:
        px: List[Dict[str, Any]] = []
        for fid in targets:
            if fid in self.fixtures:
                px.extend(self.fixture_pixels(fid))
        return px

    def pixel_change(self, pixel: Dict[str, Any], color: str, brightness: float, intensity: float = 1.0) -> Dict[str, Any]:
        clamped_intensity = self.clamp01(intensity, 1.0)
        out: Dict[str, Any] = {"target": str(pixel.get("target") or "*")}
        px = pixel.get("pixelIndex")
        if isinstance(px, int) and px >= 0:
            out["pixelIndex"] = px
        if clamped_intensity <= 0.0:
            out["off"] = True
            return out
        out["color"] = str(color)
        out["brightness"] = self.clamp01(brightness, 1.0)
        out["intensity"] = clamped_intensity
        return out

    def clamp_step(self, v: Any, default: int = 80, lo: int = 16, hi: int = 1000) -> int:
        step = int(v) if isinstance(v, (int, float)) else default
        if step < lo:
            step = lo
        if step > hi:
            step = hi
        return step

    def speed_period_ms(self, speed: Any, minimum: int = 500, maximum: int = 9000) -> int:
        s = int(speed) if isinstance(speed, (int, float)) else 80
        if s < 1:
            s = 1
        if s > 100:
            s = 100
        return max(minimum, min(maximum, 9000 - (s - 1) * 85))

    def iter_frames(self, start_t_ms: int, duration_ms: int, step: int):
        if duration_ms <= 0 or start_t_ms >= duration_ms:
            return []
        s = max(1, int(step))
        return range(start_t_ms, duration_ms, s)

    def prepare_pixels(self, scene: Dict[str, Any], op: Dict[str, Any]) -> List[Dict[str, Any]]:
        target = str(op.get("target") or "*").strip() or "*"
        return self.pixels_for_targets(self.resolve_targets(scene, target))

    def empty_frames(self, start_t_ms: int, duration_ms: int) -> Dict[int, List[Dict[str, Any]]]:
        if duration_ms <= 0 or start_t_ms >= duration_ms:
            return {}
        return {}
