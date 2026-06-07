"""Error payload builder for yfinance core fetch."""

from __future__ import annotations

from datetime import datetime

from data_trust import AUDIT_STATUS_ERROR, build_data_trust


def build_fetch_error_payload(
    ticker: str,
    exc: Exception,
    *,
    fetch_started_epoch: float,
    finished_at_epoch: float,
    append_source_fetch_audit,
) -> dict:
    failed = {
        "ticker": ticker,
        "company_name": ticker,
        "sector": "N/A",
        "industry": "N/A",
        "error": str(exc),
        "fetch_date": datetime.now().strftime("%Y年%m月%d日"),
    }
    append_source_fetch_audit(
        failed,
        "market_data",
        "market_data_provider",
        AUDIT_STATUS_ERROR,
        started_at_epoch=fetch_started_epoch,
        finished_at_epoch=finished_at_epoch,
        record_count=0,
        cache_hit=False,
        stale=True,
        error_kind=exc.__class__.__name__,
        message=str(exc)[:240],
    )
    failed["data_trust"] = build_data_trust(failed)
    return failed
