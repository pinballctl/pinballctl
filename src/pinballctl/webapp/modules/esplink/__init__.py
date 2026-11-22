"""ESPLink firmware management module wiring its UI and API blueprints."""
MODULE_META = {
    "title": "ESPLink",
    "order": 40,
    "icon": "microchip",
    "show_in_menu": True
}

def init_module(app):
    """Register UI and API blueprints for ESPLink if not already attached."""
    from .views import ui_bp
    from .api import api_bp, sync_bp
    if "esplink_ui" not in app.blueprints:
        app.register_blueprint(ui_bp, url_prefix="/esplink")
    if "esplink_api" not in app.blueprints:
        app.register_blueprint(api_bp, url_prefix="/esplink/api")
    if "esplink_sync_api" not in app.blueprints:
        app.register_blueprint(sync_bp, url_prefix="/api/esplink")
