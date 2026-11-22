"""Integrity Check module wiring and menu metadata."""

from flask import Blueprint

bp = Blueprint("integrity", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("integrity_api", __name__)

MODULE_META = {
    "title": "Integrity Check",
    "order": 35,
    "icon": "shield-halved",
    "category": "platform",
}

from . import views, api  # noqa: E402,F401
