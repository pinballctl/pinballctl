"""Routes for the playfield UI."""
from flask import render_template, request
from . import bp

@bp.get("/")
def index():
    """Render the playfield page shell."""
    tab = request.args.get("tab")
    initial_tab = tab if tab in {"stage", "settings", "live", "rules-state"} else "stage"
    return render_template("playfield.html", title="Playfield", initial_tab=initial_tab)
