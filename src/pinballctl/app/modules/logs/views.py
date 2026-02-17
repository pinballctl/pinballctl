"""Routes for the log viewer UI."""
from flask import Blueprint, render_template

ui_bp = Blueprint("logs_ui", __name__, template_folder="templates", static_folder="static")

@ui_bp.get("/")
def index():
    """Render the log viewer shell."""
    return render_template("logs.html", title="Logs")
