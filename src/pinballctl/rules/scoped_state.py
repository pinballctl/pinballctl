"""Named Rules values and countdowns owned by a machine, game, or player."""

import re
from uuid import uuid4

from pinballctl.game.registry import TIMER_EVENT

from . import play_clock

SCOPES = ("global", "game", "player")
KINDS = ("flag", "counter", "timer")
TIMER_ACTIONS = {"start_timer", "pause_timer", "resume_timer", "reset_timer"}
MAX_DURATION = 86_400_000
SYSTEM_FLAGS = {"ENABLED", "IDLE", "TILT"}


def definition(kind, key, values):
    from pinballctl.game.registry import LEGACY

    if kind not in KINDS or not isinstance(key, str) or not re.fullmatch(r"[A-Z0-9_]{1,32}", key):
        raise ValueError("Use a name of 1–32 uppercase letters, digits or underscores.")
    if key in LEGACY or (kind == "flag" and key in SYSTEM_FLAGS):
        raise ValueError("This name is reserved.")
    scope = values.get("scope")
    if scope not in SCOPES:
        raise ValueError("Choose Global, Per game or Per player.")
    result = {"scope": scope}
    if kind == "timer":
        duration = values.get("durationMs")
        if type(duration) is not int or not 1 <= duration <= MAX_DURATION:
            raise ValueError("Timer duration must be between 1 and 86,400,000 ms.")
        clock = values.get("clock")
        if clock not in (("play",) if scope == "player" else ("wall", "play")):
            raise ValueError("Choose a clock available for this scope.")
        result.update(durationMs=duration, clock=clock)
    return result


def configuration(state, kind, key):
    return state.get("definitions", {}).get(kind, {}).get(key, {"scope": "global"})


def context(game, params=None):
    if not game or not game["gameId"]:
        return None, None
    if params and (params.get("_managerEventId") or params.get("_rulesTimerEvent")):
        if params.get("gameId") != game["gameId"]:
            return None, None
        player = params.get("_rulesPlayerKey")
        if player is None and type(params.get("playerId")) is int:
            player = play_clock.player_key(game, params["playerId"])
        if player not in {p.get("rulesKey", p["id"]) for p in game["players"]}:
            player = None
        return game["gameId"], player
    if game["status"] in ("IDLE", "GAME_ENDED", "FAULT"):
        return None, None
    if params and "_turnId" in params and params["_turnId"] != game["turnId"]:
        return None, None
    return game["gameId"], play_clock.player_key(game)


def prepare(state, game):
    generation = game.get("rulesRestoreGeneration")
    if state.get("restoreGeneration") != generation:
        state["restoreGeneration"] = generation
        cancel_timers(state)
    scoped = state.setdefault("scoped", {})
    if scoped.get("gameId") != game.get("gameId"):
        scoped.clear()
        scoped["gameId"] = game.get("gameId")
    players = scoped.setdefault("players", {})
    keys = {p.get("rulesKey", p["id"]) for p in game.get("players", [])}
    for key in players.keys() - keys:
        del players[key]


def values(state, kind, scope, owner):
    group = kind + "s"
    game_id, player = owner
    if scope == "global":
        return state.setdefault(group, {})
    if not game_id:
        return None
    if scope == "game":
        return state["scoped"].setdefault(group, {})
    if player is None:
        return None
    return state["scoped"]["players"].setdefault(player, {}).setdefault(group, {})


def set_definition(state, kind, key, config):
    previous = configuration(state, kind, key)
    state.setdefault("definitions", {}).setdefault(kind, {})[key] = config
    if config["scope"] != previous["scope"] or (kind == "timer" and config != previous):
        group = kind + "s"
        state.get(group, {}).pop(key, None)
        scoped = state.get("scoped", {})
        scoped.get(group, {}).pop(key, None)
        for player in scoped.get("players", {}).values():
            player.get(group, {}).pop(key, None)
        if kind == "timer":
            state["timerOutbox"] = [
                item for item in state.get("timerOutbox", []) if item["timer"] != key
            ]


def clock_value(config, game, owner, now):
    if config["clock"] == "wall":
        return now
    return play_clock.elapsed(
        game, owner[1] if config["scope"] == "player" else None, play_clock.now_ms(),
        global_clock=config["scope"] == "global",
    )


def remaining(timer, clock):
    if timer is None:
        return 0
    if "deadline" in timer:
        return max(0, timer["deadline"] - clock)
    return timer["remainingMs"]


def timer_action(state, action, key, game, owner, now):
    config = state.get("definitions", {}).get("timer", {}).get(key)
    if config is None:
        return
    timers = values(state, "timer", config["scope"], owner)
    if timers is None:
        return
    clock = clock_value(config, game, owner, now)
    timer = timers.get(key)
    if action == "start_timer":
        timers[key] = {"deadline": clock + config["durationMs"]}
    elif action == "reset_timer":
        timers.pop(key, None)
    elif action == "pause_timer" and timer and "deadline" in timer:
        left = remaining(timer, clock)
        if left > 0:
            timers[key] = {"remainingMs": left}
    elif action == "resume_timer" and timer and timer.get("remainingMs", 0) > 0:
        timers[key] = {"deadline": clock + timer["remainingMs"]}


def collect_expired(state, game, now):
    prepare(state, game)
    game_id = game.get("gameId")
    current = play_clock.player_key(game)
    players = [(p.get("rulesKey", p["id"]), index) for index, p in enumerate(game["players"], 1)]
    outbox = state.setdefault("timerOutbox", [])
    for key, config in state.get("definitions", {}).get("timer", {}).items():
        scope = config["scope"]
        owners = players if scope == "player" else [(current, game["currentPlayer"])]
        for player, number in owners:
            owner = (game_id, player)
            timers = values(state, "timer", scope, owner)
            timer = timers.get(key) if timers is not None else None
            if timer is None or "deadline" not in timer:
                continue
            cutoff = min(now, game["endedAtMs"]) if scope != "global" and game["status"] == "GAME_ENDED" else now
            if remaining(timer, clock_value(config, game, owner, cutoff)) > 0:
                continue
            clock = game.get("rulesClock", {})
            turn = game["turnId"]
            if config["clock"] == "play":
                turn = clock.get("turns", {}).get(player) if scope == "player" else clock.get("turn")
            timers[key] = {"remainingMs": 0, "expired": True}
            outbox.append({
                "_eventId": uuid4().hex, "_rulesTimerEvent": True, "_rulesPlayerKey": player,
                "timer": key, "scope": scope, "clock": config["clock"], "gameId": game_id,
                "playerId": number or None, "_turnId": turn,
            })
    return list(outbox)


def visible(state, game, now):
    prepare(state, game)
    owner = (game.get("gameId"), play_clock.player_key(game))
    rows = []
    definitions = state.get("definitions", {})
    for kind in KINDS:
        names = set(definitions.get(kind, {})) | set(state.get(kind + "s", {}))
        for key in sorted(names):
            config = configuration(state, kind, key)
            scope = config["scope"]
            owners = [(None, owner)]
            if scope == "player":
                owners = [
                    (p["name"], (owner[0], p.get("rulesKey", p["id"]))) for p in game["players"]
                ] or [(None, (None, None))]
            for name, target in owners:
                bucket = values(state, kind, scope, target)
                value = bucket.get(key) if bucket is not None else None
                if kind == "timer" and bucket is not None:
                    left = remaining(value, clock_value(config, game, target, now))
                    running = value is not None and "deadline" in value
                    if running and config["clock"] == "play":
                        running = play_clock.playing(game) and (scope != "player" or target[1] == owner[1])
                    status = "Expired" if value and value.get("expired") else "Running" if running else "Paused" if value else "Ready"
                    value = {"remainingMs": left, "status": status}
                if value is None and bucket is not None:
                    value = False if kind == "flag" else 0
                rows.append({"kind": kind, "key": key, "scope": scope, "player": name, "value": value})
    return rows


def cancel_timers(state):
    state.pop("timers", None)
    state.pop("timerOutbox", None)
    scoped = state.get("scoped", {})
    scoped.pop("timers", None)
    for player in scoped.get("players", {}).values():
        player.pop("timers", None)
