"""Restart only the previously running local bridge after a successful restore."""
import fcntl
from pathlib import Path
import shlex
import subprocess

from . import service


def bridge_options(pid):
    """Capture explicit CLI settings; never run a recovered command line."""
    result = subprocess.run(['ps', '-ww', '-p', str(pid), '-o', 'command='],
                            capture_output=True, text=True, timeout=5, check=True)
    args = shlex.split(result.stdout)
    service.check('bridge' in args, 'Cannot identify bridge startup settings; restore cancelled')
    try:
        port = args[args.index('--port') + 1]
        baud = int(args[args.index('--baud') + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError('Cannot capture bridge port and baud; restore cancelled') from exc
    service.check(bool(port) and 0 < baud <= 4000000, 'Invalid bridge startup settings')
    return port, baud


def restore(instance, sequence, clear, report, progress):
    from pinballctl import cli
    from pinballctl.bridge.state import commands_path, write_state
    # Isolated/test instances must never manage the real machine's bridge.
    if Path(instance).resolve() != commands_path().parent.parent.resolve():
        return service.restore(instance, sequence, clear, report, progress)
    folder = Path(instance) / '.project-locks'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'restore-lifecycle.lock').open('a') as lease:
        try:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError('Another restore is already managing the bridge') from exc
        running, pid = cli._bridge_running_via_lock()
        options = bridge_options(pid) if running else None
        if running:
            progress(message='Stopping bridge for restore…')
            cli._stop_bridge_process(cli._default_bridge_pidfile())
            service.check(not cli._bridge_running_via_lock()[0], 'Bridge did not stop; restore cancelled')
            write_state(connected=False, connection_reason='backup_restore')
        try:
            result = service.restore(instance, sequence, clear, report, progress)
        except Exception as exc:
            if running:
                raise ValueError(f'Restore failed; bridge remains stopped. {exc}') from exc
            raise
        if options:
            progress(message='Restore saved. Restarting bridge…')
            try:
                service.check(not cli._bridge_running_via_lock()[0], 'Another bridge started during restore')
                port, baud = options
                started = cli._start_bridge_background(port, baud, cli._default_bridge_pidfile(), cli._default_bridge_log())
                service.check(bool(started) and cli._bridge_running_via_lock()[0], 'Bridge restart failed')
            except Exception as exc:
                raise ValueError(f'Restore completed; bridge restart failed. Start it manually. Recovery backup: {result["recoveryId"]}. {exc}') from exc
        result['bridgeRestarted'] = bool(options)
        return result
