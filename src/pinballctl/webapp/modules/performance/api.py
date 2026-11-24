import time
from flask import jsonify, request
from . import api_bp
from pinballctl.runtime.bridge.state import rpc_command, read_state, connection_live

@api_bp.get('/status')
def status():
    bridge = read_state()
    connected = connection_live(bridge)
    last_esp_message_at = bridge.get("last_rx_at")
    command = {"cmd": "BRIDGE_PERF", "history": request.args.get("history") != "0"}
    after = request.args.get("after", type=float)
    if after is not None:
        command["after"] = after
    try:
        metrics = rpc_command(command, "BRIDGE_PERF", timeout_s=0.5, wait_for_startup=False)
    except (RuntimeError, OSError):
        metrics = None
    if not isinstance(metrics, dict):
        return jsonify(ok=False, connected=connected, last_esp_message_at=last_esp_message_at,
                       error="Waiting for a response from the Bridge."), 503
    latest = metrics.get("latest")
    return jsonify(ok=True, connected=connected, last_esp_message_at=last_esp_message_at,
                   stale=latest is not None and time.time() - latest["at"] > 3, **metrics)


@api_bp.post('/reset-overload')
def reset_overload():
    try:
        result = rpc_command({'cmd': 'BRIDGE_PERF_RESET'}, 'BRIDGE_PERF_RESET',
                             timeout_s=1, wait_for_startup=False)
    except (RuntimeError, OSError):
        result = None
    if not isinstance(result, dict):
        return jsonify(ok=False, error='Bridge unavailable'), 503
    return jsonify(result), 200 if result.get('ok') else 409
