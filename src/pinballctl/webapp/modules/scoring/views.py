"""Routes for the scoring authoring UI."""

from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("scoring.html", title="Scoring")
