"""UI blueprint for settings."""

from flask import Blueprint, render_template

ui_bp = Blueprint("settings_ui", __name__, template_folder="templates", static_folder="static")


@ui_bp.get("/")
def settings_home():
    # Template lives under this blueprint's templates/ dir, so render relative.
    return render_template("settings.html")
