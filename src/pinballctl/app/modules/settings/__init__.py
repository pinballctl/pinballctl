"""Settings module: project name + import/export of instance data."""

MODULE_META = {
    "title": "Settings",
    "order": 90,
    "icon": "gear",
    "show_in_menu": True,
}


def init_module(app):
    """Register UI and API blueprints."""
    from .views import ui_bp
    from .api import api_bp
    if "settings" not in app.blueprints:
        app.register_blueprint(ui_bp, url_prefix="/settings")
    if "settings_api" not in app.blueprints:
        app.register_blueprint(api_bp, url_prefix="/api/settings")


__all__ = ["init_module", "MODULE_META"]
