"""Routes for the live view UI."""
from flask import current_app, render_template

from pinballctl.app.modules.media.kiosk_auth import make_runtime_token
from . import bp

@bp.get("/")
def index():
    """Render the live view page shell."""
    secret = str(current_app.secret_key or current_app.config.get("SECRET_KEY") or "")
    runtime_token = make_runtime_token(secret, ttl_seconds=24 * 3600)
    return render_template("liveview.html", title="Live View", media_runtime_token=runtime_token)
