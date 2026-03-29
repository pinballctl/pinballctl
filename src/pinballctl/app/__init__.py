"""Flask app factory and supporting helpers for pinballctl."""

from __future__ import annotations
import os
import importlib
import time
from threading import Thread
from importlib import metadata as importlib_metadata
from pathlib import Path
from flask import (
    Flask, jsonify, session, request, redirect, url_for, send_from_directory, abort, render_template
)
from . import config as config_module
from pinballctl.log_maintenance import maintain_logs_once
from pinballctl.media.runtime import ensure_media_bus_worker
from pinballctl.scoring.runtime import ensure_scoring_bus_worker
from pinballctl.audio.runtime import ensure_audio_bus_worker
from werkzeug.security import check_password_hash

try:
    import fcntl  # Linux/Pi runtime
except Exception:  # pragma: no cover - non-POSIX fallback
    fcntl = None

# ---------------- Version loader ----------------
def _load_version() -> str:
    """Find an app version from env, pyproject, package metadata, or default."""
    env_v = os.environ.get("PINBALLCTL_VERSION")
    if env_v:
        return env_v
    try:
        import tomllib
    except Exception:
        tomllib = None
    if tomllib:
        here = Path(__file__).resolve()
        for parent in list(here.parents)[:6]:
            pp = parent / "pyproject.toml"
            if pp.exists():
                try:
                    with pp.open("rb") as f:
                        data = tomllib.load(f)
                    v = (data.get("project", {}).get("version")
                         or data.get("tool", {}).get("poetry", {}).get("version"))
                    if v:
                        return str(v)
                except Exception:
                    pass
    try:
        from pinballctl import __version__ as _pkg_ver
        if _pkg_ver:
            return str(_pkg_ver)
    except Exception:
        pass
    try:
        return importlib_metadata.version("pinballctl")
    except Exception:
        pass
    return "0.0.0"

# ---------------- Auth helpers ----------------
def _auth_enabled(app: Flask) -> bool:
    """Return True if auth is enabled by config or environment toggle."""
    cfg = app.config.get("AUTH_ENABLED")
    if cfg is None:
        val = os.environ.get("PINBALLCTL_AUTH", "on").lower()
        return val not in ("0", "no", "false", "off")
    return bool(cfg)

def _get_user_pass_from_config(app: Flask):
    """Pull username/password checker from config/env, preferring hashed secrets."""
    user = app.config.get("AUTH_USER") or os.environ.get("PINBALLCTL_USER") or "admin"
    pwd = app.config.get("AUTH_PASSWORD") or os.environ.get("PINBALLCTL_PASSWORD")
    pwd_hash = app.config.get("AUTH_PASSWORD_HASH") or os.environ.get("PINBALLCTL_PASSWORD_HASH")

    if pwd_hash:
        def checker(candidate: str) -> bool:
            try:
                return check_password_hash(pwd_hash, candidate)
            except Exception:
                return False
    else:
        def checker(candidate: str) -> bool:
            return (pwd or "admin") == candidate
    return user, checker


def _media_autostart_lock(instance_path: str | Path):
    """Cross-process lockfile for media autostart sequence."""
    media_dir = Path(instance_path) / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    lock_path = media_dir / ".autostart.lock"
    lock_fp = lock_path.open("a+", encoding="utf-8")
    if fcntl is not None:
        try:
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
    return lock_fp


def _autostart_media_targets(cfg: dict) -> list[dict]:
    displays = [d for d in (cfg.get("displays") if isinstance(cfg.get("displays"), list) else []) if isinstance(d, dict)]
    scenes = [s for s in (cfg.get("scenes") if isinstance(cfg.get("scenes"), list) else []) if isinstance(s, dict)]
    settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
    default_map = settings.get("defaultScenesByDisplay") if isinstance(settings.get("defaultScenesByDisplay"), dict) else {}
    autoplay_map = settings.get("autoplayByDisplay") if isinstance(settings.get("autoplayByDisplay"), dict) else {}

    targets: list[dict] = []
    used_pairs: set[tuple[str, str]] = set()

    for d in displays:
        if not bool(d.get("enabled", True)):
            continue
        did = str(d.get("id") or "").strip()
        if not bool(autoplay_map.get(did, False)):
            continue
        sid = str(default_map.get(did) or "").strip()
        if not sid:
            continue
        scene = next((s for s in scenes if str(s.get("id") or "").strip() == sid), None)
        if not isinstance(scene, dict):
            continue
        pair = (did, sid)
        if pair in used_pairs:
            continue
        targets.append({"displayId": did, "sceneId": sid})
        used_pairs.add(pair)

    if targets:
        return targets
    return []


def _start_media_autodisplays_worker(app: Flask) -> None:
    """Best-effort media autostart launched after app/service boot."""
    try:
        from .settings_store import load_settings
        from pinballctl.media.runtime import load_media_config, load_media_state, play_scene
        from pinballctl.app.modules.media.kiosk_auth import make_runtime_token
    except Exception:
        app.logger.exception("Media autostart imports failed")
        return

    with app.app_context():
        lock_fp = _media_autostart_lock(app.instance_path)
        try:
            cfg = load_media_config(app.instance_path)
            if not bool((cfg.get("settings") or {}).get("enabled", True)):
                app.logger.info("Media autostart skipped: media module disabled")
                return

            targets = _autostart_media_targets(cfg)
            if not targets:
                app.logger.info("Media autostart skipped: no scenes with base assets configured")
                return

            state = load_media_state(app.instance_path)
            active = state.get("engine", {}).get("active", []) if isinstance(state.get("engine"), dict) else []
            active_pairs = {
                (str(row.get("displayId") or "").strip(), str(row.get("sceneId") or "").strip())
                for row in (active if isinstance(active, list) else [])
                if isinstance(row, dict)
            }
            target_pairs = {
                (str(row.get("displayId") or "").strip(), str(row.get("sceneId") or "").strip())
                for row in targets
                if isinstance(row, dict)
            }
            if active_pairs and target_pairs and all(pair in active_pairs for pair in target_pairs):
                app.logger.info("Media autostart skipped: target scenes already running")
                return

            base_url = str(
                os.environ.get("PINBALLCTL_BASE_URL")
                or os.environ.get("PINBALLCTL_MEDIA_BASE_URL")
                or ""
            ).strip() or None
            secret = str(app.secret_key or app.config.get("SECRET_KEY") or "")
            token = make_runtime_token(secret, ttl_seconds=24 * 3600)

            # Retry for display session readiness (X/Wayland can come up after web service).
            attempts = 18
            delay_s = 5.0
            for idx in range(attempts):
                launched = 0
                retryable_fail = False
                for target in targets:
                    sid = str((target or {}).get("sceneId") or "").strip()
                    did = str((target or {}).get("displayId") or "").strip() or None
                    if not sid:
                        continue
                    res = play_scene(
                        app.instance_path,
                        scene_id=sid,
                        display_id=did,
                        base_url=base_url,
                        runtime_token=token,
                        launch_mode="fullscreen",
                    )
                    if res.get("ok"):
                        launched += 1
                        continue
                    err = str(res.get("error") or "")
                    if err.startswith("spawn_failed"):
                        retryable_fail = True
                    app.logger.warning("Media autostart failed for scene %s: %s", sid, err or "unknown_error")
                if launched > 0:
                    app.logger.info("Media autostart launched %s scene(s)", launched)
                    return
                if not retryable_fail or idx >= attempts - 1:
                    return
                time.sleep(delay_s)
        finally:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                lock_fp.close()
            except Exception:
                pass


def _start_media_autodisplays_async(app: Flask) -> None:
    try:
        Thread(target=_start_media_autodisplays_worker, args=(app,), name="pinballctl-media-autostart", daemon=True).start()
    except Exception:
        app.logger.exception("Failed to create media autostart thread")


def _prepare_godot_video_cache_worker(app: Flask) -> None:
    try:
        from pinballctl.media.runtime import load_media_config
        from pinballctl.media import godot_runtime
    except Exception:
        app.logger.exception("Godot video cache prep imports failed")
        return

    with app.app_context():
        last_summary: tuple[int, int, int, int] | None = None
        while True:
            try:
                cfg = load_media_config(app.instance_path)
                settings = cfg.get("settings") if isinstance(cfg.get("settings"), dict) else {}
                result = godot_runtime.prepare_video_assets(app.instance_path)
                summary = (
                    int(result.get("prepared") or 0),
                    int(result.get("ready") or 0),
                    int(result.get("pending") or 0),
                    int(result.get("failed") or 0),
                )
                if summary != last_summary:
                    app.logger.info(
                        "Godot video cache prep: prepared=%s ready=%s pending=%s failed=%s",
                        summary[0],
                        summary[1],
                        summary[2],
                        summary[3],
                    )
                    last_summary = summary
            except Exception:
                app.logger.exception("Godot video cache prep failed")
            time.sleep(3.0)


def _prepare_godot_video_cache_async(app: Flask) -> None:
    try:
        Thread(target=_prepare_godot_video_cache_worker, args=(app,), name="pinballctl-godot-video-cache", daemon=True).start()
    except Exception:
        app.logger.exception("Failed to create Godot video cache prep thread")

# ---------------- Assets blueprint ----------------
def _make_assets_blueprint(app_root: Path):
    """Serve built assets from packaged paths or a local ./assets directory in dev."""
    from flask import Blueprint

    assets_bp = Blueprint("assets", __name__)

    search_dirs = [
        app_root / "static",
        app_root / "core" / "static",
    ]

    # if running from repo, support a top-level ./assets directory
    repo_assets = None
    for parent in list((app_root).parents)[:6]:
        if (parent / "pyproject.toml").exists():
            if (parent / "assets").exists():
                repo_assets = parent / "assets"
            break
    if repo_assets:
        search_dirs.insert(0, repo_assets)

    @assets_bp.route("/assets/<path:filename>")
    def serve_asset(filename: str):
        """Serve static assets from known search paths (repo/static first)."""
        for base in search_dirs:
            fp = base / filename
            if fp.is_file():
                return send_from_directory(base, filename)
        abort(404)

    return assets_bp

# ---------------- App factory ----------------
def create_app() -> Flask:
    """Create and configure the Flask app, auto-loading modules and assets."""
    # Always use src/instance as Flask's instance directory
    app_root = Path(__file__).resolve().parent          # .../src/pinballctl/app
    src_root = app_root.parent.parent                    # .../src
    instance_dir = src_root / "instance"
    instance_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(
        __name__,
        instance_path=str(instance_dir),
        instance_relative_config=True,
    )
    app.config.from_object(config_module)
    app.config["DOCS_URL"] = os.environ.get("PINBALLCTL_DOCS_URL", app.config.get("DOCS_URL", "https://docs.pinballctl.com"))
    app.logger.info("pinballctl instance_path = %s", app.instance_path)

    # Overlay user settings from instance/settings/settings.json onto app.config
    try:
        from .settings_store import load_settings, apply_to_app

        user_settings = load_settings(app.instance_path)
        app.config["USER_SETTINGS"] = user_settings
        apply_to_app(app, user_settings)
        # Surface log level into environment for bridge debug
        if user_settings.get("LOG_LEVEL"):
            os.environ["PINBALLCTL_LOG_LEVEL"] = str(user_settings["LOG_LEVEL"])
    except Exception:
        app.logger.exception("Failed to load user settings")

    # Secret key for sessions
    app.secret_key = app.config.get("SECRET_KEY") or os.environ.get("PINBALLCTL_SECRET", "dev-not-secret-change-me")

    # Version in templates
    app.config["APP_VERSION"] = _load_version()

    @app.context_processor
    def _inject_globals():
        """Inject version/auth context into all templates."""
        return {
            "app_version": app.config.get("APP_VERSION", "0.0.0"),
            "logged_in": bool(session.get("user")),
            "current_user": session.get("user"),
        }

    # Dev flags
    dev = os.environ.get("PINBALLCTL_DEVMODE") in ("1", "true", "True", "yes")
    app.config.setdefault("TEMPLATES_AUTO_RELOAD", True)
    app.jinja_env.auto_reload = True
    if app.debug or dev:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    # Register assets blueprint FIRST so it's available on login screen
    app.register_blueprint(_make_assets_blueprint(app_root))  # pass .../src/pinballctl

    # Core blueprint (templates + internal static at /core/static)
    from .core import core_bp
    app.register_blueprint(core_bp)

    # Allow: {% extends "core/templates/base.html" %}
    from jinja2 import ChoiceLoader, PrefixLoader
    app.jinja_loader = ChoiceLoader([
        app.jinja_loader,
        PrefixLoader({
            "core": PrefixLoader({
                "templates": core_bp.jinja_loader
            })
        }),
    ])

    # Module auto-discovery
    registry = []
    modules_dir = app_root / "modules"
    pkg_prefix = __name__  # 'pinballctl.app'

    if modules_dir.exists():
        for pkg_path in sorted(p for p in modules_dir.iterdir()
                               if p.is_dir() and (p / "__init__.py").exists()):
            pkg = pkg_path.name
            try:
                mod = importlib.import_module(f"{pkg_prefix}.modules.{pkg}")

                # Preload route submodules (views/api and legacy names)
                for sub in ("views", "api", "page_routes", "api_routes"):
                    try:
                        importlib.import_module(f"{pkg_prefix}.modules.{pkg}.{sub}")
                    except ModuleNotFoundError:
                        pass

                if hasattr(mod, "init_module"):
                    mod.init_module(app)

                if hasattr(mod, "bp"):
                    app.register_blueprint(mod.bp, url_prefix=f"/{pkg}")

                if hasattr(mod, "api_bp"):
                    app.register_blueprint(mod.api_bp, url_prefix=f"/api/{pkg}")

                meta = getattr(
                    mod, "MODULE_META",
                    {"title": pkg.capitalize(), "order": 100, "icon": "•"}
                )
                meta["name"] = pkg

                # Only show in menu if explicitly allowed AND there is a page blueprint
                show_in_menu = meta.get("show_in_menu", True)
                if show_in_menu:
                    registry.append(meta)

            except Exception:
                app.logger.exception("Failed to load module %s", pkg)
                raise

    registry.sort(key=lambda m: m.get("order", 100))
    app.config["MODULE_REGISTRY"] = registry

    @app.get("/api/menu")
    def api_modules():
        """Expose module metadata consumed by the sidebar/menu."""
        return jsonify(app.config.get("MODULE_REGISTRY", []))

    # Auth middleware
    @app.before_request
    def _auth_gate():
        """Redirect unauthenticated users to login except for exempt routes."""
        try:
            maintain_logs_once(throttle_s=30.0)
        except Exception:
            pass
        if not _auth_enabled(app):
            return

        ep = (request.endpoint or "")
        p = request.path or "/"

        if p.startswith("/assets/") or ep == "static" or ep.endswith(".static"):
            return
        if p in ("/login", "/logout", "/favicon.ico"):
            return
        if p.startswith("/api/health"):
            return
        if (
            p.startswith("/api/media/assets/file/")
            or p.startswith("/api/media/fonts/stylesheet")
            or p.startswith("/api/media/fonts/file/")
            or p.startswith("/api/media/complete")
            or p == "/api/events/fire"
        ):
            tok = request.args.get("kiosk_token", "")
            if tok:
                try:
                    from pinballctl.app.modules.media.kiosk_auth import verify_runtime_token

                    secret = str(app.secret_key or app.config.get("SECRET_KEY") or "")
                    if verify_runtime_token(secret, tok):
                        return
                except Exception:
                    pass
        if session.get("user"):
            return

        if p.startswith("/api/"):
            return ("Unauthorized", 401)
        return redirect(url_for("core.login", next=request.full_path or "/"))

    @app.get("/")
    def home():
        """Redirect to the first registered module's page."""
        mods = app.config.get("MODULE_REGISTRY", [])
        if not mods:
            return "No modules installed", 500
        first = mods[0]["name"]
        return f"<meta http-equiv='refresh' content='0; url=/{first}'>Redirecting to /{first}..."

    @app.errorhandler(404)
    def not_found(err):
        """Consistent not-found response across UI and APIs."""
        wants_json = (
            request.path.startswith("/api/")
            or request.accept_mimetypes["application/json"] >= request.accept_mimetypes["text/html"]
        )
        if wants_json:
            return jsonify({"ok": False, "error": "not_found", "path": request.path}), 404
        return render_template("404.html", title="Not Found", missing_path=request.path), 404

    app.config["_AUTH_GET_USER_PASS"] = lambda: _get_user_pass_from_config(app)

    try:
        ensure_media_bus_worker(
            app.instance_path,
            logger=lambda msg: app.logger.debug(msg),
        )
    except Exception:
        app.logger.exception("Failed to start media bus worker")
    try:
        ensure_scoring_bus_worker(
            app.instance_path,
            logger=lambda msg: app.logger.debug(msg),
        )
    except Exception:
        app.logger.exception("Failed to start scoring bus worker")
    try:
        ensure_audio_bus_worker(
            app.instance_path,
            logger=lambda msg: app.logger.debug(msg),
        )
    except Exception:
        app.logger.exception("Failed to start audio bus worker")

    _start_media_autodisplays_async(app)

    return app
