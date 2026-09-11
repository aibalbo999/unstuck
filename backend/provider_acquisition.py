"""Read-only acquisition evidence for the source panel.

Legacy SLA availability remains a separate compatibility metric. This projection
counts provider observations, not HTTP requests, reports or unique data records.
It never treats aggregate audit rows, caches or tolerated empty results as fresh
acquisitions, and does not rewrite historical telemetry.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

COUNTERS = (
    "fetched_count", "empty_count", "failed_count", "degraded_count",
    "fresh_cache_count", "empty_cache_count", "stale_cache_count",
    "unknown_count", "not_configured_count", "aggregate_count",
)
WINDOW_SECONDS = {"last_1h": 3600, "last_24h": 86400, "last_7d": 604800}
# These are workflow summaries, not independently observed provider requests.
AGGREGATE_PROVIDERS = {
    "News/Search providers", "Search providers", "Recent catalysts providers",
    "Peer discovery providers", "Global market context", "International news context",
    "Alternative data providers", "Social Forum Sentiment", "Taiwan Open Data",
    "Free news waterfall",
}
BASE_AGGREGATE_MESSAGES = {
    "本次重新抓取完成。", "市場價格或估值資料缺漏", "年度財報資料缺漏",
    "非台股或 FinMind 月營收暫無可用資料", "近期催化劑暫無可用資料",
    "非台股或法人籌碼暫無可用資料", "同業指標暫無可用資料",
    "P/E 河流圖資料暫無可用資料", "同業搜尋暫無可用資料",
}


def observation_kind(row: dict) -> str:
    provider, status = row["provider"], row["status"]
    count, message = row["record_count"], row["message"]
    if (provider in AGGREGATE_PROVIDERS or message in BASE_AGGREGATE_MESSAGES
            or message.startswith("optional 外部來源")):
        return "aggregate_count"
    if status == "not_configured":
        return "not_configured_count"
    if status in {"error", "unavailable"}:
        return "failed_count"
    if provider == "cache" or status == "skipped_fresh_cache":
        if count <= 0:
            return "empty_cache_count"
        if status == "skipped_fresh_cache":
            return "fresh_cache_count"
        if status == "degraded_enrichment":
            return "stale_cache_count"
        return "unknown_count"
    if status in {"success", "degraded_enrichment"}:
        if count <= 0:
            return "empty_count"
        return "fetched_count" if status == "success" else "degraded_count"
    return "unknown_count"


def _empty_counts() -> dict:
    return {key: 0 for key in COUNTERS}


def _finish_counts(row: dict) -> dict:
    row["fetch_attempts"] = sum(row[key] for key in (
        "fetched_count", "empty_count", "degraded_count", "failed_count", "unknown_count",
    )) - row.pop("cache_nonfetch_count", 0)
    row["nonempty_rate"] = (
        row["fetched_count"] / row["fetch_attempts"] if row["fetch_attempts"] else None
    )
    row["observations"] = sum(row[key] for key in COUNTERS if key != "aggregate_count")
    return row


def project_acquisition_events(events, *, window: str, now: float) -> dict:
    """Project ordered audit rows; keep repeated actual attempts and all failures."""
    groups = {}
    first_at = None
    start = now - WINDOW_SECONDS[window] if window in WINDOW_SECONDS else None
    for raw in events:
        row = dict(raw)
        at = float(row["created_at"])
        if at > now or (start is not None and at < start):
            continue
        first_at = at if first_at is None else min(first_at, at)
        source = row["source"]
        group = groups.setdefault(source, dict(source=source, providers={}, **_empty_counts()))
        kind = observation_kind(row)
        group[kind] += 1
        if kind == "aggregate_count":
            continue
        provider = group["providers"].setdefault(row["provider"], dict(
            provider=row["provider"], last_at=None, last_kind=None, **_empty_counts(),
        ))
        provider[kind] += 1
        if row["provider"] == "cache" and kind in {"failed_count", "unknown_count"}:
            for target in (group, provider):
                target["cache_nonfetch_count"] = target.get("cache_nonfetch_count", 0) + 1
        if provider["last_at"] is None or at >= provider["last_at"]:
            provider["last_at"], provider["last_kind"] = at, kind
    sources = []
    for group in groups.values():
        group["providers"] = sorted(
            (_finish_counts(p) for p in group["providers"].values()),
            key=lambda p: (-p["failed_count"], -p["unknown_count"], -p["empty_count"], p["provider"]),
        )
        sources.append(_finish_counts(group))
    return {
        "schema_version": "provider-acquisition.v1", "available": True,
        "selected_window": window, "generated_at": now, "window_start": start,
        "first_observed_at": first_at, "sources": sorted(sources, key=lambda s: s["source"]),
        "basis": "retained_provider_observations",
    }


def get_provider_acquisition_summary(window: str = "last_24h") -> dict:
    # Resolve dynamically so the canonical runtime path and isolated tests agree.
    import provider_sla

    window = str(window or "all").strip().lower()
    window = window if window in {*WINDOW_SECONDS, "all"} else "all"
    now = time.time()
    start = now - WINDOW_SECONDS[window] if window in WINDOW_SECONDS else 0
    try:
        uri = Path(provider_sla.TASK_DB_PATH).resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            events = conn.execute(
                "SELECT source, provider, status, record_count, message, created_at "
                "FROM provider_sla_events WHERE created_at >= ? AND created_at <= ? "
                "ORDER BY created_at, id",
                (start, now),
            )
            return project_acquisition_events(events, window=window, now=now)
    except sqlite3.Error:
        return {
            "schema_version": "provider-acquisition.v1", "available": False,
            "selected_window": window, "generated_at": now, "sources": [],
            "message": "來源觀測紀錄暫時無法讀取，無法判定資料取得情況。",
        }
