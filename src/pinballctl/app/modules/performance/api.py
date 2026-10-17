import time
from flask import jsonify
from . import api_bp
from pinballctl.bridge.state import rpc_command, read_state, connection_live

@api_bp.get('/status')
def status():
    try:
        metrics = rpc_command({'cmd': 'BRIDGE_PERF'}, 'BRIDGE_PERF', timeout_s=1)
    except (RuntimeError, OSError):
        metrics = None
    if not isinstance(metrics, dict) or not metrics.get('latest'):
        return jsonify(ok=False, error='Bridge performance metrics unavailable'), 503
    bridge = read_state()
    latest = metrics['latest']
    return jsonify(ok=True, connected=connection_live(bridge),
                   stale=time.time() - latest['at'] > 3, **metrics)


@api_bp.post('/reset-overload')
def reset_overload():
    try:
        result = rpc_command({'cmd': 'BRIDGE_PERF_RESET'}, 'BRIDGE_PERF_RESET', timeout_s=1)
    except (RuntimeError, OSError):
        result = None
    if not isinstance(result, dict):
        return jsonify(ok=False, error='Bridge unavailable'), 503
    return jsonify(result), 200 if result.get('ok') else 409
