"""Install and manage the independent systemd services for PinballCTL."""

from pathlib import Path
import pwd
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory


LEGACY_UNIT = "pinball.service"
RUNTIME_TARGET = "pinball-runtime.target"
WEB_UNIT = "pinball-web.service"
BRIDGE_UNIT = "pinball-bridge.service"
MEDIA_UNIT = "pinball-media.service"

SERVICE_TARGETS = {
    "web": (WEB_UNIT,),
    "bridge": (BRIDGE_UNIT,),
    "runtime": (RUNTIME_TARGET,),
    "all": (RUNTIME_TARGET, WEB_UNIT),
}

STATUS_UNITS = (RUNTIME_TARGET, BRIDGE_UNIT, MEDIA_UNIT, WEB_UNIT)

_RUNTIME = """[Unit]
Description=PinballCTL machine runtime
Wants=pinball-bridge.service pinball-media.service
Conflicts=pinball.service
After=pinball.service

[Install]
WantedBy=multi-user.target
"""

_SERVICE = """[Service]
User=@SERVICE_USER@
WorkingDirectory=@WORKDIR@
Environment="PATH=@BIN_DIR@:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="XDG_STATE_HOME=@STATE_HOME@"
RestartSec=2
"""

_WEB = """[Unit]
Description=PinballCTL admin webapp
Wants=network-online.target
After=network-online.target pinball-media.service pinball.service
Conflicts=pinball.service

""" + _SERVICE + """Type=exec
Environment="PINBALLCTL_SYSTEMD=1"
ExecStart="@PYTHON@" -m gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class gthread --threads 4 --access-logfile "@STATE_HOME@/pinballctl/gunicorn-access.log" --error-logfile "@STATE_HOME@/pinballctl/gunicorn-error.log" pinballctl.webapp:create_app()
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure

[Install]
WantedBy=multi-user.target
"""

_BRIDGE = """[Unit]
Description=PinballCTL ESP serial bridge
PartOf=pinball-runtime.target
StartLimitIntervalSec=0

""" + _SERVICE + """Type=exec
ExecStart="@PINBALLCTL@" bridge
ExecStopPost="@PYTHON@" -c "from pinballctl.runtime.bridge.state import write_state; write_state(connected=False, connection_reason='bridge_stopped')"
Restart=always
StandardOutput=append:@STATE_HOME@/pinballctl/bridge.log
StandardError=inherit
"""

_MEDIA = """[Unit]
Description=PinballCTL Godot supervisor
PartOf=pinball-runtime.target

""" + _SERVICE + """Type=notify
ExecStart="@PYTHON@" -m pinballctl.runtime.media.godot_daemon
TimeoutStartSec=20
Restart=on-failure
StandardOutput=append:@STATE_HOME@/pinballctl/media-daemon.log
StandardError=inherit
"""


def _render_units(user: str, workdir: Path, executable: Path, python: Path, state_home: Path) -> dict[str, str]:
    values = {
        "SERVICE_USER": user,
        "WORKDIR": str(workdir),
        "BIN_DIR": str(executable.parent),
        "PINBALLCTL": str(executable),
        "PYTHON": str(python),
        "STATE_HOME": str(state_home),
    }
    units = {
        RUNTIME_TARGET: _RUNTIME,
        WEB_UNIT: _WEB,
        BRIDGE_UNIT: _BRIDGE,
        MEDIA_UNIT: _MEDIA,
    }
    for key, value in values.items():
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
        units = {name: template.replace(f"@{key}@", escaped) for name, template in units.items()}
    return units


def _systemctl(*args: str) -> None:
    subprocess.check_call(["sudo", "systemctl", *args])


def _read_systemctl(*args: str) -> str:
    return subprocess.check_output(["systemctl", *args], text=True, timeout=5).strip()


def _unit_exists(unit: str) -> bool:
    return _read_systemctl("show", "--property=LoadState", "--value", unit) != "not-found"


def unit_active(unit: str) -> bool:
    if not Path("/run/systemd/system").is_dir():
        return False
    state = _read_systemctl("show", "--property=ActiveState", "--value", unit)
    return state not in {"", "inactive", "failed"}


def require_bridge_service_stopped() -> None:
    if unit_active(BRIDGE_UNIT):
        raise RuntimeError("Run 'pinballctl service stop bridge' before this maintenance operation.")


def service_install(user: str = "pi", systemd_dir: str = "/etc/systemd/system",
                    workdir: str | None = None, venv_bin: str | None = None) -> None:
    """Install the independent units and migrate the previous bundled service."""
    workdir_path = Path(workdir or Path.cwd()).resolve()
    candidates = Path(venv_bin).absolute() if venv_bin else workdir_path / ".venv/bin"
    executable = candidates / "pinballctl"
    if not executable.is_file():
        installed = shutil.which("pinballctl")
        if not installed:
            raise SystemExit("pinballctl not found. Activate the environment where it is installed.")
        executable = Path(installed).resolve()
    python = executable.parent / "python"
    if not python.is_file():
        python = Path(sys.executable).absolute()

    try:
        state_home = Path(pwd.getpwnam(user).pw_dir) / ".local/state"
    except KeyError:
        raise SystemExit(f"Service user does not exist: {user}") from None

    units = _render_units(user, workdir_path, executable, python, state_home)
    subprocess.check_call(["sudo", "-u", user, "mkdir", "-p", str(state_home / "pinballctl")])
    with TemporaryDirectory() as temp:
        for name, text in units.items():
            path = Path(temp) / name
            path.write_text(text, encoding="utf-8")
            subprocess.check_call(["sudo", "install", "-m", "0644", str(path), str(Path(systemd_dir) / name)])
    _systemctl("daemon-reload")
    if _unit_exists(LEGACY_UNIT):
        _systemctl("disable", "--now", LEGACY_UNIT)
    _systemctl("enable", RUNTIME_TARGET, WEB_UNIT)
    _systemctl("restart", RUNTIME_TARGET, WEB_UNIT)
    print_service_status()


def service_uninstall(systemd_dir: str = "/etc/systemd/system") -> None:
    """Stop and remove installed PinballCTL units."""
    for unit in (WEB_UNIT, RUNTIME_TARGET, LEGACY_UNIT):
        if _unit_exists(unit):
            _systemctl("disable", "--now", unit)
    # Also stop any runtime members started directly while the target was inactive.
    members = tuple(unit for unit in (BRIDGE_UNIT, MEDIA_UNIT) if _unit_exists(unit))
    if members:
        _systemctl("stop", *members)
    units = [str(Path(systemd_dir) / name) for name in (*STATUS_UNITS, LEGACY_UNIT)]
    subprocess.check_call(["sudo", "rm", "-f", *units])
    _systemctl("daemon-reload")
    print("Uninstalled PinballCTL units.")


def service_action(action: str, which: str) -> None:
    """Route systemd operations to the requested PinballCTL service."""
    if which not in SERVICE_TARGETS:
        raise SystemExit(f"Unknown service target: {which}")
    if action not in ("start", "stop", "reload"):
        raise SystemExit(f"Unsupported service action: {action}")

    if not _unit_exists(RUNTIME_TARGET) and _unit_exists(LEGACY_UNIT):
        if which != "all":
            raise SystemExit("Run pinballctl service install to migrate the bundled service before managing it separately.")
        _systemctl(action, LEGACY_UNIT)
    elif action == "reload":
        if which != "web":
            # Targets do not support reload; restart their member services.
            runtime_unit = BRIDGE_UNIT if which == "bridge" else RUNTIME_TARGET
            _systemctl("try-restart", runtime_unit)
        if which in ("web", "all"):
            web_action = "reload" if which == "web" else "try-reload-or-restart"
            _systemctl(web_action, WEB_UNIT)
    elif action == "stop" and which in ("runtime", "all"):
        _systemctl("stop", *SERVICE_TARGETS[which], BRIDGE_UNIT, MEDIA_UNIT)
    else:
        _systemctl(action, *SERVICE_TARGETS[which])
    print_service_status()


def print_service_status() -> None:
    """Show the managed services and the legacy unit when installed."""
    for unit in (*STATUS_UNITS, LEGACY_UNIT):
        try:
            properties = _read_systemctl("show", "--property=LoadState,ActiveState,UnitFileState", unit)
        except (OSError, subprocess.SubprocessError):
            continue
        values = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
        if values.get("LoadState") != "not-found":
            state = values.get("ActiveState", "unknown")
            enabled = values.get("UnitFileState")
            print(f"{unit}: {state}" + (f" ({enabled})" if enabled else ""))
