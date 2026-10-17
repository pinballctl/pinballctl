"""Acknowledged coil safety controls. Never arm or retry commands automatically."""
from flask import jsonify, request
from pinballctl.bridge.state import rpc_command
from . import api_bp


@api_bp.route("/coil-safety", methods=["GET", "POST"])
def coil_safety():
    payload = {"cmd": "COIL_STATUS"}
    if request.method == "POST":
        # A custom header and JSON prevent cross-origin forms from arming outputs.
        if request.headers.get("X-Coil-Control") != "1" or not request.is_json:
            return jsonify(error="JSON and X-Coil-Control required"), 400
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Invalid request"), 400
        action = data.get("action")
        commands = {"arm": "ENABLE", "disable": "DISABLE", "reset": "COIL_RESET"}
        if action not in commands:
            return jsonify(error="Unknown action"), 400
        payload = {"cmd": commands[action]}
        if action == "arm":
            generation = data.get("generation")
            if type(generation) is not int or not 0 <= generation <= 0xFFFFFFFF:
                return jsonify(error="Refresh status before arming"), 400
            payload["generation"] = generation
    try:
        result = rpc_command(payload, match_t="COIL_STATUS", timeout_s=2.0)
    except Exception:
        result = None
    if not isinstance(result, dict) or result.get("t") != "COIL_STATUS":
        return jsonify(error="Safety status unavailable; action not confirmed. Refresh before retrying."), 503
    return jsonify(result), 200 if result.get("ok") else 409
