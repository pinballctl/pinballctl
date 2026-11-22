from flask import render_template
from . import bp


@bp.get("/")
def index():
    return render_template("management.html", title="Ball Management", manager="ball")
