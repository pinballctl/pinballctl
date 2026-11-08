"""Persistent completed results shared by the operator UI and backglass."""

from datetime import datetime
import re
import time

from pinballctl.game import store

CATEGORIES = ("all-time", "year", "month", "latest")
MAX_SCORE = 2**53 - 1  # Exact in JavaScript and Godot's JSON reader.
PROMPT_MS = 60_000


def prepare(db):
    if store.read(db, "leaderboardInitialized", False):
        return
    db.execute("""CREATE TABLE IF NOT EXISTS leaderboard (
        game_id TEXT NOT NULL, player_id TEXT NOT NULL, name TEXT NOT NULL,
        initials TEXT NOT NULL DEFAULT '', score INTEGER NOT NULL,
        ended_at INTEGER NOT NULL, pending INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (game_id, player_id))""")
    db.execute("CREATE INDEX IF NOT EXISTS leaderboard_score ON leaderboard(score DESC, ended_at)")
    db.execute("CREATE INDEX IF NOT EXISTS leaderboard_date ON leaderboard(ended_at DESC)")
    history = store.read(db, "history", {"games": []})
    for game in history["games"]:
        for player in game.get("players", []):
            _insert(db, game["gameId"], game["endedAtMs"], player)
    for player in store.read(db, "highScores", {"scores": []})["scores"]:
        _insert(db, player["gameId"], player["endedAtMs"], player)
    store.write(db, "leaderboardInitialized", True)


def _insert(db, game_id, ended_at, player):
    name = player["name"]
    initials = name.upper() if re.fullmatch(r"[A-Za-z]{3}", name) else ""
    db.execute(
        """INSERT OR IGNORE INTO leaderboard(game_id,player_id,name,initials,score,ended_at)
           VALUES(?,?,?,?,?,?)""",
        (game_id, player["playerId"], name, initials, min(player["score"], MAX_SCORE), ended_at),
    )


def display_rows(db):
    return store.read(db, "leaderboardRows", 5)


def _period(category, now):
    if category not in ("month", "year"):
        return 0, None
    local = datetime.fromtimestamp(now / 1000)
    year, month = local.year, local.month if category == "month" else 1
    if category == "year" or month == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, month + 1, 1)
    return int(datetime(year, month, 1).timestamp() * 1000), int(end.timestamp() * 1000)


def board(db, category, limit, offset=0, now=None):
    now = int(time.time() * 1000) if now is None else now
    start, end = _period(category, now)
    order = "ended_at DESC, game_id, CAST(player_id AS INTEGER), player_id" if category == "latest" else (
        "score DESC, ended_at ASC, game_id, CAST(player_id AS INTEGER), player_id"
    )
    where = "ended_at>=?" if end is None else "ended_at>=? AND ended_at<?"
    args = (start,) if end is None else (start, end)
    rows = db.execute(
        f"""SELECT game_id,player_id,name,initials,score,ended_at FROM leaderboard
            WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?""",
        (*args, limit, offset),
    )
    return [
        {"rank": rank, "gameId": game_id, "playerId": player_id, "name": name,
         "initials": initials or "---", "score": score, "endedAtMs": ended_at}
        for rank, (game_id, player_id, name, initials, score, ended_at) in enumerate(rows, offset + 1)
    ]


def record_game(db, game):
    prepare(db)
    for player in game["players"]:
        _insert(db, game["gameId"], game["endedAtMs"], player)
    # Latest is chronological, so qualifying there would prompt every player.
    for category in CATEGORIES[:3]:
        for row in board(db, category, display_rows(db), now=game["endedAtMs"]):
            if row["gameId"] == game["gameId"] and row["score"] > 0 and row["initials"] == "---":
                db.execute(
                    "UPDATE leaderboard SET pending=1 WHERE game_id=? AND player_id=?",
                    (row["gameId"], row["playerId"]),
                )


def _prompt(db, now):
    game = store.read(db, "game", {})
    if game.get("status") != "GAME_ENDED":
        return None
    row = db.execute(
        """SELECT game_id,player_id,name,score FROM leaderboard WHERE game_id=?
           AND pending=1 AND ended_at>=? ORDER BY CAST(player_id AS INTEGER), player_id LIMIT 1""",
        (game["gameId"], now - PROMPT_MS),
    ).fetchone()
    return dict(zip(("gameId", "playerId", "name", "score"), row)) if row else None


def backglass_state(db, now):
    return {
        "boards": {category: board(db, category, display_rows(db), now=now) for category in CATEGORIES},
        "prompt": _prompt(db, now),
    }


def initials_value(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{3}", value.strip()):
        raise ValueError("Enter three letters for the initials.")
    return value.strip().upper()


def backglass_request(instance, action, params):
    now = int(time.time() * 1000)
    with store.transaction(instance) as db:
        prepare(db)
        if action != "state":
            initials = initials_value(params.get("initials")) if action == "submit" else ""
            target = (params.get("gameId"), params.get("playerId"))
            if any(not isinstance(value, str) for value in target):
                raise ValueError("Select a valid result.")
            prompt = _prompt(db, now)
            if prompt and target == (prompt["gameId"], prompt["playerId"]):
                db.execute(
                    "UPDATE leaderboard SET initials=?, pending=0 WHERE game_id=? AND player_id=?",
                    (initials, *target),
                )
        return backglass_state(db, now)


def edit(db, game_id, player_id, name, initials, score):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError("Enter a name between 1 and 40 characters.")
    initials = "" if initials in ("", "---") else initials_value(initials)
    if type(score) is not int or not 0 <= score <= MAX_SCORE:
        raise ValueError(f"Enter a whole score between 0 and {MAX_SCORE:,}.")
    return db.execute(
        """UPDATE leaderboard SET name=?, initials=?, score=?, pending=0 WHERE game_id=? AND player_id=?""",
        (name.strip(), initials, score, game_id, player_id),
    ).rowcount


def export_rows(db):
    prepare(db)
    return list(db.execute("SELECT game_id,player_id,name,initials,score,ended_at FROM leaderboard"))


def restore_rows(db, managed):
    db.execute("DELETE FROM documents WHERE key='leaderboardRows'")
    if store.read(db, "leaderboardInitialized", False):
        db.execute("DELETE FROM leaderboard")
    db.execute("DELETE FROM documents WHERE key='leaderboardInitialized'")
    prepare(db)
    if "leaderboard" not in managed:
        return
    db.execute("DELETE FROM leaderboard")
    db.executemany(
        "INSERT INTO leaderboard(game_id,player_id,name,initials,score,ended_at) VALUES(?,?,?,?,?,?)",
        managed["leaderboard"],
    )
    rows = managed.get("leaderboardRows", 5)
    if type(rows) is int and 1 <= rows <= 10:
        store.write(db, "leaderboardRows", rows)
