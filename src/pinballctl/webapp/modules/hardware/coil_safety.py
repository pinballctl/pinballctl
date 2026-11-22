"""Read ESP safety status and acknowledge explicit fault resets."""
import time

from flask import jsonify, request
from pinballctl.runtime.bridge.state import read_state, rpc_command
from . import api_bp


@api_bp.route("/coil-safety", methods=["GET", "POST"])
def coil_safety():
    payload = {"cmd": "COIL_STATUS"}
    if request.method == "POST":
        # A custom header and JSON prevent cross-origin forms from resetting a fault.
        if request.headers.get("X-Coil-Control") != "1" or not request.is_json:
            return jsonify(error="JSON and X-Coil-Control required"), 400
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify(error="Invalid request"), 400
        if data.get("action") != "reset":
            return jsonify(error="Unknown action"), 400
        payload = {"cmd": "COIL_RESET"}
    try:
        result = rpc_command(payload, match_t="COIL_STATUS", timeout_s=2.0)
    except Exception:
        result = None
    if not isinstance(result, dict) or result.get("t") != "COIL_STATUS":
        return jsonify(error="Safety status unavailable; action not confirmed. Refresh before retrying."), 503
    return jsonify(result), 200 if result.get("ok") else 409


@api_bp.get("/coil-safety/summary")
def coil_safety_summary():
    state = read_state()
    status = state.get("coil_status")
    if state.get("connected") is True and isinstance(status, dict):
        reported_at = status.get("reported_at")
        if (isinstance(reported_at, (int, float)) and 0 <= time.time() - reported_at < 3
                and isinstance(status.get("armed"), bool) and isinstance(status.get("fault"), str)):
            return jsonify(armed=status["armed"], fault=status["fault"])
    return jsonify(armed=None, fault=None)
