from flask import Blueprint

bp = Blueprint("ball", __name__)
api_bp = Blueprint("ball_api", __name__)
MODULE_META = {
    "title": "Ball Management",
    "order": 10,
    "icon": "circle",
    "category": "authoring",
}
from . import views
from ..game.api import install_api

install_api(api_bp, "ball")
