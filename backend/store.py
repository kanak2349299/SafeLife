"""
Persistence for SafeLife.

What the server stores, and what it never sees:
  * Accounts: email, scrypt password hash, optional TOTP secret (wrapped at rest).
  * Vault items: the encrypted metadata and the encrypted file, both produced in the
    browser. Document names, categories, and expiry dates are inside the ciphertext.
  * Checklist: per-document status (uploaded / pending / not_applicable). This reveals
    which document TYPES a user marked, not their contents.
  * Family contacts, SOS and check-in events, and an audit log of account actions.
"""
from __future__ import annotations

import base64
import hashlib
import re
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from .security import Wrapper

SESSION_TTL = 7 * 24 * 3600
MAX_FAILS = 8
FAIL_WINDOW = 15 * 60
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATUSES = {"uploaded", "pending", "not_applicable"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    pw_hash TEXT NOT NULL,
    full_name TEXT DEFAULT '',
    state TEXT DEFAULT '',
    city TEXT DEFAULT '',
    lat REAL,
    lon REAL,
    blood_group TEXT DEFAULT '',
    profile_json TEXT DEFAULT '{}',
    mfa_secret TEXT,
    mfa_enabled INTEGER DEFAULT 0,
    vault_salt TEXT,
    vault_check TEXT,
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vault_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    meta TEXT NOT NULL,
    blob_ref TEXT NOT NULL,
    size INTEGER NOT NULL,
    created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_items_user ON vault_items(user_id);
CREATE TABLE IF NOT EXISTS checklist (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    doc_key TEXT NOT NULL,
    status TEXT NOT NULL,
    updated REAL NOT NULL,
    PRIMARY KEY (user_id, doc_key)
);
CREATE TABLE IF NOT EXISTS family (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    relation TEXT DEFAULT '',
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    detail TEXT DEFAULT '',
    created REAL NOT NULL
);
"""


class AuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.status = status


class NotFound(Exception):
    pass


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, path: str | Path, wrapper: Wrapper | None = None):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        self.wrap = wrapper or Wrapper(None)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._fails: dict[str, list[float]] = {}

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, args: tuple = ()):
        cur = self._db.execute(sql, args)
        self._db.commit()
        return cur

    def _one(self, sql: str, args: tuple = ()):
        return self._db.execute(sql, args).fetchone()

    def _all(self, sql: str, args: tuple = ()):
        return self._db.execute(sql, args).fetchall()

    # ------------------------------------------------------------ accounts
    def create_user(self, email: str, password: str) -> int:
        email = (email or "").strip().lower()
        if not EMAIL_RE.match(email):
            raise ValueError("Please enter a valid email address.")
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters.")
        if len(password) > 256:
            raise ValueError("Password is too long.")
        with self._lock:
            try:
                cur = self._db.execute(
                    "INSERT INTO users (email, pw_hash, created) VALUES (?, ?, ?)",
                    (email, generate_password_hash(password), time.time()),
                )
            except sqlite3.IntegrityError:
                raise ValueError("An account with this email already exists.")
            self._db.commit()
            return cur.lastrowid

    def authenticate(self, email: str, password: str) -> dict:
        """Check the password. Returns the user row as a dict. MFA is checked by the caller."""
        email = (email or "").strip().lower()
        now = time.time()
        with self._lock:
            recent = [t for t in self._fails.get(email, []) if now - t < FAIL_WINDOW]
            self._fails[email] = recent
            if len(recent) >= MAX_FAILS:
                raise AuthError("Too many failed attempts. Try again in 15 minutes.", 429)
            row = self._one("SELECT * FROM users WHERE email = ?", (email,))
            ok = row is not None and check_password_hash(row["pw_hash"], password or "")
            if not ok:
                self._fails[email].append(now)
                raise AuthError("Invalid email or password.")
            self._fails.pop(email, None)
            return dict(row)

    def user(self, user_id: int) -> dict | None:
        row = self._one("SELECT * FROM users WHERE id = ?", (user_id,))
        return dict(row) if row else None

    def update_profile(self, user_id: int, **fields) -> None:
        allowed = {"full_name", "state", "city", "lat", "lon", "blood_group", "profile_json"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"unknown profile fields: {', '.join(sorted(bad))}")
        if not fields:
            return
        cols = ", ".join(f"{k} = ?" for k in fields)
        self._exec(f"UPDATE users SET {cols} WHERE id = ?", (*fields.values(), user_id))

    # ----------------------------------------------------------------- MFA
    def set_mfa_secret(self, user_id: int, secret: str) -> None:
        self._exec("UPDATE users SET mfa_secret = ?, mfa_enabled = 0 WHERE id = ?",
                   (self.wrap.wrap(secret), user_id))

    def mfa_secret(self, user_id: int) -> str | None:
        row = self._one("SELECT mfa_secret FROM users WHERE id = ?", (user_id,))
        return self.wrap.unwrap(row["mfa_secret"]) if row and row["mfa_secret"] else None

    def enable_mfa(self, user_id: int) -> None:
        self._exec("UPDATE users SET mfa_enabled = 1 WHERE id = ?", (user_id,))

    def disable_mfa(self, user_id: int) -> None:
        self._exec("UPDATE users SET mfa_enabled = 0, mfa_secret = NULL WHERE id = ?", (user_id,))

    def delete_account(self, user_id: int) -> None:
        self._exec("DELETE FROM users WHERE id = ?", (user_id,))

    # ------------------------------------------------------------ sessions
    def create_session(self, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        self._exec("INSERT INTO sessions (token_hash, user_id, expires) VALUES (?, ?, ?)",
                   (_hash_token(token), user_id, time.time() + SESSION_TTL))
        return token

    def user_for_token(self, token: str) -> int | None:
        if not token:
            return None
        row = self._one("SELECT user_id, expires FROM sessions WHERE token_hash = ?", (_hash_token(token),))
        if row is None or row["expires"] < time.time():
            return None
        return row["user_id"]

    def delete_session(self, token: str) -> None:
        self._exec("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))

    def delete_all_sessions(self, user_id: int) -> None:
        self._exec("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    # --------------------------------------------------------- vault setup
    def vault_setup(self, user_id: int) -> dict:
        row = self._one("SELECT vault_salt, vault_check FROM users WHERE id = ?", (user_id,))
        if row is None:
            raise AuthError("Account not found.")
        salt = row["vault_salt"]
        if salt is None:
            salt = base64.b64encode(secrets.token_bytes(16)).decode()
            self._exec("UPDATE users SET vault_salt = ? WHERE id = ?", (salt, user_id))
        return {"salt": salt, "check": row["vault_check"]}

    def set_vault_check(self, user_id: int, check_blob: str) -> None:
        if not isinstance(check_blob, str) or not check_blob or len(check_blob) > 1024:
            raise ValueError("Invalid key-check value.")
        row = self._one("SELECT vault_check FROM users WHERE id = ?", (user_id,))
        if row["vault_check"] is not None:
            raise ValueError("Vault is already set up.")
        self._exec("UPDATE users SET vault_check = ? WHERE id = ?", (check_blob, user_id))

    # ----------------------------------------------------------- vault items
    def list_items(self, user_id: int) -> list[dict]:
        rows = self._all("SELECT id, meta, size, created FROM vault_items WHERE user_id = ? ORDER BY created DESC",
                         (user_id,))
        return [{"id": r["id"], "meta": self.wrap.unwrap(r["meta"]), "size": r["size"], "created": r["created"]}
                for r in rows]

    def add_item(self, user_id: int, meta: str, blob_ref: str, size: int) -> int:
        if not isinstance(meta, str) or not meta or len(meta) > 4096:
            raise ValueError("Invalid item metadata.")
        cur = self._exec(
            "INSERT INTO vault_items (user_id, meta, blob_ref, size, created) VALUES (?, ?, ?, ?, ?)",
            (user_id, self.wrap.wrap(meta), blob_ref, size, time.time()))
        return cur.lastrowid

    def get_item(self, user_id: int, item_id: int) -> dict | None:
        row = self._one("SELECT id, meta, blob_ref, size, created FROM vault_items WHERE id = ? AND user_id = ?",
                        (item_id, user_id))
        if row is None:
            return None
        d = dict(row)
        d["meta"] = self.wrap.unwrap(d["meta"])
        return d

    def delete_item(self, user_id: int, item_id: int) -> str | None:
        """Delete the row and return its blob reference so the caller can purge the blob."""
        row = self._one("SELECT blob_ref FROM vault_items WHERE id = ? AND user_id = ?", (item_id, user_id))
        if row is None:
            return None
        self._exec("DELETE FROM vault_items WHERE id = ? AND user_id = ?", (item_id, user_id))
        return row["blob_ref"]

    def delete_everything(self, user_id: int) -> list[str]:
        """Permanent account-wide wipe. Returns blob refs to purge."""
        refs = [r["blob_ref"] for r in self._all("SELECT blob_ref FROM vault_items WHERE user_id = ?", (user_id,))]
        self._exec("DELETE FROM vault_items WHERE user_id = ?", (user_id,))
        self._exec("DELETE FROM checklist WHERE user_id = ?", (user_id,))
        self._exec("DELETE FROM family WHERE user_id = ?", (user_id,))
        self._exec("DELETE FROM events WHERE user_id = ?", (user_id,))
        self._exec("UPDATE users SET vault_salt = NULL, vault_check = NULL WHERE id = ?", (user_id,))
        return refs

    # ------------------------------------------------------------- checklist
    def checklist(self, user_id: int) -> dict[str, dict]:
        return {r["doc_key"]: {"status": r["status"], "updated": r["updated"]}
                for r in self._all("SELECT doc_key, status, updated FROM checklist WHERE user_id = ?", (user_id,))}

    def set_checklist(self, user_id: int, doc_key: str, status: str) -> None:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        if not re.fullmatch(r"[a-z_:]{2,60}", doc_key or ""):
            raise ValueError("invalid item key")
        self._exec(
            "INSERT INTO checklist (user_id, doc_key, status, updated) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, doc_key) DO UPDATE SET status = excluded.status, updated = excluded.updated",
            (user_id, doc_key, status, time.time()))

    # --------------------------------------------------------------- family
    def list_family(self, user_id: int) -> list[dict]:
        return [dict(r) for r in self._all(
            "SELECT id, name, relation, phone, email, created FROM family WHERE user_id = ? ORDER BY created", (user_id,))]

    def add_family(self, user_id: int, name: str, relation: str, phone: str, email: str) -> int:
        if not name or len(name) > 100:
            raise ValueError("Name is required (max 100 characters).")
        if phone and not re.fullmatch(r"\+?[0-9 ()-]{7,20}", phone):
            raise ValueError("Phone number looks invalid.")
        if email and not EMAIL_RE.match(email):
            raise ValueError("Email looks invalid.")
        cur = self._exec(
            "INSERT INTO family (user_id, name, relation, phone, email, created) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name.strip(), relation.strip()[:50], phone.strip(), email.strip(), time.time()))
        return cur.lastrowid

    def delete_family(self, user_id: int, member_id: int) -> bool:
        cur = self._exec("DELETE FROM family WHERE id = ? AND user_id = ?", (member_id, user_id))
        return cur.rowcount > 0

    # --------------------------------------------------------------- events
    def log_event(self, user_id: int, kind: str, detail: str = "") -> None:
        self._exec("INSERT INTO events (user_id, kind, detail, created) VALUES (?, ?, ?, ?)",
                   (user_id, kind, detail[:300], time.time()))

    def list_events(self, user_id: int, limit: int = 50) -> list[dict]:
        return [dict(r) for r in self._all(
            "SELECT kind, detail, created FROM events WHERE user_id = ? ORDER BY created DESC LIMIT ?",
            (user_id, limit))]
