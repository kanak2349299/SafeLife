"""
Configuration for SafeLife.

Values come from environment variables. A `.env` file in the project root is
loaded automatically if present (variables already set in the environment win).
No secret is hardcoded in this project.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("safelife")
ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Tiny .env parser: KEY=VALUE lines, # comments, optional quotes."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    secret_key: str
    cookie_secure: bool
    db_path: str
    fernet_key: str | None
    supabase_url: str | None
    supabase_key: str | None
    supabase_bucket: str
    gemini_key: str | None
    gemini_model: str
    warnings: list[str] = field(default_factory=list)

    @property
    def blob_backend(self) -> str:
        return "supabase" if self.supabase_url and self.supabase_key else "sqlite"


def load_settings() -> Settings:
    if (ROOT / ".env").exists():
        load_dotenv(ROOT / ".env")
    elif (ROOT.parent / ".env").exists():
        load_dotenv(ROOT.parent / ".env")
    warnings: list[str] = []

    secret = os.environ.get("AAPDA_SECRET_KEY", "")
    if not secret or secret.startswith("replace_"):
        warnings.append("AAPDA_SECRET_KEY is missing or a placeholder; using a random key (sessions reset on restart).")
        import secrets as _s
        secret = _s.token_urlsafe(48)

    fernet = os.environ.get("AAPDA_VAULT_ENCRYPTION_KEY") or None
    if fernet and fernet.startswith("replace_"):
        fernet = None
    if fernet:
        try:
            from cryptography.fernet import Fernet
            Fernet(fernet.encode())
        except Exception:
            warnings.append("AAPDA_VAULT_ENCRYPTION_KEY is not a valid Fernet key; at-rest wrapping is disabled.")
            fernet = None
    else:
        warnings.append("AAPDA_VAULT_ENCRYPTION_KEY not set; vault data is client-encrypted only (no server-side wrapping).")

    sb_url = os.environ.get("AAPDA_SUPABASE_URL") or None
    sb_key = os.environ.get("AAPDA_SUPABASE_SERVICE_ROLE_KEY") or None
    if sb_url and "supabase.com/dashboard" in sb_url:
        warnings.append("AAPDA_SUPABASE_URL points to the dashboard. Use https://<project-ref>.supabase.co instead.")
        sb_url = None
    if sb_url and sb_key and sb_key.startswith("replace_"):
        sb_key = None
    if sb_url and not sb_key:
        warnings.append("Supabase URL set without a service key; using local SQLite blob storage.")
        sb_url = None

    gkey = os.environ.get("GEMINI_API_KEY") or None
    if gkey and gkey.startswith("replace_"):
        gkey = None

    return Settings(
        secret_key=secret,
        cookie_secure=_bool("AAPDA_COOKIE_SECURE", False),
        db_path=os.environ.get("AAPDA_VAULT_DB", str(ROOT / "data" / "vault.sqlite3")),
        fernet_key=fernet,
        supabase_url=sb_url.rstrip("/") if sb_url else None,
        supabase_key=sb_key,
        supabase_bucket=os.environ.get("AAPDA_SUPABASE_BUCKET", "safelife-vault"),
        gemini_key=gkey,
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        warnings=warnings,
    )
