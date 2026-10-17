"""Serial discovery that is safe inside macOS Gunicorn workers."""

import json
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
    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    return [SimpleNamespace(**port) for port in json.loads(result.stdout)]
