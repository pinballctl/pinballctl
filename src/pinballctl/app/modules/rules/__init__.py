"""Blueprints for authoring and persisting gameplay rules."""

from flask import Blueprint

MODULE_META = {
    "title": "Rules",
    "order": 10,
    "icon": "toolbox",
}

bp = Blueprint("rules", __name__, template_folder="templates", static_folder="static")
api_bp = Blueprint("rules_api", __name__)

from . import views, api  # noqa
