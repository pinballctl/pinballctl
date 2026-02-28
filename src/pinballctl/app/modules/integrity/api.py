"""Integrity report + cleanup API for cross-module references."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from flask import current_app, jsonify, request
from pinballctl.app.modules.rules import api as rules_api
from pinballctl.app.modules.lighting import api as lighting_api

from . import api_bp


@dataclass
class RefUsage:
    module: str
    detail: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _instance_dir() -> Path:
    return Path(current_app.instance_path)


def _path(*parts: str) -> Path:
    return _instance_dir().joinpath(*parts)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def _rebuild_rules_artifacts(paths: Dict[str, Path], changes: List[Dict[str, Any]]) -> None:
    rules_path = paths["rules"]
    blob = rules_api._build_rules_pd_from_path(rules_path)
    rules_pd_path = rules_api._rules_pd_path()
    rules_pd_path.write_bytes(blob)
    rules_api._write_rules_meta(blob)
    changes.append(
        {
            "file": str(rules_pd_path),
            "change": "rebuild_rules_artifact",
            "bytes": len(blob),
        }
    )


def _rebuild_lighting_artifacts(paths: Dict[str, Path], changes: List[Dict[str, Any]]) -> None:
    _, meta = lighting_api._compile_lighting_outputs()
    lighting_pd_path = lighting_api._lighting_pd_path()
    changes.append(
        {
            "file": str(lighting_pd_path),
            "change": "rebuild_lighting_artifact",
            "bytes": int(meta.get("size") or 0),
            "sha256": str(meta.get("sha256") or ""),
        }
    )


def _is_hardware_uid(value: Any) -> bool:
    s = str(value or "").strip()
    return "__" in s and "GPIO" in s


def _issue_key(kind: str, ident: str) -> str:
    return f"{str(kind or '').strip()}:{str(ident or '').strip()}"


def _selected_issue_set(selected: Any) -> Optional[Set[str]]:
    if selected is None:
        return None
    if isinstance(selected, str):
        s = selected.strip()
        return {s} if s else set()
    if isinstance(selected, list):
        out = {str(x).strip() for x in selected if str(x).strip()}
        return out
    return set()


def _component_mapping_data(raw_mapping: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    data = raw_mapping.get("data") if isinstance(raw_mapping, dict) else None
    if not isinstance(data, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for uid, row in data.items():
        if not isinstance(row, dict):
            continue
        friendly = str(row.get("friendly") or "").strip()
        fn = str(row.get("function") or "").strip()
        purpose = str(row.get("purpose") or "").strip()
        if friendly or fn or purpose:
            out[str(uid)] = row
    return out


def _collect_refs(
    rules: List[Dict[str, Any]],
    playfield: Dict[str, Any],
    lighting: Dict[str, Any],
    scoring: Dict[str, Any],
) -> Tuple[Dict[str, List[RefUsage]], Dict[str, List[RefUsage]]]:
    hw_refs: Dict[str, List[RefUsage]] = {}
    cue_refs: Dict[str, List[RefUsage]] = {}

    def add_ref(ref_map: Dict[str, List[RefUsage]], key: Any, module: str, detail: str) -> None:
        k = str(key or "").strip()
        if not k:
            return
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
    assets: List[Dict[str, Any]],
    cues: List[Dict[str, Any]],
    hw_refs: Dict[str, List[RefUsage]],
    cue_refs: Dict[str, List[RefUsage]],
    asset_refs: Dict[str, List[RefUsage]],
) -> Dict[str, Any]:
    valid_hw = set(component_map.keys())
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

    missing_hw = sorted(k for k in hw_refs.keys() if k and k not in valid_hw)
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
    }


def _report_and_cleanup(apply_changes: bool = False, selected_issues: Optional[Set[str]] = None) -> Dict[str, Any]:
    paths = {
        "hardware": _path("hardware", "mapping.json"),
        "rules": _path("rules", "rules.json"),
        "playfield": _path("playfield", "layout.json"),
        "lighting": _path("lighting", "lighting.json"),
        "audio": _path("audio", "audio.json"),
        "scoring": _path("scoring", "scoring.json"),
    }

    hardware_raw = _read_json(paths["hardware"], {"data": {}})
    rules = _read_json(paths["rules"], [])
    playfield = _read_json(paths["playfield"], {"elements": [], "keymap": {}})
    lighting = _read_json(paths["lighting"], {"fixtures": {}, "scenes": []})
    audio_cfg = _read_json(paths["audio"], {"assets": [], "cues": []})
    scoring = _read_json(paths["scoring"], {"basePoints": [], "scoreRules": [], "combos": []})

    if not isinstance(rules, list):
        rules = []
    if not isinstance(playfield, dict):
        playfield = {"elements": [], "keymap": {}}
    if not isinstance(lighting, dict):
        lighting = {"fixtures": {}, "scenes": []}
    if not isinstance(audio_cfg, dict):
        audio_cfg = {"assets": [], "cues": []}
    if not isinstance(scoring, dict):
        scoring = {"basePoints": [], "scoreRules": [], "combos": []}

    component_map = _component_mapping_data(hardware_raw)
    assets = [a for a in (audio_cfg.get("assets") or []) if isinstance(a, dict)]
    cues = [c for c in (audio_cfg.get("cues") or []) if isinstance(c, dict)]
    hw_refs, cue_refs = _collect_refs(rules, playfield, lighting, scoring)
    asset_refs = _collect_asset_refs(audio_cfg)

    report = _build_report(component_map, assets, cues, hw_refs, cue_refs, asset_refs)
    report_items = report["items"]
    valid_hw = report["validHw"]
    missing_hw = report["missingHw"]
    missing_cues = report["missingCues"]
    invalid_cue_ids = report["invalidCueIds"]

    changes: List[Dict[str, Any]] = []

    if apply_changes:
        sel = selected_issues

        def selected(kind: str, ident: str) -> bool:
            key = _issue_key(kind, ident)
            return sel is None or key in sel

        target_hw_ids = {hid for hid in missing_hw if selected("hardware_reference", hid)}
        target_cue_refs = {cid for cid in missing_cues if selected("cue_reference", cid)}
        target_invalid_cues = {cid for cid in invalid_cue_ids if selected("audio_cue", cid)}
        target_cues_for_rules = set(target_cue_refs) | set(target_invalid_cues)

        if target_invalid_cues:
            before = len(cues)
            audio_cfg["cues"] = [c for c in cues if str(c.get("id") or "").strip() not in target_invalid_cues]
            after = len(audio_cfg["cues"])
            if after != before:
                changes.append({"file": str(paths["audio"]), "change": "remove_orphan_cues", "count": before - after})
            cues = [c for c in (audio_cfg.get("cues") or []) if isinstance(c, dict)]

        valid_cues_after = {str(c.get("id") or "").strip() for c in cues if str(c.get("id") or "").strip()}

        def should_remove_hw_ref(uid: str) -> bool:
            u = str(uid or "").strip()
            if not u or u in valid_hw:
                return False
            if sel is None:
                return True
            return u in target_hw_ids

        def should_remove_cue_ref(cid: str) -> bool:
            c = str(cid or "").strip()
            if not c:
                return False
            if c in valid_cues_after:
                return False
            if sel is None:
                return True
            return c in target_cues_for_rules

        cleaned_rules: List[Dict[str, Any]] = []
        removed_actions = 0
        removed_triggers = 0

        for rule in rules:
            if not isinstance(rule, dict):
                continue
            r = dict(rule)

            def action_ok(action: Dict[str, Any]) -> bool:
                nonlocal removed_actions
                atype = str(action.get("type") or "").strip().lower()
                params = action.get("params") if isinstance(action.get("params"), dict) else {}
                target = action.get("target")
                if atype in ("set_output", "pulse", "set_lcd_text"):
                    candidate = str(target or params.get("device") or params.get("target") or "").strip()
                    if should_remove_hw_ref(candidate):
                        removed_actions += 1
                        return False
                if atype in ("play_audio_cue", "stop_audio_cue", "toggle_audio_cue"):
                    cue_id = str(params.get("cueId") or target or "").strip()
                    if should_remove_cue_ref(cue_id):
                        removed_actions += 1
                        return False
                return True

            def trig_ok(item: Dict[str, Any]) -> bool:
                nonlocal removed_triggers
                if str(item.get("type") or "").strip().lower() != "hardware":
                    return True
                source = str(item.get("source") or "").strip()
                if should_remove_hw_ref(source):
                    removed_triggers += 1
                    return False
                return True

            r["actions"] = [a for a in (r.get("actions") or []) if isinstance(a, dict) and action_ok(a)]
            r["triggers"] = [t for t in (r.get("triggers") or []) if isinstance(t, dict) and trig_ok(t)]

            tgroups = r.get("triggerGroups") if isinstance(r.get("triggerGroups"), dict) else {"logic": "ALL", "groups": []}
            groups_out = []
            for g in tgroups.get("groups") or []:
                if not isinstance(g, dict):
                    continue
                gg = dict(g)
                gg["items"] = [it for it in (g.get("items") or []) if isinstance(it, dict) and trig_ok(it)]
                groups_out.append(gg)
            tgroups["groups"] = groups_out
            r["triggerGroups"] = tgroups
            cleaned_rules.append(r)

        if removed_actions or removed_triggers:
            changes.append(
                {
                    "file": str(paths["rules"]),
                    "change": "remove_orphan_references",
                    "removedActions": removed_actions,
                    "removedTriggers": removed_triggers,
                }
            )
        rules = cleaned_rules

        removed_playfield = 0
        removed_keymap = 0
        elements = playfield.get("elements") if isinstance(playfield.get("elements"), list) else []
        keep_elements = []
        removed_ids = set()
        for el in elements:
            if not isinstance(el, dict):
                continue
            hid = str(el.get("hardwareId") or "").strip()
            eid = str(el.get("id") or "").strip()
            candidate = hid or eid
            if candidate and _is_hardware_uid(candidate) and should_remove_hw_ref(candidate):
                removed_playfield += 1
                removed_ids.add(eid or candidate)
                continue
            keep_elements.append(el)
        playfield["elements"] = keep_elements

        keymap = playfield.get("keymap") if isinstance(playfield.get("keymap"), dict) else {}
        keymap_out = {}
        for k, row in keymap.items():
            if isinstance(row, dict):
                rid = str(row.get("id") or "").strip()
                if rid and rid in removed_ids:
                    removed_keymap += 1
                    continue
            keymap_out[k] = row
        playfield["keymap"] = keymap_out
        if removed_playfield or removed_keymap:
            changes.append(
                {
                    "file": str(paths["playfield"]),
                    "change": "remove_orphan_hardware",
                    "removedElements": removed_playfield,
                    "removedKeymap": removed_keymap,
                }
            )

        fixtures = lighting.get("fixtures") if isinstance(lighting.get("fixtures"), dict) else {}
        removed_fixture_ids = [fid for fid in list(fixtures.keys()) if should_remove_hw_ref(fid)]
        for fid in removed_fixture_ids:
            fixtures.pop(fid, None)
        lighting["fixtures"] = fixtures

        removed_scene_cast = 0
        removed_scene_timeline = 0
        scenes = lighting.get("scenes") if isinstance(lighting.get("scenes"), list) else []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            cast = scene.get("cast") if isinstance(scene.get("cast"), list) else []
            new_cast = []
            for fid in cast:
                if fid in removed_fixture_ids:
                    removed_scene_cast += 1
                    continue
                new_cast.append(fid)
            scene["cast"] = new_cast

            timeline = scene.get("timeline") if isinstance(scene.get("timeline"), list) else []
            new_timeline = []
            for frame in timeline:
                if not isinstance(frame, dict):
                    continue
                fid = str(frame.get("fixtureId") or "").strip()
                if fid in removed_fixture_ids:
                    removed_scene_timeline += 1
                    continue
                new_timeline.append(frame)
            scene["timeline"] = new_timeline
        lighting["scenes"] = scenes

        if removed_fixture_ids or removed_scene_cast or removed_scene_timeline:
            changes.append(
                {
                    "file": str(paths["lighting"]),
                    "change": "remove_orphan_fixture_refs",
                    "removedFixtures": len(removed_fixture_ids),
                    "removedSceneCast": removed_scene_cast,
                    "removedSceneTimeline": removed_scene_timeline,
                }
            )

        removed_bp = 0
        removed_sr = 0
        removed_combo_steps = 0
        removed_combos = 0

        bp_rows = scoring.get("basePoints") if isinstance(scoring.get("basePoints"), list) else []
        sr_rows = scoring.get("scoreRules") if isinstance(scoring.get("scoreRules"), list) else []
        combos = scoring.get("combos") if isinstance(scoring.get("combos"), list) else []

        new_bp = []
        for row in bp_rows:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source") or "").strip()
            if source and should_remove_hw_ref(source):
                removed_bp += 1
                continue
            new_bp.append(row)
        scoring["basePoints"] = new_bp

        new_sr = []
        for row in sr_rows:
            if not isinstance(row, dict):
                continue
            source = str(row.get("source") or "").strip()
            if source and should_remove_hw_ref(source):
                removed_sr += 1
                continue
            new_sr.append(row)
        scoring["scoreRules"] = new_sr

        new_combos = []
        for combo in combos:
            if not isinstance(combo, dict):
                continue
            steps = combo.get("steps") if isinstance(combo.get("steps"), list) else []
            keep_steps = []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                source = str(step.get("source") or "").strip()
                if source and should_remove_hw_ref(source):
                    removed_combo_steps += 1
                    continue
                keep_steps.append(step)
            combo["steps"] = keep_steps
            if not keep_steps:
                removed_combos += 1
                continue
            new_combos.append(combo)
        scoring["combos"] = new_combos

        if removed_bp or removed_sr or removed_combo_steps or removed_combos:
            changes.append(
                {
                    "file": str(paths["scoring"]),
                    "change": "remove_orphan_hardware_refs",
                    "removedBasePoints": removed_bp,
                    "removedScoreRules": removed_sr,
                    "removedComboSteps": removed_combo_steps,
                    "removedCombos": removed_combos,
                }
            )

        if changes:
            audio_cfg["updatedAt"] = _now_iso()
            playfield["updatedAt"] = _now_iso()
            lighting["updatedAt"] = _now_iso()
            scoring["updatedAt"] = _now_iso()

            _write_json(paths["audio"], audio_cfg)
            _write_json(paths["rules"], rules)
            _write_json(paths["playfield"], playfield)
            _write_json(paths["lighting"], lighting)
            _write_json(paths["scoring"], scoring)

            changed_files = {str(c.get("file") or "") for c in changes}
            try:
                if str(paths["rules"]) in changed_files:
                    _rebuild_rules_artifacts(paths, changes)
                if str(paths["lighting"]) in changed_files:
                    _rebuild_lighting_artifacts(paths, changes)
            except Exception as exc:
                current_app.logger.exception("Integrity cleanup artifact rebuild failed")
                changes.append(
                    {
                        "change": "artifact_rebuild_failed",
                        "error": str(exc),
                    }
                )

    status_counts = {
        "ok": sum(1 for x in report_items if x.get("status") == "ok"),
        "error": sum(1 for x in report_items if x.get("status") == "error"),
        "warning": sum(1 for x in report_items if x.get("status") == "warning"),
    }

    return {
        "ok": True,
        "generatedAt": _now_iso(),
        "apply": bool(apply_changes),
        "stats": {
            "total": len(report_items),
            **status_counts,
        },
        "items": report_items,
        "changes": changes,
    }


def _post_apply_with_fresh_report(result: Dict[str, Any]) -> Dict[str, Any]:
    fresh = _report_and_cleanup(apply_changes=False)
    fresh["apply"] = True
    fresh["changes"] = result.get("changes", [])
    return fresh


@api_bp.get("/report")
def integrity_report():
    return jsonify(_report_and_cleanup(apply_changes=False))


@api_bp.post("/cleanup")
def integrity_cleanup():
    body = request.get_json(silent=True) or {}
    apply_changes = bool(body.get("apply", True))
    selected = _selected_issue_set(body.get("selectedIssues"))
    result = _report_and_cleanup(apply_changes=apply_changes, selected_issues=selected)
    if apply_changes:
        result = _post_apply_with_fresh_report(result)
    return jsonify(result)


@api_bp.post("/cleanup-item")
def integrity_cleanup_item():
    body = request.get_json(silent=True) or {}
    issue_key = str(body.get("issueKey") or "").strip()
    kind = str(body.get("kind") or "").strip()
    ident = str(body.get("id") or "").strip()
    if issue_key:
        selected = {issue_key}
    else:
        if not kind or not ident:
            return jsonify({"ok": False, "error": "missing_issue_key_or_kind_id"}), 400
        selected = {_issue_key(kind, ident)}
    result = _report_and_cleanup(apply_changes=True, selected_issues=selected)
    result = _post_apply_with_fresh_report(result)
    return jsonify(result)
