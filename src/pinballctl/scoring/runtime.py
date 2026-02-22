"""Pi-side scoring runtime and persistence."""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from queue import Empty
from threading import Event, Lock, Thread
from typing import Any, Callable, Dict, List
from uuid import uuid4

from pinballctl.bridge.state import command_socket_path, enqueue_command, rpc_socket_path
from pinballctl.events import EventContext, get_bus, get_event_manager
from pinballctl.events.audit_log import append_event_log


_CFG_LOCK = Lock()
_STATE_LOCK = Lock()
_BRIDGE_ENQUEUE_LOCK = Lock()
_BRIDGE_ENQUEUE_SKIP_UNTIL_MONO = 0.0
_BUS_WORKER_LOCK = Lock()
_BUS_WORKERS: Dict[str, Dict[str, Any]] = {}


def _bridge_enqueue_ready() -> bool:
    """True when at least one bridge unix socket is immediately connectable."""
    for p in (command_socket_path(), rpc_socket_path()):
        if not p.exists():
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.02)
                s.connect(str(p))
            return True
        except Exception:
            continue
    return False


def _worker_log(logger: Callable[[str], None] | None, msg: str) -> None:
    if logger is None:
        return
    try:
        logger(msg)
    except Exception:
        pass


def ensure_scoring_bus_worker(
    instance_path: str | Path,
    logger: Callable[[str], None] | None = None,
) -> None:
    """Start one scoring worker per instance path in this process.

    The worker subscribes to the in-process EventBus and runs scoring
    sequentially in receive order for that process.
    """
    inst = str(Path(instance_path).resolve())
    with _BUS_WORKER_LOCK:
        existing = _BUS_WORKERS.get(inst)
        if isinstance(existing, dict):
            t = existing.get("thread")
            if isinstance(t, Thread) and t.is_alive():
                return
        stop_evt = Event()
        worker = Thread(
            target=_scoring_bus_loop,
            kwargs={"instance_path": inst, "stop_evt": stop_evt, "logger": logger},
            daemon=True,
            name=f"scoring-bus-{Path(inst).name}",
        )
        _BUS_WORKERS[inst] = {"thread": worker, "stop_evt": stop_evt}
        worker.start()
    _worker_log(logger, f"scoring bus worker started instance={inst}")


def _scoring_bus_loop(
    *,
    instance_path: str,
    stop_evt: Event,
    logger: Callable[[str], None] | None = None,
) -> None:
    bus = get_bus()
    q = bus.subscribe()
    try:
        while not stop_evt.is_set():
            try:
                ev = q.get(timeout=0.5)
            except Empty:
                continue
            try:
                process_event(
                    instance_path,
                    name=ev.name,
                    source=ev.source,
                    params=ev.params,
                    origin="bus",
                )
            except Exception as exc:
                _worker_log(logger, f"scoring bus processing failed: {exc}")
    finally:
        bus.unsubscribe(q)


def _scoring_dir(instance_path: str | Path) -> Path:
    p = Path(instance_path) / "scoring"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _config_path(instance_path: str | Path) -> Path:
    return _scoring_dir(instance_path) / "scoring.json"


def _state_path(instance_path: str | Path) -> Path:
    return _scoring_dir(instance_path) / "state.json"


def _high_scores_path(instance_path: str | Path) -> Path:
    return _scoring_dir(instance_path) / "high_scores.json"


def _history_path(instance_path: str | Path) -> Path:
    return _scoring_dir(instance_path) / "history.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _to_int(value: Any, default: int = 0, minimum: int | None = None, maximum: int | None = None) -> int:
    try:
        v = int(value)
    except Exception:
        v = int(default)
    if minimum is not None and v < minimum:
        v = minimum
    if maximum is not None and v > maximum:
        v = maximum
    return v


def _to_float(value: Any, default: float = 0.0, minimum: float | None = None, maximum: float | None = None) -> float:
    try:
        v = float(value)
    except Exception:
        v = float(default)
    if minimum is not None and v < minimum:
        v = minimum
    if maximum is not None and v > maximum:
        v = maximum
    return v


def default_scoring_config() -> Dict[str, Any]:
    return {
        "_version": 2,
        "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "settings": {
            "enabled": True,
            "emitEvents": True,
            "scoreEvent": "SCORE_CHANGED",
            "comboEvent": "SCORE_COMBO_HIT",
            "multiplierEvent": "SCORE_MULTIPLIER_CHANGED",
        },
        "basePoints": [],
        "scoreRules": [],
        "combos": [],
    }


def _default_state() -> Dict[str, Any]:
    return {
        "_version": 2,
        "updatedAtMs": _now_ms(),
        "score": 0,
        "game": {
            "active": False,
            "gameId": "",
            "startedAtMs": 0,
            "endedAtMs": 0,
        },
        "activeMultiplier": {"value": 1.0, "untilMs": 0, "sourceComboId": ""},
        "comboHits": 0,
        "comboState": {},
        "scoreRuleState": {},
        "lastAward": None,
    }


def _default_high_scores() -> Dict[str, Any]:
    return {
        "_version": 1,
        "updatedAtMs": _now_ms(),
        "scores": [],
    }


def _append_game_history(instance_path: str | Path, entry: Dict[str, Any], limit: int = 200) -> None:
    history = _read_json(_history_path(instance_path), {"_version": 1, "updatedAtMs": _now_ms(), "games": []})
    games = history.get("games") if isinstance(history, dict) and isinstance(history.get("games"), list) else []
    games.append(entry)
    if len(games) > limit:
        games = games[-limit:]
    payload = {"_version": 1, "updatedAtMs": _now_ms(), "games": games}
    _write_json(_history_path(instance_path), payload)


def _record_high_score(instance_path: str | Path, entry: Dict[str, Any], limit: int = 25) -> Dict[str, Any]:
    high = _read_json(_high_scores_path(instance_path), _default_high_scores())
    scores = high.get("scores") if isinstance(high, dict) and isinstance(high.get("scores"), list) else []
    scores.append(entry)
    scores = [s for s in scores if isinstance(s, dict)]
    scores.sort(key=lambda s: int(s.get("score", 0)), reverse=True)
    if len(scores) > limit:
        scores = scores[:limit]
    payload = {
        "_version": 1,
        "updatedAtMs": _now_ms(),
        "scores": scores,
    }
    _write_json(_high_scores_path(instance_path), payload)
    return payload


def _normalize_base_points(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        event_type = str(row.get("eventType") or "").strip().upper()
        event_name = str(row.get("eventName") or "").strip().upper()
        mode = str(row.get("mode") or "").strip().lower()
        if mode not in ("hardware", "event"):
            mode = "hardware" if source else ("event" if event_name else "hardware")
        points = _to_int(row.get("points"), default=0)
        note = str(row.get("note") or "").strip()
        if not source and not event_name and not event_type and not points and not note:
            continue
        enabled_raw = bool(row.get("enabled", True))
        enabled = enabled_raw and bool(source or event_name)
        out.append(
            {
                "id": str(row.get("id") or uuid4().hex),
                "enabled": enabled,
                "mode": mode,
                "source": source,
                "eventType": event_type,
                "eventName": event_name,
                "points": points,
                "note": note,
            }
        )
    return out


def _normalize_score_rules(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source") or "").strip()
        event_name = str(row.get("eventName") or "").strip().upper()
        event_type = str(row.get("eventType") or "").strip().upper()
        mode = str(row.get("mode") or "").strip().lower()
        if mode not in ("hardware", "event"):
            mode = "hardware" if source else ("event" if event_name else "hardware")
        row_name = str(row.get("name") or "Rule").strip() or "Rule"
        base_points = _to_int(row.get("basePoints"), default=10)
        points_per_hit = _to_int(row.get("pointsPerHit"), default=0)
        has_any = bool(source or event_name or event_type or row_name or base_points or points_per_hit)
        if not has_any:
            continue
        enabled_raw = bool(row.get("enabled", True))
        enabled = enabled_raw and bool(source or event_name)
        out.append(
            {
                "id": str(row.get("id") or uuid4().hex),
                "name": row_name,
                "enabled": enabled,
                "mode": mode,
                "source": source,
                "eventType": event_type,
                "eventName": event_name,
                "minHits": _to_int(row.get("minHits"), default=1, minimum=1, maximum=10000),
                "minHitsWithinMs": _to_int(row.get("minHitsWithinMs"), default=0, minimum=0, maximum=600000),
                "basePoints": base_points,
                "pointsPerHit": points_per_hit,
                "maxBonusHits": _to_int(row.get("maxBonusHits"), default=0, minimum=0, maximum=10000),
                "cooloffMs": _to_int(row.get("cooloffMs"), default=0, minimum=0, maximum=600000),
                "cooloffStep": _to_int(row.get("cooloffStep"), default=1, minimum=1, maximum=1000),
                "emitEvent": str(row.get("emitEvent") or "").strip().upper(),
                "note": str(row.get("note") or "").strip(),
            }
        )
    return out


def _normalize_combo_step(step: Any) -> Dict[str, Any] | None:
    if not isinstance(step, dict):
        return None
    source = str(step.get("source") or "").strip()
    event_type = str(step.get("eventType") or "").strip().upper()
    event_name = str(step.get("eventName") or "").strip().upper()
    if not source and not event_type and not event_name:
        return None
    return {
        "id": str(step.get("id") or uuid4().hex),
        "source": source,
        "eventType": event_type,
        "eventName": event_name,
    }


def _normalize_combos(rows: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        steps_in = row.get("steps") if isinstance(row.get("steps"), list) else []
        steps = [s for s in (_normalize_combo_step(s) for s in steps_in) if s]
        if not steps:
            continue
        mode = str(row.get("mode") or "ordered").strip().lower()
        if mode not in ("ordered", "any"):
            mode = "ordered"
        out.append(
            {
                "id": str(row.get("id") or uuid4().hex),
                "name": str(row.get("name") or "Combo").strip() or "Combo",
                "enabled": bool(row.get("enabled", True)),
                "mode": mode,
                "windowMs": _to_int(row.get("windowMs"), default=3000, minimum=100, maximum=120000),
                "awardPoints": _to_int(row.get("awardPoints"), default=0),
                "multiplierValue": _to_float(row.get("multiplierValue"), default=1.0, minimum=1.0, maximum=100.0),
                "multiplierDurationMs": _to_int(row.get("multiplierDurationMs"), default=0, minimum=0, maximum=600000),
                "emitEvent": str(row.get("emitEvent") or "").strip().upper(),
                "steps": steps,
            }
        )
    return out


def _normalize_config(config: Dict[str, Any]) -> Dict[str, Any]:
    out = default_scoring_config()
    settings_in = config.get("settings") if isinstance(config.get("settings"), dict) else {}
    out["settings"] = {
        "enabled": bool(settings_in.get("enabled", True)),
        "emitEvents": bool(settings_in.get("emitEvents", True)),
        "scoreEvent": str(settings_in.get("scoreEvent") or "SCORE_CHANGED").strip().upper() or "SCORE_CHANGED",
        "comboEvent": str(settings_in.get("comboEvent") or "SCORE_COMBO_HIT").strip().upper() or "SCORE_COMBO_HIT",
        "multiplierEvent": str(settings_in.get("multiplierEvent") or "SCORE_MULTIPLIER_CHANGED").strip().upper() or "SCORE_MULTIPLIER_CHANGED",
    }

    legacy_base = config.get("baseScores") if isinstance(config.get("baseScores"), list) else []
    base_in = config.get("basePoints") if isinstance(config.get("basePoints"), list) else legacy_base
    out["basePoints"] = _normalize_base_points(base_in)

    rules_in = config.get("scoreRules") if isinstance(config.get("scoreRules"), list) else []
    out["scoreRules"] = _normalize_score_rules(rules_in)

    out["combos"] = _normalize_combos(config.get("combos"))
    out["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return out


def load_scoring_config(instance_path: str | Path) -> Dict[str, Any]:
    with _CFG_LOCK:
        raw = _read_json(_config_path(instance_path), default_scoring_config())
        if not isinstance(raw, dict):
            return default_scoring_config()
        return _normalize_config(raw)


def save_scoring_config(instance_path: str | Path, config: Dict[str, Any]) -> Dict[str, Any]:
    normalized = _normalize_config(config if isinstance(config, dict) else {})
    with _CFG_LOCK:
        _write_json(_config_path(instance_path), normalized)
    return normalized


def load_scoring_state(instance_path: str | Path) -> Dict[str, Any]:
    with _STATE_LOCK:
        raw = _read_json(_state_path(instance_path), _default_state())
        if not isinstance(raw, dict):
            raw = _default_state()
        raw.setdefault("score", 0)
        raw.setdefault("game", {"active": False, "gameId": "", "startedAtMs": 0, "endedAtMs": 0})
        raw.setdefault("comboHits", 0)
        raw.setdefault("activeMultiplier", {"value": 1.0, "untilMs": 0, "sourceComboId": ""})
        raw.setdefault("comboState", {})
        raw.setdefault("scoreRuleState", {})
        raw.setdefault("lastAward", None)
        raw.setdefault("updatedAtMs", _now_ms())
        return raw


def reset_scoring_state(instance_path: str | Path) -> Dict[str, Any]:
    state = _default_state()
    with _STATE_LOCK:
        _write_json(_state_path(instance_path), state)
    return state


def load_high_scores(instance_path: str | Path) -> Dict[str, Any]:
    data = _read_json(_high_scores_path(instance_path), _default_high_scores())
    if not isinstance(data, dict):
        data = _default_high_scores()
    data.setdefault("scores", [])
    data.setdefault("updatedAtMs", _now_ms())
    return data


def load_game_history(instance_path: str | Path) -> Dict[str, Any]:
    data = _read_json(_history_path(instance_path), {"_version": 1, "updatedAtMs": _now_ms(), "games": []})
    if not isinstance(data, dict):
        data = {"_version": 1, "updatedAtMs": _now_ms(), "games": []}
    data.setdefault("games", [])
    data.setdefault("updatedAtMs", _now_ms())
    return data


def _event_type_from(name: str, params: Dict[str, Any]) -> str:
    raw = params.get("eventType")
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()
    return name.strip().upper()


def _match_source_event(rule: Dict[str, Any], *, source: str | None, event_type: str, event_name: str) -> bool:
    r_source = str(rule.get("source") or "").strip()
    r_type = str(rule.get("eventType") or "").strip().upper()
    r_name = str(rule.get("eventName") or "").strip().upper()
    if r_source and r_source != (source or ""):
        return False
    if r_type and r_type != event_type:
        return False
    if r_name and r_name != event_name:
        return False
    return True


def _emit_runtime_event(instance_path: str | Path, *, name: str, params: Dict[str, Any]) -> None:
    envelope = get_bus().emit(name=name, source="pi.scoring", params=params)
    try:
        mgr = get_event_manager(instance_path=str(instance_path))
        mgr.dispatch(
            EventContext(
                id=envelope.id,
                ts=envelope.ts,
                name=envelope.name,
                source=envelope.source,
                params=envelope.params,
                origin="scoring",
            )
        )
    except Exception:
        pass
    try:
        global _BRIDGE_ENQUEUE_SKIP_UNTIL_MONO  # noqa: PLW0603
        now = time.monotonic()
        with _BRIDGE_ENQUEUE_LOCK:
            skip_until = float(_BRIDGE_ENQUEUE_SKIP_UNTIL_MONO or 0.0)
        if now >= skip_until:
            # Avoid enqueue_commands startup wait when bridge daemon is down.
            # If no bridge sockets exist, skip immediately and back off.
            if not _bridge_enqueue_ready():
                with _BRIDGE_ENQUEUE_LOCK:
                    _BRIDGE_ENQUEUE_SKIP_UNTIL_MONO = time.monotonic() + 2.0
                return
            try:
                enqueue_command(
                    {
                        "cmd": "EVENT_FIRE",
                        "name": name,
                        "source": "pi.scoring",
                        "seq": _now_ms(),
                        "params": params,
                    }
                )
            except Exception:
                with _BRIDGE_ENQUEUE_LOCK:
                    _BRIDGE_ENQUEUE_SKIP_UNTIL_MONO = time.monotonic() + 2.0
    except Exception:
        pass
    try:
        append_event_log(
            origin="scoring",
            direction="pi->esp",
            name=name,
            source="pi.scoring",
            params=params,
            meta={"event_id": envelope.id},
        )
    except Exception:
        pass


def _active_multiplier_value(state: Dict[str, Any], now_ms: int) -> float:
    active = state.get("activeMultiplier") if isinstance(state.get("activeMultiplier"), dict) else {}
    value = _to_float(active.get("value"), default=1.0, minimum=1.0)
    until_ms = _to_int(active.get("untilMs"), default=0)
    if value > 1.0 and until_ms > now_ms:
        return value
    return 1.0


def _step_matches(step: Dict[str, Any], *, source: str | None, event_type: str, event_name: str) -> bool:
    s_source = str(step.get("source") or "").strip()
    s_type = str(step.get("eventType") or "").strip().upper()
    s_name = str(step.get("eventName") or "").strip().upper()
    if s_source and s_source != (source or ""):
        return False
    if s_type and s_type != event_type:
        return False
    if s_name and s_name != event_name:
        return False
    return True


def _apply_cooloff(rule: Dict[str, Any], rstate: Dict[str, Any], now_ms: int) -> None:
    cooloff_ms = _to_int(rule.get("cooloffMs"), default=0, minimum=0)
    if cooloff_ms <= 0:
        return
    step = _to_int(rule.get("cooloffStep"), default=1, minimum=1)
    last_at = _to_int(rstate.get("lastHitAtMs"), default=0)
    if last_at <= 0 or now_ms <= last_at:
        return
    elapsed = now_ms - last_at
    ticks = elapsed // cooloff_ms
    if ticks <= 0:
        return
    drop = int(ticks) * step
    rstate["hitCount"] = max(0, _to_int(rstate.get("hitCount"), default=0) - drop)


def process_event(
    instance_path: str | Path,
    *,
    name: str,
    source: str | None,
    params: Dict[str, Any] | None,
    origin: str = "runtime",
) -> Dict[str, Any]:
    """Apply scoring config for one event and persist updated runtime state."""
    cfg = load_scoring_config(instance_path)
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    if not settings.get("enabled", True):
        return {"ok": True, "processed": False, "reason": "disabled"}
    if (source or "") == "pi.scoring":
        return {"ok": True, "processed": False, "reason": "scoring_source"}

    payload = params if isinstance(params, dict) else {}
    now_ms = _now_ms()
    event_name = str(name or "").strip().upper()
    event_type = _event_type_from(event_name, payload)

    with _STATE_LOCK:
        state = _read_json(_state_path(instance_path), _default_state())
        if not isinstance(state, dict):
            state = _default_state()
        state.setdefault("score", 0)
        state.setdefault("game", {"active": False, "gameId": "", "startedAtMs": 0, "endedAtMs": 0})
        state.setdefault("comboHits", 0)
        state.setdefault("activeMultiplier", {"value": 1.0, "untilMs": 0, "sourceComboId": ""})
        state.setdefault("comboState", {})
        state.setdefault("scoreRuleState", {})
        state.setdefault("lastAward", None)
        state.setdefault("updatedAtMs", now_ms)
        game = state.get("game") if isinstance(state.get("game"), dict) else {}
        game.setdefault("active", False)
        game.setdefault("gameId", "")
        game.setdefault("startedAtMs", 0)
        game.setdefault("endedAtMs", 0)
        state["game"] = game

        # Session lifecycle events: make scoring state explicit and durable.
        if event_name == "GAME_STARTED":
            state["score"] = 0
            state["comboHits"] = 0
            state["activeMultiplier"] = {"value": 1.0, "untilMs": 0, "sourceComboId": ""}
            state["comboState"] = {}
            state["scoreRuleState"] = {}
            state["lastAward"] = None
            state["game"] = {
                "active": True,
                "gameId": str(payload.get("gameId") or uuid4().hex),
                "startedAtMs": now_ms,
                "endedAtMs": 0,
            }
            state["updatedAtMs"] = now_ms
            _write_json(_state_path(instance_path), state)
            return {
                "ok": True,
                "processed": True,
                "score": 0,
                "awards": [],
                "comboHits": [],
                "multiplier": state.get("activeMultiplier"),
                "game": state.get("game"),
            }
        if event_name == "GAME_ENDED":
            state["game"] = {
                "active": False,
                "gameId": str(game.get("gameId") or ""),
                "startedAtMs": _to_int(game.get("startedAtMs"), default=0),
                "endedAtMs": now_ms,
            }
            state["updatedAtMs"] = now_ms
            _write_json(_state_path(instance_path), state)
            final_entry = {
                "gameId": state["game"]["gameId"] or uuid4().hex,
                "score": _to_int(state.get("score"), default=0),
                "comboHits": _to_int(state.get("comboHits"), default=0),
                "startedAtMs": _to_int(state["game"].get("startedAtMs"), default=0),
                "endedAtMs": now_ms,
                "durationMs": max(0, now_ms - _to_int(state["game"].get("startedAtMs"), default=now_ms)),
                "source": source,
                "origin": origin,
            }
            _append_game_history(instance_path, final_entry)
            _record_high_score(instance_path, final_entry)
            return {
                "ok": True,
                "processed": True,
                "score": state.get("score", 0),
                "awards": [],
                "comboHits": [],
                "multiplier": state.get("activeMultiplier"),
                "game": state.get("game"),
            }

        active = state.get("activeMultiplier") if isinstance(state.get("activeMultiplier"), dict) else {}
        if _to_float(active.get("value"), default=1.0, minimum=1.0) > 1.0 and _to_int(active.get("untilMs"), default=0) <= now_ms:
            state["activeMultiplier"] = {"value": 1.0, "untilMs": 0, "sourceComboId": ""}

        awards: List[Dict[str, Any]] = []
        combo_hits: List[Dict[str, Any]] = []
        multiplier_events: List[Dict[str, Any]] = []

        def award_points(points: int, reason: str, combo_id: str = "", combo_name: str = "", rule_id: str = "", rule_name: str = "") -> None:
            multiplier = _active_multiplier_value(state, now_ms)
            awarded = int(round(points * multiplier))
            state["score"] = _to_int(state.get("score"), default=0) + awarded
            state["lastAward"] = {
                "atMs": now_ms,
                "reason": reason,
                "pointsBase": int(points),
                "multiplier": multiplier,
                "pointsAwarded": awarded,
                "comboId": combo_id,
                "comboName": combo_name,
                "ruleId": rule_id,
                "ruleName": rule_name,
                "source": source,
                "eventName": event_name,
                "eventType": event_type,
            }
            awards.append(dict(state["lastAward"]))

        # Base points table.
        for row in cfg.get("basePoints") if isinstance(cfg.get("basePoints"), list) else []:
            if not isinstance(row, dict) or not row.get("enabled", True):
                continue
            if not _match_source_event(row, source=source, event_type=event_type, event_name=event_name):
                continue
            pts = _to_int(row.get("points"), default=0)
            if pts:
                award_points(pts, reason="base")

        # Scoring rules table (increasing points, cooloff, min hits).
        sr_state = state.get("scoreRuleState") if isinstance(state.get("scoreRuleState"), dict) else {}
        state["scoreRuleState"] = sr_state
        for rule in cfg.get("scoreRules") if isinstance(cfg.get("scoreRules"), list) else []:
            if not isinstance(rule, dict) or not rule.get("enabled", True):
                continue
            if not _match_source_event(rule, source=source, event_type=event_type, event_name=event_name):
                continue

            rid = str(rule.get("id") or "").strip()
            if not rid:
                continue
            rname = str(rule.get("name") or rid)
            rstate = sr_state.get(rid) if isinstance(sr_state.get(rid), dict) else {
                "hitCount": 0,
                "lastHitAtMs": 0,
                "recentHits": [],
            }

            _apply_cooloff(rule, rstate, now_ms)
            rstate["hitCount"] = _to_int(rstate.get("hitCount"), default=0) + 1
            rstate["lastHitAtMs"] = now_ms

            recent = rstate.get("recentHits") if isinstance(rstate.get("recentHits"), list) else []
            recent = [h for h in recent if isinstance(h, (int, float))]
            recent.append(now_ms)
            min_window = _to_int(rule.get("minHitsWithinMs"), default=0, minimum=0)
            keep_window = max(min_window, _to_int(rule.get("cooloffMs"), default=0, minimum=0), 1000)
            cutoff = now_ms - keep_window
            recent = [int(h) for h in recent if int(h) >= cutoff]
            rstate["recentHits"] = recent

            min_hits = _to_int(rule.get("minHits"), default=1, minimum=1)
            hits_ok = _to_int(rstate.get("hitCount"), default=0) >= min_hits
            if hits_ok and min_window > 0:
                hits_in_window = sum(1 for h in recent if h >= now_ms - min_window)
                hits_ok = hits_in_window >= min_hits

            if hits_ok:
                base = _to_int(rule.get("basePoints"), default=0)
                per_hit = _to_int(rule.get("pointsPerHit"), default=0)
                max_bonus_hits = _to_int(rule.get("maxBonusHits"), default=0, minimum=0)
                bonus_hits = max(0, _to_int(rstate.get("hitCount"), default=0) - min_hits)
                if max_bonus_hits > 0:
                    bonus_hits = min(bonus_hits, max_bonus_hits)
                points = base + (bonus_hits * per_hit)
                if points:
                    award_points(points, reason="rule", rule_id=rid, rule_name=rname)
                emit_event = str(rule.get("emitEvent") or "").strip().upper()
                if emit_event and settings.get("emitEvents", True):
                    _emit_runtime_event(
                        instance_path,
                        name=emit_event,
                        params={
                            "ruleId": rid,
                            "ruleName": rname,
                            "hitCount": _to_int(rstate.get("hitCount"), default=0),
                            "score": state.get("score", 0),
                        },
                    )

            sr_state[rid] = rstate

        # Combos table.
        combo_state = state.get("comboState") if isinstance(state.get("comboState"), dict) else {}
        state["comboState"] = combo_state
        combos = cfg.get("combos") if isinstance(cfg.get("combos"), list) else []

        for combo in combos:
            if not isinstance(combo, dict) or not combo.get("enabled", True):
                continue
            combo_id = str(combo.get("id") or "").strip()
            if not combo_id:
                continue
            steps = combo.get("steps") if isinstance(combo.get("steps"), list) else []
            if not steps:
                continue

            mode = str(combo.get("mode") or "ordered").strip().lower()
            window_ms = _to_int(combo.get("windowMs"), default=3000, minimum=100)
            cstate = combo_state.get(combo_id) if isinstance(combo_state.get(combo_id), dict) else {
                "startedAtMs": 0,
                "lastAtMs": 0,
                "nextIndex": 0,
                "matched": [],
            }

            started = _to_int(cstate.get("startedAtMs"), default=0)
            if started and (now_ms - started > window_ms):
                cstate = {"startedAtMs": 0, "lastAtMs": 0, "nextIndex": 0, "matched": []}

            completed = False
            if mode == "ordered":
                idx = _to_int(cstate.get("nextIndex"), default=0, minimum=0)
                if idx >= len(steps):
                    idx = 0
                target = steps[idx] if idx < len(steps) else None
                if isinstance(target, dict) and _step_matches(target, source=source, event_type=event_type, event_name=event_name):
                    if idx == 0:
                        cstate["startedAtMs"] = now_ms
                    cstate["lastAtMs"] = now_ms
                    cstate["nextIndex"] = idx + 1
                    if _to_int(cstate.get("nextIndex"), default=0) >= len(steps):
                        completed = True
                else:
                    first = steps[0] if steps else None
                    if isinstance(first, dict) and _step_matches(first, source=source, event_type=event_type, event_name=event_name):
                        cstate["startedAtMs"] = now_ms
                        cstate["lastAtMs"] = now_ms
                        cstate["nextIndex"] = 1
                    elif _to_int(cstate.get("nextIndex"), default=0) > 0:
                        cstate = {"startedAtMs": 0, "lastAtMs": 0, "nextIndex": 0, "matched": []}
            else:
                matched = cstate.get("matched") if isinstance(cstate.get("matched"), list) else []
                matched_set = {str(x) for x in matched}
                if not matched_set:
                    cstate["startedAtMs"] = now_ms
                for step in steps:
                    if not isinstance(step, dict):
                        continue
                    sid = str(step.get("id") or "")
                    if not sid or sid in matched_set:
                        continue
                    if _step_matches(step, source=source, event_type=event_type, event_name=event_name):
                        matched_set.add(sid)
                        cstate["lastAtMs"] = now_ms
                cstate["matched"] = sorted(matched_set)
                completed = len(matched_set) >= len(steps)

            if completed:
                combo_name = str(combo.get("name") or combo_id)
                award = _to_int(combo.get("awardPoints"), default=0)
                if award:
                    award_points(award, reason="combo", combo_id=combo_id, combo_name=combo_name)
                state["comboHits"] = _to_int(state.get("comboHits"), default=0) + 1

                mult_value = _to_float(combo.get("multiplierValue"), default=1.0, minimum=1.0)
                mult_duration = _to_int(combo.get("multiplierDurationMs"), default=0, minimum=0)
                if mult_value > 1.0 and mult_duration > 0:
                    until_ms = now_ms + mult_duration
                    state["activeMultiplier"] = {
                        "value": mult_value,
                        "untilMs": until_ms,
                        "sourceComboId": combo_id,
                    }
                    multiplier_events.append(
                        {
                            "comboId": combo_id,
                            "comboName": combo_name,
                            "value": mult_value,
                            "untilMs": until_ms,
                        }
                    )

                combo_hits.append(
                    {
                        "comboId": combo_id,
                        "comboName": combo_name,
                        "mode": mode,
                        "awardPoints": award,
                        "atMs": now_ms,
                        "source": source,
                        "eventName": event_name,
                        "eventType": event_type,
                    }
                )
                cstate = {"startedAtMs": 0, "lastAtMs": 0, "nextIndex": 0, "matched": []}

            combo_state[combo_id] = cstate

        state["updatedAtMs"] = now_ms
        _write_json(_state_path(instance_path), state)

    if settings.get("emitEvents", True):
        score_event = str(settings.get("scoreEvent") or "SCORE_CHANGED").strip().upper()
        combo_event = str(settings.get("comboEvent") or "SCORE_COMBO_HIT").strip().upper()
        mult_event = str(settings.get("multiplierEvent") or "SCORE_MULTIPLIER_CHANGED").strip().upper()

        if awards and score_event:
            _emit_runtime_event(
                instance_path,
                name=score_event,
                params={
                    "score": state.get("score", 0),
                    "lastAward": awards[-1],
                },
            )

        for hit in combo_hits:
            if combo_event:
                _emit_runtime_event(instance_path, name=combo_event, params=hit)
            emit_custom = ""
            for combo in combos:
                if isinstance(combo, dict) and str(combo.get("id") or "") == str(hit.get("comboId") or ""):
                    emit_custom = str(combo.get("emitEvent") or "").strip().upper()
                    break
            if emit_custom:
                _emit_runtime_event(
                    instance_path,
                    name=emit_custom,
                    params={
                        "comboId": hit.get("comboId"),
                        "comboName": hit.get("comboName"),
                        "score": state.get("score", 0),
                    },
                )

        for evt in multiplier_events:
            if mult_event:
                _emit_runtime_event(instance_path, name=mult_event, params=evt)

    try:
        append_event_log(
            origin="scoring",
            direction="pi-local",
            name="SCORING_EVAL",
            source="pi.scoring",
            params={
                "source": source,
                "eventName": event_name,
                "eventType": event_type,
                "score": state.get("score", 0),
            },
            meta={
                "awards": len(awards),
                "combos": len(combo_hits),
                "origin": origin,
            },
        )
    except Exception:
        pass

    return {
        "ok": True,
        "processed": True,
        "score": state.get("score", 0),
        "awards": awards,
        "comboHits": combo_hits,
        "multiplier": state.get("activeMultiplier"),
    }


def list_scoring_sources(instance_path: str | Path) -> List[Dict[str, Any]]:
    mapping_path = Path(instance_path) / "hardware" / "mapping.json"
    if not mapping_path.exists():
        return []
    raw = _read_json(mapping_path, {})
    data = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), dict) else raw
    if not isinstance(data, dict):
        return []
    function_map = {
        "Button": "button",
        "Switch": "switch",
        "Accelerometer": "gyro",
        "NFC": "nfc",
        "Solenoid": "coil",
        "LED": "output",
        "RGB Strip": "led",
    }
    out: List[Dict[str, Any]] = []
    for uid, row in data.items():
        if not isinstance(uid, str) or not isinstance(row, dict):
            continue
        fn = str(row.get("function") or "").strip()
        if fn != "Button":
            continue
        friendly = str(row.get("friendly") or "").strip()
        if not friendly:
            continue
        out.append(
            {
                "id": uid,
                "friendly": friendly,
                "function": fn,
                "deviceClass": function_map.get(fn, "other"),
            }
        )
    out.sort(key=lambda r: r["friendly"].lower())
    return out
