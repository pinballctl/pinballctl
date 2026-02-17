"""Signed short-lived tokens for media kiosk runtime access."""
from __future__ import annotations

import base64
import hashlib
import hmac
import time


def _norm_secret(secret: str | None) -> bytes:
    raw = str(secret or "").strip()
    if not raw:
        raw = "pinballctl-media-kiosk-dev-secret"
    return raw.encode("utf-8")


def make_runtime_token(secret: str | None, ttl_seconds: int = 12 * 3600) -> str:
    """Return token format: `<exp>.<sig>` with HMAC-SHA256 signature."""
    exp = int(time.time()) + max(60, int(ttl_seconds or 0))
    payload = f"media-runtime:{exp}".encode("utf-8")
    mac = hmac.new(_norm_secret(secret), payload, hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")
    return f"{exp}.{sig}"


def verify_runtime_token(secret: str | None, token: str | None) -> bool:
    tok = str(token or "").strip()
    if not tok or "." not in tok:
        return False
    exp_s, sig = tok.split(".", 1)
    try:
        exp = int(exp_s)
    except Exception:
        return False
    now = int(time.time())
    if exp < now:
        return False
    payload = f"media-runtime:{exp}".encode("utf-8")
    mac = hmac.new(_norm_secret(secret), payload, hashlib.sha256).digest()
    expected = base64.urlsafe_b64encode(mac).decode("ascii").rstrip("=")
    return hmac.compare_digest(expected, sig)

