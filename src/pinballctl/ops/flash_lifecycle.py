"""Shared flash lifecycle helpers for lock + bridge process coordination."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any


def _state_dir() -> Path:
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "pinballctl"


def bridge_pidfile() -> Path:
    return _state_dir() / "bridge.pid"


def bridge_logfile() -> Path:
    return _state_dir() / "bridge.log"


def upload_lockfile() -> Path:
    return _state_dir() / "firmware_upload.lock"


def _read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _kill_pid(pid: int, sig: int) -> None:
    try:
        os.kill(pid, sig)
    except Exception:
        pass


def claim_upload_lock(reason: str = "firmware_upload", stale_s: int = 20 * 60) -> bool:
    lock = upload_lockfile()
    lock.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if lock.exists():
        try:
            data = json.loads(lock.read_text())
            started = float(data.get("started_at", 0) or 0)
        except Exception:
            started = lock.stat().st_mtime
        if started and (now - started) > stale_s:
            try:
                lock.unlink(missing_ok=True)
            except Exception:
                pass
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps({"started_at": now, "reason": reason}))
        return True
    except FileExistsError:
        return False
    except Exception:
        return False


def release_upload_lock() -> None:
    try:
        upload_lockfile().unlink(missing_ok=True)
    except Exception:
        pass


def _kill_stray_bridge_processes() -> None:
    if shutil.which("pkill"):
        subprocess.run(["pkill", "-TERM", "-f", "pinballctl bridge"], check=False)
        time.sleep(0.4)
        subprocess.run(["pkill", "-KILL", "-f", "pinballctl bridge"], check=False)


def stop_bridge(force: bool = True, kill_strays: bool = True) -> dict[str, Any]:
    pidfile = bridge_pidfile()
    pid = _read_pid(pidfile) if pidfile.exists() else None
    was_running = bool(pid and _pid_alive(pid))
    if pid and _pid_alive(pid):
        _kill_pid(pid, signal.SIGTERM)
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not _pid_alive(pid):
                break
            time.sleep(0.05)
        if force and _pid_alive(pid):
            _kill_pid(pid, signal.SIGKILL)
            time.sleep(0.2)
    try:
        pidfile.unlink(missing_ok=True)
    except Exception:
        pass
    if kill_strays:
        _kill_stray_bridge_processes()
    return {"was_running": was_running}


def _resolve_pinballctl_bin() -> str | None:
    cand = shutil.which("pinballctl")
    if cand:
        return cand
    venv = Path.cwd() / ".venv" / "bin" / "pinballctl"
    if venv.exists():
        return str(venv)
    return None


def start_bridge(port: str, baud: int = 460800) -> int | None:
    pinballctl_bin = _resolve_pinballctl_bin()
    if not pinballctl_bin:
        return None
    pidfile = bridge_pidfile()
    logfile = bridge_logfile()
    pidfile.parent.mkdir(parents=True, exist_ok=True)
    logfile.parent.mkdir(parents=True, exist_ok=True)
    lf = open(logfile, "ab", buffering=0)
    proc = subprocess.Popen(
        [pinballctl_bin, "bridge", "--port", port, "--baud", str(baud)],
        stdin=subprocess.DEVNULL,
        stdout=lf,
        stderr=lf,
        close_fds=False,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
        env=os.environ.copy(),
    )
    pidfile.write_text(str(proc.pid))
    return int(proc.pid)


def flash_begin(port: str, reason: str = "firmware_upload", settle_s: float = 0.8) -> dict[str, Any]:
    if not claim_upload_lock(reason=reason):
        raise RuntimeError("another firmware upload is already in progress")
    try:
        stop = stop_bridge(force=True, kill_strays=True)
        if settle_s > 0:
            time.sleep(settle_s)
        return {
            "port": port,
            "bridge_was_running": bool(stop.get("was_running")),
            "reason": reason,
            "started_at": time.time(),
        }
    except Exception:
        release_upload_lock()
        raise


def flash_end(ctx: dict[str, Any] | None, success: bool, restart_on_success: bool = True, restart_baud: int = 460800) -> dict[str, Any]:
    restart_pid = None
    try:
        if success and restart_on_success and isinstance(ctx, dict) and ctx.get("bridge_was_running") and ctx.get("port"):
            # Give USB CDC a brief settle window after flashing.
            time.sleep(1.0)
            restart_pid = start_bridge(str(ctx.get("port")), baud=int(restart_baud))
    finally:
        release_upload_lock()
    return {"restarted": restart_pid is not None, "pid": restart_pid}


def _main() -> int:
    parser = argparse.ArgumentParser(description="Shared flash lifecycle begin/end helper.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_begin = sub.add_parser("begin")
    p_begin.add_argument("--port", required=True)
    p_begin.add_argument("--reason", default="firmware_upload")
    p_begin.add_argument("--settle", type=float, default=0.8)
    p_begin.add_argument("--context-file", default="")

    p_end = sub.add_parser("end")
    p_end.add_argument("--success", type=int, default=0)
    p_end.add_argument("--restart-on-success", type=int, default=1)
    p_end.add_argument("--restart-baud", type=int, default=460800)
    p_end.add_argument("--context-file", default="")
    p_end.add_argument("--context", default="")

    args = parser.parse_args()
    if args.cmd == "begin":
        ctx = flash_begin(port=args.port, reason=args.reason, settle_s=float(args.settle))
        out = json.dumps(ctx)
        if args.context_file:
            Path(args.context_file).write_text(out)
        print(out)
        return 0
    ctx: dict[str, Any] | None = None
    if args.context:
        ctx = json.loads(args.context)
    elif args.context_file:
        p = Path(args.context_file)
        if p.exists():
            ctx = json.loads(p.read_text())
    result = flash_end(
        ctx=ctx,
        success=bool(int(args.success)),
        restart_on_success=bool(int(args.restart_on_success)),
        restart_baud=int(args.restart_baud),
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
