"""Conservative shared BLS unregistered admission before each outbound attempt.

A rolling 24-hour ceiling avoids assuming a provider reset timezone. Reservations
are retained even on timeout/crash; they are local admission, never HTTP evidence.
All stocks, processes and unregistered BLS routes share this one database scope.
"""
from __future__ import annotations

import math
import sqlite3
import time
import uuid

from storage.sqlite_resource import ThreadLocalSqliteResource

LIMIT = 25
WINDOW_SECONDS = 86400


class BlsAdmissionBlocked(RuntimeError):
    def __init__(self, reason, retry_after_seconds=60):
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"BLS local admission blocked: {reason}")


def _path():
    import config
    return config.TASK_DB_PATH


def _schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS bls_unregistered_attempts (
        reservation_id TEXT PRIMARY KEY,
        reserved_at REAL NOT NULL CHECK (reserved_at > 0)
    )""")
    conn.execute("""CREATE INDEX IF NOT EXISTS bls_unregistered_attempts_time
        ON bls_unregistered_attempts(reserved_at)""")
    conn.commit()


_RESOURCE = ThreadLocalSqliteResource(
    _path, init_schema=_schema, busy_timeout_ms=3000, timeout_seconds=3,
)


class BlsAdmissionStore:
    def __init__(self, *, path_getter=None, clock=None):
        self._clock = clock or time.time
        self._resource = _RESOURCE if path_getter is None else ThreadLocalSqliteResource(
            path_getter, init_schema=_schema, busy_timeout_ms=3000, timeout_seconds=3,
        )

    def close_current_thread(self):
        self._resource.close_current_thread()

    def reserve(self):
        """Atomically consume one attempt; no refund/reset or provider send here."""
        conn = None
        try:
            conn = self._resource.connect()
            conn.execute("BEGIN IMMEDIATE")
            now = self._clock()
            if type(now) not in (int, float) or not math.isfinite(now) or now <= 0:
                raise BlsAdmissionBlocked("invalid_clock")
            latest = conn.execute(
                "SELECT MAX(reserved_at) FROM bls_unregistered_attempts"
            ).fetchone()[0]
            if latest is not None and (
                type(latest) not in (int, float) or not math.isfinite(latest) or latest > now
            ):
                raise BlsAdmissionBlocked("clock_rollback")
            count, oldest = conn.execute(
                "SELECT COUNT(*), MIN(reserved_at) FROM bls_unregistered_attempts WHERE reserved_at > ?",
                (now - WINDOW_SECONDS,),
            ).fetchone()
            if count >= LIMIT:
                raise BlsAdmissionBlocked("rolling_24h_limit", max(1, oldest + WINDOW_SECONDS - now))
            reservation_id = uuid.uuid4().hex
            conn.execute(
                "INSERT INTO bls_unregistered_attempts VALUES (?, ?)", (reservation_id, now),
            )
            conn.commit()
            return {"reserved": True, "reservation_id": reservation_id,
                    "reserved_at": now, "window_seconds": WINDOW_SECONDS,
                    "limit": LIMIT, "http_request_sent": False,
                    "basis": "local_pre_send_admission_not_provider_usage"}
        except BlsAdmissionBlocked:
            if conn is not None:
                conn.rollback()
            raise
        except (sqlite3.Error, OSError):
            if conn is not None:
                conn.rollback()
            raise BlsAdmissionBlocked("admission_store_unavailable") from None
