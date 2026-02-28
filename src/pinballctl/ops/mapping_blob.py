"""Build and enqueue hardware mapping blob payloads."""
from __future__ import annotations

import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Tuple


@dataclass(frozen=True)
class MappingBlobResult:
    count: int
    payload_len: int
    payload_crc32: int
    output_path: Path


def _instance_dir() -> Path:
    """Locate the src/instance directory relative to this file."""
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
    inst = _instance_dir() / "hardware"
    inst.mkdir(parents=True, exist_ok=True)
    return inst / "mapping.json", inst / "mapping.pb"


def _discovered_path() -> Path:
    """Path to the discovered.json persisted by the bridge."""
    return _instance_dir() / "hardware" / "discovered.json"


def _load_mapping(mapping_path: Path) -> Dict[str, dict]:
    data = json.loads(mapping_path.read_text())
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        return data["data"]
    if isinstance(data, dict):
        return data
    raise ValueError("invalid mapping payload")


def _load_discovered_state(path: Path | None = None) -> Dict[str, str]:
    """Return uid -> HIGH/LOW from the latest discovered snapshot."""
    path = path or _discovered_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {}
    pins = data.get("pins") if isinstance(data, dict) else None
    if not isinstance(pins, list):
        return {}
    states: Dict[str, str] = {}
    for pin in pins:
        if not isinstance(pin, dict):
            continue
        uid = pin.get("uid")
        if not isinstance(uid, str) or not uid:
            continue
        state = pin.get("state")
        if isinstance(state, str):
            state_val = state.strip().upper()
            if state_val in ("HIGH", "LOW"):
                states[uid] = state_val
            elif state_val in ("1", "0"):
                states[uid] = "HIGH" if state_val == "1" else "LOW"
            continue
        if isinstance(state, bool):
            states[uid] = "HIGH" if state else "LOW"
            continue
        if isinstance(state, int):
            states[uid] = "HIGH" if state else "LOW"
    return states


def _parse_gpio_pin(uid: str) -> int | None:
    parts = uid.split("__")
    if len(parts) < 4:
        return None
    pin_type = parts[-2]
    chan = parts[-1]
    if pin_type != "GPIO":
        return None
    if not chan.isdigit():
        return None
    pin = int(chan)
    if pin < 0 or pin > 0xFFFF:
        return None
    return pin


def _iter_mapping_entries(mapping: Dict[str, dict], discovered_states: Dict[str, str]) -> Iterable[Tuple[int, int]]:
    by_pin: Dict[int, int] = {}
    for uid, row in mapping.items():
        if not isinstance(row, dict):
            continue
        safety = (row.get("safety") or "").strip().upper()
        if safety not in ("HIGH", "LOW"):
            safety = discovered_states.get(uid, "")
        if safety not in ("HIGH", "LOW"):
            continue
        pin = _parse_gpio_pin(uid)
        if pin is None:
            continue
        by_pin[pin] = 1 if safety == "HIGH" else 0
    for pin in sorted(by_pin):
        yield pin, by_pin[pin]


def _iter_component_driver_entries(mapping: Dict[str, dict]) -> Iterable[Tuple[str, str, str]]:
    by_component: Dict[str, Tuple[str, str]] = {}
    for uid, row in mapping.items():
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        if not fn:
            continue
        linked_primary = str(row.get("linkedPrimaryUid") or "").strip()
        if linked_primary:
            # Skip linked secondary rows; primary carries the shared component identity.
            continue

        component_id = str(row.get("componentId") or "").strip()
        if not component_id:
            component_id = str(uid or "").strip()
        if not component_id:
            continue
        driver = str(row.get("driver") or "").strip() or "Default"
        if component_id not in by_component:
            by_component[component_id] = (fn, driver)
    for component_id in sorted(by_component):
        fn, driver = by_component[component_id]
        yield component_id, fn, driver


def build_mapping_blob(mapping_path: Path | None = None, output_path: Path | None = None) -> MappingBlobResult:
    """Build mapping.pb from mapping.json and return summary details."""
    if mapping_path is None or output_path is None:
        default_mapping, default_output = _default_paths()
        mapping_path = mapping_path or default_mapping
        output_path = output_path or default_output

    if not mapping_path.exists():
        raise FileNotFoundError(f"missing mapping.json at {mapping_path}")

    blob = build_mapping_blob_bytes(mapping_path)
    payload = blob[12:]
    payload_crc = struct.unpack("<I", blob[8:12])[0]
    count = struct.unpack("<H", payload[:2])[0] if payload else 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(blob)
    return MappingBlobResult(
        count=count,
        payload_len=len(payload),
        payload_crc32=payload_crc,
        output_path=output_path,
    )


def build_mapping_pb(mapping_path: Path | None = None, output_path: Path | None = None) -> MappingBlobResult:
    """Public wrapper to build mapping.pb (preferred API)."""
    return build_mapping_blob(mapping_path=mapping_path, output_path=output_path)


def build_mapping_blob_bytes(mapping_path: Path) -> bytes:
    """Build mapping.pb bytes from mapping.json without writing to disk."""
    mapping = _load_mapping(mapping_path)
    discovered_path = mapping_path.parent / "discovered.json"
    discovered_states = _load_discovered_state(discovered_path if discovered_path.exists() else None)
    entries = list(_iter_mapping_entries(mapping, discovered_states))
    component_entries = list(_iter_component_driver_entries(mapping))
    count = len(entries)

    payload = bytearray()
    payload.extend(struct.pack("<H", count))
    for pin, safe in entries:
        payload.extend(struct.pack("<HB", pin, safe))
    payload.extend(struct.pack("<H", len(component_entries)))
    for component_id, function_name, driver in component_entries:
        comp_bytes = component_id.encode("utf-8", errors="ignore")[:255]
        fn_bytes = function_name.encode("utf-8", errors="ignore")[:255]
        drv_bytes = driver.encode("utf-8", errors="ignore")[:255]
        payload.extend(struct.pack("<B", len(comp_bytes)))
        payload.extend(comp_bytes)
        payload.extend(struct.pack("<B", len(fn_bytes)))
        payload.extend(fn_bytes)
        payload.extend(struct.pack("<B", len(drv_bytes)))
        payload.extend(drv_bytes)

    payload_crc = zlib.crc32(payload) & 0xFFFFFFFF
    header = struct.pack("<2sBBII", b"PB", 3, 1, len(payload), payload_crc)
    return header + payload
