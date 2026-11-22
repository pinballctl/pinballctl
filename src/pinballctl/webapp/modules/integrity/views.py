"""Routes for integrity check UI."""

from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("integrity.html", title="Integrity Check")
