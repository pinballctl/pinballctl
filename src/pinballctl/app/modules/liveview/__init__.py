"""Live View module wiring."""
from flask import Blueprint

MODULE_META = {
    "title": "Live View",
    "order": 21,
    "icon": "tower-broadcast",
    "category": "platform",
}

bp = Blueprint("liveview", __name__, template_folder="templates", static_folder="static")

from . import views  # noqa
