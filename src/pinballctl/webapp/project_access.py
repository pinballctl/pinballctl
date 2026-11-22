"""Apply the project maintenance barrier to HTTP requests."""

import json
from pathlib import Path

from flask import g, jsonify, request

from pinballctl.runtime.backup.guard import access

from .settings_store import load_settings


def _refresh_restored_settings(app):
    root = Path(app.instance_path)
    path = root / ".project-locks" / "generation"
    try:
        stat = path.stat()
    except FileNotFoundError:
        return

    signature = (stat.st_mtime_ns, stat.st_ino, stat.st_size)
    if app.config.get("_RESTORE_SETTINGS_GENERATION") == signature:
        return

    metadata = json.loads(path.read_text())
    settings_version = metadata.get("components", {}).get("settings")
    if not settings_version and "settings" in metadata.get("affected", []):
        settings_version = metadata.get("id")

    if settings_version and app.config.get("_RESTORE_SETTINGS_VERSION") != settings_version:
        data = load_settings(root)
        app.config["USER_SETTINGS"] = data
        app.config["_RESTORE_SETTINGS_VERSION"] = settings_version
        for name in ("LOG_LEVEL", "CURRENCY"):
            if name in data:
                app.config[name] = data[name]
            else:
                app.config.pop(name, None)
    app.config["_RESTORE_SETTINGS_GENERATION"] = signature


def install(app):
    """Keep requests out of an active restore and reload restored settings."""

    @app.before_request
    def project_barrier():
        if request.path.startswith(("/api/backups", "/backups", "/assets/")) or str(request.endpoint).endswith(".static"):
            return
        manager = access(app.instance_path)
        try:
            manager.__enter__()
        except RuntimeError as exc:
            return jsonify(ok=False, error="project_maintenance", detail=str(exc)), 503
        g._project_backup_access = manager
        _refresh_restored_settings(app)

    @app.teardown_request
    def release_project_barrier(error):
        manager = g.pop("_project_backup_access", None)
        if manager is not None:
            manager.__exit__(None, None, None)
