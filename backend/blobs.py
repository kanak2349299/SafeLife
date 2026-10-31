"""
Storage for encrypted vault file bodies.

The bytes stored here are already encrypted in the browser (AES-256-GCM).
Optional server-side Fernet wrapping adds a second layer.

Backends
  * SqliteBlobs: keeps the blob in a side table (default, works offline).
  * SupabaseBlobs: uploads to a PRIVATE Supabase Storage bucket through the REST API,
    authenticated with the service role key from the environment. The key never
    reaches the browser. Objects are never public: every download goes through
    this server after the user's session is checked.
"""
from __future__ import annotations

import secrets
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request

from .security import Wrapper


class BlobError(Exception):
    pass


class SqliteBlobs:
    kind = "sqlite"

    def __init__(self, db: sqlite3.Connection, lock: threading.Lock, wrapper: Wrapper):
        self._db, self._lock, self._w = db, lock, wrapper
        with self._lock:
            self._db.execute("CREATE TABLE IF NOT EXISTS blobs (ref TEXT PRIMARY KEY, data TEXT NOT NULL)")
            self._db.commit()

    def put(self, user_id: int, data: str) -> str:
        ref = "sq:" + secrets.token_urlsafe(18)
        with self._lock:
            self._db.execute("INSERT INTO blobs (ref, data) VALUES (?, ?)", (ref, self._w.wrap(data)))
            self._db.commit()
        return ref

    def get(self, ref: str) -> str:
        with self._lock:
            row = self._db.execute("SELECT data FROM blobs WHERE ref = ?", (ref,)).fetchone()
        if row is None:
            raise BlobError("blob missing")
        return self._w.unwrap(row[0])

    def delete(self, ref: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM blobs WHERE ref = ?", (ref,))
            self._db.commit()


class SupabaseBlobs:
    kind = "supabase"

    def __init__(self, base_url: str, service_key: str, bucket: str, wrapper: Wrapper, opener=None):
        self.base = base_url.rstrip("/")
        self.key = service_key
        self.bucket = bucket
        self._w = wrapper
        self._open = opener or urllib.request.urlopen

    def _req(self, method: str, path: str, body: bytes | None = None, headers: dict | None = None) -> bytes:
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=h)
        try:
            with self._open(req, timeout=20) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            raise BlobError(f"Supabase storage returned HTTP {exc.code}") from None
        except urllib.error.URLError:
            raise BlobError("Supabase storage is unreachable") from None

    def put(self, user_id: int, data: str) -> str:
        path = f"{user_id}/{secrets.token_urlsafe(18)}.bin"
        payload = self._w.wrap(data).encode()
        self._req("POST", f"/storage/v1/object/{self.bucket}/{urllib.parse.quote(path)}",
                  body=payload, headers={"Content-Type": "application/octet-stream", "x-upsert": "false"})
        return "sb:" + path

    def get(self, ref: str) -> str:
        if not ref.startswith("sb:"):
            raise BlobError("not a Supabase reference")
        path = ref[3:]
        raw = self._req("GET", f"/storage/v1/object/{self.bucket}/{urllib.parse.quote(path)}")
        return self._w.unwrap(raw.decode())

    def delete(self, ref: str) -> None:
        if not ref.startswith("sb:"):
            return
        self._req("DELETE", f"/storage/v1/object/{self.bucket}",
                  body=('{"prefixes":["%s"]}' % ref[3:]).encode(),
                  headers={"Content-Type": "application/json"})


def make_blobs(settings, db, lock, wrapper, opener=None):
    if settings.blob_backend == "supabase":
        return SupabaseBlobs(settings.supabase_url, settings.supabase_key, settings.supabase_bucket, wrapper, opener)
    return SqliteBlobs(db, lock, wrapper)
