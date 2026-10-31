"""
Security helpers: TOTP (RFC 6238) for MFA, and optional at-rest wrapping with Fernet.

Two layers protect vault data:
  1. Client-side AES-256-GCM (browser). The server cannot read document contents.
  2. Optional server-side Fernet wrapping of the already-encrypted blob, so a
     database leak alone exposes nothing even if the client layer were broken.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

# ----------------------------------------------------------------- TOTP
def new_totp_secret() -> str:
    """160-bit secret, base32 (the format authenticator apps expect)."""
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret_b32: str, counter: int, digits: int = 6) -> str:
    key = base64.b32decode(secret_b32 + "=" * (-len(secret_b32) % 8), casefold=True)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    off = h[-1] & 0x0F
    code = (struct.unpack(">I", h[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp_at(secret_b32: str, timestamp: float, step: int = 30) -> str:
    return _hotp(secret_b32, int(timestamp // step))


def verify_totp(secret_b32: str, code: str, window: int = 1, now: float | None = None) -> bool:
    """Accept codes from the previous/current/next 30-second step (clock drift)."""
    code = (code or "").replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return False
    now = time.time() if now is None else now
    ok = False
    for drift in range(-window, window + 1):
        if hmac.compare_digest(totp_at(secret_b32, now + drift * 30), code):
            ok = True
    return ok


def otpauth_uri(secret_b32: str, email: str, issuer: str = "SafeLife") -> str:
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret_b32}&issuer={quote(issuer)}&digits=6&period=30"


# ------------------------------------------------------- at-rest wrapping
class Wrapper:
    """Wraps strings with Fernet when a key is configured; otherwise passes through."""

    def __init__(self, fernet_key: str | None):
        self._f = None
        if fernet_key:
            from cryptography.fernet import Fernet
            self._f = Fernet(fernet_key.encode())

    @property
    def enabled(self) -> bool:
        return self._f is not None

    def wrap(self, text: str) -> str:
        if self._f is None:
            return text
        return "F1:" + self._f.encrypt(text.encode()).decode()

    def unwrap(self, text: str) -> str:
        if text.startswith("F1:"):
            if self._f is None:
                raise RuntimeError("Encrypted record found but AAPDA_VAULT_ENCRYPTION_KEY is not set.")
            return self._f.decrypt(text[3:].encode()).decode()
        return text
