"""API endpoints backing the dashboard widgets."""
from json import JSONDecodeError
import sqlite3

from flask import current_app, jsonify

from . import api_bp
from .services import get_dashboard_status, get_gameplay_summary, get_machine_summary

# ---------- endpoints ---------------------------------------------------------

@api_bp.get("/status")
def api_status():
    """Return hardware status, gameplay totals, and recorded service activity."""
    status = get_dashboard_status()
    try:
        status["gameplay"] = get_gameplay_summary(current_app.instance_path)
    except (JSONDecodeError, OSError, sqlite3.Error):
        current_app.logger.exception("Could not load dashboard game history")
        status["gameplay"] = None
    try:
        status["machine"] = get_machine_summary(current_app.instance_path)
    except (OSError, ValueError):
        current_app.logger.exception("Could not load dashboard service history")
        status["machine"] = None
    return jsonify(status)
