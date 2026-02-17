"""Bridge event handlers that hydrate shared snapshots for the web UI."""

from datetime import datetime
from flask import current_app

def handle_event(msg: dict):
    """Update in-memory status dicts (if Flask app exists) from a bridge message."""
    try:
        app = current_app._get_current_object()
        from pinballctl.app.routes import HARDWARE_SNAPSHOT, STATUS
        t = msg.get('t')
        if t == 'STAT':
            STATUS.update({k: msg.get(k, STATUS.get(k)) for k in ('coils_enabled', 'fault')})
        elif t in ('SCAN','HW'):
            HARDWARE_SNAPSHOT.update({k: msg.get(k) for k in ('expanders',)})
        HARDWARE_SNAPSHOT['last_update'] = datetime.utcnow().isoformat() + 'Z'
    except Exception:
        pass
