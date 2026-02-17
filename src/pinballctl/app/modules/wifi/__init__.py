"""Blueprints for Wi-Fi status and configuration."""

from flask import Blueprint

bp = Blueprint("wifi", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("wifi_api", __name__)

MODULE_META = {"title": "Wi-Fi", "order": 70, "icon": "wifi", "category": "system"}

__all__ = ["bp", "api_bp", "MODULE_META"]
