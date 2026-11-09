"""Persistent completed results shared by the operator UI and backglass."""

from datetime import datetime
import re
import time

from pinballctl.game import store

CATEGORIES = ("all-time", "year", "month", "latest")
COMPETITION = "competition"
MAX_SCORE = 2**53 - 1  # Exact in JavaScript and Godot's JSON reader.
PROMPT_MS = 60_000


def prepare(db):
    if not store.read(db, "competitionInitialized", False):
        db.execute("""CREATE TABLE IF NOT EXISTS competition_scores (
            game_id TEXT NOT NULL, player_id TEXT NOT NULL, name TEXT NOT NULL,
            initials TEXT NOT NULL DEFAULT '', score INTEGER NOT NULL,
            ended_at INTEGER NOT NULL, pending INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (game_id, player_id))""")
        store.write(db, "competitionInitialized", True)
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


def score_table(category):
    return "competition_scores" if category == COMPETITION else "leaderboard"


def competition(db):
    return store.read(db, "competition", {"title": "", "active": False})


def change_competition(db, action, title):
    game = store.read(db, "game", {})
    if game.get("status", "IDLE") not in ("IDLE", "GAME_ENDED"):
        raise ValueError("End the current game before changing the competition.")
    config = competition(db)
    if action in ("start", "rename"):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 48 or any(ord(c) < 32 for c in title):
            raise ValueError("Enter a competition title between 1 and 48 characters.")
        if action == "rename" and not config["title"]:
            raise ValueError("Start a competition before renaming it.")
        config["title"] = title.strip()
    if action in ("start", "reset"):
        db.execute("DELETE FROM competition_scores")
    if action in ("start", "stop"):
        config["active"] = action == "start"
    store.write(db, "competition", config)


def _insert(db, game_id, ended_at, player, category=None):
    name = player["name"]
    initials = name.upper() if re.fullmatch(r"[A-Za-z]{3}", name) else ""
    db.execute(
        f"""INSERT OR IGNORE INTO {score_table(category)}(game_id,player_id,name,initials,score,ended_at)
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
        f"""SELECT game_id,player_id,name,initials,score,ended_at FROM {score_table(category)}
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
    active = competition(db)["active"]
    for player in game["players"]:
        _insert(db, game["gameId"], game["endedAtMs"], player)
        if active:
            _insert(db, game["gameId"], game["endedAtMs"], player, COMPETITION)
    # Latest is chronological, so qualifying there would prompt every player.
    categories = (*CATEGORIES[:3], COMPETITION) if active else CATEGORIES[:3]
    for category in categories:
        for row in board(db, category, display_rows(db), now=game["endedAtMs"]):
            if row["gameId"] == game["gameId"] and row["score"] > 0 and row["initials"] == "---":
                db.execute(
                    f"UPDATE {score_table(category)} SET pending=1 WHERE game_id=? AND player_id=?",
                    (row["gameId"], row["playerId"]),
                )


def _prompt(db, now):
    game = store.read(db, "game", {})
    if game.get("status") != "GAME_ENDED":
        return None
    target = (game["gameId"], now - PROMPT_MS)
    row = db.execute(
        """SELECT game_id,player_id,name,score FROM (
            SELECT game_id,player_id,name,score,0 AS priority FROM leaderboard
            WHERE game_id=? AND pending=1 AND ended_at>=?
            UNION ALL
            SELECT game_id,player_id,name,score,1 AS priority FROM competition_scores
            WHERE game_id=? AND pending=1 AND ended_at>=?
        ) ORDER BY CAST(player_id AS INTEGER), player_id, priority LIMIT 1""",
        (*target, *target),
    ).fetchone()
    return dict(zip(("gameId", "playerId", "name", "score"), row)) if row else None


def backglass_state(db, now):
    config = competition(db)
    categories = (*CATEGORIES, COMPETITION) if config["active"] else CATEGORIES
    game = store.read(db, "game", {})
    player = game.get("currentPlayer", 0)
    score = store.read(db, "scores", {}).get(str(player), {})
    ball = store.read(db, "ball", {})
    return {
        "competition": config,
        "boards": {category: board(db, category, display_rows(db), now=now) for category in categories},
        "prompt": _prompt(db, now),
        "game": {
            "status": game.get("status", "IDLE"),
            "player": player,
            "ball": game.get("ballNumber", 0),
            "score": score.get("score", 0),
            "multiball": (ball.get("inPlay") or 0) > 1,
        },
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
                for table in ("leaderboard", "competition_scores"):
                    db.execute(
                        f"""UPDATE {table} SET initials=?, pending=0
                            WHERE game_id=? AND player_id=? AND initials=''""",
                        (initials, *target),
                    )
        return backglass_state(db, now)


def edit(db, game_id, player_id, name, initials, score, category=None):
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40:
        raise ValueError("Enter a name between 1 and 40 characters.")
    initials = "" if initials in ("", "---") else initials_value(initials)
    if type(score) is not int or not 0 <= score <= MAX_SCORE:
        raise ValueError(f"Enter a whole score between 0 and {MAX_SCORE:,}.")
    return db.execute(
        f"""UPDATE {score_table(category)} SET name=?, initials=?, score=?, pending=0 WHERE game_id=? AND player_id=?""",
        (name.strip(), initials, score, game_id, player_id),
    ).rowcount


def export_rows(db, category=None):
    prepare(db)
    return list(db.execute(f"SELECT game_id,player_id,name,initials,score,ended_at FROM {score_table(category)}"))


def restore_rows(db, managed):
    db.execute("DELETE FROM documents WHERE key='leaderboardRows'")
    if store.read(db, "leaderboardInitialized", False):
        db.execute("DELETE FROM leaderboard")
    db.execute("DELETE FROM documents WHERE key='leaderboardInitialized'")
    prepare(db)
    db.execute("DELETE FROM competition_scores")
    db.execute("DELETE FROM documents WHERE key='competition'")
    config = managed.get("competition")
    if config:
        store.write(db, "competition", config)
        db.executemany(
            "INSERT INTO competition_scores(game_id,player_id,name,initials,score,ended_at) VALUES(?,?,?,?,?,?)",
            managed.get("competitionScores", []),
        )
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
