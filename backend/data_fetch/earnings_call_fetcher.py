"""Optional earnings-call transcript fetcher backed by FMP."""

from __future__ import annotations

from datetime import date
from typing import Any

from config import FMP_API_KEY, FMP_BASE_URL
from external_http_client import log_http_warning, sync_json_get


FMP_LEGACY_TRANSCRIPT_URL = "https://financialmodelingprep.com/api/v3/earning_call_transcript"
_sync_json_get = sync_json_get


def fetch_latest_earnings_call(ticker: str, *, max_chars: int = 12_000) -> dict:
    """Return the latest available transcript excerpt or an empty mapping."""
    if not FMP_API_KEY:
        return {}

    symbol = str(ticker or "").strip().upper()
    if not symbol:
        return {}
    candidates = [
        (f"{FMP_BASE_URL}/earning-call-transcript", {"symbol": symbol, "limit": 1, "apikey": FMP_API_KEY}),
        (f"{FMP_LEGACY_TRANSCRIPT_URL}/{symbol}", {"apikey": FMP_API_KEY}),
    ]
    for url, params in candidates:
        try:
            payload = _sync_json_get(url, params)
        except Exception as exc:
            log_http_warning("FMP", "earnings call transcript", exc)
            continue
        record = _latest_record(payload)
        if record:
            return _normalize_record(symbol, record, max_chars=max_chars)
    return {}


def _latest_record(payload: Any) -> dict:
    if isinstance(payload, dict):
        for key in ("data", "transcripts", "results"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break
    if not isinstance(payload, list):
        return {}
    rows = [row for row in payload if isinstance(row, dict) and str(row.get("content") or row.get("transcript") or "").strip()]
    return max(rows, key=lambda row: str(row.get("date") or ""), default={})


def _normalize_record(symbol: str, record: dict, *, max_chars: int) -> dict:
    content = str(record.get("content") or record.get("transcript") or "").strip()
    year = record.get("year")
    quarter = record.get("quarter")
    period = f"{year}Q{quarter}" if year and quarter else str(record.get("period") or "")
    return {
        "ticker": symbol,
        "date": str(record.get("date") or date.today().isoformat()),
        "period": period,
        "transcript_excerpt": content[:max(int(max_chars), 1)],
        "source": "FMP earnings call transcript",
        "source_url": str(record.get("url") or ""),
    }
