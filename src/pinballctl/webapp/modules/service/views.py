"""Routes for the service log UI."""
from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the service log page shell."""
    return render_template("service.html", title="Service Log")
