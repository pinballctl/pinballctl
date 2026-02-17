"""Hardware mapping module wiring blueprints and menu metadata."""
# File: hardware/__init__.py
from flask import Blueprint

bp = Blueprint("hardware", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("hardware_api", __name__)

MODULE_META = {
    "title": "Hardware",
    "order": 30,
    "icon": "microchip",
}

def init_module(app):
    """Placeholder initializer; kept for symmetry with other modules."""
    return None
