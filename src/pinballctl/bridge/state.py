"""Persist lightweight bridge state (e.g., firmware version) to instance."""
from __future__ import annotations

import json
import time
import os
import socket
from uuid import uuid4
from pathlib import Path
from datetime import datetime, timezone
try:
    import fcntl
except Exception:  # pragma: no cover - non-POSIX platforms
    fcntl = None


def _instance_dir() -> Path:
    """Locate the src/instance directory relative to this file."""
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "src":
            inst = p / "instance"
            inst.mkdir(parents=True, exist_ok=True)
            return inst
    inst = Path.cwd() / "src" / "instance"
    inst.mkdir(parents=True, exist_ok=True)
    return inst


def _bridge_dir() -> Path:
    p = _instance_dir() / "bridge"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _legacy_bridge_file(name: str) -> Path:
    return _instance_dir() / name


def _bridge_file(name: str) -> Path:
    p = _bridge_dir() / name
    legacy = _legacy_bridge_file(name)
    # One-time migration for legacy json files from instance root.
    if not p.exists() and legacy.exists() and p.suffix == ".json":
        try:
            legacy.replace(p)
        except Exception:
            pass
    return p


def state_path() -> Path:
    return _bridge_file("bridge_state.json")

def commands_path() -> Path:
    return _bridge_file("bridge_commands.json")

def responses_path() -> Path:
    return _bridge_file("bridge_responses.json")

def command_socket_path() -> Path:
    return _bridge_dir() / "bridge_cmd.sock"

def rpc_socket_path() -> Path:
    return _bridge_dir() / "bridge_rpc.sock"

def hardware_discovered_path() -> Path:
    """Path to the latest hardware discovery snapshot."""
    p = _instance_dir() / "hardware"
    p.mkdir(parents=True, exist_ok=True)
    return p / "discovered.json"


def read_state() -> dict:
    fp = state_path()
    if not fp.exists():
        return {}
    for _ in range(3):
        try:
            return json.loads(fp.read_text())
        except Exception:
            time.sleep(0.01)
    return {}


def write_state(
    port: str | None = None,
    firmware: str | None = None,
    chip: str | None = None,
    profile: str | None = None,
    chip_model: str | None = None,
    chip_revision: int | None = None,
    chip_cores: int | None = None,
    controller: str | None = None,
    proto: int | None = None,
    connected: bool | None = None,
    time_value: str | None = None,
    time_in_sync: bool | None = None,
    fs_status: dict | None = None,
    echo_status: dict | None = None,
    echo_seq: int | None = None,
    fs_list: dict | None = None,
    manifest: dict | None = None,
    blob_status: dict | None = None,
    lighting_status: dict | None = None,
    rules_status: dict | None = None,
    event_metrics: dict | None = None,
):
    data = read_state()
    if port:
        data["port"] = port
    if firmware:
        data["firmware"] = firmware
    if chip:
        data["chip"] = chip
    if profile:
        data["profile"] = profile
    if chip_model:
        data["chip_model"] = chip_model
    if chip_revision is not None:
        data["chip_revision"] = int(chip_revision)
    if chip_cores is not None:
        data["chip_cores"] = int(chip_cores)
    if controller:
        data["controller"] = controller
    if proto is not None:
        data["proto"] = int(proto)
    if connected is not None:
        data["connected"] = bool(connected)
    info_updated = False
    if time_value is not None:
        data["time"] = time_value
        info_updated = True
    if time_in_sync is not None:
        data["time_in_sync"] = bool(time_in_sync)
        info_updated = True
    if (
        firmware
        or chip
        or profile
        or chip_model
        or chip_revision is not None
        or chip_cores is not None
        or controller
        or proto is not None
    ):
        info_updated = True
    if info_updated:
        data["info_at"] = datetime.now(timezone.utc).timestamp()
    if fs_status is not None:
        data["fs_status"] = fs_status
        data["fs_status_at"] = datetime.now(timezone.utc).timestamp()
    if echo_status is not None:
        data["echo_status"] = echo_status
        data["echo_at"] = datetime.now(timezone.utc).timestamp()
    if echo_seq is not None:
        data["echo_seq"] = int(echo_seq)
    if fs_list is not None:
        data["fs_list"] = fs_list
        data["fs_list_at"] = datetime.now(timezone.utc).timestamp()
    if manifest is not None:
        data["manifest"] = manifest
        data["manifest_at"] = datetime.now(timezone.utc).timestamp()
    if blob_status is not None:
        data["blob_status"] = blob_status
        data["blob_at"] = datetime.now(timezone.utc).timestamp()
    if lighting_status is not None:
        data["lighting_status"] = lighting_status
        data["lighting_at"] = datetime.now(timezone.utc).timestamp()
    if rules_status is not None:
        data["rules_status"] = rules_status
        data["rules_at"] = datetime.now(timezone.utc).timestamp()
    if event_metrics is not None:
        data["event_metrics"] = event_metrics
        data["event_at"] = datetime.now(timezone.utc).timestamp()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    fp = state_path()
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(fp)


def enqueue_command(cmd: dict, *, wait_for_startup: bool = True):
    """Persist a command for the bridge daemon to consume."""
    enqueue_commands([cmd], wait_for_startup=wait_for_startup)


def bridge_enqueue_ready() -> bool:
    """True when at least one bridge unix socket is immediately connectable."""
    for sock_path in (command_socket_path(), rpc_socket_path()):
        if not sock_path.exists():
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.02)
                s.connect(str(sock_path))
            return True
        except Exception:
            continue
    return False


def is_headless_mode() -> bool:
    """True when running without a live bridge->ESP connection."""
    env = str(os.environ.get("PINBALLCTL_HEADLESS", "")).strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    st = read_state()
    if isinstance(st, dict):
        if st.get("connected") is False:
            return True
        # If bridge state says we're connected, don't treat transient socket readiness
        # checks as headless; callers can still surface rpc_error/no_response if needed.
        if st.get("connected") is True:
            return False
    return not bridge_enqueue_ready()


def enqueue_commands(cmds_to_add: list[dict], *, wait_for_startup: bool = True):
    """Persist multiple commands for bridge daemon consumption in one lock cycle."""
    if not isinstance(cmds_to_add, list) or not cmds_to_add:
        return
    batch_id = uuid4().hex
    cmd_sock = command_socket_path().exists()
    rpc_sock = rpc_socket_path().exists()
    # Prefer command socket first; it is the primary low-overhead enqueue path.
    # RPC ENQUEUE_BATCH remains a fallback path.
    if cmd_sock:
        if _enqueue_via_socket(cmds_to_add):
            return
        # If command socket exists but send failed, try RPC batch as fallback.
        if rpc_sock and _enqueue_via_rpc_batch(cmds_to_add, batch_id=batch_id):
            return
        raise RuntimeError("bridge command socket unavailable")
    if rpc_sock:
        if _enqueue_via_rpc_batch(cmds_to_add, batch_id=batch_id):
            return
        raise RuntimeError("bridge rpc batch unavailable")
    # Startup/transient path: wait briefly for one socket, then use only that socket.
    if wait_for_startup:
        start = time.monotonic()
        startup_wait = 2.0
        while (time.monotonic() - start) < startup_wait:
            time.sleep(0.05)
            cmd_sock = command_socket_path().exists()
            rpc_sock = rpc_socket_path().exists()
            if cmd_sock:
                if _enqueue_via_socket(cmds_to_add):
                    return
                if rpc_sock and _enqueue_via_rpc_batch(cmds_to_add, batch_id=batch_id):
                    return
                raise RuntimeError("bridge command socket unavailable")
            if rpc_sock:
                if _enqueue_via_rpc_batch(cmds_to_add, batch_id=batch_id):
                    return
                raise RuntimeError("bridge rpc batch unavailable")
    # Optional fallback path: file-backed queue (disabled by default).
    if os.environ.get("PINBALLCTL_BRIDGE_FILE_FALLBACK", "").strip().lower() not in {"1", "true", "yes", "on"}:
        raise RuntimeError("bridge command socket unavailable")
    fp = commands_path()
    fp.parent.mkdir(parents=True, exist_ok=True)
    lock_fp = fp.with_suffix(fp.suffix + ".lock")
    lock_handle = None
    try:
        lock_handle = open(lock_fp, "w", encoding="utf-8")
        if fcntl is not None:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        cmds = []
        try:
            if fp.exists():
                cmds = json.loads(fp.read_text())
                if not isinstance(cmds, list):
                    cmds = []
        except Exception:
            cmds = []
        for cmd in cmds_to_add:
            if isinstance(cmd, dict):
                cmds.append(cmd)
        tmp = fp.with_suffix(fp.suffix + f".tmp.{os.getpid()}")
        tmp.write_text(json.dumps(cmds))
        os.replace(tmp, fp)
    finally:
        if lock_handle is not None:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            lock_handle.close()


def _enqueue_via_socket(cmds_to_add: list[dict]) -> bool:
    """Try to deliver commands to live bridge via unix socket."""
    sock_path = command_socket_path()
    if not sock_path.exists():
        return False
    payloads = []
    for cmd in cmds_to_add:
        if isinstance(cmd, dict):
            payloads.append(json.dumps(cmd, separators=(",", ":")))
    if not payloads:
        return True
    data = ("\n".join(payloads) + "\n").encode("utf-8")
    attempts = 5
    for _ in range(attempts):
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                s.connect(str(sock_path))
                s.sendall(data)
            return True
        except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
            time.sleep(0.02)
            continue
        except Exception:
            return False
    return False


def _enqueue_via_rpc_batch(cmds_to_add: list[dict], batch_id: str | None = None) -> bool:
    """Fallback enqueue path over RPC socket when cmd socket is unavailable."""
    sock_path = rpc_socket_path()
    if not sock_path.exists():
        return False
    items = [cmd for cmd in cmds_to_add if isinstance(cmd, dict)]
    if not items:
        return True
    if not batch_id:
        batch_id = uuid4().hex
    payload = {
        "cmd": "ENQUEUE_BATCH",
        "batchId": batch_id,
        "items": items,
        "timeout_s": 2.0,
    }
    data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    attempts = 3
    for _ in range(attempts):
        sent = False
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                s.connect(str(sock_path))
                s.sendall(data)
                sent = True
                buf = b""
                deadline = time.monotonic() + 2.0
                while time.monotonic() < deadline:
                    try:
                        chunk = s.recv(65536)
                    except (TimeoutError, socket.timeout):
                        break
                    if not chunk:
                        break
                    buf += chunk
                    idx = buf.find(b"\n")
                    if idx < 0:
                        continue
                    line = buf[:idx].decode("utf-8", errors="replace").strip()
                    if not line:
                        # Payload was sent; avoid duplicate fallback enqueue.
                        return True
                    try:
                        msg = json.loads(line)
                    except Exception:
                        # Payload was sent; avoid duplicate fallback enqueue.
                        return True
                    return isinstance(msg, dict) and bool(msg.get("ok"))
                # Ack missing, but batch was sent; avoid duplicate enqueue.
                if sent:
                    return True
        except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
            if sent:
                # Unknown delivery status; safest is to avoid duplicate retries.
                return True
            time.sleep(0.03)
            continue
        except Exception:
            return False
    return False


def rpc_command(cmd: dict, match_t: str, timeout_s: float = 3.0):
    """Execute an RPC command through bridge unix socket and return payload dict or None."""
    sock_path = rpc_socket_path()
    start = time.monotonic()
    startup_wait = max(5.0, min(20.0, float(timeout_s) + 8.0))
    payload = dict(cmd or {})
    payload["match_t"] = match_t
    payload["timeout_s"] = float(timeout_s)
    data = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
    while True:
        if (time.monotonic() - start) >= startup_wait:
            raise RuntimeError("bridge rpc socket unavailable")
        if not sock_path.exists():
            time.sleep(0.05)
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(max(0.5, timeout_s + 0.75))
                s.connect(str(sock_path))
                s.sendall(data)
                buf = b""
                deadline = time.monotonic() + max(0.5, timeout_s + 0.75)
                while time.monotonic() < deadline:
                    try:
                        chunk = s.recv(65536)
                    except (TimeoutError, socket.timeout):
                        break
                    if not chunk:
                        break
                    buf += chunk
                    nl = buf.find(b"\n")
                    if nl < 0:
                        continue
                    line = buf[:nl].decode("utf-8", errors="replace").strip()
                    if not line:
                        return None
                    msg = json.loads(line)
                    if isinstance(msg, dict) and msg.get("ok") is False:
                        return None
                    if isinstance(msg, dict) and "payload" in msg:
                        return msg.get("payload")
                    if isinstance(msg, dict):
                        return msg
                return None
        except (FileNotFoundError, ConnectionRefusedError, ConnectionResetError, BrokenPipeError, TimeoutError, socket.timeout):
            time.sleep(0.05)
            continue


def bridge_event_stats(timeout_s: float = 2.0) -> dict:
    """Read in-memory bridge event counters via RPC (not file snapshots)."""
    resp = rpc_command({"cmd": "BRIDGE_EVENT_STATS"}, match_t="BRIDGE_EVENT_STATS", timeout_s=timeout_s)
    if isinstance(resp, dict):
        return resp
    return {}


def queue_blob_put(blob_type: str, local_path: str, remote_path: str):
    """Queue a blob transfer for the bridge daemon."""
    enqueue_command({
        "cmd": "BLOB_PUT",
        "blobType": blob_type,
        "localPath": local_path,
        "remotePath": remote_path,
    })


def write_hardware_snapshot(payload: dict, append: bool = False):
    """Persist hardware discovery payload (e.g., from ESP GET_HW)."""
    fp = hardware_discovered_path()
    try:
        if append and fp.exists():
            try:
                existing = json.loads(fp.read_text())
                pins = existing.get("pins", [])
                pins.extend(payload.get("pins", []))
                payload["pins"] = pins
                payload["controller"] = payload.get("controller") or existing.get("controller")
            except Exception:
                pass
        fp.write_text(json.dumps(payload, indent=2))
    except Exception:
        pass
