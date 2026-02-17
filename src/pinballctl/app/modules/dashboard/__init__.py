"""Dashboard module blueprints for the summary/home screen."""
from flask import Blueprint

bp = Blueprint("dashboard", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("dashboard_api", __name__)

MODULE_META = {"title": "Dashboard", "order": 0, "icon": "gauge"}

__all__ = ["bp", "api_bp", "MODULE_META"]
