"""Build and enqueue rules blob payloads."""
from __future__ import annotations

import gzip
import json
import struct
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class RulesBlobResult:
    payload_len: int
    payload_sha256: str
    output_path: Path


@dataclass(frozen=True)
class RulesBundle:
    schema: int
    rules: List[Dict[str, Any]]
    index: Dict[str, List[int]]
    built_at: int | None = None
    source_hash: str | None = None

    def get_rule_ids_for_event(self, event_key: str) -> List[int]:
        return list(self.index.get(event_key, []))


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
    inst = _instance_dir() / "rules"
    inst.mkdir(parents=True, exist_ok=True)
    return inst / "rules.json", inst / "rules.pd"


def _normalize_group(logic: str, items: Any, window_ms: Any | None = None) -> dict:
    group = {
        "logic": logic if logic in ("ALL", "ANY") else "ALL",
        "items": items if isinstance(items, list) else [],
    }
    if window_ms is not None:
        group["windowMs"] = int(window_ms) if isinstance(window_ms, (int, float)) else 750
    return group


def _compile_rule(rule: Dict[str, Any], rule_id: int) -> Dict[str, Any]:
    enabled = rule.get("enabled", True)
    trigger_groups = rule.get("triggerGroups")
    condition_groups = rule.get("conditionGroups")
    if not isinstance(trigger_groups, dict):
        logic = (rule.get("logic") or "ALL").upper()
        items = rule.get("triggers") if isinstance(rule.get("triggers"), list) else []
        trigger_groups = {"logic": logic, "groups": [_normalize_group(logic, items, 750)] if items else []}
    if not isinstance(condition_groups, dict):
        logic = (rule.get("conditionLogic") or "ALL").upper()
        items = rule.get("conditions") if isinstance(rule.get("conditions"), list) else []
        condition_groups = {"logic": logic, "groups": [_normalize_group(logic, items)] if items else []}
    actions = rule.get("actions") if isinstance(rule.get("actions"), list) else []
    return {
        "id": int(rule_id),
        "enabled": bool(enabled),
        "triggerGroups": trigger_groups,
        "conditionGroups": condition_groups,
        "actions": actions,
    }


def _rule_id_for(rule: Dict[str, Any], fallback_id: int) -> int:
    existing = rule.get("id")
    if isinstance(existing, int) and existing >= 0:
        return existing
    return fallback_id


def _compile_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compiled: List[Dict[str, Any]] = []
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        compiled.append(_compile_rule(rule, _rule_id_for(rule, idx)))
    return compiled


def _canonical_json_bytes(data: Any) -> bytes:
    payload_json = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
    return payload_json.encode("utf-8")


def _iter_trigger_event_keys(trigger_groups: Any) -> List[str]:
    if not isinstance(trigger_groups, dict):
        return []
    groups = trigger_groups.get("groups")
    if not isinstance(groups, list):
        return []
    keys: List[str] = []
    seen = set()
    for group in groups:
        items = group.get("items") if isinstance(group, dict) else None
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            event_key = item.get("event")
            if not isinstance(event_key, str):
                continue
            event_key = event_key.strip()
            if not event_key or event_key in seen:
                continue
            seen.add(event_key)
            keys.append(event_key)
    return keys


def _build_index(compiled_rules: List[Dict[str, Any]]) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    for rule in compiled_rules:
        rule_id = rule.get("id")
        if not isinstance(rule_id, int):
            continue
        trigger_groups = rule.get("triggerGroups")
        for event_key in _iter_trigger_event_keys(trigger_groups):
            index.setdefault(event_key, []).append(rule_id)
    return index


def build_rules_pd(rules_path: Path | None = None, output_path: Path | None = None) -> RulesBlobResult:
    """Build rules.pd from rules.json and return summary details."""
    if rules_path is None or output_path is None:
        default_rules, default_output = _default_paths()
        rules_path = rules_path or default_rules
        output_path = output_path or default_output

    blob = build_rules_pd_bytes(rules_path)
    payload_len = struct.unpack("<I", blob[8:12])[0]
    sha = blob[12:44].hex()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(blob)
    return RulesBlobResult(
        payload_len=payload_len,
        payload_sha256=sha,
        output_path=output_path,
    )


def build_rules_pd_bytes(rules_path: Path) -> bytes:
    """Build rules.pd bytes from rules.json without writing to disk."""
    if not rules_path.exists():
        raise FileNotFoundError(f"missing rules.json at {rules_path}")

    data = json.loads(rules_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("invalid rules payload")
    compiled_rules = _compile_rules(data)
    index = _build_index(compiled_rules)
    source_hash = hashlib.sha256(_canonical_json_bytes(data)).hexdigest()
    payload_obj = {
        "schema": 2,
        "builtAt": int(time.time()),
        "sourceHash": source_hash,
        "rules": compiled_rules,
        "index": index,
    }
    payload_bytes = _canonical_json_bytes(payload_obj)
    payload = gzip.compress(payload_bytes, mtime=0)
    sha = hashlib.sha256(payload).digest()
    header = struct.pack("<4sHHI32s", b"PDR1", 1, 1, len(payload), sha)
    return header + payload


def load_rules_pd(path: Path) -> RulesBundle:
    """Load a rules.pd bundle from disk and parse it once."""
    return decode_rules_pd_bytes(path.read_bytes())


def decode_rules_pd_bytes(blob: bytes) -> RulesBundle:
    """Decode rules.pd bytes and return a runtime bundle."""
    if len(blob) < 44:
        raise ValueError("rules.pd too small")
    magic, version, flags, payload_len, sha = struct.unpack("<4sHHI32s", blob[:44])
    if magic != b"PDR1":
        raise ValueError("rules.pd bad magic")
    if version != 1:
        raise ValueError("rules.pd bad version")
    if len(blob) != 44 + payload_len:
        raise ValueError("rules.pd size mismatch")
    payload = blob[44:]
    if hashlib.sha256(payload).digest() != sha:
        raise ValueError("rules.pd sha mismatch")
    if flags & 0x1:
        payload = gzip.decompress(payload)
    data = json.loads(payload.decode("utf-8"))
    if isinstance(data, list):
        compiled_rules = data
        index = _build_index(compiled_rules)
        return RulesBundle(schema=1, rules=compiled_rules, index=index)
    if not isinstance(data, dict):
        raise ValueError("rules.pd payload invalid")
    schema = data.get("schema")
    if schema is None:
        compiled_rules = data.get("rules") if isinstance(data.get("rules"), list) else []
        index = _build_index(compiled_rules)
        return RulesBundle(schema=1, rules=compiled_rules, index=index)
    if int(schema) != 2:
        raise ValueError(f"unsupported rules.pd schema {schema}")
    compiled_rules = data.get("rules") if isinstance(data.get("rules"), list) else []
    index = data.get("index") if isinstance(data.get("index"), dict) else {}
    normalized_index: Dict[str, List[int]] = {}
    for key, ids in index.items():
        if not isinstance(key, str) or not isinstance(ids, list):
            continue
        normalized_index[key] = [int(v) for v in ids if isinstance(v, int)]
    built_at = data.get("builtAt")
    built_at_val = int(built_at) if isinstance(built_at, (int, float)) else None
    source_hash = data.get("sourceHash") if isinstance(data.get("sourceHash"), str) else None
    return RulesBundle(
        schema=2,
        rules=compiled_rules,
        index=normalized_index,
        built_at=built_at_val,
        source_hash=source_hash,
    )
