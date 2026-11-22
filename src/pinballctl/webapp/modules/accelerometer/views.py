"""Routes for accelerometer runtime/calibration UI."""
from flask import render_template

from . import bp


@bp.get("/")
def index():
    return render_template("accelerometer.html", title="Accelerometer")

