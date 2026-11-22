"""Private loopback requests from Godot display processes."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
from pathlib import Path
import secrets
from threading import Thread

from pinballctl.runtime.backup.guard import access
from pinballctl.runtime.bridge.state import is_headless_mode
from pinballctl.runtime.events.ingress import fire
from pinballctl.runtime.scoring.leaderboard import backglass_request

EVENT_PATH = "/api/events/fire"
SCORES_PATH = "/api/highscores/backglass"
URL_ENV = "PINBALLCTL_BACKGLASS_EVENT_URL"
TOKEN_ENV = "PINBALLCTL_BACKGLASS_TOKEN"
MAX_REQUEST_BYTES = 64 * 1024
LOG = logging.getLogger(__name__)


class BackglassServer(HTTPServer):
    def __init__(self, instance_path: Path):
        self.instance_path = instance_path
        self.token = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", 0), BackglassHandler)

    def get_request(self):
        conn, address = super().get_request()
        conn.settimeout(3)
        return conn, address


class BackglassHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        LOG.debug(format, *args)

    def _respond(self, body: dict, status: int = 200) -> None:
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path not in (EVENT_PATH, SCORES_PATH):
            self._respond({"ok": False, "error": "not_found"}, 404)
            return
        expected = f"Bearer {self.server.token}".encode()
        supplied = self.headers.get("Authorization", "").encode()
        if not secrets.compare_digest(supplied, expected):
            self._respond({"ok": False, "error": "unauthorized"}, 401)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_REQUEST_BYTES:
                raise ValueError("invalid_length")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("invalid_json")
        except (ValueError, UnicodeError):
            self._respond({"ok": False, "error": "invalid_request"}, 400)
            return

        instance = self.server.instance_path
        try:
            with access(instance):
                if self.path == EVENT_PATH:
                    # Scenes can emit events but cannot impersonate hardware or
                    # provide private manager/bridge context.
                    if is_headless_mode():
                        _ensure_local_workers(instance)
                    body, status = fire(instance, {"name": payload.get("name"), "params": payload.get("params")})
                else:
                    action = payload.get("action")
                    if action not in ("state", "submit", "skip"):
                        raise ValueError("Unknown backglass action.")
                    body = {"ok": True, "leaderboard": backglass_request(instance, action, payload)}
                    status = 200
        except ValueError as exc:
            body, status = {"ok": False, "error": str(exc)}, 400
        except Exception:
            LOG.exception("Backglass request failed for %s", self.path)
            body, status = {"ok": False, "error": "request_failed"}, 503
        self._respond(body, status)


def _ensure_local_workers(instance: Path) -> None:
    from pinballctl.runtime.audio.runtime import ensure_audio_bus_worker
    from pinballctl.runtime.game.runtime import ensure_worker
    from pinballctl.runtime.media.runtime import ensure_media_bus_worker
    from pinballctl.runtime.scoring.runtime import ensure_scoring_bus_worker

    ensure_worker(instance)
    ensure_audio_bus_worker(instance)
    ensure_media_bus_worker(instance)
    ensure_scoring_bus_worker(instance)


@contextmanager
def serve(instance_path: Path):
    """Keep the private endpoint active for the supervisor's lifetime."""
    with BackglassServer(instance_path) as server:
        thread = Thread(target=server.serve_forever, name="pinballctl-backglass-api", daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}{EVENT_PATH}", server.token
        finally:
            server.shutdown()
            thread.join()
