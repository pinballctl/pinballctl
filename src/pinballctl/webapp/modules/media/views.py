"""Routes for media module UI."""

from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("media.html", title="Media")
