"""Media module wiring and menu metadata."""

from flask import Blueprint

bp = Blueprint("media", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("media_api", __name__)

MODULE_META = {
    "title": "Media",
    "order": 14,
    "icon": "film",
    "category": "authoring",
}

from . import views, api  # noqa
