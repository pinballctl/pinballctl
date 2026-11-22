"""Routes for the live view UI."""
from flask import redirect, url_for

from . import bp

@bp.get("/")
def index():
    """Keep existing Live View bookmarks working."""
    return redirect(url_for("playfield.index", tab="live"))
