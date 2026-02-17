"""Systemd unit helpers for installing, managing, and inspecting pinballctl."""

# pinballctl/ops/service.py

import os, subprocess, shutil, glob
from typing import Optional

UNIT = "pinball.service"

UNIT_TEMPLATE = """[Unit]
Description=pinballctl (bridge + web)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=@SERVICE_USER@
WorkingDirectory=@WORKDIR@
Environment="PATH=@PATH_PREFIX@"
# Allow binding to privileged ports if needed (safe even if unused)
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
RuntimeDirectory=pinball
# Start bridge in background, web in foreground so systemd tracks it
ExecStart=/bin/bash -lc '@PINBALLCTL_BIN@ bridge & exec @PINBALLCTL_BIN@ start --host 0.0.0.0 --port 8000 --foreground --pidfile /run/pinball/gunicorn.pid'
# Graceful reload of Gunicorn workers
ExecReload=@PINBALLCTL_BIN@ reload --pidfile /run/pinball/gunicorn.pid
# Stop: systemd sends SIGTERM to the foreground process; the background bridge will be killed with it
KillMode=mixed
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
"""

def _detect_paths(workdir: Optional[str]=None, venv_bin: Optional[str]=None):
    """Resolve repository path, virtualenv bin dir, and pinballctl binary."""
    repo_dir = workdir or os.getcwd()
    venv_candidate = venv_bin or os.path.join(repo_dir, ".venv", "bin")

    pinballctl_bin = shutil.which("pinballctl") or ""
    if os.path.exists(os.path.join(venv_candidate, "pinballctl")):
        pinballctl_bin = os.path.join(venv_candidate, "pinballctl")

    if not pinballctl_bin:
        raise SystemExit("pinballctl not found. Activate your venv or install the package in this environment.")

    path_prefix = os.path.dirname(pinballctl_bin)
    return repo_dir, venv_candidate, pinballctl_bin, path_prefix

def _render(template: str, **kw) -> str:
    """Render a template by replacing @KEY@ placeholders."""
    out = template
    for k,v in kw.items():
        out = out.replace(f"@{k}@", v)
    return out

def _write_temp_unit(content: str) -> str:
    """Write a temporary unit file and return its path."""
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".service")
    with os.fdopen(fd, "w") as f:
        f.write(content)
    return path

def service_install(user: str="pi", systemd_dir: str="/etc/systemd/system", workdir: Optional[str]=None, venv_bin: Optional[str]=None):
    """Render and install the systemd unit, enabling and restarting it."""
    repo_dir, venv_candidate, pinballctl_bin, path_prefix = _detect_paths(workdir, venv_bin)

    unit_text = _render(UNIT_TEMPLATE,
        SERVICE_USER=user,
        WORKDIR=repo_dir,
        PATH_PREFIX=path_prefix,
        PINBALLCTL_BIN=pinballctl_bin,
    )

    unit_path_tmp = _write_temp_unit(unit_text)

    print("Installing unit to", systemd_dir)
    subprocess.check_call(["sudo", "cp", unit_path_tmp, os.path.join(systemd_dir, UNIT)])
    subprocess.check_call(["sudo", "systemctl", "daemon-reload"])
    subprocess.check_call(["sudo", "systemctl", "enable", UNIT])
    subprocess.check_call(["sudo", "systemctl", "restart", UNIT])
    print_status()

def service_uninstall(systemd_dir: str="/etc/systemd/system"):
    """Disable and remove the installed systemd unit if present."""
    subprocess.call(["sudo", "systemctl", "disable", "--now", UNIT])
    try:
        subprocess.check_call(["sudo", "rm", "-f", os.path.join(systemd_dir, UNIT)])
    except subprocess.CalledProcessError:
        pass
    subprocess.call(["sudo", "systemctl", "daemon-reload"])
    print("Uninstalled unit.")

def service_action(action: str, which: str):
    """Invoke a systemctl action on the single pinballctl unit."""
    # 'which' kept for CLI compatibility; ignore and always target the single unit
    if action not in ("start", "stop", "reload", "restart", "status"):
        raise SystemExit(f"Unsupported action: {action}")
    cmd = ["sudo", "systemctl", action, UNIT] if action != "status" else ["systemctl", "status", UNIT]
    subprocess.check_call(cmd)
    if action != "status":
        print_status()

def _read_cmd(cmd):
    """Return stdout from a command or empty string on failure."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
        return out.strip()
    except Exception:
        return ""

def _net_info():
    """Lightweight SSID/IP lookup for the service status report."""
    ssid = _read_cmd(["iwgetid", "-r"]) or _read_cmd(["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
    if ssid and ":" in ssid:
        parts = [line for line in ssid.splitlines() if line.startswith("yes:")]
        if parts:
            ssid = parts[0].split(":",1)[1]
    ips = _read_cmd(["hostname", "-I"]) or _read_cmd(["ip", "-4", "addr", "show"])
    return ssid or "(unknown)", (ips.strip() if ips else "(none)")

def _esp_ports():
    """Return USB serial ports that look like ESP32 boards."""
    return sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*"))

def print_status():
    """Print a concise systemd/web/bridge status overview."""
    print("=== pinballctl status ===")
    py = _read_cmd(["which", "python"]) or "(unknown)"
    pinballctl = _read_cmd(["which", "pinballctl"]) or "(unknown)"
    gunicorn = _read_cmd(["which", "gunicorn"]) or "(unknown)"
    print("python    :", py)
    print("pinballctl:", pinballctl)
    print("gunicorn  :", gunicorn)
    print()
    active = _read_cmd(["systemctl", "is-active", UNIT]) or "(unknown)"
    enabled = _read_cmd(["systemctl", "is-enabled", UNIT]) or "(unknown)"
    print(f"-- {UNIT} --")
    print("active   :", active)
    print("enabled  :", enabled)
    show = _read_cmd(["systemctl", "show", UNIT, "-p", "ExecStart,ExecReload,WorkingDirectory,User"]) or ""
    if show:
        print(show)
    print()
    ssid, ips = _net_info()
    print(f"Network:  SSID={ssid}  IP={ips}")
    ports = _esp_ports()
    if ports:
        print("ESP32:   ", ", ".join(ports))
    else:
        print("ESP32:    (no /dev/ttyUSB* or /dev/ttyACM* found)")
    print()
