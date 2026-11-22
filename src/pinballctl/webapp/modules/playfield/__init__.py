"""Blueprints for the playfield UI and API."""
from flask import Blueprint

MODULE_META = {
    "title": "Playfield",
    "order": 20,
    "icon": "cubes-stacked",
}

bp = Blueprint("playfield", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("playfield_api", __name__)

from . import views, api  # noqa
