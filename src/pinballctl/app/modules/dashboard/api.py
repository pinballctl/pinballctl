"""API endpoints backing the dashboard widgets."""
from flask import jsonify
from . import api_bp
from .services import get_dashboard_status

# ---------- endpoints ---------------------------------------------------------

@api_bp.get("/status")
def api_status():
    """Return composite uptime/bridge/wifi status for the dashboard."""
    return jsonify(get_dashboard_status())
