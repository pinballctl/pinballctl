"""Routes for audio module UI."""

from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("audio.html", title="Audio")
