"""Routes for the ESPLink firmware UI."""
from flask import Blueprint, render_template
ui_bp = Blueprint("esplink_ui", __name__, template_folder="templates", static_folder="static")

@ui_bp.get("/")
def index():
    """Render the ESPLink page shell."""
    return render_template("esplink.html", title="ESPLink")
