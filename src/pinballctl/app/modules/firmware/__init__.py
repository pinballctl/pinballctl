"""Firmware module: UI + API for serving firmware manifests/binaries."""

MODULE_META = {
    "title": "Firmware",
    "order": 50,
    "icon": "download",
    "show_in_menu": True,
}

def init_module(app):
    """Register UI and API blueprints."""
    from .views import ui_bp
    from .api import api_bp
    if "firmware" not in app.blueprints:
        app.register_blueprint(ui_bp, url_prefix="/firmware")
    if "firmware_api" not in app.blueprints:
        app.register_blueprint(api_bp, url_prefix="/api/firmware")

__all__ = ["init_module", "MODULE_META"]
