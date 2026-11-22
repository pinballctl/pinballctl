"""Routes for the hardware mapping UI."""
# File: hardware/views.py
from flask import render_template
from . import bp

@bp.get("/")
def index():
    """Render the hardware mapping page shell."""
    return render_template("hardware.html", title="Hardware Mapping")
