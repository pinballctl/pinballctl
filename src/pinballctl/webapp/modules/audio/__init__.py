"""Audio module wiring and menu metadata."""

from flask import Blueprint

bp = Blueprint("audio", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("audio_api", __name__)

MODULE_META = {
    "title": "Audio",
    "order": 13,
    "icon": "music",
    "category": "authoring",
}

from . import views, api  # noqa
