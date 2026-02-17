"""Routes for the playfield UI."""
from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the playfield page shell."""
    return render_template("playfield.html", title="Playfield")
