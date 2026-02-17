"""API for scoring config and runtime state."""
from __future__ import annotations

from flask import current_app, jsonify, request

from pinballctl.scoring.runtime import (
    load_game_history,
    load_high_scores,
    list_scoring_sources,
    load_scoring_config,
    load_scoring_state,
    reset_scoring_state,
    save_scoring_config,
)

from . import api_bp


@api_bp.get("/config")
def scoring_config_get():
    cfg = load_scoring_config(current_app.instance_path)
    return jsonify({"ok": True, "config": cfg})


@api_bp.post("/config")
def scoring_config_save():
    body = request.get_json(silent=True) or {}
    config = body.get("config") if isinstance(body, dict) else None
    if not isinstance(config, dict):
        return jsonify({"ok": False, "error": "invalid_config"}), 400
    saved = save_scoring_config(current_app.instance_path, config)
    return jsonify({"ok": True, "config": saved})


@api_bp.get("/state")
def scoring_state_get():
    state = load_scoring_state(current_app.instance_path)
    return jsonify({"ok": True, "state": state})


@api_bp.post("/reset")
def scoring_state_reset():
    state = reset_scoring_state(current_app.instance_path)
    return jsonify({"ok": True, "state": state})


@api_bp.get("/sources")
def scoring_sources():
    sources = list_scoring_sources(current_app.instance_path)
    return jsonify({"ok": True, "sources": sources})


@api_bp.get("/highscores")
def scoring_high_scores():
    scores = load_high_scores(current_app.instance_path)
    return jsonify({"ok": True, "highScores": scores})


@api_bp.get("/history")
def scoring_history():
    history = load_game_history(current_app.instance_path)
    return jsonify({"ok": True, "history": history})
