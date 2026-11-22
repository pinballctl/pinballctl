"""UI routes for firmware versions."""

from flask import Blueprint, render_template

ui_bp = Blueprint("firmware", __name__, template_folder="templates", static_folder="static")

@ui_bp.get("/")
def page():
    """Render the firmware versions page (data fetched via API)."""
    return render_template("firmware.html")
