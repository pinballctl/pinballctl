"""Routes for media module UI."""

from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("media.html", title="Media")


@bp.get("/runtime/display/<display_id>")
def runtime_display(display_id: str):
    return render_template("media_runtime_display.html", title="Media Runtime", display_id=display_id)
