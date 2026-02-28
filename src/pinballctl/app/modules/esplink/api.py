"""ESPLink API: device discovery, firmware manifests, flashing, and console."""

from flask import Blueprint, jsonify, request, Response, stream_with_context, abort, current_app
import time, json, threading, os, subprocess, tempfile, hashlib, shutil, re, shlex, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, urljoin, unquote
from pinballctl.bridge.state import read_state as read_bridge_state, write_state as write_bridge_state, responses_path
from pinballctl.bridge.state import enqueue_command
from pinballctl.bridge.state import rpc_command as bridge_rpc_command
from pinballctl.app.sync_state import read_sync_state
from pinballctl.ops.mapping_blob import build_mapping_blob_bytes
from pinballctl.ops.rules_blob import decode_rules_pd_bytes
from pinballctl.ops.flash_lifecycle import (
    upload_lockfile as shared_upload_lockfile,
    flash_begin as shared_flash_begin,
    flash_end as shared_flash_end,
)
from pinballctl.cli import _esp_ports, _pinballctl_bin, _default_bridge_pidfile, _default_bridge_log
import serial  # bridge controls/flash already optional pyserial elsewhere
from datetime import datetime, timezone
from uuid import uuid4
import os

api_bp = Blueprint("esplink_api", __name__)
sync_bp = Blueprint("esplink_sync_api", __name__)

_reconcile_lock = threading.Lock()
_bridge_action_cooldown_s = 2.0
_bridge_missing_grace_s = 10.0
_bridge_last_action_at = 0.0
_bridge_missing_since = None
_fs_list_lock = threading.Lock()
_last_get_info_poll_at = 0.0
_get_info_min_interval_s = 20.0
_bridge_reconcile_suspended_until = 0.0
_bridge_reconcile_suspend_reason = ""
_firmware_upload_lock = threading.Lock()
_firmware_upload_active = False
_upload_lock_stale_s = 20 * 60


def _upload_lockfile() -> Path:
    return shared_upload_lockfile()


def _auto_reconcile_enabled() -> bool:
    """Auto bridge lifecycle is on by default; allow explicit disable via env."""
    val = os.environ.get("PINBALLCTL_ESPLINK_AUTORECONCILE", "1").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _set_bridge_reconcile_suspended(seconds: float, reason: str = ""):
    """Temporarily disable bridge auto lifecycle actions (e.g., during flashing)."""
    global _bridge_reconcile_suspended_until, _bridge_reconcile_suspend_reason  # noqa: PLW0603
    _bridge_reconcile_suspended_until = time.monotonic() + max(0.0, float(seconds))
    _bridge_reconcile_suspend_reason = reason or ""


def _clear_bridge_reconcile_suspended():
    global _bridge_reconcile_suspended_until, _bridge_reconcile_suspend_reason  # noqa: PLW0603
    _bridge_reconcile_suspended_until = 0.0
    _bridge_reconcile_suspend_reason = ""


def _is_upload_active() -> bool:
    global _firmware_upload_active  # noqa: PLW0603
    if _firmware_upload_active:
        # Self-heal stale in-memory state if the shared lockfile is gone.
        if not _upload_lockfile().exists():
            _firmware_upload_active = False
            return False
        return True
    lock = _upload_lockfile()
    if not lock.exists():
        return False
    try:
        data = json.loads(lock.read_text())
        started = float(data.get("started_at", 0) or 0)
    except Exception:
        started = lock.stat().st_mtime
    if started and (time.time() - started) > _upload_lock_stale_s:
        try:
            lock.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    return True

# -------- Serial discovery -----------------------------------------------------
try:
    import serial
    import serial.tools.list_ports as list_ports
except Exception:  # pyserial not installed
    serial = None
    list_ports = None


def _norm_dev_id(dev_id: str) -> str:
    """Ensure device paths start with a forward slash."""
    return dev_id if dev_id.startswith("/") else ("/" + dev_id)


def _ports_equivalent(a: str | None, b: str | None) -> bool:
    """Treat matching /dev/cu.* and /dev/tty.* siblings as equivalent."""
    if not a or not b:
        return False
    if a == b:
        return True
    aa = str(a).strip()
    bb = str(b).strip()
    for left, right in ((aa, bb), (bb, aa)):
        if left.startswith("/dev/cu.") and right.startswith("/dev/tty."):
            if left[len("/dev/cu."):] == right[len("/dev/tty."):]:
                return True
    return False

def _sha256_file(path: Path) -> str:
    try:
        data = path.read_bytes()
    except Exception:
        return ""
    return hashlib.sha256(data).hexdigest()


def _read_bridge_responses() -> dict:
    fp = responses_path()
    if not fp.exists():
        return {}
    for _ in range(3):
        try:
            return json.loads(fp.read_text())
        except Exception:
            time.sleep(0.01)
    return {}


def _latest_manifest_from_responses() -> dict | None:
    responses = _read_bridge_responses()
    latest = None
    latest_at = 0.0
    for entry in responses.values():
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("t") != "MANIFEST" or not payload.get("ok"):
            continue
        data = payload.get("data")
        if not isinstance(data, dict):
            continue
        try:
            at = float(entry.get("at", 0) or 0)
        except Exception:
            at = 0.0
        if at >= latest_at:
            latest_at = at
            latest = data
    return latest


def _normalize_manifest(manifest: dict | None) -> dict | None:
    if not isinstance(manifest, dict):
        return None
    out = dict(manifest)
    for key, value in list(manifest.items()):
        if not isinstance(key, str):
            continue
        if key.startswith("/cfg/"):
            bare = key.split("/cfg/", 1)[1]
            out[bare] = value
    return out


def _bridge_rpc(cmd: dict, match_t: str, timeout_s: float = 3.0):
    req_id = uuid4().hex
    payload = dict(cmd)
    payload["reqId"] = req_id
    try:
        return bridge_rpc_command(payload, match_t=match_t, timeout_s=timeout_s)
    except Exception:
        return None

def _esptool_cmd():
    """Resolve an esptool command list."""
    env = os.environ.get("ESPLINK_ESPTOOL")
    if env:
        return shlex.split(env)
    for cand in ("esptool.py", "esptool"):
        if shutil.which(cand):
            return [cand]
    py = sys.executable or "python3"
    return [py, "-m", "esptool"]


# -------- Bridge control helpers ---------------------------------------------

def _bridge_pidfile() -> Path:
    try:
        return Path(_default_bridge_pidfile())
    except Exception:
        state_home = os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state"))
        return Path(state_home) / "pinballctl" / "bridge.pid"


def _bridge_logfile() -> Path:
    try:
        return Path(_default_bridge_log())
    except Exception:
        state_home = os.environ.get("XDG_STATE_HOME", os.path.join(os.path.expanduser("~"), ".local", "state"))
        return Path(state_home) / "pinballctl" / "bridge.log"

def _bridge_log(msg: str):
    try:
        lf = _bridge_logfile()
        lf.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with open(lf, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

def _bridge_debug(msg: str):
    try:
        lvl = os.environ.get("PINBALLCTL_LOG_LEVEL", "").upper()
        if lvl == "DEBUG":
            _bridge_log(msg)
    except Exception:
        pass


def _bridge_running_on(port: str) -> bool:
    pidfile = _bridge_pidfile()
    if not pidfile.exists():
        return False
    try:
        pid = int(pidfile.read_text().strip())
    except Exception:
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        # Stale pidfile: clean it so auto-reconcile can recover.
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            write_bridge_state(connected=False)
        except Exception:
            pass
        _bridge_log(f"Removed stale bridge pidfile (pid {pid} not running)")
        return False
    except Exception:
        return False
    try:
        st = read_bridge_state()
        # If a specific port is provided, ensure it matches recorded state
        if port and st.get("port") and (st.get("port") != port) and not _ports_equivalent(st.get("port"), port):
            return False
        return True
    except Exception:
        return False


def _bridge_reconcile(devices: list[dict], preferred_port: str | None = None):
    """Ensure bridge lifecycle follows device availability."""
    global _bridge_last_action_at, _bridge_missing_since  # noqa: PLW0603
    if not _reconcile_lock.acquire(blocking=False):
        return
    try:
        now = time.monotonic()
        if _is_upload_active():
            return
        if now < _bridge_reconcile_suspended_until:
            return
        if (now - _bridge_last_action_at) < _bridge_action_cooldown_s:
            return

        ports = []
        for d in devices or []:
            dev = (d or {}).get("id")
            if isinstance(dev, str) and dev:
                ports.append(dev)
        ports = list(dict.fromkeys(ports))

        st = read_bridge_state()
        bridge_port = st.get("port") if isinstance(st, dict) else None
        running = _bridge_running_on(bridge_port or "")

        if not ports:
            if _bridge_missing_since is None:
                _bridge_missing_since = now
            if running and (now - _bridge_missing_since) >= _bridge_missing_grace_s:
                if _stop_bridge():
                    _bridge_last_action_at = now
                    _bridge_log("Auto-stopped bridge: no serial devices detected")
            return

        _bridge_missing_since = None

        target = None
        if preferred_port and preferred_port in ports:
            target = preferred_port
        elif bridge_port and any(_ports_equivalent(bridge_port, p) for p in ports):
            target = next((p for p in ports if _ports_equivalent(bridge_port, p)), bridge_port)
        else:
            target = ports[0]

        if not running:
            try:
                _start_bridge(target)
                _bridge_last_action_at = now
                _bridge_log(f"Auto-started bridge on {target}")
            except Exception as e:
                _bridge_log(f"Auto-start bridge failed on {target}: {e}")
            return

        if bridge_port and not _ports_equivalent(bridge_port, target):
            try:
                _stop_bridge()
                _start_bridge(target)
                _bridge_last_action_at = now
                _bridge_log(f"Auto-moved bridge from {bridge_port} to {target}")
            except Exception as e:
                _bridge_log(f"Auto-move bridge failed {bridge_port} -> {target}: {e}")
    finally:
        _reconcile_lock.release()


def _stop_bridge() -> bool:
    pidfile = _bridge_pidfile()
    if not pidfile.exists():
        return False
    try:
        pid = int(pidfile.read_text().strip())
    except Exception:
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    try:
        os.kill(pid, 15)
    except ProcessLookupError:
        try:
            pidfile.unlink(missing_ok=True)
        except Exception:
            pass
        try:
            write_bridge_state(connected=False)
        except Exception:
            pass
        _bridge_log(f"Removed stale bridge pidfile during stop (pid {pid} not running)")
        return False
    except Exception:
        return False
    try:
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            except Exception:
                break
            time.sleep(0.05)
        # Escalate if still alive to avoid dual-bridge serial contention.
        try:
            os.kill(pid, 0)
            try:
                os.kill(pid, 9)
            except Exception:
                pass
            kill_deadline = time.monotonic() + 1.0
            while time.monotonic() < kill_deadline:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                except Exception:
                    break
                time.sleep(0.05)
        except ProcessLookupError:
            pass
        except Exception:
            pass
        pidfile.unlink(missing_ok=True)
        try:
            write_bridge_state(connected=False)
        except Exception:
            pass
        _bridge_log(f"Bridge stopped (pid {pid})")
        return True
    except Exception:
        try:
            # If anything went wrong but process is already gone, clean pidfile.
            os.kill(pid, 0)
        except ProcessLookupError:
            try:
                pidfile.unlink(missing_ok=True)
            except Exception:
                pass
        except Exception:
            pass
        return False


def _start_bridge(port: str, baud: int = 460800) -> int:
    try:
        st = read_bridge_state()
        existing_port = st.get("port") if isinstance(st, dict) else None
        if _bridge_running_on(existing_port or "") and (existing_port == port or _ports_equivalent(existing_port, port)):
            pid = int(_bridge_pidfile().read_text().strip())
            return pid
    except Exception:
        pass
    logf = _bridge_logfile()
    logf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [_pinballctl_bin(), "bridge", "--port", port, "--baud", str(baud)]
    # Open log file and keep handle alive within subprocess via file descriptor duplication
    lf = open(logf, "ab", buffering=0)
    env = os.environ.copy()
    proc = subprocess.Popen(
        cmd,
        stdout=lf,
        stderr=lf,
        stdin=subprocess.DEVNULL,
        close_fds=False,  # keep stdout/stderr fds valid
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        env=env,
    )
    _bridge_pidfile().write_text(str(proc.pid))
    _bridge_log(f"Bridge started on {port} @ {baud} (pid {proc.pid})")
    try:
        # Mark port immediately, but let the daemon assert live connectivity.
        write_bridge_state(port=port, connected=False)
    except Exception:
        pass
    return proc.pid


def _list_serial_devices():
    """Enumerate USB serial devices that look like ESP32 boards."""
    devices = []
    if list_ports is None:
        return devices

    CANDIDATE_VIDS = {0x303A, 0x10C4, 0x1A86, 0x0403}  # Espressif, CP210x, CH34x, FTDI
    BAD_SUBSTR = {"debug-console"}

    for p in list_ports.comports():
        dev = (p.device or "").lower()
        desc = (p.description or "").lower()
        hwid = (getattr(p, "hwid", "") or "").lower()
        vid = getattr(p, "vid", None)

        is_usb_name = ("usb" in dev) or ("usb" in desc) or ("usb" in hwid)
        has_vid = isinstance(vid, int)
        looks_usb = is_usb_name or has_vid

        if any(bad in dev for bad in BAD_SUBSTR):
            continue
        if not looks_usb:
            continue
        if has_vid and (vid not in CANDIDATE_VIDS):
            continue

        devices.append({
            "id": p.device,
            "port": p.device,
            "connected": True,
            "last_seen": int(time.time()),
            "chip": "ESP32 (USB serial)",
            "description": p.description,
            "manufacturer": getattr(p, "manufacturer", None),
            "vid": vid,
            "pid": getattr(p, "pid", None),
            "serial_number": getattr(p, "serial_number", None),
            "firmware": None,
            "ip": None,
            "rssi": None,
        })

    def _rank(d):
        v = d.get("vid")
        return (0 if v == 0x303A else 1, d["port"])
    devices.sort(key=_rank)
    return devices


# -------- Firmware versions & paths -------------------------------------------

def _instance_path() -> Path:
    """Return the instance directory, tolerating contexts without Flask app."""
    # Prefer Flask's instance_path (hard-bound to src/instance in create_app)
    try:
        ip = Path(current_app.instance_path)
        ip.mkdir(parents=True, exist_ok=True)
        return ip
    except Exception:
        pass

    # Fallback: find ../src/instance relative to this file
    here = Path(__file__).resolve()
    src_dir = None
    for p in here.parents:
        if p.name == "src":
            src_dir = p
            break
    if src_dir is None:
        src_dir = Path.cwd() / "src"

    ip = src_dir / "instance"
    ip.mkdir(parents=True, exist_ok=True)
    return ip


def _instance_bin_dir() -> Path:
    # You renamed to "firmware"
    """Return/create the firmware bin directory under the instance path."""
    p = _instance_path() / "firmware"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _repo_root_via_src() -> Path:
    """Walk up until we find 'src'; repo root is its parent."""
    here = Path(__file__).resolve()
    for p in here.parents:
        if p.name == "src":
            return p.parent
    return Path.cwd()


def _read_json(fp: Path):
    """Read JSON from disk, returning None on error."""
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(fp: Path, data: dict):
    """Write JSON to disk atomically via a temp file."""
    fp.parent.mkdir(parents=True, exist_ok=True)
    tmp = fp.with_suffix(fp.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(fp)


# --- Version manifest normalization -------------------------------------------
SEMVER_RE = re.compile(r'^v?(\d+)\.(\d+)\.(\d+)$')
FIRMWARE_FILE_RE = re.compile(r'^firmware-v(\d+\.\d+\.\d+)\.bin$')


def _iso_utc_from_mtime(fp: Path) -> str:
    """Format a file mtime as UTC ISO8601."""
    ts = fp.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _normalize_versions_payload(raw: dict, base_dir: Path) -> dict | None:
    """Normalize manifests from either the new schema or legacy files list."""
    # New schema
    if isinstance(raw, dict) and "versions" in raw and "latest" in raw:
        versions = []
        for v in raw.get("versions", []):
            fn = v.get("filename") or ""
            fpp = base_dir / fn if fn else None
            date_val = v.get("date")
            if not date_val and fn and fpp and fpp.exists():
                date_val = _iso_utc_from_mtime(fpp)
            elif not date_val:
                date_val = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            versions.append({
                "version": v.get("version", ""),
                "date": date_val,
                "notes": v.get("notes", "") or "",
                "filename": fn,
                "size": int(v.get("size", 0)) if v.get("size") is not None else None,
                "sha256": v.get("sha256", ""),
                "partitions": v.get("partitions") or "",
                "partitions_sha256": v.get("partitions_sha256") or "",
                "bootloader": v.get("bootloader") or "",
                "bootloader_sha256": v.get("bootloader_sha256") or "",
            })
        def _verkey(s: str):
            m = SEMVER_RE.match(s or "")
            return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
        versions.sort(key=lambda it: _verkey(it["version"]), reverse=True)
        latest = raw.get("latest") or (versions[0]["version"] if versions else "v0.0.0")
        return {"latest": latest, "versions": versions}

    # Legacy schema
    if isinstance(raw, dict) and "files" in raw:
        versions_map = {}
        for f in raw.get("files", []):
            name = f.get("name") or f.get("filename") or ""
            m = FIRMWARE_FILE_RE.match(name)
            if not m:
                continue
            ver = m.group(1)
            vkey = f"v{ver}"
            fpp = base_dir / name
            versions_map[vkey] = {
                "version": vkey,
                "date": _iso_utc_from_mtime(fpp) if fpp.exists() else (raw.get("updatedAt") or datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')),
                "notes": "",
                "filename": name,
                "size": int(f.get("size") or 0),
                "sha256": f.get("sha256") or "",
                "partitions": "",
                "partitions_sha256": "",
                "bootloader": "",
                "bootloader_sha256": "",
            }
        versions = list(versions_map.values())
        def _verkey(s: str):
            m = SEMVER_RE.match(s or "")
            return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
        versions.sort(key=lambda it: _verkey(it["version"]), reverse=True)
        latest = f"v{raw.get('lastVersion')}" if raw.get("lastVersion") else (versions[0]["version"] if versions else "v0.0.0")
        return {"latest": latest, "versions": versions}

    return None


def _dist_versions_local():
    """Return a normalized versions manifest from the instance bin directory."""
    fp = _instance_bin_dir() / "versions.json"
    if not fp.exists():
        return None
    raw = _read_json(fp)
    if not raw:
        return None
    return _normalize_versions_payload(raw, base_dir=fp.parent)


def _resolve_local_entry(version: str):
    """Return the manifest entry for a given semantic version if available."""
    manifest = _dist_versions_local() or {"versions": []}
    entry = next((v for v in manifest.get("versions", []) if v.get("version") == version), None)
    return entry or None


def _sha256_file(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# --- helper: open URL with forwarded auth (for same-origin protected endpoints)
def _open_with_forwarded_auth(url: str):
    """
    Build a urllib request that forwards Authorization and (if same-origin) Cookie,
    so server-side fetches can pass the auth gate on this app.
    """
    import urllib.request

    req = urllib.request.Request(url)
    # Pass through Authorization if the client used it (Bearer/Basic etc.)
    auth = request.headers.get("Authorization")
    if auth:
        req.add_header("Authorization", auth)

    # Only forward Cookie for same-origin (avoid leaking cookies cross-origin)
    try:
        tgt = urlparse(url)
        cur = urlparse(request.host_url)
        same_origin = (
            (tgt.scheme or "http") == (cur.scheme or "http")
            and (tgt.hostname or "").lower() == (cur.hostname or "").lower()
            and (tgt.port or (-1)) == (cur.port or (-1))
        )
        if same_origin:
            cookie = request.headers.get("Cookie")
            if cookie:
                req.add_header("Cookie", cookie)
    except Exception:
        pass

    # Nice to have UA
    req.add_header("User-Agent", "pinballctl-esplink/1.0")
    req.add_header("Accept", "application/json, */*;q=0.1")
    timeout_s = float(os.environ.get("PINBALLCTL_HTTP_FETCH_TIMEOUT_S", "20"))
    return urllib.request.urlopen(req, timeout=timeout_s)

# Minimal download helper (wraps opener)
def _download_with_forwarded_auth(url: str):
    return _open_with_forwarded_auth(url)


def _same_origin(url: str) -> bool:
    """True when URL matches the current request origin."""
    try:
        tgt = urlparse(url)
        cur = urlparse(request.host_url)
        return (
            (tgt.scheme or "http") == (cur.scheme or "http")
            and (tgt.hostname or "").lower() == (cur.hostname or "").lower()
            and (tgt.port or (-1)) == (cur.port or (-1))
        )
    except Exception:
        return False


def _resolve_same_origin_firmware_asset(url: str) -> Path | None:
    """
    Resolve known same-origin firmware download URLs to on-disk files.
    This avoids server->server HTTP fetches for local assets.
    """
    if not _same_origin(url):
        return None
    parsed = urlparse(url)
    path = unquote(parsed.path or "")
    if not path:
        return None
    bn = Path(path).name
    if Path(bn).suffix.lower() != ".bin":
        return None
    if path.startswith("/api/firmware/download/remote/"):
        fp = (_repo_root_via_src() / "dist" / "firmware" / bn).resolve()
    elif path.startswith("/api/firmware/download/"):
        fp = (_instance_bin_dir() / bn).resolve()
    else:
        return None
    try:
        if path.startswith("/api/firmware/download/remote/"):
            fp.relative_to((_repo_root_via_src() / "dist" / "firmware").resolve())
        else:
            fp.relative_to(_instance_bin_dir().resolve())
    except Exception:
        return None
    if not fp.exists() or not fp.is_file():
        return None
    return fp


def _download_asset_to_file(url: str, dst: Path):
    """
    Download/copy a firmware asset URL to dst.
    Same-origin /api/firmware URLs are copied from disk directly.
    """
    local_fp = _resolve_same_origin_firmware_asset(url)
    if local_fp is not None:
        shutil.copyfile(local_fp, dst)
        return
    with _download_with_forwarded_auth(url) as r, open(dst, "wb") as out:
        shutil.copyfileobj(r, out)


def _load_remote_versions(url: str, debug: bool = False) -> dict:
    """
    Server-side fetch of a remote manifest.
    For same-origin URLs, forward Cookie/Authorization so /api/firmware/versions
    succeeds through the auth gate.
    """
    dbg = {}
    try:
        with _open_with_forwarded_auth(url) as r:
            raw = r.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        out = {"latest": data.get("latest"), "versions": []}

        for v in data.get("versions", []):
            fn = v.get("filename")
            if not (isinstance(fn, str) and (fn.startswith("http://") or fn.startswith("https://"))):
                continue
            out["versions"].append({
                "version": v.get("version"),
                "date": v.get("date"),
                "notes": v.get("notes") or "",
                "filename": fn,
                "sha256": v.get("sha256"),
                "size": v.get("size"),
            })

        def _verkey(s: str):
            m = SEMVER_RE.match(s or "")
            return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
        out["versions"].sort(key=lambda it: _verkey(it["version"]), reverse=True)
        if not out.get("latest") and out["versions"]:
            out["latest"] = out["versions"][0]["version"]

        if debug:
            out["_debug"] = {**dbg, "remote_url": url}
        return out

    except HTTPError as e:
        if debug:
            return {"latest": None, "versions": [], "_debug": {**dbg, "remote_url": url, "fetch_error": f"HTTP Error {e.code}: {e.reason}"}}
        return {"latest": None, "versions": []}
    except URLError as e:
        if debug:
            return {"latest": None, "versions": [], "_debug": {**dbg, "remote_url": url, "fetch_error": f"URL Error: {e.reason}"}}
        return {"latest": None, "versions": []}
    except Exception as e:
        if debug:
            return {"latest": None, "versions": [], "_debug": {**dbg, "remote_url": url, "fetch_error": str(e)}}
        return {"latest": None, "versions": []}


# -------- API: devices ---------------------------------------------------------
@api_bp.get("/devices")
def devices():
    """List detected ESP32-class serial devices."""
    devs = _list_serial_devices()
    if _auto_reconcile_enabled():
        try:
            _bridge_reconcile(devs)
        except Exception:
            pass
    return jsonify(devs)


@api_bp.get("/bridge/status")
def bridge_status():
    if _auto_reconcile_enabled():
        try:
            _bridge_reconcile(_list_serial_devices())
        except Exception:
            pass
    st = read_bridge_state()
    running = _bridge_running_on(st.get("port") or "")
    return jsonify({
        "running": running,
        "port": st.get("port"),
        "firmware": st.get("firmware"),
        "chip": st.get("chip"),
        "profile": st.get("profile"),
        "chip_model": st.get("chip_model"),
        "chip_revision": st.get("chip_revision"),
        "chip_cores": st.get("chip_cores"),
        "controller": st.get("controller"),
        "proto": st.get("proto"),
        "updated_at": st.get("updated_at"),
    })


@api_bp.post("/bridge/start")
def bridge_start():
    if _is_upload_active():
        return jsonify({"ok": False, "error": "firmware upload in progress"}), 423
    payload = request.get_json(silent=True) or {}
    port = (payload.get("port") or "").strip()
    if not port or port == "auto":
        ports = _esp_ports()
        port = ports[0] if ports else None
    if not port:
        return jsonify({"ok": False, "error": "No port found"}), 400
    try:
        pid = _start_bridge(port)
        return jsonify({"ok": True, "pid": pid, "port": port})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@api_bp.post("/bridge/stop")
def bridge_stop():
    ok = _stop_bridge()
    return jsonify({"ok": ok})


@api_bp.post("/bridge/restart")
def bridge_restart():
    if _is_upload_active():
        return jsonify({"ok": False, "error": "firmware upload in progress"}), 423
    payload = request.get_json(silent=True) or {}
    port = (payload.get("port") or "").strip()
    stopped = _stop_bridge()
    if not port or port == "auto":
        ports = _esp_ports()
        port = ports[0] if ports else None
    if not port:
        return jsonify({"ok": False, "error": "No port found"}), 400
    try:
        pid = _start_bridge(port)
        _bridge_log(f"Bridge restarted on {port} (pid {pid})")
        return jsonify({"ok": True, "pid": pid, "port": port, "stopped": stopped})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# -------- Connection probe -----------------------------------------------------
def _probe_connected(dev_id: str):
    """Check whether the given device path is present and openable."""
    dev_id = _norm_dev_id(dev_id)

    if list_ports is None:
        return False, "pyserial-missing"

    present = any((p.device == dev_id) for p in list_ports.comports())
    if not present:
        return False, "not-present"

    # Never touch serial during firmware upload; esptool must have exclusive access.
    if _is_upload_active():
        return True, "upload-active"

    # Never probe-open a serial device already owned by the bridge.
    # Competing opens can steal/perturb traffic and cause request timeouts.
    try:
        st = read_bridge_state()
        bridge_port = st.get("port") if isinstance(st, dict) else None
        if bridge_port and _ports_equivalent(bridge_port, dev_id) and _bridge_running_on(bridge_port):
            return bool(st.get("connected")), "bridge-owned"
    except Exception:
        pass

    # Do not probe-open serial from API; bridge must be the only owner.
    return True, "present"


# --- /status: actively probe the selected device ------------------------------
@api_bp.get("/devices/<path:dev_id>/status")
def status(dev_id):
    """Inspect a selected device and mark whether it is reachable."""
    dev_id = _norm_dev_id(dev_id)
    out = {
        "connected": False,
        "firmware": None,
        "chip": None,
        "profile": None,
        "chip_model": None,
        "chip_revision": None,
        "chip_cores": None,
        "controller": None,
        "proto": None,
        "ip": None,
        "rssi": None,
        "uptime": None,
        "heap": None,
        "temp": None,
        "features": [],
    }

    devs = {d["id"]: d for d in _list_serial_devices()}
    if _auto_reconcile_enabled():
        try:
            _bridge_reconcile(list(devs.values()), preferred_port=dev_id)
        except Exception:
            pass
    d = devs.get(dev_id)
    if not d:
        return jsonify(out)

    out["chip"] = d.get("chip")
    fallback_fw = None
    fallback_chip = None
    fallback_profile = None
    fallback_chip_model = None
    fallback_chip_revision = None
    fallback_chip_cores = None
    fallback_controller = None
    fallback_proto = None
    use_cached_info = False
    try:
        st = read_bridge_state()
        if (st.get("port") == dev_id or _ports_equivalent(st.get("port"), dev_id)) and _bridge_running_on(dev_id):
            fallback_fw = st.get("firmware")
            fallback_chip = st.get("chip")
            fallback_profile = st.get("profile")
            fallback_chip_model = st.get("chip_model")
            fallback_chip_revision = st.get("chip_revision")
            fallback_chip_cores = st.get("chip_cores")
            fallback_controller = st.get("controller")
            fallback_proto = st.get("proto")
            info_at = float(st.get("info_at", 0) or 0)
            use_cached_info = bool(info_at and ((time.time() - info_at) < 6.0) and (fallback_fw or fallback_chip or fallback_profile))
    except Exception:
        pass

    bridge_owns_port = False
    bridge_connected = False
    try:
        st = read_bridge_state()
        bridge_port = st.get("port") if isinstance(st, dict) else None
        bridge_owns_port = bool(bridge_port and _ports_equivalent(bridge_port, dev_id) and _bridge_running_on(bridge_port))
        bridge_connected = bool(st.get("connected")) if bridge_owns_port else False
    except Exception:
        bridge_owns_port = False
        bridge_connected = False

    info_payload = None
    global _last_get_info_poll_at  # noqa: PLW0603
    now = time.monotonic()
    should_poll_info = (not use_cached_info) and ((now - _last_get_info_poll_at) >= _get_info_min_interval_s)
    if should_poll_info:
        _last_get_info_poll_at = now
        info_payload = _bridge_rpc({"cmd": "GET_INFO"}, "INFO", timeout_s=2.0)
    if isinstance(info_payload, dict):
        fw = info_payload.get("fw") or info_payload.get("version")
        chip = info_payload.get("chip") or info_payload.get("chip_model")
        profile = info_payload.get("profile")
        chip_model = info_payload.get("chipModel") or info_payload.get("chip_model")
        chip_revision = info_payload.get("chipRev") if info_payload.get("chipRev") is not None else info_payload.get("chip_revision")
        chip_cores = info_payload.get("chipCores") if info_payload.get("chipCores") is not None else info_payload.get("chip_cores")
        controller = info_payload.get("controller") or info_payload.get("controller_id")
        proto = info_payload.get("proto")
        if fw:
            out["firmware"] = fw
        if chip:
            out["chip"] = chip
        if profile:
            out["profile"] = profile
        if chip_model:
            out["chip_model"] = chip_model
        if chip_revision is not None:
            out["chip_revision"] = chip_revision
        if chip_cores is not None:
            out["chip_cores"] = chip_cores
        if controller:
            out["controller"] = controller
        if proto is not None:
            out["proto"] = proto
    else:
        if fallback_fw:
            out["firmware"] = fallback_fw
        if fallback_chip:
            out["chip"] = fallback_chip
        if fallback_profile:
            out["profile"] = fallback_profile
        if fallback_chip_model:
            out["chip_model"] = fallback_chip_model
        if fallback_chip_revision is not None:
            out["chip_revision"] = fallback_chip_revision
        if fallback_chip_cores is not None:
            out["chip_cores"] = fallback_chip_cores
        if fallback_controller:
            out["controller"] = fallback_controller
        if fallback_proto is not None:
            out["proto"] = fallback_proto
    if bridge_owns_port:
        # If bridge owns the port, do not touch serial directly from API.
        out["connected"] = bridge_connected
    else:
        ok, _reason = _probe_connected(dev_id)
        out["connected"] = bool(ok)
    return jsonify(out)


@api_bp.post("/devices/<path:dev_id>/fs-status")
def fs_status(dev_id):
    """Request filesystem status from the connected ESP via the bridge."""
    dev_id = _norm_dev_id(dev_id)
    try:
        st = read_bridge_state()
        if st.get("port") and (st.get("port") != dev_id) and not _ports_equivalent(st.get("port"), dev_id):
            return jsonify({"ok": False, "error": "bridge is on a different port"}), 400
        if not _bridge_running_on(dev_id):
            return jsonify({"ok": False, "error": "bridge not running"}), 400
    except Exception:
        pass

    status_payload = _bridge_rpc({"cmd": "GET_FS_STATUS"}, "FS_STATUS", timeout_s=5.0)

    if not status_payload:
        return jsonify({"ok": False, "error": "timeout waiting for fs status"}), 504
    return jsonify({"ok": True, "status": status_payload})


def _fs_list_impl(dev_id: str, path: str):
    dev_id = _norm_dev_id(dev_id)
    target = (path or "/").strip() or "/"
    try:
        st = read_bridge_state()
        if st.get("port") and (st.get("port") != dev_id) and not _ports_equivalent(st.get("port"), dev_id):
            return jsonify({"success": False, "error": "bridge is on a different port"}), 400
        if not _bridge_running_on(dev_id):
            return jsonify({"success": False, "error": "bridge not running"}), 400
    except Exception:
        pass

    _bridge_log("Requesting file list from ESP")
    with _fs_list_lock:
        payload = _bridge_rpc({"cmd": "FS_LIST", "path": target}, "FS_LIST", timeout_s=6.0)
    if not payload:
        _bridge_log("File list request failed: timeout waiting for FS_END")
        return jsonify({"success": False, "error": "Timeout waiting for FS_END"}), 504

    files = payload.get("files") if isinstance(payload, dict) else None
    if not isinstance(files, list):
        files = []
    manifest = _fetch_manifest()
    if manifest is None:
        _bridge_log("Manifest missing or unreadable; file list will omit uploadedAt")
        manifest = {}
    normalized = []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") if isinstance(entry.get("name"), str) else ""
        try:
            size = int(entry.get("size", 0))
        except Exception:
            size = 0
        base = name.split("/")[-1] if "/" in name else name
        meta = manifest.get(base) if isinstance(manifest, dict) else None
        uploaded_at = 0
        if isinstance(meta, dict):
            try:
                uploaded_at = int(meta.get("uploadedAt", 0))
            except Exception:
                uploaded_at = 0
            try:
                size = int(meta.get("size", size))
            except Exception:
                pass
        normalized.append({"name": name, "size": size, "uploadedAt": uploaded_at})
    count = len(normalized)
    _bridge_log(f"Received file list ({count} files)")
    return jsonify({
        "success": True,
        "path": payload.get("path") if isinstance(payload, dict) else target,
        "files": normalized,
        "count": count,
    })


@api_bp.post("/devices/<path:dev_id>/fs/list")
def fs_list_for_device(dev_id):
    body = request.get_json(silent=True) or {}
    path = body.get("path") if isinstance(body, dict) else "/"
    return _fs_list_impl(dev_id, path)


@api_bp.post("/fs/list")
def fs_list():
    body = request.get_json(silent=True) or {}
    path = body.get("path") if isinstance(body, dict) else "/"
    st = read_bridge_state()
    port = st.get("port") or ""
    if not port:
        return jsonify({"success": False, "error": "bridge not connected"}), 400
    return _fs_list_impl(port, path)


def _local_rules_info(rules_pd_path: Path) -> dict:
    if not rules_pd_path.exists():
        return {"exists": False, "sha256": "", "size": 0, "builtAt": None, "sourceHash": None}
    meta_path = rules_pd_path.with_name("rules_meta.json")
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    sha = meta.get("sha256") if isinstance(meta.get("sha256"), str) else ""
    size = int(meta.get("size", 0) or 0)
    built_at = meta.get("builtAt")
    source_hash = meta.get("sourceHash") if isinstance(meta.get("sourceHash"), str) else None
    if not sha or not size:
        try:
            blob = rules_pd_path.read_bytes()
            size = size or len(blob)
            sha = sha or hashlib.sha256(blob).hexdigest()
            if built_at is None or source_hash is None:
                bundle = decode_rules_pd_bytes(blob)
                built_at = bundle.built_at
                source_hash = bundle.source_hash
        except Exception:
            return {"exists": False, "sha256": "", "size": 0, "builtAt": None, "sourceHash": None}
    return {"exists": True, "sha256": sha, "size": size, "builtAt": built_at, "sourceHash": source_hash}


def _local_hardware_info(mapping_path: Path) -> dict:
    if not mapping_path.exists():
        return {"exists": False, "sha256": "", "size": 0, "sourceHash": ""}
    source_hash = ""
    try:
        source_hash = hashlib.sha256(mapping_path.read_bytes()).hexdigest()
    except Exception:
        source_hash = ""
    try:
        blob = build_mapping_blob_bytes(mapping_path)
    except Exception:
        return {"exists": False, "sha256": "", "size": 0, "sourceHash": source_hash}
    sha = hashlib.sha256(blob).hexdigest()
    return {"exists": True, "sha256": sha, "size": len(blob), "sourceHash": source_hash}


def _local_lighting_info(lighting_pd_path: Path) -> dict:
    if not lighting_pd_path.exists():
        return {"exists": False, "sha256": "", "size": 0, "builtAt": None}
    meta_path = lighting_pd_path.with_name("lighting_meta.json")
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    sha = meta.get("sha256") if isinstance(meta.get("sha256"), str) else ""
    size = int(meta.get("size", 0) or 0)
    built_at = meta.get("updatedAt")
    if not sha or not size:
        try:
            blob = lighting_pd_path.read_bytes()
            size = size or len(blob)
            sha = sha or hashlib.sha256(blob).hexdigest()
        except Exception:
            return {"exists": False, "sha256": "", "size": 0, "builtAt": None}
    return {"exists": True, "sha256": sha, "size": size, "builtAt": built_at}


def _esp_artifact_info(manifest: dict, name: str) -> dict:
    entry = None
    if isinstance(manifest, dict):
        if not name.startswith("/"):
            entry = manifest.get(f"/cfg/{name}")
            if entry is None:
                entry = manifest.get(name)
        if entry is None and name.startswith("/cfg/"):
            entry = manifest.get(name.split("/cfg/", 1)[1])
    if not isinstance(entry, dict):
        return {"exists": False, "sha256": "", "size": 0, "uploadedAt": None}
    sha = entry.get("sha256") if isinstance(entry.get("sha256"), str) else ""
    size = int(entry.get("size", 0) or 0)
    uploaded_at = entry.get("uploadedAt")
    return {"exists": True, "sha256": sha, "size": size, "uploadedAt": uploaded_at}


def _compute_in_sync(local: dict, esp: dict) -> bool:
    if not local.get("exists") or not esp.get("exists"):
        return False
    if local.get("sha256") and esp.get("sha256"):
        return local.get("sha256") == esp.get("sha256")
    return False


def _fetch_manifest() -> dict | None:
    try:
        st = read_bridge_state()
        cached = st.get("manifest") if isinstance(st, dict) else None
        if isinstance(cached, dict) and cached.get("ok"):
            data = cached.get("data")
            norm = _normalize_manifest(data)
            if isinstance(norm, dict):
                return norm
        blob_status = st.get("blob_status") if isinstance(st, dict) else None
        if isinstance(blob_status, dict):
            state = blob_status.get("state")
            if state in ("begin", "send", "await_ready", "await_result", "await_manifest"):
                return None
    except Exception:
        pass
    payload = _bridge_rpc({"cmd": "FS_MANIFEST_GET"}, "MANIFEST", timeout_s=3.0)
    if not isinstance(payload, dict) or not payload.get("ok"):
        return _normalize_manifest(_latest_manifest_from_responses())
    data = payload.get("data")
    norm = _normalize_manifest(data)
    if isinstance(norm, dict):
        return norm
    return _normalize_manifest(_latest_manifest_from_responses())


@sync_bp.get("/sync/status")
def sync_status():
    """Return rules/hardware sync status by comparing local and ESP hashes."""
    inst = Path(current_app.instance_path)
    local_rules = _local_rules_info(inst / "rules" / "rules.pd")
    local_hw = _local_hardware_info(inst / "hardware" / "mapping.json")
    local_lighting = _local_lighting_info(inst / "lighting" / "lighting.pd")
    sync_state = read_sync_state(current_app.instance_path)

    st = read_bridge_state()
    port = st.get("port") or ""
    esp_connected = bool(port) and _bridge_running_on(port) and bool(st.get("connected"))
    if not esp_connected:
        return jsonify({
            "success": True,
        "espConnected": False,
        "rules": {
            "local": local_rules,
            "esp": {"exists": False, "sha256": "", "size": 0, "uploadedAt": None},
            "inSync": False,
            "lastSyncedAt": sync_state.get("rules", {}).get("lastSyncedAt"),
        },
        "hardware": {
            "local": local_hw,
            "esp": {"exists": False, "sha256": "", "size": 0, "uploadedAt": None},
            "inSync": False,
            "lastSyncedAt": sync_state.get("hardware", {}).get("lastSyncedAt"),
        },
        "lighting": {
            "local": local_lighting,
            "esp": {"exists": False, "sha256": "", "size": 0, "uploadedAt": None},
            "inSync": False,
            "lastSyncedAt": sync_state.get("lighting", {}).get("lastSyncedAt"),
        },
        })

    manifest = _fetch_manifest()
    if manifest is None:
        _bridge_log("Manifest missing or unreadable; treating artifacts as out of sync")
        manifest = {}

    esp_rules = _esp_artifact_info(manifest, "rules.pd")
    esp_hw = _esp_artifact_info(manifest, "mapping.pb")
    esp_lighting = _esp_artifact_info(manifest, "lighting.pd")

    synced_hw_source_hash = str((sync_state.get("hardware") or {}).get("sourceHash") or "")
    local_hw_source_hash = str(local_hw.get("sourceHash") or "")
    hardware_in_sync = _compute_in_sync(local_hw, esp_hw)
    if local_hw.get("exists"):
        # Hardware is only considered in sync when both deployed blob and authored source config match.
        hardware_in_sync = hardware_in_sync and bool(local_hw_source_hash) and (synced_hw_source_hash == local_hw_source_hash)

    return jsonify({
        "success": True,
        "espConnected": True,
        "rules": {
            "local": local_rules,
            "esp": esp_rules,
            "inSync": _compute_in_sync(local_rules, esp_rules),
            "lastSyncedAt": sync_state.get("rules", {}).get("lastSyncedAt"),
        },
        "hardware": {
            "local": local_hw,
            "esp": esp_hw,
            "inSync": hardware_in_sync,
            "lastSyncedAt": sync_state.get("hardware", {}).get("lastSyncedAt"),
        },
        "lighting": {
            "local": local_lighting,
            "esp": esp_lighting,
            "inSync": _compute_in_sync(local_lighting, esp_lighting),
            "lastSyncedAt": sync_state.get("lighting", {}).get("lastSyncedAt"),
        },
    })


@api_bp.post("/devices/<path:dev_id>/echo")
def echo(dev_id):
    """Send a simple echo test command and return the response."""
    dev_id = _norm_dev_id(dev_id)
    try:
        st = read_bridge_state()
        if st.get("port") and (st.get("port") != dev_id) and not _ports_equivalent(st.get("port"), dev_id):
            return jsonify({"ok": False, "error": "bridge is on a different port"}), 400
        if not _bridge_running_on(dev_id):
            return jsonify({"ok": False, "error": "bridge not running"}), 400
    except Exception:
        pass

    try:
        status_payload = _bridge_rpc({"cmd": "ECHO"}, "ECHO", timeout_s=4.0)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

    if not status_payload:
        return jsonify({"ok": False, "error": "timeout waiting for echo"}), 504
    return jsonify({"ok": True, "status": status_payload})


@api_bp.post("/devices/<path:dev_id>/reboot")
def reboot(dev_id):
    """Request ESP reboot through the bridge only."""
    dev_id = _norm_dev_id(dev_id)
    if _is_upload_active():
        return jsonify({"ok": False, "error": "firmware upload in progress"}), 423
    if not _bridge_running_on(dev_id):
        return jsonify({"ok": False, "error": "bridge not running"}), 400
    try:
        payload = _bridge_rpc({"cmd": "HOST_REBOOT"}, "REBOOT", timeout_s=4.0)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "timeout waiting for reboot ack"}), 504
    if payload.get("ok") is not True:
        return jsonify({"ok": False, "error": payload.get("error") or "reboot failed", "status": payload}), 500
    _bridge_log(f"ESP reboot requested via bridge on {dev_id}")
    return jsonify({"ok": True, "status": payload})


@api_bp.post("/devices/<path:dev_id>/sync-time")
def sync_time(dev_id):
    """Push host time to the ESP via bridge RPC."""
    dev_id = _norm_dev_id(dev_id)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    epoch = int(time.time())
    # Prefer bridge state port if available
    port = dev_id
    st = {}
    try:
        st = read_bridge_state()
        if st.get("port"):
            port = st["port"]
    except Exception:
        pass

    if not _bridge_running_on(port):
        return jsonify({"ok": False, "error": "bridge not running", "now_iso": now_iso}), 400
    payload = _bridge_rpc({"cmd": "SYNC_TIME", "ts": epoch}, "TIME", timeout_s=4.0)
    if not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "timeout waiting for time ack", "now_iso": now_iso}), 504
    if payload.get("status") != "ok":
        return jsonify({"ok": False, "error": payload.get("reason") or "sync failed", "status": payload, "now_iso": now_iso}), 500
    return jsonify({"ok": True, "now_iso": now_iso, "epoch": epoch, "bridge_port": port, "bridge_connected": st.get("connected"), "status": payload})


# -------- API: versions (local / remote) --------------------------------------
@api_bp.get("/versions")
def versions():
    """Return firmware manifests from local storage or a remote URL."""
    source = (request.args.get("source", "local") or "").strip().lower()
    debug_flag = request.args.get("debug") in ("1", "true", "yes")

    if source == "remote":
        remote_url = (request.args.get("remote_url") or "").strip()
        if not remote_url:
            return jsonify({"latest": None, "versions": []})
        out = _load_remote_versions(remote_url, debug=debug_flag)
        return jsonify(out)

    # local
    fp = _instance_bin_dir() / "versions.json"
    raw = _dist_versions_local()

    if debug_flag:
        return jsonify({
            "_debug": {
                "instance_path": str(_instance_path()),
                "bin_dir": str(_instance_bin_dir()),
                "manifest_path": str(fp),
                "manifest_exists": fp.exists(),
                "manifest_bytes": (fp.stat().st_size if fp.exists() else None),
            },
            "latest": (raw or {}).get("latest"),
            "versions": (raw or {}).get("versions", []),
        })

    if not raw:
        return jsonify({"latest": None, "versions": []})

    return jsonify({
        "latest": raw.get("latest"),
        "versions": raw.get("versions", []),
    })


@api_bp.post("/versions/download")
def versions_download():
    """Download a remote firmware entry and upsert it into the local manifest."""
    payload = request.get_json(silent=True) or {}
    entry = payload.get("entry") or {}
    app_url = entry.get("download_url") or entry.get("filename")
    version = entry.get("version")

    if not (app_url and version):
        return jsonify({"ok": False, "error": "missing version or filename"}), 400
    if isinstance(app_url, str) and app_url.startswith("/"):
        app_url = urljoin(request.host_url, app_url)
    if not (isinstance(app_url, str) and (app_url.startswith("http://") or app_url.startswith("https://"))):
        return jsonify({"ok": False, "error": "filename must be an absolute URL"}), 400

    bin_dir = _instance_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    base_url = app_url.rsplit("/", 1)[0] if "/" in app_url else app_url
    def _resolve_asset_url(asset: str) -> str:
        if asset.startswith("http://") or asset.startswith("https://"):
            return asset
        return urljoin(base_url + "/", asset)

    partitions_name = (entry.get("partitions") or "partitions.bin").strip()
    partitions_url = _resolve_asset_url(partitions_name)
    partitions_basename = Path(urlparse(partitions_url).path).name or Path(partitions_name).name or "partitions.bin"
    partitions_dst = bin_dir / partitions_basename
    try:
        _download_asset_to_file(partitions_url, partitions_dst)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{partitions_basename} download failed: {e}"}), 400

    # ---- 2) Download bootloader (optional) ------------------------------------
    bootloader_name = (entry.get("bootloader") or "").strip()
    bootloader_basename = ""
    bootloader_dst = None
    if bootloader_name:
        bootloader_url = _resolve_asset_url(bootloader_name)
        bootloader_basename = Path(urlparse(bootloader_url).path).name or Path(bootloader_name).name
        bootloader_dst = bin_dir / bootloader_basename
        try:
            _download_asset_to_file(bootloader_url, bootloader_dst)
        except Exception as e:
            return jsonify({"ok": False, "error": f"{bootloader_basename} download failed: {e}"}), 400

    # ---- 3) Download app image ------------------------------------------------
    app_basename = Path(urlparse(app_url).path).name
    app_dst = bin_dir / app_basename
    try:
        _download_asset_to_file(app_url, app_dst)
    except Exception as e:
        return jsonify({"ok": False, "error": f"download failed: {e}"}), 400

    size = app_dst.stat().st_size
    sha256 = None
    partitions_sha = None
    bootloader_sha = None
    try:
        sha256 = _sha256_file(app_dst)
    except Exception:
        pass
    try:
        partitions_sha = _sha256_file(partitions_dst)
    except Exception:
        partitions_sha = None
    if bootloader_dst:
        try:
            bootloader_sha = _sha256_file(bootloader_dst)
        except Exception:
            bootloader_sha = None

    # ---- 2) Upsert manifest (unchanged schema) --------------------------------
    manifest_fp = bin_dir / "versions.json"
    manifest = _read_json(manifest_fp) or {"latest": version, "versions": []}

    updated = False
    for v in manifest["versions"]:
        if v.get("version") == version:
            v.update({
                "version": version,
                "date": entry.get("date"),
                "notes": entry.get("notes") or "",
                "filename": app_basename,
                "size": size,
                "sha256": sha256 or entry.get("sha256"),
                "partitions": partitions_basename,
                "partitions_sha256": partitions_sha or entry.get("partitions_sha256"),
                "bootloader": bootloader_basename or entry.get("bootloader"),
                "bootloader_sha256": bootloader_sha or entry.get("bootloader_sha256"),
            })
            updated = True
            break
    if not updated:
        manifest["versions"].insert(0, {
            "version": version,
            "date": entry.get("date"),
            "notes": entry.get("notes") or "",
            "filename": app_basename,
            "size": size,
            "sha256": sha256 or entry.get("sha256"),
            "partitions": partitions_basename,
            "partitions_sha256": partitions_sha or entry.get("partitions_sha256"),
            "bootloader": bootloader_basename or entry.get("bootloader"),
            "bootloader_sha256": bootloader_sha or entry.get("bootloader_sha256"),
        })
        if not manifest.get("latest"):
            manifest["latest"] = version

    _write_json(manifest_fp, manifest)
    return jsonify({
        "ok": True,
        "saved": app_basename,
        "size": size,
        "sha256": sha256,
    })


# -------- API: upload (serial flash via esptool) -------------------------------
def _stream_proc_lines(cmd):
    """Yield lines from a subprocess, including exit codes/errors."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
        close_fds=True,
    )
    try:
        for line in proc.stdout:
            yield line.rstrip("\n")
        proc.wait()
        yield f"[exit] {proc.returncode}"
    except Exception as e:
        yield f"[error] {e}"
    finally:
        try:
            proc.terminate()
        except Exception:
            pass


@api_bp.post("/devices/<path:dev_id>/upload")
def upload(dev_id):
    """Flash firmware to a selected device using esptool (local or remote image)."""
    dev_id = _norm_dev_id(dev_id)
    payload = request.get_json(silent=True) or {}
    method = payload.get("method", "local")  # local or remote
    version = payload.get("version")
    url = payload.get("url")
    default_baud = int(os.environ.get("ESPLINK_FLASH_BAUD_DEFAULT", "460800"))
    baud = int(payload.get("baud", default_baud))

    tmpfile = None
    fw_path = None
    src_name = None

    bootloader_fp = None
    partitions_fp = None

    if method == "local" and version:
        entry = _resolve_local_entry(version)
        if not entry:
            return Response("event: ERROR\ndata: Local version not found\n\n",
                            mimetype="text/event-stream")
        fw_name = entry.get("filename") or ""
        fw_fp = _instance_bin_dir() / Path(fw_name).name if fw_name else None
        if not fw_fp or not fw_fp.exists():
            return Response("event: ERROR\ndata: Local firmware file missing\n\n",
                            mimetype="text/event-stream")
        fw_path = str(fw_fp)
        src_name = Path(fw_path).name
        partitions_name = entry.get("partitions") or "partitions.bin"
        partitions_fp = _instance_bin_dir() / Path(partitions_name).name
        if not partitions_fp.exists():
            return Response(f"event: ERROR\ndata: {partitions_fp.name} not found in instance/firmware\n\n",
                            mimetype="text/event-stream")
        bootloader_name = entry.get("bootloader") or ""
        if bootloader_name:
            bootloader_fp = _instance_bin_dir() / Path(bootloader_name).name
            if not bootloader_fp.exists():
                return Response(f"event: ERROR\ndata: {bootloader_fp.name} not found in instance/firmware\n\n",
                                mimetype="text/event-stream")
    elif method == "remote" and url:
        tdir = tempfile.mkdtemp(prefix="esplink_")
        tmpfile = Path(tdir) / "firmware.bin"
        try:
            with _open_with_forwarded_auth(url) as r, open(tmpfile, "wb") as out:
                shutil.copyfileobj(r, out)
        except Exception as e:
            return Response(f"event: ERROR\ndata: Download failed: {e}\n\n",
                            mimetype="text/event-stream")
        fw_path = str(tmpfile)
        src_name = Path(urlparse(url).path).name or "firmware.bin"
    else:
        return Response("event: ERROR\ndata: Invalid upload payload\n\n",
                        mimetype="text/event-stream")

    if not partitions_fp:
        partitions_fp = _instance_bin_dir() / "partitions.bin"
    if not partitions_fp.exists():
        return Response(f"event: ERROR\ndata: {partitions_fp.name} not found in instance/firmware\n\n",
                        mimetype="text/event-stream")

    if not _firmware_upload_lock.acquire(blocking=False):
        return Response("event: ERROR\ndata: Another firmware upload is already in progress\n\n",
                        mimetype="text/event-stream")
    global _firmware_upload_active  # noqa: PLW0603
    _firmware_upload_active = True

    # Stop bridge if running on this port to avoid contention, and restart after.
    _set_bridge_reconcile_suspended(600.0, reason="firmware_upload")
    flash_ctx = None
    try:
        flash_ctx = shared_flash_begin(port=dev_id, reason="firmware_upload", settle_s=0.8)
    except Exception as e:
        _clear_bridge_reconcile_suspended()
        _firmware_upload_active = False
        try:
            _firmware_upload_lock.release()
        except Exception:
            pass
        return Response(f"event: ERROR\ndata: Failed to start flash session: {e}\n\n",
                        mimetype="text/event-stream")

    esptool = _esptool_cmd()
    chip = os.environ.get("ESPLINK_CHIP", "esp32s3")
    addr_boot = os.environ.get("ESPLINK_BOOTLOADER_ADDR", "0x0000")
    addr_partitions = "0x8000"
    addr_app = os.environ.get("ESPLINK_APP_ADDR", "0x10000")

    def _build_cmd(
        run_baud: int,
        *,
        compress: bool = True,
        no_stub: bool = False,
        include_bootloader: bool = True,
        include_partitions: bool = True,
        include_app: bool = True,
    ) -> list[str]:
        c = [
            *esptool, "--chip", chip,
            "--port", dev_id,
            "--baud", str(run_baud),
            "--before", "default_reset",
            "--after", "hard_reset",
        ]
        if no_stub:
            c.append("--no-stub")
        c.extend([
            "write_flash",
            "-z" if compress else "-u",
        ])
        if include_bootloader and bootloader_fp:
            c.extend([addr_boot, str(bootloader_fp)])
        if include_partitions:
            c.extend([addr_partitions, str(partitions_fp)])
        if include_app:
            c.extend([addr_app, fw_path])
        return c

    baud_plan = []
    for b in (baud, 230400, 115200):
        try:
            bi = int(b)
        except Exception:
            continue
        if bi > 0 and bi not in baud_plan:
            baud_plan.append(bi)

    def gen():
        global _firmware_upload_active  # noqa: PLW0603
        upload_ok = False
        try:
            if bootloader_fp:
                yield f"event: LOG\ndata: Flashing bootloader @ {addr_boot}, {partitions_fp.name} @ {addr_partitions}, {src_name} @ {addr_app}\n\n"
            else:
                yield f"event: LOG\ndata: Flashing {partitions_fp.name} @ {addr_partitions} and {src_name} @ {addr_app}\n\n"
            yield "event: STEP\ndata: enter-bootloader\n\n"

            last_code = 1
            for idx, run_baud in enumerate(baud_plan):
                if idx > 0:
                    yield f"event: LOG\ndata: Retrying flash at lower baud {run_baud}\n\n"
                cmd = _build_cmd(
                    run_baud,
                    compress=True,
                    include_bootloader=True,
                    include_partitions=True,
                    include_app=True,
                )
                run_code = None
                for line in _stream_proc_lines(cmd):
                    lower = line.lower()
                    if "writing at" in lower and "%" in line:
                        yield f"event: STEP\ndata: transfer {line.strip()}\n\n"
                    elif line.startswith("[exit]"):
                        run_code = int(line.split()[-1])
                    elif line.startswith("[error]"):
                        yield f"event: ERROR\ndata: {line}\n\n"
                    else:
                        yield f"event: LOG\ndata: {line}\n\n"
                if run_code is None:
                    run_code = 1
                last_code = run_code
                if run_code == 0:
                    upload_ok = True
                    yield "event: STEP\ndata: done\n\n"
                    break
                if idx < len(baud_plan) - 1:
                    yield f"event: LOG\ndata: esptool exited {run_code}; preparing retry\n\n"
                    time.sleep(0.8)
                else:
                    yield f"event: LOG\ndata: esptool exited {run_code}; trying recovery mode (app-only @ 115200)\n\n"
                    safe_cmd = _build_cmd(
                        115200,
                        compress=True,
                        no_stub=False,
                        include_bootloader=False,
                        include_partitions=False,
                        include_app=True,
                    )
                    safe_code = None
                    for line in _stream_proc_lines(safe_cmd):
                        lower = line.lower()
                        if "writing at" in lower and "%" in line:
                            yield f"event: STEP\ndata: transfer {line.strip()}\n\n"
                        elif line.startswith("[exit]"):
                            safe_code = int(line.split()[-1])
                        elif line.startswith("[error]"):
                            yield f"event: ERROR\ndata: {line}\n\n"
                        else:
                            yield f"event: LOG\ndata: {line}\n\n"
                    if safe_code == 0:
                        yield "event: STEP\ndata: done\n\n"
                    else:
                        yield "event: LOG\ndata: app-only compressed retry failed; trying app-only uncompressed @ 115200\n\n"
                        safer_cmd = _build_cmd(
                            115200,
                            compress=False,
                            no_stub=True,
                            include_bootloader=False,
                            include_partitions=False,
                            include_app=True,
                        )
                        safer_code = None
                        for line in _stream_proc_lines(safer_cmd):
                            lower = line.lower()
                            if "writing at" in lower and "%" in line:
                                yield f"event: STEP\ndata: transfer {line.strip()}\n\n"
                            elif line.startswith("[exit]"):
                                safer_code = int(line.split()[-1])
                            elif line.startswith("[error]"):
                                yield f"event: ERROR\ndata: {line}\n\n"
                            else:
                                yield f"event: LOG\ndata: {line}\n\n"
                        if safer_code == 0:
                            upload_ok = True
                            yield "event: STEP\ndata: done\n\n"
                        else:
                            final_code = safer_code if safer_code is not None else (safe_code if safe_code is not None else run_code)
                            yield f"event: ERROR\ndata: esptool exited {final_code}\n\n"
        finally:
            if tmpfile:
                try:
                    shutil.rmtree(tmpfile.parent)
                except Exception:
                    pass
            try:
                end_result = shared_flash_end(
                    ctx=flash_ctx,
                    success=bool(upload_ok),
                    restart_on_success=True,
                    restart_baud=460800,
                )
                if bool(end_result.get("restarted")):
                    yield "event: LOG\ndata: Bridge restarted\n\n"
                elif flash_ctx and flash_ctx.get("bridge_was_running") and not upload_ok:
                    yield "event: LOG\ndata: Bridge remains stopped after failed upload\n\n"
            except Exception as e:
                yield f"event: ERROR\ndata: Flash session end failed: {e}\n\n"
            _clear_bridge_reconcile_suspended()
            _firmware_upload_active = False
            try:
                _firmware_upload_lock.release()
            except Exception:
                pass

    return Response(stream_with_context(gen()), headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    })


@api_bp.get("/bridge/reconcile")
def bridge_reconcile_status():
    """Expose whether auto bridge lifecycle is temporarily suspended."""
    now = time.monotonic()
    active = now < _bridge_reconcile_suspended_until
    return jsonify({
        "suspended": active,
        "reason": _bridge_reconcile_suspend_reason if active else "",
        "remaining_s": max(0.0, _bridge_reconcile_suspended_until - now) if active else 0.0,
        "upload_active": _is_upload_active(),
    })
    if _is_upload_active():
        # Avoid touching the serial port while flashing.
        return True, "upload-active"
