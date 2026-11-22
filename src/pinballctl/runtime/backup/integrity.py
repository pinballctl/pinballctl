"""Check references between project configuration files."""

from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple


@dataclass
class RefUsage:
    module: str
    detail: str


def _is_hardware_uid(value: Any) -> bool:
    s = str(value or "").strip()
    return "__" in s and "GPIO" in s


def _uid_tail(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    idx = s.find("__")
    return s[idx + 2 :] if idx >= 0 else s


def _canonical_hw_id(value: Any, valid_hw: Set[str], by_tail: Dict[str, str]) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if s in valid_hw:
        return s
    tail = _uid_tail(s)
    if not tail:
        return s
    return by_tail.get(tail, s)


def _issue_key(kind: str, ident: str) -> str:
    return f"{str(kind or '').strip()}:{str(ident or '').strip()}"


def _component_mapping_data(raw_mapping: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data = raw_mapping.get("data") if isinstance(raw_mapping, dict) else None
    if not isinstance(data, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for uid, row in data.items():
        if not isinstance(row, dict):
            continue
        # Integrity checks must treat all mapped hardware IDs as valid, even if
        # a pin has no friendly/function metadata yet.
        out[str(uid)] = row
    return out


def _collect_refs(
    rules: List[Dict[str, Any]],
    playfield: Dict[str, Any],
    lighting: Dict[str, Any],
    scoring: Dict[str, Any],
    valid_hw: Set[str],
    hw_by_tail: Dict[str, str],
) -> Tuple[Dict[str, List[RefUsage]], Dict[str, List[RefUsage]]]:
    hw_refs: Dict[str, List[RefUsage]] = {}
    cue_refs: Dict[str, List[RefUsage]] = {}

    def add_ref(ref_map: Dict[str, List[RefUsage]], key: Any, module: str, detail: str) -> None:
        k = str(key or "").strip()
        if not k:
            return
        if _is_hardware_uid(k):
            k = _canonical_hw_id(k, valid_hw, hw_by_tail)
        ref_map.setdefault(k, []).append(RefUsage(module=module, detail=detail))

    for rule in rules:
        rid = str(rule.get("id") or "")
        rname = str(rule.get("name") or rid)
        for idx, trig in enumerate(rule.get("triggers") or []):
            if isinstance(trig, dict) and str(trig.get("type") or "").strip().lower() == "hardware":
                add_ref(hw_refs, trig.get("source"), "rules", f"{rname} trigger[{idx}]")
        for gidx, grp in enumerate((rule.get("triggerGroups") or {}).get("groups") or []):
            if not isinstance(grp, dict):
                continue
            for iidx, item in enumerate(grp.get("items") or []):
                if isinstance(item, dict) and str(item.get("type") or "").strip().lower() == "hardware":
                    add_ref(hw_refs, item.get("source"), "rules", f"{rname} triggerGroups[{gidx}].items[{iidx}]")
        for aidx, action in enumerate(rule.get("actions") or []):
            if not isinstance(action, dict):
                continue
            atype = str(action.get("type") or "").strip().lower()
            params = action.get("params") if isinstance(action.get("params"), dict) else {}
            target = action.get("target")
            if atype in ("set_output", "pulse", "set_lcd_text"):
                candidate = target or params.get("device") or params.get("target")
                add_ref(hw_refs, candidate, "rules", f"{rname} action[{aidx}] {atype}")
            elif atype in ("play_audio_cue", "stop_audio_cue", "toggle_audio_cue"):
                cue_id = params.get("cueId") or target
                add_ref(cue_refs, cue_id, "rules", f"{rname} action[{aidx}] {atype}")

    for eidx, el in enumerate(playfield.get("elements") or []):
        if not isinstance(el, dict):
            continue
        uid = el.get("hardwareId") or el.get("id")
        if _is_hardware_uid(uid):
            add_ref(hw_refs, uid, "playfield", f"elements[{eidx}] {el.get('label') or el.get('id')}")
    for key, row in (playfield.get("keymap") or {}).items():
        if isinstance(row, dict):
            uid = row.get("id")
            if _is_hardware_uid(uid):
                add_ref(hw_refs, uid, "playfield", f"keymap[{key}]")

    fixtures = lighting.get("fixtures") if isinstance(lighting.get("fixtures"), dict) else {}
    for fixture_id in fixtures.keys():
        add_ref(hw_refs, fixture_id, "lighting", f"fixtures[{fixture_id}]")
    for sidx, scene in enumerate(lighting.get("scenes") or []):
        if not isinstance(scene, dict):
            continue
        for cidx, cast_id in enumerate(scene.get("cast") or []):
            add_ref(hw_refs, cast_id, "lighting", f"scenes[{sidx}].cast[{cidx}]")
        for tidx, frame in enumerate(scene.get("timeline") or []):
            if isinstance(frame, dict):
                add_ref(hw_refs, frame.get("fixtureId"), "lighting", f"scenes[{sidx}].timeline[{tidx}]")

    for bidx, row in enumerate(scoring.get("basePoints") or []):
        if isinstance(row, dict):
            add_ref(hw_refs, row.get("source"), "scoring", f"basePoints[{bidx}]")
    for ridx, row in enumerate(scoring.get("scoreRules") or []):
        if isinstance(row, dict):
            add_ref(hw_refs, row.get("source"), "scoring", f"scoreRules[{ridx}]")
    for cidx, combo in enumerate(scoring.get("combos") or []):
        if not isinstance(combo, dict):
            continue
        for sidx, step in enumerate(combo.get("steps") or []):
            if isinstance(step, dict):
                add_ref(hw_refs, step.get("source"), "scoring", f"combos[{cidx}].steps[{sidx}]")

    return hw_refs, cue_refs


def _collect_lcd_device_ids(raw_mapping: Dict[str, Any]) -> Set[str]:
    data = raw_mapping.get("data") if isinstance(raw_mapping, dict) else None
    if not isinstance(data, dict):
        return set()
    out: Set[str] = set()
    for _, row in data.items():
        if not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        if fn not in ("LCD Display", "LCD1602"):
            continue
        comp = str(row.get("componentId") or "").strip()
        if not comp:
            continue
        out.add(f"LCD_DISPLAY::{comp}")
    return out


def _collect_asset_refs(audio_cfg: Dict[str, Any]) -> Dict[str, List[RefUsage]]:
    refs: Dict[str, List[RefUsage]] = {}
    for idx, cue in enumerate(audio_cfg.get("cues") or []):
        if not isinstance(cue, dict):
            continue
        aid = str(cue.get("assetId") or "").strip()
        if not aid:
            continue
        refs.setdefault(aid, []).append(RefUsage(module="audio", detail=f"cues[{idx}] {cue.get('name') or cue.get('id') or ''}"))
    return refs


def _tags_for_item(kind: str, status: str, uses: List[Dict[str, str]]) -> List[str]:
    tags = {str(kind or "").strip().lower(), str(status or "").strip().lower()}
    for u in uses:
        tags.add(str(u.get("module") or "").strip().lower())
    tags.discard("")
    return sorted(tags)


def _build_report(
    component_map: Dict[str, Dict[str, Any]],
    lcd_device_ids: Set[str],
    assets: List[Dict[str, Any]],
    cues: List[Dict[str, Any]],
    hw_refs: Dict[str, List[RefUsage]],
    cue_refs: Dict[str, List[RefUsage]],
    asset_refs: Dict[str, List[RefUsage]],
) -> Dict[str, Any]:
    valid_hw = set(component_map.keys())
    valid_targets = set(valid_hw) | set(lcd_device_ids)
    valid_assets = {str(a.get("id") or "").strip() for a in assets if str(a.get("id") or "").strip()}
    valid_cues = {str(c.get("id") or "").strip() for c in cues if str(c.get("id") or "").strip()}

    report_items: List[Dict[str, Any]] = []

    def uses_list(refs: List[RefUsage]) -> List[Dict[str, str]]:
        return [{"module": r.module, "detail": r.detail} for r in refs]

    def add_item(kind: str, ident: str, name: str, status: str, details: str, uses: List[Dict[str, str]], fixable: bool) -> None:
        report_items.append(
            {
                "issueKey": _issue_key(kind, ident),
                "kind": kind,
                "id": ident,
                "name": name,
                "status": status,
                "details": details,
                "uses": uses,
                "tags": _tags_for_item(kind, status, uses),
                "fixable": fixable,
            }
        )

    for aid in sorted(valid_assets):
        refs = asset_refs.get(aid, [])
        asset = next((a for a in assets if str(a.get("id") or "") == aid), None)
        add_item(
            "audio_asset",
            aid,
            str((asset or {}).get("displayName") or aid),
            "ok",
            f"Referenced by {len(refs)} cue(s)",
            uses_list(refs),
            False,
        )

    invalid_cues_by_asset = [cue for cue in cues if str(cue.get("assetId") or "").strip() not in valid_assets]
    for cue in invalid_cues_by_asset:
        cid = str(cue.get("id") or "").strip() or "(missing-id)"
        aid = str(cue.get("assetId") or "").strip()
        add_item(
            "audio_cue",
            cid,
            str(cue.get("name") or cid),
            "error",
            f"Orphaned cue asset: {aid or '(none)'}",
            uses_list(cue_refs.get(cid, [])),
            True,
        )

    invalid_cue_ids = {str(c.get("id") or "").strip() for c in invalid_cues_by_asset}
    for cid in sorted(valid_cues):
        if cid in invalid_cue_ids:
            continue
        cue = next((c for c in cues if str(c.get("id") or "") == cid), None)
        refs = cue_refs.get(cid, [])
        add_item(
            "audio_cue",
            cid,
            str((cue or {}).get("name") or cid),
            "ok",
            f"Referenced by {len(refs)} rule action(s)",
            uses_list(refs),
            False,
        )

    for hid in sorted(valid_hw):
        row = component_map.get(hid, {})
        refs = hw_refs.get(hid, [])
        add_item(
            "hardware_component",
            hid,
            str(row.get("friendly") or hid),
            "ok",
            f"Referenced by {len(refs)} item(s)",
            uses_list(refs),
            False,
        )

    missing_hw = sorted(k for k in hw_refs.keys() if k and k not in valid_targets)
    for hid in missing_hw:
        add_item(
            "hardware_reference",
            hid,
            hid,
            "error",
            "Orphaned hardware reference",
            uses_list(hw_refs.get(hid, [])),
            True,
        )

    missing_cues = sorted(k for k in cue_refs.keys() if k and k not in valid_cues)
    for cid in missing_cues:
        add_item(
            "cue_reference",
            cid,
            cid,
            "error",
            "Orphaned cue reference in rules",
            uses_list(cue_refs.get(cid, [])),
            True,
        )

    return {
        "items": report_items,
        "missingHw": set(missing_hw),
        "missingCues": set(missing_cues),
        "invalidCueIds": {x for x in invalid_cue_ids if x},
        "validHw": valid_hw,
        "validTargets": valid_targets,
        "validLcdIds": set(lcd_device_ids),
    }
