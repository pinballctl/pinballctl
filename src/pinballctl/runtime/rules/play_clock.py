"""Accumulate monotonic playable time at authoritative game transitions."""

import time


def now_ms():
    return time.monotonic_ns() // 1_000_000


def playing(game):
    return game["status"] == "BALL_ACTIVE"


def player_key(game, number=None):
    number = game["currentPlayer"] if number is None else number
    if not 1 <= number <= len(game["players"]):
        return None
    player = game["players"][number - 1]
    return player.get("rulesKey", player["id"])


def transition(before, game, now):
    if before["gameId"] == game["gameId"] and before["status"] == game["status"] and player_key(before) == player_key(game):
        return
    clock = game.setdefault("rulesClock", {})
    if before["gameId"] != game["gameId"]:
        total = before.get("rulesClock", {}).get("global", 0)
        clock.clear()
        clock["global"] = total
    elif playing(before):
        since = clock.get("since", now)
        elapsed = max(0, now - since)
        clock["game"] = clock.get("game", 0) + elapsed
        clock["global"] = clock.get("global", 0) + elapsed
        players = clock.setdefault("players", {})
        key = player_key(before)
        if key is not None:
            players[key] = players.get(key, 0) + elapsed
    if playing(game):
        clock["since"] = now
        clock["turn"] = game["turnId"]
        clock.setdefault("turns", {})[player_key(game)] = game["turnId"]
    else:
        clock.pop("since", None)


def elapsed(game, player, now, *, global_clock=False):
    clock = game.get("rulesClock", {})
    total = clock.get("game", 0) if player is None else clock.get("players", {}).get(player, 0)
    if global_clock:
        total = clock.get("global", 0)
    if playing(game) and (player is None or player == player_key(game)):
        total += max(0, now - clock.get("since", now))
    return total
