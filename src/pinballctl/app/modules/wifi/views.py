"""Routes for the Wi-Fi configuration UI."""
from flask import render_template
from . import bp


@bp.get("/")
def index():
    """Render the Wi-Fi configuration page shell."""
    return render_template("wifi.html", title=" · Wi-Fi")
