import time

from flask import current_app, jsonify, render_template, request

from pinballctl.game import store
from pinballctl.scoring import leaderboard

from ..media.kiosk_auth import make_runtime_token, verify_runtime_token
from . import api_bp, bp


@bp.get("/")
def index():
    return render_template("highscores.html", title="High Scores", max_score=leaderboard.MAX_SCORE)


def _error(message, status=400):
    return jsonify(ok=False, error=message), status


def _body():
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


@api_bp.get("/")
def list_scores():
    category = request.args.get("category", "all-time")
    page = request.args.get("page", 1, type=int)
    if category not in leaderboard.CATEGORIES or not 1 <= page <= 100_000_000:
        return _error("Invalid leaderboard or page.")
    page_size = 25
    with store.transaction(current_app.instance_path) as db:
        leaderboard.prepare(db)
        rows = leaderboard.board(db, category, page_size + 1, (page - 1) * page_size)
        return jsonify(ok=True, scores=rows[:page_size], more=len(rows) > page_size,
                       displayRows=leaderboard.display_rows(db))


@api_bp.patch("/entry")
def update_entry():
    body = _body()
    game_id, player_id = body.get("gameId"), body.get("playerId")
    if not isinstance(game_id, str) or not isinstance(player_id, str):
        return _error("Select a valid result.")
    try:
        with store.transaction(current_app.instance_path) as db:
            leaderboard.prepare(db)
            updated = leaderboard.edit(db, game_id, player_id, body.get("name"), body.get("initials"), body.get("score"))
    except ValueError as exc:
        return _error(str(exc))
    return jsonify(ok=True) if updated else _error("Result no longer exists.", 404)


@api_bp.delete("/entry")
def delete_entry():
    body = _body()
    game_id, player_id = body.get("gameId"), body.get("playerId")
    if not isinstance(game_id, str) or not isinstance(player_id, str):
        return _error("Select a valid result.")
    with store.transaction(current_app.instance_path) as db:
        leaderboard.prepare(db)
        deleted = db.execute("DELETE FROM leaderboard WHERE game_id=? AND player_id=?", (game_id, player_id)).rowcount
    return jsonify(ok=True) if deleted else _error("Result no longer exists.", 404)


@api_bp.post("/reset")
def reset():
    if _body().get("confirm") is not True:
        return _error("Confirm that you want to clear every leaderboard.")
    with store.transaction(current_app.instance_path) as db:
        leaderboard.prepare(db)
        db.execute("DELETE FROM leaderboard")
    return jsonify(ok=True)


@api_bp.put("/settings")
def settings():
    rows = _body().get("displayRows")
    if type(rows) is not int or not 1 <= rows <= 10:
        return _error("Choose between 1 and 10 rows.")
    with store.transaction(current_app.instance_path) as db:
        store.write(db, "leaderboardRows", rows)
    return jsonify(ok=True)


@api_bp.post("/backglass")
def backglass():
    body = _body()
    action = body.get("action")
    if action not in ("state", "submit", "skip"):
        return _error("Unknown backglass action.")
    try:
        state = leaderboard.backglass_request(current_app.instance_path, action, body)
        token = request.args.get("kiosk_token", "")
        secret = current_app.secret_key
        scoped = verify_runtime_token(secret, token, scope="leaderboard")
        if scoped and int(token.split(".", 1)[0]) > time.time() + 3600:
            return jsonify(ok=True, leaderboard=state)
        if scoped or verify_runtime_token(secret, token):
            token = make_runtime_token(secret, scope="leaderboard")
            return jsonify(ok=True, leaderboard=state, leaderboardToken=token)
        return jsonify(ok=True, leaderboard=state)
    except ValueError as exc:
        return _error(str(exc))
