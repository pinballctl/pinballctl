from flask import Blueprint

bp = Blueprint("game", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("game_api", __name__)
MODULE_META = {
    "title": "Game Management",
    "order": 9,
    "icon": "play",
    "category": "authoring",
}
from . import api, views
