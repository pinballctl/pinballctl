"""Routes for the live view UI."""
from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the live view page shell."""
    return render_template("liveview.html", title="Live View")
