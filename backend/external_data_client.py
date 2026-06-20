"""Waterfall client for free external news and official financial fallbacks."""

from __future__ import annotations

from datetime import date
import logging
import math
import re
from typing import Any, Callable

from news_fetchers import fetch_duckduckgo_news, fetch_google_news_rss, fetch_ptt_stock_sentiment
from official_financials import fetch_mops_balance_sheet


LOGGER = logging.getLogger(__name__)
NewsFetcher = Callable[..., list[dict[str, str]]]
FinancialFetcher = Callable[[str], dict[str, Any]]
MopsFetcher = Callable[..., dict[str, Any] | None]


class ExternalDataClient:
    """Coordinate free external data sources with observable fallbacks."""

    def __init__(
        self,
        *,
        google_news: NewsFetcher = fetch_google_news_rss,
        ddg_news: NewsFetcher = fetch_duckduckgo_news,
        ptt_news: NewsFetcher = fetch_ptt_stock_sentiment,
        financial_fetcher: FinancialFetcher | None = None,
        mops_fetcher: MopsFetcher = fetch_mops_balance_sheet,
    ) -> None:
        self.google_news = google_news
        self.ddg_news = ddg_news
        self.ptt_news = ptt_news
        self.financial_fetcher = financial_fetcher or (lambda _ticker: {})
        self.mops_fetcher = mops_fetcher
        self.last_news_audit: list[dict[str, Any]] = []

    def get_news(self, query: str, *, ticker: str | None = None, limit: int = 10) -> list[dict[str, str]]:
        """Fetch news through Google RSS, DuckDuckGo, then PTT for Taiwan tickers."""
        self.last_news_audit = []
        google = self._safe_news("Google News RSS", self.google_news, query, limit)
        if google:
            return _dedupe_news(google, limit)
        self._log_fallback("Google News RSS", "DuckDuckGo News")

        ddg = self._safe_news("DuckDuckGo News", self.ddg_news, query, limit)
        if ddg:
            return _dedupe_news(ddg, limit)

        if not ticker or not _is_taiwan_ticker(ticker):
            return []
        self._log_fallback("DuckDuckGo News", "PTT Stock")
        return _dedupe_news(self._safe_news("PTT Stock", self.ptt_news, ticker, limit), limit)

    def get_financial_data(
        self,
        ticker: str,
        *,
        year: int | None = None,
        season: int | None = None,
    ) -> dict[str, Any]:
        """Fetch primary financial data and reconcile invalid debt with MOPS."""
        payload = dict(self.financial_fetcher(ticker) or {})
        if not isinstance(payload.get("field_provenance"), dict):
            payload["field_provenance"] = {}
        if not isinstance(payload.get("audit_events"), list):
            payload["audit_events"] = []
        if not _needs_official_debt(payload.get("total_debt_raw")):
            payload["official_reconciliation_status"] = "not_required"
            return payload

        payload["audit_events"].append({
            "event": "invalid_total_debt_mops_fallback",
            "field": "total_debt_raw",
            "provider": "MOPS",
        })
        if not _is_taiwan_ticker(ticker):
            payload["official_reconciliation_status"] = "not_applicable"
            payload["field_provenance"]["total_debt_raw"] = "unresolved"
            payload["circuit_breaker_signal"] = {"status": "open", "field": "total_debt_raw"}
            return payload

        year, season = _latest_closed_quarter(year, season)
        mops_payload = self._safe_mops(ticker, year, season)
        if not mops_payload or mops_payload.get("total_liabilities") is None:
            payload["official_reconciliation_status"] = "unresolved"
            payload["field_provenance"]["total_debt_raw"] = "unresolved"
            payload["circuit_breaker_signal"] = {"status": "open", "field": "total_debt_raw"}
            return payload

        payload["total_debt_raw"] = mops_payload["total_liabilities"]
        payload["mops_balance_sheet"] = mops_payload
        payload["official_reconciliation_status"] = "resolved"
        payload["field_provenance"]["total_debt_raw"] = "MOPS"
        payload["circuit_breaker_signal"] = {"status": "closed", "field": "total_debt_raw"}
        return payload

    def _safe_news(self, provider: str, fetcher: NewsFetcher, query: str, limit: int) -> list[dict[str, str]]:
        try:
            records = list(fetcher(query, limit=limit) or [])
            self.last_news_audit.append({
                "source": "recent_catalysts",
                "provider": provider,
                "status": "success" if records else "unavailable",
                "record_count": len(records),
            })
            return records
        except Exception as exc:
            LOGGER.warning("%s news fetch failed [%s]", provider, exc.__class__.__name__)
            self.last_news_audit.append({
                "source": "recent_catalysts",
                "provider": provider,
                "status": "error",
                "record_count": 0,
                "error_kind": exc.__class__.__name__,
            })
            return []

    def _safe_mops(self, ticker: str, year: int, season: int) -> dict[str, Any] | None:
        try:
            return self.mops_fetcher(ticker, year, season)
        except Exception as exc:
            LOGGER.warning("MOPS debt fallback failed [%s]", exc.__class__.__name__)
            return None

    def _log_fallback(self, source: str, next_source: str) -> None:
        LOGGER.warning("%s returned no records; falling back to %s", source, next_source)


def _dedupe_news(records: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        identity = str(record.get("link") or record.get("title") or "").casefold()
        if not identity or identity in seen:
            continue
        seen.add(identity)
        output.append(record)
        if len(output) >= max(1, int(limit or 10)):
            break
    return output


def _needs_official_debt(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return True
    return not math.isfinite(number) or number < 0


def _is_taiwan_ticker(value: Any) -> bool:
    text = str(value or "").strip()
    if "." in text:
        symbol, suffix = text.split(".", 1)
        return suffix.upper() in {"TW", "TWO"} and bool(re.fullmatch(r"\d{4,6}", symbol))
    return bool(re.search(r"\b\d{4,6}\b", text))


def _latest_closed_quarter(year: int | None, season: int | None) -> tuple[int, int]:
    try:
        year_int = int(year) if year is not None else None
        season_int = int(season) if season is not None else None
    except (TypeError, ValueError):
        year_int = None
        season_int = None
    if year_int is not None and season_int in {1, 2, 3, 4}:
        return year_int, season_int
    today = date.today()
    current_quarter = (today.month - 1) // 3 + 1
    closed_quarter = current_quarter - 1
    closed_year = today.year
    if closed_quarter == 0:
        closed_quarter = 4
        closed_year -= 1
    return closed_year, closed_quarter
