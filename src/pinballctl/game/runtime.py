"""Authoritative game transitions and integration with the existing event path."""

import hashlib
import json
import time
from uuid import uuid4
from pathlib import Path
from . import store, registry
from pinballctl.ball import runtime as balls
from pinballctl.backup.guard import guarded

GAME_DEFAULTS = {
    "maxPlayers": 4,
    "ballsPerPlayer": 3,
    "creditCost": 1,
    "unitsPerCredit": 100,
    "denominations": [100, 200],
    "freePlay": True,
    "joinPolicy": "first_ball",
    "testCredits": False,
    "ballSaveMs": 0,
    "bonusPoints": 0,
    "startInput": "",
    "startButton": "start_or_join",
    "coinInputs": [],
}
BALL_DEFAULTS = {"inventory": 1, "sensors": [], "devices": [], "staleMs": 30000}


def initial():
    return {
        "status": "IDLE",
        "gameId": None,
        "turnId": None,
        "players": [],
        "currentPlayer": 0,
        "ballNumber": 0,
        "credits": 0,
        "creditUnits": 0,
        "version": 0,
        "ballSaveUntil": 0,
        "reason": "",
        "startedAtMs": 0,
        "endedAtMs": 0,
    }


def check(ok, message):
    if not ok:
        raise ValueError(message)


def now_ms():
    return int(time.time() * 1000)


def snapshot_db(db):
    game = store.read(db, "game", initial())
    ball = store.read(db, "ball", balls.initial())
    config = store.read(db, "gameConfig", GAME_DEFAULTS)
    return {
        "game": game,
        "ball": ball,
        "gameConfig": config,
        "ballConfig": store.read(db, "ballConfig", BALL_DEFAULTS),
        "scores": store.read(db, "scores", {}),
        "registry": registry.contract(),
        "timeline": [
            {"id": r[0], "name": r[1], "params": json.loads(r[2])}
            for r in db.execute(
                "SELECT id,name,params FROM outbox ORDER BY seq DESC LIMIT 30"
            )
        ],
    }


@guarded
def snapshot(instance):
    with store.transaction(instance) as db:
        return snapshot_db(db)


def validate_config(kind, values):
    check(isinstance(values, dict), "Configuration must be an object")
    defaults = GAME_DEFAULTS if kind == "game" else BALL_DEFAULTS
    check(not set(values) - set(defaults), "Unknown configuration fields")
    cfg = {**defaults, **values}
    if kind == "game":
        for key, low, high in [
            ("maxPlayers", 1, 8),
            ("ballsPerPlayer", 1, 20),
            ("creditCost", 1, 100),
            ("unitsPerCredit", 1, 100000),
            ("ballSaveMs", 0, 120000),
            ("bonusPoints", 0, 10000000),
        ]:
            check(type(cfg[key]) is int and low <= cfg[key] <= high, "Invalid " + key)
        for key in ("freePlay", "testCredits"):
            check(type(cfg[key]) is bool, "Invalid " + key)
        check(
            isinstance(cfg["startInput"], str) and len(cfg["startInput"]) <= 200,
            "Invalid start input",
        )
        check(
            cfg["startButton"] in ("start_only", "start_or_join"),
            "Invalid start button policy",
        )
        check(
            isinstance(cfg["coinInputs"], list) and len(cfg["coinInputs"]) <= 20,
            "Invalid coin inputs",
        )
        for coin in cfg["coinInputs"]:
            check(
                isinstance(coin, dict)
                and set(coin) == {"source", "units"}
                and isinstance(coin["source"], str)
                and coin["source"]
                and type(coin["units"]) is int
                and coin["units"] in cfg["denominations"],
                "Coin inputs require a mapped source and accepted denomination",
            )
        check(
            cfg["joinPolicy"] in ("first_ball", "before_launch", "never"),
            "Invalid join policy",
        )
        check(
            isinstance(cfg["denominations"], list)
            and 0 < len(cfg["denominations"]) <= 20
            and all(type(v) is int and 0 < v <= 100000 for v in cfg["denominations"]),
            "Invalid coin denominations",
        )
    else:
        check(
            type(cfg["inventory"]) is int and 1 <= cfg["inventory"] <= 20,
            "Invalid physical inventory",
        )
        check(
            type(cfg["staleMs"]) is int and 1000 <= cfg["staleMs"] <= 3600000,
            "Invalid sensor freshness timeout",
        )
        check(
            isinstance(cfg["devices"], list) and len(cfg["devices"]) <= 64,
            "Invalid devices",
        )
        ids = set()
        for d in cfg["devices"]:
            check(
                isinstance(d, dict)
                and not set(d)
                - {
                    "id",
                    "name",
                    "capacity",
                    "destination",
                    "timeoutMs",
                    "releaseOutput",
                    "pulseMs",
                },
                "Invalid device fields",
            )
            check(
                isinstance(d.get("id"), str) and d["id"] and d["id"] not in ids,
                "Device IDs must be unique",
            )
            ids.add(d["id"])
            check(
                type(d.get("capacity")) is int and 1 <= d["capacity"] <= 20,
                "Invalid device capacity",
            )
            check(
                type(d.get("timeoutMs", 5000)) is int
                and 250 <= d.get("timeoutMs", 5000) <= 60000,
                "Invalid movement timeout",
            )
            check(
                not d.get("releaseOutput")
                or type(d.get("pulseMs")) is int
                and 1 <= d["pulseMs"] <= 250,
                "Release output requires a bounded pulse",
            )
        check(
            all(
                not d.get("destination") or d["destination"] in ids
                for d in cfg["devices"]
            ),
            "Unknown destination",
        )
        check(
            isinstance(cfg["sensors"], list) and len(cfg["sensors"]) <= 128,
            "Invalid sensors",
        )
        seen = set()
        for s in cfg["sensors"]:
            check(
                isinstance(s, dict)
                and not set(s) - {"source", "role", "zone", "active", "debounceMs"},
                "Invalid sensor fields",
            )
            check(
                isinstance(s.get("source"), str)
                and s["source"]
                and s["source"] not in seen,
                "Sensor sources must be unique",
            )
            seen.add(s["source"])
            check(
                s.get("role")
                in ("launch", "drain", "occupancy", "entrance", "exit", "lock"),
                "Invalid sensor role",
            )
            check(not s.get("zone") or s["zone"] in ids, "Unknown sensor zone")
            check(type(s.get("active", True)) is bool, "Invalid sensor polarity")
            check(
                type(s.get("debounceMs", 50)) is int
                and 0 <= s.get("debounceMs", 50) <= 5000,
                "Invalid debounce",
            )
    return cfg


@guarded
def configure(instance, kind, values):
    check(kind in ("game", "ball"), "Unknown manager")
    cfg = validate_config(kind, values)
    with store.transaction(instance) as db:
        game = store.read(db, "game", initial())
        check(
            game["status"] in ("IDLE", "GAME_ENDED"),
            "Finish or cancel the game before changing configuration",
        )
        store.write(db, kind + "Config", cfg)
    return cfg


def _event(db, game, name, params=None):
    ident = uuid4().hex
    payload = {
        **(params or {}),
        "gameId": game["gameId"],
        "turnId": game["turnId"],
        "playerId": game["currentPlayer"],
        "stateVersion": game["version"],
        "timestampMs": now_ms(),
        "_managerEventId": ident,
        "_eventId": ident,
    }
    db.execute(
        "INSERT INTO outbox(id,name,params) VALUES(?,?,?)",
        (ident, name, json.dumps(payload)),
    )


def _new_turn(game, ball, event, now):
    game["turnId"] = uuid4().hex
    game["status"] = "PREPARING"
    game["reason"] = "Awaiting shooter departure"
    game["ballSaveUntil"] = 0
    game["ballSaveStarted"] = False
    ball["inPlay"] = 0
    ball["confidence"] = "inferred"
    ball["reason"] = "New turn; awaiting physical launch"
    event("PLAYER_CHANGED")
    event("BALL_TURN_STARTED", {"ball": game["ballNumber"]})


def _finish_turn(game, ball, scores, event, now):
    game["status"] = "TURN_END_PENDING"
    player = game["players"][game["currentPlayer"] - 1]
    score = scores.setdefault(player["id"], {"score": 0})
    # Finalisation and next-player publication share this transaction. A replay
    # cannot award the bonus twice or switch the player before finalisation.
    from pinballctl.scoring.runtime import finalize_turn

    finalize_turn(score, game["turnId"], game["policy"].get("bonusPoints", 0))
    event("BALL_TURN_ENDED", {"score": score["score"]})
    if player["extraBalls"]:
        player["extraBalls"] -= 1
    elif game["currentPlayer"] < len(game["players"]):
        game["currentPlayer"] += 1
    elif game["ballNumber"] < game["policy"]["ballsPerPlayer"]:
        game["currentPlayer"] = 1
        game["ballNumber"] += 1
    else:
        game["status"] = "GAME_ENDED"
        game["endedAtMs"] = now
        game["reason"] = "All player turns complete"
        event(
            "GAME_ENDED", {"scores": {k: v.get("score", 0) for k, v in scores.items()}}
        )
        return
    _new_turn(game, ball, event, now)


def _spend(game, config, event):
    if config["freePlay"]:
        return
    check(game["credits"] >= config["creditCost"], "Insufficient credits")
    game["credits"] -= config["creditCost"]
    event("CREDIT_SPENT", {"amount": config["creditCost"]})
    event("CREDIT_BALANCE_CHANGED", {"credits": game["credits"]})


@guarded
def execute(
    instance, command, params, command_id, *, authority="rules", compute=None, depth=0
):
    check(
        isinstance(command_id, str) and 1 <= len(command_id) <= 200,
        "A command ID is required",
    )
    check(isinstance(params, dict), "Invalid parameters")
    check(type(depth) is int and 0 <= depth <= 16, "Manager event chain limit reached")
    request = json.dumps([command, params, authority], sort_keys=True)
    with store.transaction(instance) as db:
        old = (
            db.execute(
                "SELECT request,result FROM financial_ids WHERE id=?", (command_id,)
            ).fetchone()
            or db.execute(
                "SELECT request,result FROM commands WHERE id=?", (command_id,)
            ).fetchone()
        )
        if old:
            check(old[0] == request, "Command ID already used with different data")
            return json.loads(old[1])
        view = snapshot_db(db)
        game, ball, scores = view["game"], view["ball"], view["scores"]
        config, bcfg = view["gameConfig"], view["ballConfig"]
        now = now_ms()
        if command == "TICK" and not (
            (game["ballSaveUntil"] and game["ballSaveUntil"] <= now)
            or any(p["deadline"] <= now for p in ball["pending"])
            or any(
                s["active"]
                and now - s["at"] > bcfg["staleMs"]
                and source not in ball.get("alerts", {})
                for source, s in ball["sensors"].items()
            )
        ):
            return {
                "ok": True,
                "commandId": command_id,
                "stateVersion": game["version"],
            }
        game["version"] += 1
        event = lambda name, p=None: _event(
            db, game, name, {**(p or {}), "_rulesDepth": depth}
        )
        db.execute("SAVEPOINT transition")
        try:
            if command in registry.COMMANDS:
                check(
                    registry.command_valid(command, params),
                    "Invalid command parameters",
                )
                if command in registry.PRIVILEGED:
                    check(
                        authority in ("operator", "coin", "payment"),
                        "Command requires a trusted operator or adapter",
                    )
            if command == "REQUEST_START_GAME":
                check(
                    game["status"] in ("IDLE", "GAME_ENDED"), "A game is already active"
                )
                check(
                    not ball["pending"] and ball["inPlay"] in (None, 0),
                    "Physical balls or pending movements remain; reconcile before starting",
                )
                _spend(game, config, event)
                game.update(
                    status="START_REQUESTED",
                    gameId=uuid4().hex,
                    players=[{"id": "1", "name": "Player 1", "extraBalls": 0}],
                    currentPlayer=1,
                    ballNumber=1,
                    policy=config.copy(),
                    startedAtMs=now,
                    endedAtMs=0,
                )
                scores = {"1": {"score": 0}}
                event("GAME_STARTED")
                _new_turn(game, ball, event, now)
            elif command == "REQUEST_ADD_PLAYER":
                check(
                    game["status"] in ("PREPARING", "BALL_ACTIVE"),
                    "Game is not accepting players",
                )
                policy = game["policy"]
                check(
                    len(game["players"]) < policy["maxPlayers"], "Player limit reached"
                )
                check(
                    policy["joinPolicy"] != "never"
                    and game["ballNumber"] == 1
                    and (
                        policy["joinPolicy"] != "before_launch"
                        or game["status"] == "PREPARING"
                    ),
                    "Joining is closed",
                )
                _spend(game, policy, event)
                ident = str(len(game["players"]) + 1)
                game["players"].append(
                    {"id": ident, "name": "Player " + ident, "extraBalls": 0}
                )
                scores[ident] = {"score": 0}
                event("PLAYER_ADDED", {"playerCount": len(game["players"])})
            elif command == "REQUEST_AWARD_CREDIT":
                check(
                    authority in ("coin", "payment") or config["testCredits"],
                    "Enable authorised test credits or use a trusted payment adapter",
                )
                units = params["units"]
                check(
                    authority != "coin" or units in config["denominations"],
                    "Unsupported coin denomination",
                )
                game["creditUnits"] += units
                credits, game["creditUnits"] = divmod(
                    game["creditUnits"], config["unitsPerCredit"]
                )
                game["credits"] += credits
                event("CREDIT_ADDED", {"units": units, "creditsAdded": credits})
                event("CREDIT_BALANCE_CHANGED", {"credits": game["credits"]})
            elif command == "REQUEST_AWARD_EXTRA_BALL":
                check(
                    game["status"] in ("PREPARING", "BALL_ACTIVE"), "No active player"
                )
                check(
                    params["count"] <= 20
                    and game["players"][game["currentPlayer"] - 1]["extraBalls"]
                    + params["count"]
                    <= 1000,
                    "Extra-ball limit exceeded",
                )
                game["players"][game["currentPlayer"] - 1]["extraBalls"] += params[
                    "count"
                ]
                event("EXTRA_BALL_AWARDED", params)
            elif command == "REQUEST_BALL_SAVE":
                check(game["status"] == "BALL_ACTIVE", "Ball save requires active play")
                check(params["durationMs"] <= 120000, "Ball-save limit exceeded")
                game["ballSaveUntil"] = now + params["durationMs"]
                event("BALL_SAVE_ACTIVATED", params)
            elif command == "REQUEST_END_GAME":
                check(game["status"] not in ("IDLE", "GAME_ENDED"), "No game to end")
                game.update(
                    status="GAME_ENDED", endedAtMs=now, reason="Ended by operator"
                )
                event(
                    "GAME_ENDED",
                    {"scores": {k: v.get("score", 0) for k, v in scores.items()}},
                )
            elif command == "REQUEST_PAUSE_GAME":
                check(
                    game["status"] in ("PREPARING", "BALL_ACTIVE"),
                    "Game cannot be paused",
                )
                game["resumeStatus"] = game["status"]
                game.update(status="PAUSED", reason="Paused by operator")
                event("GAME_PAUSED")
            elif command == "REQUEST_RESUME_GAME":
                check(game["status"] == "PAUSED", "Reconcile recovery before resuming")
                check(
                    ball["inPlay"] is not None and not ball["pending"],
                    "Reconcile unknown balls and pending movements before resuming",
                )
                previous = game.pop("resumeStatus", "PREPARING")
                game["reason"] = ""
                event("GAME_RESUMED")
                if previous == "BALL_ACTIVE" and ball["inPlay"] == 0:
                    if game["ballSaveUntil"] > now:
                        game["status"] = "PREPARING"
                        game["reason"] = "Ball saved; awaiting replacement launch"
                    else:
                        _finish_turn(game, ball, scores, event, now)
                else:
                    game["status"] = "BALL_ACTIVE" if ball["inPlay"] else "PREPARING"
            elif command == "REQUEST_BALL_MOVEMENT":
                check(
                    game["status"] in ("PREPARING", "BALL_ACTIVE"),
                    "Movement requires an active game",
                )
                balls.movement(ball, bcfg, params["deviceId"], now, event)
            elif command == "RECONCILE":
                check(authority == "operator", "Only the operator can reconcile")
                check(
                    type(params.get("inPlay")) is int
                    and 0 <= params["inPlay"] <= bcfg["inventory"],
                    "Invalid in-play count",
                )
                check(
                    isinstance(params.get("reason"), str) and params["reason"].strip(),
                    "A reconciliation reason is required",
                )
                ball.update(
                    inPlay=params["inPlay"],
                    confidence="inferred",
                    reason=params["reason"],
                    pending=[],
                    alerts={},
                )
                check(
                    game["status"]
                    in ("RECOVERY_REQUIRED", "PAUSED", "IDLE", "GAME_ENDED"),
                    "Pause before reconciliation",
                )
                if game["status"] == "RECOVERY_REQUIRED":
                    game["status"] = "PAUSED"
                    game["resumeStatus"] = game.get(
                        "resumeStatus", "BALL_ACTIVE" if ball["inPlay"] else "PREPARING"
                    )
                event("BALL_RECONCILED", params)
            elif command == "RECOVER":
                check(authority == "internal", "Recovery requires internal authority")
                store.write(db, "ingressClock", {})
                if game["status"] not in ("IDLE", "GAME_ENDED"):
                    if game["status"] in ("PREPARING", "BALL_ACTIVE"):
                        game["resumeStatus"] = game["status"]
                    game.update(
                        status="RECOVERY_REQUIRED",
                        reason=params.get(
                            "reason", "Runtime restarted; reconcile physical state"
                        ),
                    )
                    ball.update(
                        inPlay=None, confidence="unknown", reason=game["reason"]
                    )
                    event("RECOVERY_REQUIRED", {"reason": game["reason"]})
            elif command == "OBSERVE":
                check(
                    authority in ("hardware", "simulation"),
                    "Observations require trusted ingress",
                )
                if authority == "simulation":
                    check(
                        config["testCredits"],
                        "Enable test mode before simulating inputs",
                    )
                check(
                    type(params.get("active")) is bool
                    and isinstance(params.get("sensor"), str),
                    "Observation requires a sensor and boolean active level",
                )
                outcome = balls.observe(
                    ball, bcfg, params["sensor"], params["active"], now, event
                )
                for device in bcfg["devices"]:
                    count = ball["zones"].get(device["id"], {}).get("count")
                    if count is not None and not 0 <= count <= device["capacity"]:
                        outcome = "uncertain"
                        ball["reason"] = "Observed occupancy exceeds device capacity"
                if ball["inPlay"] is not None and ball["inPlay"] > bcfg["inventory"]:
                    outcome = "uncertain"
                    ball["reason"] = (
                        "Observed launches exceed configured physical inventory"
                    )
                if outcome == "uncertain":
                    game.update(status="RECOVERY_REQUIRED", reason=ball["reason"])
                    event("RECOVERY_REQUIRED", {"reason": ball["reason"]})
                elif game["status"] == "PREPARING" and outcome == "launch":
                    game["status"] = "BALL_ACTIVE"
                    game["reason"] = ""
                    duration = game["policy"]["ballSaveMs"]
                    if duration and not game.get("ballSaveStarted"):
                        game["ballSaveUntil"] = now + duration
                        game["ballSaveStarted"] = True
                        event("BALL_SAVE_ACTIVATED", {"durationMs": duration})
                elif (
                    game["status"] == "BALL_ACTIVE"
                    and outcome == "drain"
                    and ball["inPlay"] == 0
                    and not ball["pending"]
                ):
                    if game["ballSaveUntil"] > now:
                        game["status"] = "PREPARING"
                        game["reason"] = "Ball saved; awaiting replacement launch"
                        event("BALL_SAVE_ACTIVATED", {"saved": True})
                    else:
                        _finish_turn(game, ball, scores, event, now)
            elif command == "TICK":
                check(authority == "internal", "Timer requires internal authority")
                expired, fresh = balls.tick(ball, bcfg, now, event)
                if expired:
                    game.update(status="RECOVERY_REQUIRED", reason=ball["reason"])
                    event("RECOVERY_REQUIRED", {"reason": ball["reason"]})
                if game["ballSaveUntil"] and now >= game["ballSaveUntil"]:
                    game["ballSaveUntil"] = 0
                    event("BALL_SAVE_EXPIRED")
            elif command == "SCORE":
                check(authority == "internal", "Scoring requires internal authority")
                check(compute is not None, "Scoring handler required")
                if game["status"] == "BALL_ACTIVE":
                    expected = params.get("turnId")
                    check(
                        expected == game["turnId"],
                        "Scoring event belongs to an earlier turn",
                    )
                    player = game["players"][game["currentPlayer"] - 1]["id"]
                    score = scores.setdefault(player, {"score": 0})
                    compute(score, event)
            else:
                raise ValueError("Unknown manager command")
            result = {
                "ok": True,
                "commandId": command_id,
                "stateVersion": game["version"],
            }
        except ValueError as exc:
            db.execute("ROLLBACK TO transition")
            view = snapshot_db(db)
            game, ball, scores = view["game"], view["ball"], view["scores"]
            game["version"] += 1
            result = {
                "ok": False,
                "commandId": command_id,
                "error": str(exc),
                "stateVersion": game["version"],
            }
            if command in ("REQUEST_START_GAME", "REQUEST_ADD_PLAYER"):
                event(
                    (
                        "GAME_START_REJECTED"
                        if command == "REQUEST_START_GAME"
                        else "PLAYER_ADD_REJECTED"
                    ),
                    {"reason": str(exc)},
                )
        if result["ok"] and game["status"] == "GAME_ENDED" and game["gameId"]:
            from pinballctl.scoring.runtime import finalize_game

            finalize_game(db, game, scores)
        store.write(db, "game", game)
        store.write(db, "ball", ball)
        store.write(db, "scores", scores)
        db.execute(
            "INSERT INTO commands VALUES(?,?,?)",
            (command_id, request, json.dumps(result)),
        )
        if command == "REQUEST_AWARD_CREDIT" and authority in ("coin", "payment"):
            db.execute(
                "INSERT INTO financial_ids VALUES(?,?,?)",
                (command_id, request, json.dumps(result)),
            )
    return result


def read_manager_fields(instance):
    view = snapshot(instance)
    game, ball = view["game"], view["ball"]
    now = now_ms()
    zones = [ball["zones"].get(d["id"], {}) for d in view["ballConfig"]["devices"]]
    known = bool(zones) and all(z.get("count") is not None for z in zones)
    observed = sum(z["count"] for z in zones) if known else None
    occupancy = (
        "unknown"
        if not known
        else (
            "confirmed"
            if all(z.get("confidence") == "confirmed" for z in zones)
            else "inferred"
        )
    )
    return {
        "game": {
            "status": game["status"],
            "currentPlayer": game["currentPlayer"],
            "playerCount": len(game["players"]),
            "ballNumber": game["ballNumber"],
            "credits": game["credits"],
            "freePlay": view["gameConfig"]["freePlay"],
            "extraBalls": (
                game["players"][game["currentPlayer"] - 1]["extraBalls"]
                if game["players"]
                else 0
            ),
            "ballSave": game["ballSaveUntil"] > now,
        },
        "ball": {
            "observedCount": observed,
            "occupancyConfidence": occupancy,
            "inPlay": ball["inPlay"],
            "confidence": ball["confidence"],
            "pending": len(ball["pending"]),
            "sensorFresh": (
                None
                if not ball["sensors"]
                else all(
                    now - s["at"] <= view["ballConfig"]["staleMs"]
                    for s in ball["sensors"].values()
                )
            ),
        },
    }


def read_fields(instance, kind):
    return read_manager_fields(instance)[kind]


def trusted_result(instance, name, params):
    ident = params.get("_managerEventId") if isinstance(params, dict) else None
    if not ident:
        return False
    with store.transaction(instance) as db:
        row = db.execute(
            "SELECT name,params FROM outbox WHERE id=?", (ident,)
        ).fetchone()
        return bool(row and row[0] == name and json.loads(row[1]) == params)


def ingest(instance, name, source, params, event_id=None):
    """Called in existing event execution order; stable IDs survive retries."""
    if name in registry.RESERVED:
        return
    payload = params or {}
    ident = event_id or payload.get("_eventId")
    if payload.get("_hardwareIngress") and payload.get("seq") is not None:
        ident = hashlib.sha256(
            json.dumps(
                [
                    source,
                    name,
                    payload["seq"],
                    (payload.get("payload") or {}).get("tsMs"),
                ]
            ).encode()
        ).hexdigest()
    if not ident:
        seq = payload.get("seq")
        stamp = (payload.get("payload") or {}).get("tsMs")
        if seq is not None:
            ident = hashlib.sha256(
                json.dumps([source, name, seq, stamp]).encode()
            ).hexdigest()
        else:
            ident = uuid4().hex
    captured = capture_ingress(instance, ident, payload)
    if captured["rejected"]:
        return
    payload = {**payload, "_turnId": captured["turnId"]}
    if name in (
        "PLATFORM_OVERLOAD",
        "PLATFORM_OVERLOAD_FAULT",
        "BRIDGE_DISCONNECTED",
        "BOOT_COMPLETED",
    ):
        execute(
            instance,
            "RECOVER",
            {"reason": name.replace("_", " ").title()},
            "recovery-event:" + ident,
            authority="internal",
        )
    from pinballctl.scoring.runtime import score_managed_event

    score_managed_event(
        instance, name=name, source=source, params=payload, event_id=ident
    )
    event_type = str(payload.get("eventType") or "").upper()
    if (
        event_type in ("PRESSED", "RELEASED", "CLOSED", "OPENED")
        and payload.get("_hardwareIngress") is True
    ):
        config = snapshot(instance)["gameConfig"]
        if event_type in ("PRESSED", "CLOSED"):
            for coin in config["coinInputs"]:
                if coin["source"] == source:
                    execute(
                        instance,
                        "REQUEST_AWARD_CREDIT",
                        {"units": coin["units"]},
                        "coin:" + ident,
                        authority="coin",
                    )
            if config["startInput"] == source:
                current = snapshot(instance)["game"]["status"]
                cmd = (
                    "REQUEST_ADD_PLAYER"
                    if config["startButton"] == "start_or_join"
                    and current in ("PREPARING", "BALL_ACTIVE")
                    else "REQUEST_START_GAME"
                )
                execute(instance, cmd, {}, "start:" + ident, authority="hardware")
        execute(
            instance,
            "OBSERVE",
            {"sensor": source or name, "active": event_type in ("PRESSED", "CLOSED")},
            "sensor:" + ident,
            authority="hardware",
        )
    return payload


@guarded
def dispatch(instance):
    """One dispatcher per installation, with durable IDs for retrying consumers."""
    import fcntl

    folder = Path(instance) / "game"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".dispatch.lock").open("a") as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        with store.transaction(instance) as db:
            pending = db.execute(
                "SELECT id,name,params FROM outbox WHERE delivered=0 ORDER BY seq LIMIT 64"
            ).fetchall()
        for ident, name, raw in pending:
            params = json.loads(raw)
            if name == "BALL_MOVEMENT_REQUESTED":
                _send_release_once(instance, ident, params)
            from pinballctl.events import get_bus, get_event_manager, EventContext
            from pinballctl.rules.runtime import apply_rules_for_event

            get_bus().emit(name, source="pi.game", params=params)
            get_event_manager(instance_path=str(instance)).dispatch(
                EventContext(
                    id=ident,
                    ts=time.time(),
                    name=name,
                    source="pi.game",
                    params=params,
                    origin="manager",
                )
            )
            apply_rules_for_event(
                instance, name=name, source="pi.game", params=params, origin="manager"
            )
            with store.transaction(instance) as db:
                db.execute("UPDATE outbox SET delivered=1 WHERE id=?", (ident,))


def ensure_worker(instance):
    import logging
    from threading import Thread, Lock

    key = str(Path(instance).resolve())
    with _WORKER_LOCK:
        if key in _WORKERS and _WORKERS[key].is_alive():
            return

        def loop():
            import fcntl

            folder = Path(key) / "game"
            folder.mkdir(parents=True, exist_ok=True)
            while True:
                with (folder / ".runtime.lock").open("a") as owner:
                    try:
                        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        time.sleep(1)
                        continue
                    # Losing the last coordinator makes physical state uncertain.
                    execute(
                        key,
                        "RECOVER",
                        {
                            "reason": "Runtime ownership changed; inspect and reconcile physical balls"
                        },
                        "recover:" + uuid4().hex,
                        authority="internal",
                    )
                    while True:
                        try:
                            execute(
                                key,
                                "TICK",
                                {},
                                "tick:" + str(now_ms() // 500),
                                authority="internal",
                            )
                            dispatch(key)
                            from pinballctl.scoring.runtime import (
                                load_scoring_state,
                                _sync_media_overlay_values,
                            )

                            _sync_media_overlay_values(
                                key, load_scoring_state(key), now_ms()
                            )
                        except Exception:
                            logging.getLogger(__name__).exception(
                                "Manager delivery failed"
                            )
                        time.sleep(0.5)

        thread = Thread(target=loop, daemon=True, name="game-ball-manager")
        _WORKERS[key] = thread
        thread.start()


from threading import Lock

_WORKER_LOCK = Lock()
_WORKERS = {}


def _send_release_once(instance, ident, params):
    from pinballctl.bridge.state import commands_path, rpc_command, read_state

    with store.transaction(instance) as db:
        if db.execute(
            "SELECT 1 FROM receipts WHERE consumer=? AND id=?", ("release", ident)
        ).fetchone():
            return
        state = store.read(db, "game", initial())
        physical = store.read(db, "ball", balls.initial())
        config = store.read(db, "ballConfig", BALL_DEFAULTS)
        device = next(
            (d for d in config["devices"] if d["id"] == params.get("deviceId")), None
        )
        # Reserve before side effects. A crash after this point never re-fires.
        db.execute("INSERT INTO receipts VALUES(?,?)", ("release", ident))
        allowed = state["status"] in ("PREPARING", "BALL_ACTIVE") and any(
            p["id"] == params.get("id") for p in physical["pending"]
        )
    if not device or not device.get("releaseOutput"):
        return
    if not allowed:
        return
    try:
        check(
            Path(instance).resolve() == commands_path().parent.parent.resolve(),
            "Isolated instances cannot operate outputs",
        )
        bridge = read_state()
        check(bridge.get("connected"), "Bridge is offline")
        clock = rpc_command({"cmd": "GET_RUNTIME_CLOCK"}, "RUNTIME_CLOCK", timeout_s=1)
        check(
            isinstance(clock, dict) and type(clock.get("tsMs")) is int,
            "Firmware runtime clock is unavailable; update firmware",
        )
        result = rpc_command(
            {
                "cmd": "RULE_ACTIONS",
                "actions": [
                    {
                        "type": "pulse",
                        "target": device["releaseOutput"],
                        "params": {"ms": device["pulseMs"]},
                    }
                ],
                "source": "pi.ball",
                "eventType": "REQUEST",
                "triggeredAtMs": clock["tsMs"],
            },
            "RULE_ACTIONS_STATUS",
            timeout_s=1,
        )
        check(
            isinstance(result, dict) and result.get("accepted") is True,
            "ESP rejected or did not confirm the release",
        )
    except Exception as exc:
        execute(
            instance,
            "RECOVER",
            {"reason": "Release delivery uncertain: " + str(exc)},
            "release-failed:" + ident,
            authority="internal",
        )


def award_verified_settlement(instance, settlement_id, units):
    """Trusted Python adapter boundary; never exposed through a generic event API.

    A payment integration must authenticate settlement before calling this API.
    Provider implementations remain outside the current feature scope.
    """
    check(
        isinstance(settlement_id, str) and settlement_id,
        "Verified settlement ID required",
    )
    return execute(
        instance,
        "REQUEST_AWARD_CREDIT",
        {"units": units},
        "settlement:" + settlement_id,
        authority="payment",
    )


def observation_rules(instance, game_config=None, ball_config=None, mapping=None):
    """Compiled input watches, never user-visible gameplay rules or outputs."""
    if mapping is None:
        file = Path(instance) / "hardware/mapping.json"
        mapping = json.loads(file.read_text()) if file.exists() else {}
    if isinstance(mapping.get("data"), dict):
        mapping = mapping["data"]
    from pinballctl.app.modules.rules.api import _build_hardware_devices

    devices, _ = _build_hardware_devices(mapping)
    available = {
        device["id"]: device
        for device in devices
        if device["deviceClass"] in ("button", "switch")
    }
    view = snapshot(instance)
    gc = game_config or view["gameConfig"]
    bc = ball_config or view["ballConfig"]
    sources = {s["source"] for s in bc["sensors"]} | {
        s["source"] for s in gc["coinInputs"]
    }
    if gc["startInput"]:
        sources.add(gc["startInput"])
    result = []
    for index, source in enumerate(sorted(sources)):
        check(source in available, "Manager input is not mapped: " + source)
        d = available[source]
        events = (
            ("PRESSED", "RELEASED")
            if d["deviceClass"] == "button"
            else ("CLOSED", "OPENED")
        )
        result.append(
            {
                "id": 1000000 + index,
                "name": "Manager input observation",
                "enabled": True,
                "logic": "ANY",
                "triggers": [
                    {
                        "type": "hardware",
                        "source": source,
                        "event": d["eventBase"],
                        "fn": event,
                        "params": {},
                    }
                    for event in events
                ],
                "actions": [],
            }
        )
    return result


def capture_ingress(instance, ident, payload):
    """Capture turn attribution once, before asynchronous fanout or retry."""
    with store.transaction(instance) as db:
        old = db.execute(
            "SELECT turn_id,rejected FROM ingress WHERE id=?", (ident,)
        ).fetchone()
        if old:
            return {"turnId": old[0], "rejected": bool(old[1])}
        game = store.read(db, "game", initial())
        rejected = False
        stamp = (payload.get("payload") or {}).get("tsMs")
        if payload.get("_hardwareIngress") and type(stamp) is int:
            clock = store.read(db, "ingressClock", {})
            if "at" in clock and ((stamp - clock["at"]) & 0xFFFFFFFF) > 0x80000000:
                rejected = True
            if not rejected:
                store.write(db, "ingressClock", {"at": stamp})
        turn = payload.get("_turnId", game["turnId"])
        db.execute("INSERT INTO ingress VALUES(?,?,?)", (ident, turn, int(rejected)))
        return {"turnId": turn, "rejected": rejected}


def validate_snapshot(kind, data):
    check(isinstance(data, dict), "Invalid manager snapshot")
    cfg = validate_config(kind, data.get("config", {}))
    state = data.get("state", {})
    check(isinstance(state, dict), "Manager state must be an object")
    if kind == "game":
        check(
            state.get("status")
            in (
                "IDLE",
                "GAME_ENDED",
                "START_REQUESTED",
                "PREPARING",
                "BALL_ACTIVE",
                "TURN_END_PENDING",
                "PAUSED",
                "RECOVERY_REQUIRED",
                "FAULT",
            ),
            "Invalid game status",
        )
        for key in (
            "credits",
            "creditUnits",
            "currentPlayer",
            "ballNumber",
            "version",
            "ballSaveUntil",
            "startedAtMs",
            "endedAtMs",
        ):
            check(
                type(state.get(key)) is int and state[key] >= 0,
                "Invalid game state " + key,
            )
        players = state.get("players")
        check(isinstance(players, list) and len(players) <= 8, "Invalid player list")
        for index, player in enumerate(players):
            check(
                isinstance(player, dict)
                and player.get("id") == str(index + 1)
                and isinstance(player.get("name"), str)
                and len(player["name"]) <= 100
                and type(player.get("extraBalls")) is int
                and 0 <= player["extraBalls"] <= 1000,
                "Invalid player state",
            )
        check(0 <= state["currentPlayer"] <= len(players), "Invalid current player")
        if players:
            check(state["currentPlayer"] > 0, "Missing current player")
        if state.get("policy"):
            validate_config("game", state["policy"])
    else:
        check(
            state.get("inPlay") is None
            or type(state["inPlay"]) is int
            and 0 <= state["inPlay"] <= 20,
            "Invalid in-play count",
        )
        check(
            state.get("confidence") in ("confirmed", "inferred", "unknown"),
            "Invalid ball confidence",
        )
        check(
            isinstance(state.get("zones"), dict)
            and isinstance(state.get("sensors"), dict)
            and isinstance(state.get("pending"), list)
            and len(state["pending"]) <= 64,
            "Invalid ball observations",
        )
    return cfg
