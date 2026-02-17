"""Events API module."""

from flask import Blueprint

api_bp = Blueprint("events_api", __name__)

MODULE_META = {
    "title": "Events",
    "order": 200,
    "icon": "⚡",
    "show_in_menu": False,
}
