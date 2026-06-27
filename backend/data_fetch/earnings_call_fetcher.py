"""Optional earnings-call data fetchers."""

from __future__ import annotations

import os
import time
from datetime import date
from typing import Any

from config import FMP_API_KEY, FMP_BASE_URL
from external_http_client import log_http_warning, sync_json_get


FMP_LEGACY_TRANSCRIPT_URL = "https://financialmodelingprep.com/api/v3/earning_call_transcript"
FREE_EARNINGS_CALL_PROVIDER_NAME = "MOPS investor conference"
FREE_EARNINGS_CALL_COVERAGE_NOTE = "MOPS/TWSE 免費來源提供法說會資訊、簡報或影音連結；未提供完整逐字稿。"
DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS = 6 * 60 * 60
FMP_TRANSCRIPT_RESTRICTED_STATUS_CODES = {401, 402, 403}
_sync_json_get = sync_json_get
_fmp_transcript_cooldown_until = 0.0


def fetch_free_earnings_call_context(ticker: str) -> dict:
    """Return free official investor-conference context for Taiwan tickers."""
    from official_financials import fetch_mops_investor_conference_events

    events = fetch_mops_investor_conference_events(ticker, limit=1)
    if not events:
        events = fetch_mops_investor_conference_events(ticker, year=date.today().year - 1, limit=1)
    if not events:
        return {}

    event = events[0]
    summary = str(event.get("summary") or "").strip() or FREE_EARNINGS_CALL_COVERAGE_NOTE
    return {
        "ticker": str(event.get("ticker") or ticker).strip().upper(),
        "date": str(event.get("date") or date.today().isoformat()),
        "period": str(event.get("date") or ""),
        "title": str(event.get("title") or "").strip(),
        "summary": summary,
        "transcript_excerpt": "",
        "transcript_available": False,
        "materials": list(event.get("materials") or []),
        "source": FREE_EARNINGS_CALL_PROVIDER_NAME,
        "source_url": str(event.get("source_url") or ""),
        "coverage_notes": [FREE_EARNINGS_CALL_COVERAGE_NOTE],
    }


def fetch_latest_earnings_call(ticker: str, *, max_chars: int = 12_000) -> dict:
    """Return the latest available transcript excerpt or an empty mapping."""
    if not FMP_API_KEY:
        return {}
    if _fmp_transcript_cooldown_active():
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
            if _is_restricted_fmp_response(exc):
                _mark_fmp_transcript_cooldown()
                break
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


def _now() -> float:
    return time.time()


def _restricted_cooldown_seconds() -> float:
    try:
        configured = os.getenv(
            "FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS",
            str(DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS),
        )
        return max(float(configured), 0.0)
    except ValueError:
        return float(DEFAULT_FMP_TRANSCRIPT_RESTRICTED_COOLDOWN_SECONDS)


def _fmp_transcript_cooldown_active() -> bool:
    return _now() < _fmp_transcript_cooldown_until


def _mark_fmp_transcript_cooldown() -> None:
    global _fmp_transcript_cooldown_until
    cooldown_seconds = _restricted_cooldown_seconds()
    if cooldown_seconds <= 0:
        return
    _fmp_transcript_cooldown_until = max(_fmp_transcript_cooldown_until, _now() + cooldown_seconds)


def clear_fmp_transcript_cooldown() -> None:
    global _fmp_transcript_cooldown_until
    _fmp_transcript_cooldown_until = 0.0


def _is_restricted_fmp_response(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    try:
        return int(status_code) in FMP_TRANSCRIPT_RESTRICTED_STATUS_CODES
    except (TypeError, ValueError):
        return False
