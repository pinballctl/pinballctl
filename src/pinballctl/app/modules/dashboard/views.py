"""Routes for the dashboard landing page."""
from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the dashboard page shell."""
    return render_template("dashboard.html", title=" · Dashboard")
