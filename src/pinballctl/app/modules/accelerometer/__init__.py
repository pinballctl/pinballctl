"""Accelerometer module wiring and menu metadata."""
from flask import Blueprint

bp = Blueprint("accelerometer", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("accelerometer_api", __name__)

MODULE_META = {
    "title": "Accelerometer",
    "order": 5,
    "icon": "compass",
    "category": "overview",
}

from . import views, api  # noqa
