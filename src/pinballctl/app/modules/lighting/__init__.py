"""Lighting module wiring and menu metadata."""
from flask import Blueprint

bp = Blueprint("lighting", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("lighting_api", __name__)

MODULE_META = {
    "title": "Lighting",
    "order": 12,
    "icon": "sun",
    "category": "authoring",
}

from . import views, api  # noqa
