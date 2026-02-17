"""Service log module wiring blueprints and menu metadata."""
from flask import Blueprint

bp = Blueprint("service", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("service_api", __name__)

MODULE_META = {
    "title": "Service Log",
    "order": 60,
    "icon": "wrench",
}

__all__ = ["bp", "api_bp", "MODULE_META"]
