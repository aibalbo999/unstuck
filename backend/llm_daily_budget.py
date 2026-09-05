"""Durable local request budgets, not provider billing or quota entitlements."""

from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from shared_runtime_guard_utils import guard_hash, seconds_until_next_pacific_midnight
from storage.sqlite_resource import ThreadLocalSqliteResource


PACIFIC = ZoneInfo("America/Los_Angeles")


class AllKeysRpdDisabledError(RuntimeError):
    """Every key is disabled for this model until the provider's daily reset."""

    def __init__(self, model: str, retry_wait_seconds: float):
        super().__init__(f"所有 API key 對模型 {model} 的每日額度已暫停，約 {retry_wait_seconds:.1f} 秒後恢復。")
        self.model = model
        self.retry_wait_seconds = retry_wait_seconds


class DailyBudgetBlockedError(RuntimeError):
    """A local preflight rejection; no provider request has been sent."""

    def __init__(self, model: str, retry_wait_seconds: float, reason: str):
        self.model = model
        self.retry_wait_seconds = retry_wait_seconds
        self.reason = reason
        super().__init__(f"Local daily budget blocked for {model}: {reason}")


def _db_path():
    # Resolve on demand so worker, API and isolated tests share canonical paths.
    import config
    return config.TASK_DB_PATH


def _init_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS llm_daily_budgets (
        quota_day TEXT NOT NULL, model_id TEXT NOT NULL, key_hash TEXT NOT NULL,
        used INTEGER NOT NULL DEFAULT 0, seeded INTEGER NOT NULL DEFAULT 0,
        updated_at REAL NOT NULL,
        PRIMARY KEY (quota_day, model_id, key_hash)
    )""")


_RESOURCE = ThreadLocalSqliteResource(
    _db_path, init_schema=_init_schema, row_factory=sqlite3.Row, busy_timeout_ms=3000,
)


class DailyBudgetStore:
    def __init__(self, *, path_getter=None, clock=None):
        self._clock = clock or time.time
        self._resource = _RESOURCE if path_getter is None else ThreadLocalSqliteResource(
            path_getter, init_schema=_init_schema,
            row_factory=sqlite3.Row, busy_timeout_ms=3000,
        )

    def close_current_thread(self):
        self._resource.close_current_thread()

    def _now(self):
        return datetime.fromtimestamp(self._clock(), PACIFIC)

    def reset_wait(self):
        return seconds_until_next_pacific_midnight(self._now())

    def _seed_counts(self, conn, keys, model, now):
        counts = dict.fromkeys(keys, 0)
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='api_usage_events'").fetchone():
            return counts
        midnight = datetime.combine(now.date(), dt_time(), tzinfo=PACIFIC).timestamp()
        rows = conn.execute(
            """SELECT units, metadata_json FROM api_usage_events
               WHERE model_id=? AND operation IN (
                   'llm_provider_request', 'diagnostic_model_smoke', 'diagnostic_quota_probe',
                   'diagnostic_mode_canary', 'diagnostic_analysis_canary', 'diagnostic_summary_canary'
               ) AND created_at>=? AND created_at<=?""",
            (model, midnight, now.timestamp()),
        )
        unknown = 0
        for row in rows:
            try:
                metadata = json.loads(row["metadata_json"])
                slot = metadata.get("key_slot") if isinstance(metadata, dict) else None
            except (ValueError, TypeError):
                slot = None
            units = max(int(row["units"] or 0), 0)
            if isinstance(slot, int) and not isinstance(slot, bool) and 1 <= slot <= len(keys):
                counts[keys[slot - 1]] += units
            else:
                unknown += units
        # Legacy events without slots cannot be attributed. Reserve a conservative
        # equal share rather than silently treating today's observed demand as zero.
        for key in counts:
            counts[key] += math.ceil(unknown / len(keys))
        return counts

    def _rows(self, conn, keys, model, now):
        day = now.date().isoformat()
        rows = {row["key_hash"]: row for row in conn.execute(
            "SELECT * FROM llm_daily_budgets WHERE quota_day=? AND model_id=?", (day, model)
        )}
        missing = [key for key in keys if guard_hash(key) not in rows]
        if missing:
            seeds = self._seed_counts(conn, keys, model, now)
            with conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO llm_daily_budgets VALUES (?, ?, ?, ?, ?, ?)",
                    [(day, model, guard_hash(key), seeds[key], seeds[key], now.timestamp()) for key in missing],
                )
            rows = {row["key_hash"]: row for row in conn.execute(
                "SELECT * FROM llm_daily_budgets WHERE quota_day=? AND model_id=?", (day, model)
            )}
        return rows

    def remaining(self, keys: list[str], model: str, limit: int) -> dict[str, int]:
        try:
            rows = self._rows(self._resource.connect(), keys, model, self._now())
            return {key: max(limit - rows[guard_hash(key)]["used"], 0) for key in keys}
        except (sqlite3.Error, OSError):
            raise DailyBudgetBlockedError(model, 60.0, "budget_store_unavailable") from None

    def reserve(self, key: str, model: str, limit: int, keys: list[str], *, request_units: int = 1) -> bool:
        request_units = max(1, int(request_units))
        try:
            conn = self._resource.connect()
            now = self._now()
            self._rows(conn, keys, model, now)
            # Conditional UPDATE is atomic across independent worker/API processes.
            with conn:
                result = conn.execute(
                    """UPDATE llm_daily_budgets SET used=used+?, updated_at=?
                       WHERE quota_day=? AND model_id=? AND key_hash=? AND used<=?""",
                    (request_units, now.timestamp(), now.date().isoformat(), model, guard_hash(key), limit - request_units),
                )
            return result.rowcount == 1
        except (sqlite3.Error, OSError):
            raise DailyBudgetBlockedError(model, 60.0, "budget_store_unavailable") from None

    def summary(self, keys: list[str], limits: dict[str, int]) -> dict:
        models = {}
        for model, limit in limits.items():
            if not isinstance(model, str) or model == "*" or isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
                continue
            remaining = self.remaining(keys, model, limit)
            models[model] = {
                "per_project_budget": limit, "total_budget": limit * len(keys),
                "remaining": sum(remaining.values()),
                "available_projects": sum(value > 0 for value in remaining.values()),
            }
        return {"available": True, "quota_day": self._now().date().isoformat(),
                "timezone": "America/Los_Angeles", "basis": "local_reservations_plus_observed_request_seed",
                "models": models}
