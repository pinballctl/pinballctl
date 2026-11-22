"""Serial discovery that is safe inside macOS Gunicorn workers."""

import json
import logging
import subprocess
import sys
from types import SimpleNamespace


def comports():
    """Return port metadata, isolating Apple's IOKit from forked workers.

    Gunicorn forks its workers. Calling macOS device APIs in those workers
    can terminate the interpreter, so enumerate in a freshly executed Python.
    Failures propagate to callers rather than masquerading as disconnected USB.
    """
    if sys.platform != "darwin":
        from serial.tools import list_ports

        return list_ports.comports()

    fields = (
        "device", "description", "hwid", "vid", "pid",
        "manufacturer", "product", "serial_number",
    )
    script = (
        "import json; from serial.tools import list_ports; "
        f"fields = {fields!r}; "
        "print(json.dumps([{k: getattr(p, k, None) for k in fields} "
        "for p in list_ports.comports()]))"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-c", script],
            # Gunicorn may close stdin; give the helper valid standard streams.
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except subprocess.CalledProcessError as exc:
        logging.getLogger(__name__).error("Serial discovery helper failed: %s", (exc.stderr or "No error output").strip())
        if hasattr(exc, "add_note"):
            exc.add_note("Serial discovery helper stderr: " + (exc.stderr or "No error output").strip())
        raise
    return [SimpleNamespace(**port) for port in json.loads(result.stdout)]
