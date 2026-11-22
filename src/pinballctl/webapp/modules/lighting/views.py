"""Routes for the lighting authoring UI."""
from flask import render_template
from . import bp


@bp.get("/")
def index():
    return render_template("lighting.html", title="Lighting")

