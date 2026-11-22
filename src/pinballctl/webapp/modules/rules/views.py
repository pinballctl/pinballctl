"""Routes for the rules editor UI."""

from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the rules page shell."""
    return render_template("rules.html", title="Rules")
