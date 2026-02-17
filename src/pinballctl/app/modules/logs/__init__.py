"""Logs module: provides UI/API for tailing pinballctl log files."""

MODULE_META = {
    "title": "Logs",
    "order": 80,
    "icon": "file-text",
}

def init_module(app):
    """Register the logs UI and API blueprints if they are not already loaded."""
    from .views import ui_bp
    from .api import api_bp
    if "logs_ui" not in app.blueprints:
        app.register_blueprint(ui_bp, url_prefix="/logs")
    if "logs_api" not in app.blueprints:
        app.register_blueprint(api_bp, url_prefix="/logs/api")
