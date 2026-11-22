"""Helpers to send commands via bridge IPC (no direct serial access)."""

from __future__ import annotations

from .state import enqueue_command, rpc_command


def send_command(
    port: str | None,
    payload: dict,
    baud: int = 460800,
    *,
    wait_for: str | None = None,
    timeout_s: float = 3.0,
):
    """Send a command through the bridge process.

    Args:
      port: Kept for backwards compatibility; ignored.
      payload: Bridge command payload.
      baud: Kept for backwards compatibility; ignored.
      wait_for: Optional response type to wait for.
      timeout_s: Wait timeout when ``wait_for`` is provided.
    """
    _ = (port, baud)
    if not isinstance(payload, dict):
        return False, "bad-payload"
    try:
        if wait_for:
            resp = rpc_command(payload, match_t=wait_for, timeout_s=timeout_s)
            if resp is None:
                return False, "timeout"
            return True, resp
        enqueue_command(payload)
        return True, None
    except Exception as e:
        return False, str(e)
