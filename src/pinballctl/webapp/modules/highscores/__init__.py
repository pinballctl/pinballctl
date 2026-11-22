"""High Scores operator and backglass routes."""
from flask import Blueprint

bp = Blueprint("highscores", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("highscores_api", __name__)
MODULE_META = {"title": "High Scores", "order": 11.5, "icon": "trophy", "category": "authoring"}

from . import routes  # noqa: E402,F401
