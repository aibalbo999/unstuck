"""Idempotent settlement of new, explicitly tracked local reservations."""

from __future__ import annotations

import sqlite3


def init_reservation_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS llm_budget_reservations (
        reservation_id TEXT PRIMARY KEY,
        quota_day TEXT NOT NULL, model_id TEXT NOT NULL, key_hash TEXT NOT NULL,
        reserved_units INTEGER NOT NULL, accounted_units INTEGER,
        created_at REAL NOT NULL, settled_at REAL
    )""")


def record_reservation(conn, receipt, day, model, key_hash, units, now):
    conn.execute(
        "INSERT INTO llm_budget_reservations VALUES (?, ?, ?, ?, ?, NULL, ?, NULL)",
        (receipt, day, model, key_hash, units, now),
    )


def settle_reservation(conn, receipt, accounted_units, now):
    if isinstance(accounted_units, bool) or not isinstance(accounted_units, int) or accounted_units < 0:
        raise ValueError("Invalid accounted request count")
    with conn:
        row = conn.execute(
            "SELECT * FROM llm_budget_reservations WHERE reservation_id=?", (receipt,),
        ).fetchone()
        if row is None or row['accounted_units'] is not None:
            return 0
        reserved = row['reserved_units']
        if accounted_units > reserved:
            raise ValueError("Accounted requests exceed the reservation")
        released = reserved - accounted_units
        # Claim this receipt once, even when independent connections settle it.
        claim = conn.execute(
            "UPDATE llm_budget_reservations SET accounted_units=?, settled_at=? "
            "WHERE reservation_id=? AND accounted_units IS NULL",
            (accounted_units, now, receipt),
        )
        if claim.rowcount != 1:
            return 0
        updated = conn.execute(
            "UPDATE llm_daily_budgets SET used=used-?, updated_at=? "
            "WHERE quota_day=? AND model_id=? AND key_hash=? AND used>=?",
            (released, now, row['quota_day'], row['model_id'], row['key_hash'], released),
        )
        if updated.rowcount != 1:
            # Roll back the receipt claim too; never manufacture budget room.
            raise sqlite3.IntegrityError("Reservation budget is unavailable")
    return released
