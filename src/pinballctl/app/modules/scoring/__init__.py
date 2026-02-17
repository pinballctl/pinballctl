"""Scoring module UI and API wiring."""

from flask import Blueprint

bp = Blueprint("scoring", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("scoring_api", __name__)

MODULE_META = {
    "title": "Scoring",
    "order": 11,
    "icon": "trophy",
    "category": "authoring",
}

from . import views, api  # noqa
