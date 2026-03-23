"""Background daemon that owns the Godot process lifecycle outside Gunicorn workers."""
from __future__ import annotations

import json
import logging
import os
import signal
import socket
import sys
from pathlib import Path
from typing import Any, Dict

from pinballctl.media import godot_runtime


LOG = logging.getLogger(__name__)


def _read_request(conn: socket.socket) -> Dict[str, Any] | None:
    raw = b""
    while True:
        chunk = conn.recv(65536)
        if not chunk:
            break
        raw += chunk
        if b"\n" in raw:
            raw = raw.split(b"\n", 1)[0]
            break
    if not raw:
        return None
    try:
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return {"op": "", "payload": {}, "_decode_error": True}
    return data if isinstance(data, dict) else {"op": "", "payload": {}, "_decode_error": True}


def _write_response(conn: socket.socket, payload: Dict[str, Any]) -> None:
    conn.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def _dispatch(instance_path: Path, op: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    runtime_id = str(payload.get("runtimeId") or "").strip() or None
    if op == "launch_runtime":
        return godot_runtime._launch_runtime_impl(
            instance_path,
            runtime_id=runtime_id,
            display_id=str(payload.get("display_id") or "").strip() or None,
            launch_mode=str(payload.get("launch_mode") or godot_runtime.LAUNCH_MODE_FULLSCREEN),
            scene_id=str(payload.get("scene_id") or "").strip() or None,
            reason=str(payload.get("reason") or "daemon"),
        )
    if op == "stop_runtime":
        return godot_runtime._stop_runtime_impl(instance_path, runtime_id=runtime_id)
    if op == "restart_runtime":
        return godot_runtime._restart_runtime_impl(instance_path, runtime_id=runtime_id, reason=str(payload.get("reason") or "daemon.restart"))
    if op == "configure_display":
        return godot_runtime._configure_display_impl(instance_path, runtime_id=runtime_id, **payload)
    if op == "send_runtime_command":
        body = payload.get("payload")
        if not isinstance(body, dict):
            return {"ok": False, "error": "missing_payload"}
        return godot_runtime._send_runtime_command_impl(
            instance_path,
            body,
            runtime_id=runtime_id,
            timeout=float(payload.get("timeout") or 2.0),
            auto_launch=bool(payload.get("auto_launch", False)),
        )
    if op == "ping":
        return {"ok": True, "pong": True}
    return {"ok": False, "error": "unknown_op", "op": op}


def run(instance_path: str | Path) -> int:
    inst = Path(instance_path).resolve()
    sock_path = godot_runtime.godot_daemon_socket_path(inst)
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    )
    try:
        sock_path.unlink(missing_ok=True)
    except Exception:
        pass

    os.environ["PINBALLCTL_GODOT_DAEMON"] = "1"
    stop_flag = {"stop": False}

    def _handle_term(_signum, _frame):
        stop_flag["stop"] = True

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(sock_path))
    server.listen(16)
    server.settimeout(0.5)
    LOG.info("Godot media daemon listening on %s", sock_path)

    try:
        while not stop_flag["stop"]:
            try:
                conn, _addr = server.accept()
            except TimeoutError:
                continue
            except socket.timeout:
                continue
            with conn:
                req = _read_request(conn)
                if not isinstance(req, dict):
                    _write_response(conn, {"ok": False, "error": "empty_request"})
                    continue
                if req.get("_decode_error"):
                    _write_response(conn, {"ok": False, "error": "bad_json"})
                    continue
                op = str(req.get("op") or "").strip()
                payload = req.get("payload") if isinstance(req.get("payload"), dict) else {}
                LOG.debug("Dispatching op=%s", op)
                res = _dispatch(inst, op, payload)
                try:
                    _write_response(conn, res if isinstance(res, dict) else {"ok": False, "error": "bad_response"})
                except BrokenPipeError:
                    LOG.warning("Client disconnected before daemon response for op=%s", op)
                except OSError:
                    LOG.warning("Failed to write daemon response for op=%s", op)
    except Exception:
        LOG.exception("Godot media daemon crashed")
        raise
    finally:
        try:
            for target in godot_runtime._runtime_targets(inst):
                godot_runtime._stop_runtime_impl(inst, runtime_id=str(target.get("id") or ""))
        except Exception:
            LOG.exception("Failed to stop Godot runtime during daemon shutdown")
        LOG.info("Godot media daemon shutting down")
        try:
            server.close()
        except Exception:
            pass
        try:
            sock_path.unlink(missing_ok=True)
        except Exception:
            pass
    return 0


def main() -> int:
    instance_path = os.environ.get("PINBALLCTL_INSTANCE_PATH") or str((Path(__file__).resolve().parents[2] / "instance"))
    if len(sys.argv) > 1 and str(sys.argv[1]).strip():
        instance_path = sys.argv[1]
    return run(instance_path)


if __name__ == "__main__":
    raise SystemExit(main())
