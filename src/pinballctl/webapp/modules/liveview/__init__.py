"""Compatibility route for the former Live View page."""
from flask import Blueprint

MODULE_META = {"show_in_menu": False}
bp = Blueprint("liveview", __name__)

from . import views  # noqa
