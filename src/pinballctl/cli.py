"""CLI entrypoint and process helpers for pinballctl web + bridge control."""

import argparse
import os
import sys
import signal
import time
import re
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from datetime import datetime
from collections import deque

from pinballctl import __version__ as PINBALLCTL_VERSION
from pinballctl.app import create_app  # still used by `pinballctl web` (dev)
from pinballctl.bridge.daemon import run as run_bridge
from pinballctl.bridge.state import queue_blob_put
from pinballctl.ops.mapping_blob import build_mapping_pb, _instance_dir
from pinballctl.ops.service import (
    service_install, service_uninstall,
    service_action,  # Linux systemd users
)

# ---- state / pid / log helpers ---------------------------------------------

def _state_dir() -> Path:
    """Return the base state directory (~/.local/state/pinballctl by default)."""
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "pinballctl"

def _ensure_state_dir() -> Path:
    """Ensure the state directory exists and return it."""
    p = _state_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

def _default_pidfile() -> Path:
    """Default Gunicorn pidfile location."""
    return _ensure_state_dir() / "gunicorn.pid"

def _default_bridge_pidfile() -> Path:
    """Default bridge pidfile location."""
    return _ensure_state_dir() / "bridge.pid"

def _default_bridge_log() -> Path:
    """Default bridge log path."""
    return _ensure_state_dir() / "bridge.log"

def _default_media_pidfile() -> Path:
    """Default Godot media daemon pidfile location."""
    return _ensure_state_dir() / "media-daemon.pid"

def _default_media_log() -> Path:
    """Default Godot media daemon log path."""
    return _ensure_state_dir() / "media-daemon.log"

def _default_gunicorn_access_log() -> Path:
    """Default Gunicorn access log path."""
    return _ensure_state_dir() / "gunicorn-access.log"

def _default_gunicorn_error_log() -> Path:
    """Default Gunicorn error log path."""
    return _ensure_state_dir() / "gunicorn-error.log"

def _now() -> str:
    """UTC timestamp string for log messages."""
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _append_line(path: Path, line: str) -> None:
    """Append a single line to a log file, creating parents if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")

def _log_paths():
    """Return canonical log paths (users can still override at start)."""
    sd = _ensure_state_dir()
    return {
        "dir": sd,
        "web_access": _default_gunicorn_access_log(),
        "web_error": _default_gunicorn_error_log(),
        "bridge": _default_bridge_log(),
        "media": _default_media_log(),
    }

# ---- pid helpers ------------------------------------------------------------

def _read_pid(pidfile: Path) -> int | None:
    """Read an integer PID from a pidfile or return None."""
    try:
        return int(pidfile.read_text().strip())
    except Exception:
        return None

def _write_pid(pidfile: Path, pid: int) -> None:
    """Write a PID to disk, ensuring the directory exists."""
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    pidfile.write_text(str(pid))

def _rm_pidfile(pidfile: Path) -> None:
    """Remove a pidfile, ignoring errors."""
    try:
        if pidfile.exists():
            pidfile.unlink()
    except Exception:
        pass

def _is_running(pid: int) -> bool:
    """Return True if the PID appears to belong to a running process."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def _wait_for_pidfile(pidfile: Path, timeout=5.0) -> int | None:
    """Poll for a pidfile to appear and contain a live PID."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = _read_pid(pidfile)
        if pid and _is_running(pid):
            return pid
        time.sleep(0.05)
    return _read_pid(pidfile)

def _stop_pidfile(pidfile: Path, sig=signal.SIGTERM, wait_cycles=100) -> bool:
    """Send a signal to the PID in pidfile and clean up; return True if signaled."""
    pid = _read_pid(pidfile)
    if not pid or not _is_running(pid):
        _rm_pidfile(pidfile)
        return False
    try:
        os.kill(pid, sig)
    except Exception:
        pass
    for _ in range(wait_cycles):
        if not _is_running(pid):
            break
        time.sleep(0.05)
    _rm_pidfile(pidfile)
    return True

def _bridge_lockfile() -> Path:
    """Path to bridge single-instance lock file."""
    return _ensure_state_dir() / "bridge.lock"

def _bridge_lock_pid() -> int | None:
    """Best-effort lock holder PID from bridge.lock metadata."""
    try:
        raw = _bridge_lockfile().read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return None
    m = re.search(r"\bpid=(\d+)\b", raw or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None

def _stop_bridge_process(pidfile: Path, wait_cycles=100) -> bool:
    """Stop bridge using pidfile and lock-holder PID to avoid split-brain runners."""
    stopped_any = False
    pid_from_file = _read_pid(pidfile)
    if _stop_pidfile(pidfile, sig=signal.SIGTERM, wait_cycles=wait_cycles):
        stopped_any = True
    # Always also check the lock holder; pidfile may have pointed at a different process.
    lpid = _bridge_lock_pid()
    if lpid and _is_running(lpid) and lpid != pid_from_file:
        try:
            os.kill(lpid, signal.SIGTERM)
            stopped_any = True
        except Exception:
            pass
        for _ in range(wait_cycles):
            if not _is_running(lpid):
                break
            time.sleep(0.05)
    # Clean stale pidfile after stop attempts.
    _rm_pidfile(pidfile)
    return stopped_any

def _bridge_running_via_lock() -> tuple[bool, int | None]:
    """Return whether lock holder bridge appears alive and its PID."""
    lpid = _bridge_lock_pid()
    if lpid and _is_running(lpid):
        return True, lpid
    return False, None

# ---- tiny ANSI color helper -------------------------------------------------

def _c(s: str, code: str) -> str:
    """Wrap text in ANSI color codes when stdout is a TTY."""
    return f"\x1b[{code}m{s}\x1b[0m" if sys.stdout.isatty() else s

GREEN, RED = "32", "31"

# ---- os / status helpers ----------------------------------------------------

def _read_cmd(cmd: list[str]) -> str:
    """Return stripped stdout from a command, or empty string on error."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except Exception:
        return ""

def _has_systemd() -> bool:
    """Detect systemd availability for service management."""
    return sys.platform.startswith("linux") and os.path.exists("/run/systemd/system")

def _ip_fallback() -> str:
    """Best-effort IP detection across available interfaces."""
    ips = set()
    try:
        for res in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = res[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if not ip.startswith("127."):
            ips.add(ip)
    except Exception:
        pass
    return ", ".join(sorted(ips)) or "(none)"

def _esp_ports() -> list[str]:
    """Return serial ports that look like ESP-class devices."""
    KNOWN_USB_IDS = {
        (0x10C4, 0xEA60),  # Silicon Labs CP210x
        (0x1A86, 0x7523),  # WCH CH340
        (0x1A86, 0x55D4),  # CH9102F
        (0x0403, 0x6001),  # FTDI FT232
        (0x303A, 0x1001), (0x303A, 0x4001), (0x303A, 0x4002),  # Espressif native USB-JTAG/Serial
    }
    results = []
    try:
        from serial.tools import list_ports
        for p in list_ports.comports():
            dev = p.device or ""
            if not dev:
                continue
            vid_pid_ok = p.vid is not None and p.pid is not None and (p.vid, p.pid) in KNOWN_USB_IDS
            path_ok = any(x in dev for x in ("/dev/ttyUSB", "/dev/ttyACM", "/dev/cu.usb", "/dev/cu.SLAB_USB"))
            desc = " ".join(filter(None, [p.manufacturer, p.product, p.description])).lower()
            desc_ok = any(x in desc for x in ("espressif", "cp210", "ch340", "ch910", "ftdi", "silicon labs", "usb"))
            if vid_pid_ok or path_ok or desc_ok:
                results.append(dev)
        results = sorted(dict.fromkeys(results))
        if results:
            return results
    except Exception:
        try:
            out = subprocess.check_output(
                [sys.executable or "python3", "-c", "import serial.tools.list_ports as lp; print('\\n'.join(p.device for p in lp.comports()))"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            fallbacks = [l.strip() for l in out.splitlines() if l.strip()]
            if fallbacks:
                return fallbacks
        except Exception:
            pass
    return results

def _net_info() -> tuple[str, str]:
    """Return a tuple of (ssid, ip addresses) for local network info."""
    system = platform.system().lower()
    ips = _ip_fallback()
    ssid = "(unknown)"
    if system == "linux":
        if shutil.which("iwgetid"):
            ssid = _read_cmd(["iwgetid", "-r"]) or "(unknown)"
        elif shutil.which("nmcli"):
            nm = _read_cmd(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
            if nm:
                active = [l for l in nm.splitlines() if l.startswith("yes:")]
                if active:
                    ssid = active[0].split(":", 1)[1] or "(unknown)"
    elif system == "darwin" and shutil.which("networksetup"):
        for dev in ("en0", "en1"):
            out = _read_cmd(["networksetup", "-getairportnetwork", dev])
            if "Current Wi-Fi Network:" in out:
                ssid = out.split(":", 1)[1].strip() or "(unknown)"
                break
    return ssid, ips

def _pinballctl_bin() -> str:
    """Resolve the pinballctl executable for subprocess invocations."""
    return shutil.which("pinballctl") or sys.argv[0]

# ---- background starters ----------------------------------------------------

def _run_gunicorn_subprocess(bind: str, workers: int, threads: int, accesslog: Path, errorlog: Path,
                             reload_: bool, pidfile: Path) -> None:
    """Launch Gunicorn in the background with thread workers and log files."""
    try:
        import gunicorn  # noqa: F401
    except ImportError:
        print("Gunicorn is not installed. Install it with: pip install gunicorn", file=sys.stderr)
        sys.exit(1)

    cmd = [
        sys.executable, "-m", "gunicorn",
        "--bind", bind,
        "--workers", str(workers),
        "-k", "gthread",                # ensure threaded worker class
        "--threads", str(threads),
        "--access-logfile", str(accesslog),
        "--error-logfile", str(errorlog),
        "--pid", str(pidfile),
        "pinballctl.app:create_app()",
    ]
    if reload_:
        cmd.append("--reload")

    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        close_fds=True,
    )

def _resolve_bridge_port(port_opt: str) -> str | None:
    """Resolve an explicit port or auto-detect the first ESP-like port."""
    if port_opt and port_opt != "auto":
        return port_opt
    ports = _esp_ports()
    return ports[0] if ports else None

def _start_bridge_background(port: str, baud: int, pidfile: Path, logfile: Path) -> int | None:
    """Start the bridge as a subprocess and persist PID only after startup is alive."""
    cmd = [_pinballctl_bin(), "bridge", "--port", port, "--baud", str(baud)]
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logf = open(logfile, "ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=logf,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        close_fds=True,
    )
    # Give bridge a brief window to fail fast (e.g. lock busy). Only then write PID.
    time.sleep(0.35)
    if proc.poll() is not None:
        return None
    _write_pid(pidfile, proc.pid)
    return proc.pid


def _start_media_daemon_background(pidfile: Path, logfile: Path) -> int | None:
    """Start the Godot media daemon in the background."""
    cmd = [sys.executable, "-m", "pinballctl.media.godot_daemon", str(_instance_dir())]
    sock_path = _instance_dir() / "media" / "godot" / "daemon.sock"
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logf = open(logfile, "ab", buffering=0)
    proc = subprocess.Popen(
        cmd,
        stdout=logf,
        stderr=logf,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        close_fds=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])},
    )
    deadline = time.time() + 3.0
    while time.time() < deadline:
        if proc.poll() is not None:
            return None
        if sock_path.exists():
            _write_pid(pidfile, proc.pid)
            return proc.pid
        time.sleep(0.05)
    if proc.poll() is not None:
        return None
    return None

# ---- log tailing ------------------------------------------------------------

def _tail_with_tailcmd(files: list[Path], lines: int):
    """Exec tail(1) to stream the requested log files."""
    cmd = ["tail", "-n", str(lines), "-F"] + [str(p) for p in files]
    os.execvp("tail", cmd)  # replace current process

def _tail_python(files: list[Path], lines: int):
    """Pure-python tail -F fallback when tail(1) is unavailable."""
    # Print last N lines per file, then follow
    def print_last_n(fp: Path, n: int):
        try:
            with open(fp, "r", encoding="utf-8", errors="replace") as f:
                dq = deque(f, maxlen=n)
            for line in dq:
                sys.stdout.write(f"[{fp.name}] {line}")
        except FileNotFoundError:
            sys.stdout.write(f"[{fp.name}] (file not found, will wait for it to appear)\n")

    for p in files:
        print_last_n(p, lines)
    sys.stdout.flush()

    # Follow
    files_state = {}
    for p in files:
        try:
            f = open(p, "r", encoding="utf-8", errors="replace")
            f.seek(0, os.SEEK_END)
            files_state[p] = f
        except FileNotFoundError:
            files_state[p] = None

    try:
        while True:
            for p in files:
                f = files_state[p]
                if f is None:
                    try:
                        f = open(p, "r", encoding="utf-8", errors="replace")
                        f.seek(0, os.SEEK_END)
                        files_state[p] = f
                        sys.stdout.write(f"[{p.name}] (created)\n")
                        sys.stdout.flush()
                    except FileNotFoundError:
                        time.sleep(0.2)
                        continue
                where = f.tell()
                line = f.readline()
                if not line:
                    time.sleep(0.2)
                    f.seek(where)
                else:
                    sys.stdout.write(f"[{p.name}] {line}")
                    sys.stdout.flush()
    except KeyboardInterrupt:
        for f in files_state.values():
            try:
                if f: f.close()
            except Exception:
                pass
        return

# ---- status printer ---------------------------------------------------------

def print_status_cli():
    """Print runtime status for web/bridge processes, service, logs, and network."""
    print("=== pinballctl status ===")
    print("python    :", sys.executable or "(unknown)")
    print("pinballctl:", shutil.which("pinballctl") or "(unknown)")
    print("gunicorn  :", shutil.which("gunicorn") or "(unknown)")
    print()

    # Web (Gunicorn)
    web_pidfile = _default_pidfile()
    web_pid = _read_pid(web_pidfile)
    web_running = bool(web_pid and _is_running(web_pid))
    print("Gunicorn : " + (_c(f"running (pid {web_pid})", GREEN) if web_running else _c("stopped", RED)))

    # Bridge: prefer pidfile, fallback to ps (for foreground/manual runs)
    bridge_pidfile = _default_bridge_pidfile()
    bridge_pid = _read_pid(bridge_pidfile)
    bridge_running = bool(bridge_pid and _is_running(bridge_pid))
    if not bridge_running:
        try:
            out = subprocess.check_output(["ps", "ax", "-o", "pid,command"], text=True)
            for line in out.splitlines():
                if "pinballctl bridge" in line and "grep" not in line:
                    try:
                        bridge_pid = int(line.split()[0]); bridge_running = True; break
                    except Exception:
                        pass
        except Exception:
            pass
    print("Bridge   : " + (_c(f"running (pid {bridge_pid})", GREEN) if bridge_running else _c("stopped", RED)))
    media_pidfile = _default_media_pidfile()
    media_pid = _read_pid(media_pidfile)
    media_running = bool(media_pid and _is_running(media_pid))
    print("Media    : " + (_c(f"running (pid {media_pid})", GREEN) if media_running else _c("stopped", RED)))
    print()

    # Service (Linux)
    print("-- pinball.service --")
    if _has_systemd():
        active = _read_cmd(["systemctl", "is-active", "pinball.service"]) or "inactive"
        enabled = _read_cmd(["systemctl", "is-enabled", "pinball.service"]) or "disabled"
        print("active   :", active)
        print("enabled  :", enabled)
        show = _read_cmd(["systemctl", "show", "pinball.service", "-p", "ExecStart,ExecReload,WorkingDirectory,User"])
        if show: print(show)
    else:
        print("systemd not detected on this OS (service status unavailable)")
    print()

    # Logs (locations)
    logs = _log_paths()
    print("-- logs --")
    print("dir      :", logs["dir"])
    print("web(access):", logs["web_access"])
    print("web(error):", logs["web_error"])
    print("bridge   :", logs["bridge"])
    print("media    :", logs["media"])
    print()

    # Network + ESP
    ssid, ips = _net_info()
    print(f"Network:  SSID={ssid}  IP={ips}")
    ports = _esp_ports()
    print("ESP32:   ", ", ".join(ports) if ports else "(none connected)")
    print()

# ---- CLI -------------------------------------------------------------------

def main():
    """Entry point for the pinballctl CLI; dispatch subcommands."""
    parser = argparse.ArgumentParser(prog="pinballctl", description="Pinball controller utilities")
    parser.add_argument("--version", action="version", version=f"%(prog)s {PINBALLCTL_VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # Start/Stop/Reload control BOTH (web + bridge)
    p_start = sub.add_parser("start", help="Start web (Gunicorn) and the serial bridge in the background")
    p_start.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    p_start.add_argument("--port", type=int, default=8888, help="Bind port (default: 8888)")
    p_start.add_argument("--workers", type=int, default=2, help="Gunicorn workers (default: 2)")
    p_start.add_argument("--threads", type=int, default=4, help="Gunicorn threads per worker (default: 4)")
    p_start.add_argument("--accesslog", default=str(_default_gunicorn_access_log()), help="Gunicorn access log")
    p_start.add_argument("--errorlog", default=str(_default_gunicorn_error_log()), help="Gunicorn error log")
    p_start.add_argument("--pidfile", default=str(_default_pidfile()), help="PID file (web)")
    p_start.add_argument("--reload", action="store_true", help="Gunicorn auto-reload on code changes (dev only)")
    p_start.add_argument("--bridge-port", default="auto", help="Bridge serial port (default: auto-detect)")
    p_start.add_argument("--bridge-baud", type=int, default=460800, help="Bridge baud rate (default: 460800)")
    p_start.add_argument("--bridge-pidfile", default=str(_default_bridge_pidfile()), help="PID file (bridge)")
    p_start.add_argument("--bridge-log", default=str(_default_bridge_log()), help="Log file (bridge)")
    p_start.add_argument("--media-pidfile", default=str(_default_media_pidfile()), help="PID file (media daemon)")
    p_start.add_argument("--media-log", default=str(_default_media_log()), help="Log file (media daemon)")
    p_start.add_argument("--devmode", action="store_true", help="Enable fast dev mode (auto-reload, 1 worker, threads=4)")

    p_stop = sub.add_parser("stop", help="Stop web and bridge")
    p_stop.add_argument("--pidfile", default=str(_default_pidfile()), help="PID file (web)")
    p_stop.add_argument("--bridge-pidfile", default=str(_default_bridge_pidfile()), help="PID file (bridge)")
    p_stop.add_argument("--media-pidfile", default=str(_default_media_pidfile()), help="PID file (media daemon)")

    p_reload = sub.add_parser("reload", help="Reload web (SIGHUP) and restart bridge")
    p_reload.add_argument("--pidfile", default=str(_default_pidfile()), help="PID file (web)")
    p_reload.add_argument("--bridge-port", default="auto", help="Bridge serial port (default: auto-detect)")
    p_reload.add_argument("--bridge-baud", type=int, default=460800, help="Bridge baud rate (default: 460800)")
    p_reload.add_argument("--bridge-pidfile", default=str(_default_bridge_pidfile()), help="PID file (bridge)")
    p_reload.add_argument("--bridge-log", default=str(_default_bridge_log()), help="Log file (bridge)")
    p_reload.add_argument("--media-pidfile", default=str(_default_media_pidfile()), help="PID file (media daemon)")
    p_reload.add_argument("--media-log", default=str(_default_media_log()), help="Log file (media daemon)")

    # Dev web (foreground)
    p_web = sub.add_parser("web", help="Run the Flask dev server (foreground, not for production)")
    p_web.add_argument("--host", default="0.0.0.0")
    p_web.add_argument("--port", type=int, default=8000)

    # Manual bridge (foreground)
    p_bridge = sub.add_parser("bridge", help="Run the serial bridge daemon (foreground)")
    p_bridge.add_argument("--port", default="auto", help="Serial port (or 'auto' to detect)")
    p_bridge.add_argument("--baud", type=int, default=460800)   # <-- fixed

    # Status
    sub.add_parser("status", help="Show local runtime (web/bridge), service status, log locations, network/IP, and ESP ports")

    # Logs (tail)
    p_logs = sub.add_parser(
        "logs",
        help="Tail logs for a specific component",
        description=(
            "View or follow recent log output.\n\n"
            "Targets:\n"
            "  bridge  – The serial bridge log file\n"
            "  error   – Gunicorn error log\n"
            "  access  – Gunicorn access log\n"
            "  web     – Combined error + access logs\n\n"
            "Examples:\n"
            "  pinballctl logs bridge\n"
            "  pinballctl logs web --lines 500\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p_logs.add_argument(
        "which",
        choices=["bridge", "error", "access", "web"],
        help="Which logs to tail",
    )
    p_logs.add_argument(
        "--lines",
        type=int,
        default=200,
        help="Number of lines to show initially (default: 200)",
    )

    # Build hardware mapping blob
    p_map_pb = sub.add_parser("build-mapping-pb", help="Build hardware mapping.pb from mapping.json")
    p_map_pb.add_argument("--mapping", default=None, help="Path to mapping.json (defaults to src/instance/hardware/mapping.json)")
    p_map_pb.add_argument("--output", default=None, help="Path to mapping.pb (defaults to src/instance/hardware/mapping.pb)")

    # Queue a blob transfer for the bridge
    p_blob_put = sub.add_parser("blob-put", help="Queue a blob transfer for the bridge daemon")
    p_blob_put.add_argument("--type", choices=["hardware", "rules"], default="hardware", help="Blob type (default: hardware)")
    p_blob_put.add_argument("--local", default=None, help="Local path to blob file")
    p_blob_put.add_argument("--remote", default=None, help="Remote SPIFFS path (e.g., /cfg/mapping.pb)")

    # Optional systemd management (Linux only)
    p_service = sub.add_parser("service", help="Manage systemd services for pinballctl (optional, Linux only)")
    service_sub = p_service.add_subparsers(dest="svc_cmd", required=True)
    p_install = service_sub.add_parser("install", help="Render and install systemd unit (pinball.service)")
    p_install.add_argument("--user", default="pi", help="User for the service (default: pi)")
    p_install.add_argument("--systemd-dir", default="/etc/systemd/system", help="Target systemd dir")
    p_install.add_argument("--workdir", default=None, help="Working directory for service (defaults to current dir)")
    p_install.add_argument("--venv-bin", default=None, help="Path to venv bin (defaults to <workdir>/.venv/bin if exists)")
    service_sub.add_parser("uninstall", help="Disable and remove installed systemd unit")
    for action in ("start", "stop", "reload"):
        p_act = service_sub.add_parser(action, help=f"{action} the pinball.service via systemd")
        p_act.add_argument("which", choices=["web", "bridge", "all"], help="(ignored; single-unit service)")

    # --- dispatch ------------------------------------------------------------
    args = parser.parse_args()

    if args.cmd == "start":
        # --- dev mode tweaks (fast reloads, lighter worker model) ---
        if getattr(args, "devmode", False):
            args.reload = True
            args.workers = 2
            args.threads = 4  # keep multithreaded even in dev
            os.environ["PINBALLCTL_DEVMODE"] = "1"

        # Start web
        web_pidfile = Path(args.pidfile)
        existing = _read_pid(web_pidfile)
        if existing and _is_running(existing):
            print(f"Web already running (pid {existing}).")
        else:
            bind = f"{args.host}:{args.port}"
            _run_gunicorn_subprocess(
                bind=bind,
                workers=args.workers,
                threads=args.threads,
                accesslog=Path(args.accesslog),
                errorlog=Path(args.errorlog),
                reload_=args.reload,
                pidfile=web_pidfile,
            )
            web_pid = _wait_for_pidfile(web_pidfile, timeout=5.0)
            if web_pid and _is_running(web_pid):
                print(f"Started web on {bind} (pid {web_pid}). PID file: {web_pidfile}")
            else:
                print("Started web, but couldn't confirm pidfile. Check logs.", file=sys.stderr)

        # Start bridge (auto-detect port if needed)
        bridge_pidfile = Path(args.bridge_pidfile)
        b_existing = _read_pid(bridge_pidfile)
        if b_existing and _is_running(b_existing):
            print(f"Bridge already running (pid {b_existing}).")
        else:
            port = _resolve_bridge_port(args.bridge_port)
            if not port:
                _append_line(Path(args.bridge_log), f"[{_now()}] Bridge: no serial port detected; skipping start.")
                print("Bridge: no serial port detected; skipping start (connect ESP32 and retry).")
            else:
                try:
                    bpid = _start_bridge_background(port, args.bridge_baud, bridge_pidfile, Path(args.bridge_log))
                    if bpid and _is_running(bpid):
                        _append_line(Path(args.bridge_log), f"[{_now()}] Bridge started on {port} @ {args.bridge_baud} (pid {bpid}).")
                        print(f"Started bridge on {port} @ {args.bridge_baud} (pid {bpid}). PID file: {bridge_pidfile}")
                    else:
                        running, lpid = _bridge_running_via_lock()
                        if running and lpid:
                            _write_pid(bridge_pidfile, lpid)
                            _append_line(Path(args.bridge_log), f"[{_now()}] Bridge already running via lock holder (pid {lpid}).")
                            print(f"Bridge already running on {port} (pid {lpid}). PID file synced: {bridge_pidfile}")
                        else:
                            _append_line(Path(args.bridge_log), f"[{_now()}] Bridge failed to start on {port}.")
                            print(f"Bridge failed to start (port {port}). See log: {args.bridge_log}", file=sys.stderr)
                except Exception as e:
                    _append_line(Path(args.bridge_log), f"[{_now()}] Bridge exception: {e}")
                    print(f"Failed to start bridge: {e}", file=sys.stderr)

        media_pidfile = Path(args.media_pidfile)
        m_existing = _read_pid(media_pidfile)
        if m_existing and _is_running(m_existing):
            print(f"Media daemon already running (pid {m_existing}).")
        else:
            try:
                mpid = _start_media_daemon_background(media_pidfile, Path(args.media_log))
                if mpid and _is_running(mpid):
                    print(f"Started media daemon (pid {mpid}). PID file: {media_pidfile}")
                else:
                    print(f"Media daemon failed to start. See log: {args.media_log}", file=sys.stderr)
            except Exception as e:
                print(f"Failed to start media daemon: {e}", file=sys.stderr)

    elif args.cmd == "stop":
        web_stopped = _stop_pidfile(Path(args.pidfile))
        print("Stopped web." if web_stopped else "Web not running.")
        bridge_stopped = _stop_bridge_process(Path(args.bridge_pidfile))
        if bridge_stopped:
            _append_line(_default_bridge_log(), f"[{_now()}] Bridge stopped.")
        print("Stopped bridge." if bridge_stopped else "Bridge not running.")
        media_stopped = _stop_pidfile(Path(args.media_pidfile))
        print("Stopped media daemon." if media_stopped else "Media daemon not running.")

    elif args.cmd == "reload":
        # Reload web
        web_pidfile = Path(args.pidfile)
        web_pid = _read_pid(web_pidfile)
        if not web_pid or not _is_running(web_pid):
            print("Web not running; cannot reload.", file=sys.stderr)
        else:
            os.kill(web_pid, signal.SIGHUP)
            print("Reload signal sent to web (SIGHUP).")

        # Restart bridge (auto-detect port if needed)
        bridge_pidfile = Path(args.bridge_pidfile)
        _stop_bridge_process(bridge_pidfile)
        port = _resolve_bridge_port(args.bridge_port)
        if not port:
            _append_line(Path(args.bridge_log), f"[{_now()}] Bridge: no serial port detected; skipping restart.")
            print("Bridge: no serial port detected; skipping restart (connect ESP32 and retry).")
        else:
            try:
                bpid = _start_bridge_background(port, args.bridge_baud, bridge_pidfile, Path(args.bridge_log))
                if bpid and _is_running(bpid):
                    _append_line(Path(args.bridge_log), f"[{_now()}] Bridge restarted on {port} @ {args.bridge_baud} (pid {bpid}).")
                    print(f"Restarted bridge on {port} @ {args.bridge_baud} (pid {bpid}).")
                else:
                    running, lpid = _bridge_running_via_lock()
                    if running and lpid:
                        _write_pid(bridge_pidfile, lpid)
                        _append_line(Path(args.bridge_log), f"[{_now()}] Bridge already running via lock holder (pid {lpid}).")
                        print(f"Bridge already running on {port} (pid {lpid}). PID file synced: {bridge_pidfile}")
                    else:
                        _append_line(Path(args.bridge_log), f"[{_now()}] Bridge restart failed on {port}.")
                        print(f"Bridge restart failed (port {port}). See log: {args.bridge_log}", file=sys.stderr)
            except Exception as e:
                _append_line(Path(args.bridge_log), f"[{_now()}] Bridge restart exception: {e}")
                print(f"Failed to restart bridge: {e}", file=sys.stderr)

        media_pidfile = Path(args.media_pidfile)
        _stop_pidfile(media_pidfile, sig=signal.SIGTERM)
        try:
            mpid = _start_media_daemon_background(media_pidfile, Path(args.media_log))
            if mpid and _is_running(mpid):
                print(f"Restarted media daemon (pid {mpid}).")
            else:
                print(f"Media daemon restart requested, but the new process was not confirmed.", file=sys.stderr)
        except Exception as e:
            print(f"Failed to restart media daemon: {e}", file=sys.stderr)

    elif args.cmd == "web":
        app = create_app()
        app.run(host=args.host, port=args.port, debug=True, threaded=True)  # threaded dev server

    elif args.cmd == "bridge":
        # Foreground bridge now supports auto-detect too
        port = _resolve_bridge_port(args.port)
        if not port:
            print("No ESP32 serial port detected. Plug it in and try again.\n"
                  "Tip: run `pinballctl status` to see detected ports.", file=sys.stderr)
            sys.exit(1)
        print(f"Connecting to {port} @ {args.baud} (Ctrl+C to quit)...")
        run_bridge(port=port, baud=args.baud)

    elif args.cmd == "status":
        print_status_cli()

    elif args.cmd == "logs":
        logs = _log_paths()
        which = args.which

        if which == "bridge":
            files = [logs["bridge"]]
        elif which == "error":
            files = [logs["web_error"]]
        elif which == "access":
            files = [logs["web_access"]]
        elif which == "web":
            files = [logs["web_error"], logs["web_access"]]
        else:
            # Should never happen due to argparse choices, but be defensive
            print(f"Unknown log target: {which}", file=sys.stderr)
            sys.exit(2)

        files = [Path(f) for f in files]

        # Prefer tail(1) if available (mac/Linux); fallback to Python
        if shutil.which("tail"):
            _tail_with_tailcmd(files, args.lines)
        else:
            _tail_python(files, args.lines)

    elif args.cmd == "build-mapping-pb":
        mapping_path = Path(args.mapping) if args.mapping else None
        output_path = Path(args.output) if args.output else None
        try:
            result = build_mapping_pb(mapping_path=mapping_path, output_path=output_path)
        except FileNotFoundError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Failed to build mapping.pb: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"Wrote mapping.pb: {result.output_path}")
        print(f"Entries: {result.count}  Payload: {result.payload_len} bytes  CRC32: 0x{result.payload_crc32:08X}")

    elif args.cmd == "blob-put":
        inst = _instance_dir()
        if args.type == "hardware":
            default_local = inst / "hardware" / "mapping.pb"
            default_remote = "/cfg/mapping.pb"
        else:
            default_local = inst / "rules" / "rules.pb"
            default_remote = "/cfg/rules.pb"
        local_path = Path(args.local) if args.local else default_local
        remote_path = args.remote or default_remote
        queue_blob_put(args.type, str(local_path), remote_path)
        print(f"Queued BLOB_PUT for {args.type}: {local_path} -> {remote_path}")

    elif args.cmd == "service":
        if args.svc_cmd == "install":
            service_install(user=args.user, systemd_dir=args.systemd_dir, workdir=args.workdir, venv_bin=args.venv_bin)
        elif args.svc_cmd == "uninstall":
            service_uninstall(systemd_dir=args.systemd_dir)
        elif args.svc_cmd in ("start", "stop", "reload"):
            service_action(args.svc_cmd, args.which)
