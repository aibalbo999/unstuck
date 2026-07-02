"""Cache write helpers for data-fetch payloads."""

from __future__ import annotations

import time as time_module
from datetime import datetime, timezone

from cache_store import set_cache_json
from config import FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS
from data_trust import build_data_trust

from .audit_helpers import _build_data_freshness, _build_source_freshness, _cache_timestamp_epoch


def _cache_financial_data(data: dict, original_ticker: str):
    if not data or "error" in data:
        return

    cacheable = dict(data)
    cacheable.pop("_cache_hit", None)
    resolved_ticker = cacheable.get("ticker", original_ticker)
    now_epoch = time_module.time()
    market_epoch = _cache_timestamp_epoch(cacheable) or now_epoch
    cacheable["cache_generated_at_epoch"] = now_epoch
    cacheable["cache_generated_at"] = datetime.fromtimestamp(now_epoch, timezone.utc).isoformat()
    cacheable["data_freshness"] = _build_data_freshness(
        str(resolved_ticker or original_ticker),
        market_epoch,
        cache_hit=False,
        now_epoch=now_epoch,
    )
    cacheable["source_freshness"] = _build_source_freshness(
        cacheable,
        str(resolved_ticker or original_ticker),
        cache_hit=False,
        now_epoch=now_epoch,
    )
    cacheable["data_trust"] = build_data_trust(cacheable)
    set_cache_json(f"financial_data:{original_ticker}", cacheable, FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS)
    if resolved_ticker != original_ticker:
        set_cache_json(f"financial_data:{resolved_ticker}", cacheable, FINANCIAL_DATA_PAYLOAD_CACHE_TTL_SECONDS)
