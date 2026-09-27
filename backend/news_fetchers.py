"""Free news and retail-sentiment fetchers with a shared record shape."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
import threading
import time
from typing import Any
from urllib.parse import quote_plus

import feedparser

from external_http_client import sync_get
from search_provider_runtime import cooldown_state, scope_key, remember_failure, record_observation
from news_record_utils import (
    MAX_INPUT_LENGTH,
    MAX_RESULTS,
    NewsRecord,
    clamp_limit as _clamp_limit,
    clean_input as _clean_input,
    clean_text as _clean_text,
    dedupe_records as _dedupe,
    news_record as _record,
)

try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - exercised only with older installations
    try:
        from duckduckgo_search import DDGS
    except ImportError:  # pragma: no cover - tested by replacing the resolved symbol
        DDGS = None  # type: ignore[assignment,misc]


LOGGER = logging.getLogger(__name__)
_DDGS_CLIENT_LOCK = threading.Lock()
_DDGS_CLIENT: Any = None
_DDGS_CLIENT_FACTORY: Any = None
TAIPEI_TZ = timezone(timedelta(hours=8))
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
PTT_STOCK_URL = "https://www.ptt.cc/bbs/Stock/index.html"
REQUEST_TIMEOUT_SECONDS = 8.0
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


def _current_taipei_year() -> int:
    return _current_taipei_datetime().year


def _current_taipei_datetime() -> datetime:
    return datetime.now(TAIPEI_TZ)


def _ptt_date_to_iso(value: Any) -> str:
    text = _clean_text(value)
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if not match:
        return ""
    try:
        now = _current_taipei_datetime()
        parsed = datetime(
            now.year,
            int(match.group(1)),
            int(match.group(2)),
            tzinfo=TAIPEI_TZ,
        )
    except ValueError:
        return ""
    if parsed > now + timedelta(days=1):
        parsed = parsed.replace(year=parsed.year - 1)
    return parsed.isoformat()


def _warn(provider: str, operation: str, exc: BaseException | None = None) -> None:
    error_kind = exc.__class__.__name__ if exc else "MissingDependency"
    LOGGER.warning("%s %s failed [%s]", provider, operation, error_kind)


def _duckduckgo_news_rows(query: str, max_results: int):
    global _DDGS_CLIENT, _DDGS_CLIENT_FACTORY
    if DDGS is None:
        return None
    with _DDGS_CLIENT_LOCK:
        if _DDGS_CLIENT is None or _DDGS_CLIENT_FACTORY is not DDGS:
            _DDGS_CLIENT = DDGS()
            _DDGS_CLIENT_FACTORY = DDGS
        return _DDGS_CLIENT.news(query=query, max_results=max_results)


def fetch_google_news_rss(query: str, limit: int = 10) -> list[NewsRecord]:
    """Fetch Google News RSS search results without requiring an API key."""
    cleaned_query = _clean_input(query)
    if not cleaned_query:
        return []
    bounded_limit = _clamp_limit(limit)
    url = (
        f"{GOOGLE_NEWS_RSS_URL}?q={quote_plus(cleaned_query)}"
        "&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    try:
        response = sync_get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
            provider="Google News RSS",
        )
        feed = feedparser.parse(response.content)
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
            raise ValueError("invalid RSS feed")
        records = []
        for entry in getattr(feed, "entries", []):
            publisher = getattr(entry, "source", {})
            publisher = publisher.get("title") if isinstance(publisher, dict) else None
            record = _record(
                title=getattr(entry, "title", ""),
                link=getattr(entry, "link", ""),
                published_date=getattr(entry, "published_parsed", None)
                or getattr(entry, "updated_parsed", None),
                source=publisher or "Google News RSS",
                summary=getattr(entry, "summary", ""),
            )
            if record:
                records.append(record)
        return _dedupe(records, bounded_limit)
    except Exception as exc:  # feedparser can surface provider-specific parser errors
        _warn("Google News RSS", "search", exc)
        return []


def fetch_duckduckgo_news(query: str, limit: int = 10) -> list[NewsRecord]:
    """Fetch DuckDuckGo news through the current or legacy Python package."""
    cleaned_query = _clean_input(query)
    if not cleaned_query:
        return []
    if DDGS is None:
        _warn("DuckDuckGo News", "dependency")
        return []
    bounded_limit = _clamp_limit(limit)
    try:
        rows = _duckduckgo_news_rows(cleaned_query, bounded_limit)
        records = []
        for row in rows or []:
            record = _record(
                title=row.get("title", ""),
                link=row.get("url", row.get("href", "")),
                published_date=row.get("date", ""),
                source=row.get("source") or "DuckDuckGo News",
                summary=row.get("body", row.get("summary", "")),
            )
            if record:
                records.append(record)
        return _dedupe(records, bounded_limit)
    except Exception as exc:
        _warn("DuckDuckGo News", "search", exc)
        return []


def fetch_ptt_stock_sentiment(ticker: str, limit: int = 10) -> list[NewsRecord]:
    """Search official PTT Stock titles within the existing 30-day evidence window."""
    from ptt_stock_search import acquire_recent_posts
    cleaned_ticker = _clean_input(ticker)
    if not cleaned_ticker or not re.fullmatch(r"[\w.-]+", cleaned_ticker, re.UNICODE):
        return []
    match_term = re.sub(r"\.(?:TW|TWO)$", "", cleaned_ticker, flags=re.IGNORECASE)
    started = time.monotonic()
    # Keep the existing scope so deployed cooldowns still protect this provider.
    cooldown_key = scope_key("PTT Stock", endpoint="stock_index")
    blocked = cooldown_state(cooldown_key)
    if blocked:
        record_observation("PTT Stock", started, source="social_sentiment", outcome="cooldown", details=blocked, sent=False)
        return []
    try:
        records, details = acquire_recent_posts(
            match_term, _clamp_limit(limit), get=sync_get,
            headers={"User-Agent": USER_AGENT, "Cookie": "over18=1"},
            now=_current_taipei_datetime(), deadline=started + REQUEST_TIMEOUT_SECONDS,
            clock=time.monotonic,
        )
        record_observation("PTT Stock", started, source="social_sentiment", outcome="results" if records else "valid_empty", count=len(records), details=details)
        return records
    except Exception as exc:
        state = {**getattr(exc, 'acquisition_details', {}), **remember_failure(cooldown_key, exc)}
        record_observation("PTT Stock", started, source="social_sentiment", outcome="failure", details=state)
        _warn("PTT Stock", "search", exc)
        return []
