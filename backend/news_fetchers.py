"""Free news and retail-sentiment fetchers with a shared record shape."""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
import logging
import re
import threading
from typing import Any, Iterable, TypedDict
from urllib.parse import parse_qsl, quote_plus, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import feedparser
import requests

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
MAX_RESULTS = 50
MAX_INPUT_LENGTH = 200
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
}


class NewsRecord(TypedDict):
    title: str
    link: str
    published_date: str
    source: str
    summary: str


def _clean_input(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:MAX_INPUT_LENGTH]


def _clamp_limit(limit: Any) -> int:
    try:
        number = int(limit)
    except (TypeError, ValueError):
        return 10
    return max(1, min(number, MAX_RESULTS))


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def _canonical_link(value: Any, base_url: str | None = None) -> str:
    raw = _clean_input(value)
    if not raw:
        return ""
    absolute = urljoin(base_url, raw) if base_url else raw
    parsed = urlsplit(absolute)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


def _iso_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, (tuple, list)) and len(value) >= 6:
        timestamp = calendar.timegm(tuple(value[:9]))
        return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    text = _clean_input(value)
    if not text:
        return ""
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    except ValueError:
        return ""


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


def _record(
    *, title: Any, link: Any, published_date: Any, source: Any, summary: Any,
    base_url: str | None = None,
) -> NewsRecord | None:
    clean_title = _clean_text(title)
    clean_link = _canonical_link(link, base_url)
    if not clean_title or not clean_link:
        return None
    return {
        "title": clean_title,
        "link": clean_link,
        "published_date": _iso_date(published_date),
        "source": _clean_text(source),
        "summary": _clean_text(summary),
    }


def _dedupe(records: Iterable[NewsRecord], limit: int) -> list[NewsRecord]:
    output: list[NewsRecord] = []
    seen: set[str] = set()
    for record in records:
        identity = record["link"] or record["title"].casefold()
        if identity in seen:
            continue
        seen.add(identity)
        output.append(record)
        if len(output) >= limit:
            break
    return output


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
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", []):
            raise ValueError("invalid RSS feed")
        records = []
        for entry in getattr(feed, "entries", []):
            record = _record(
                title=getattr(entry, "title", ""),
                link=getattr(entry, "link", ""),
                published_date=getattr(entry, "published_parsed", None)
                or getattr(entry, "updated_parsed", None),
                source="Google News RSS",
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
    """Fetch first-page PTT Stock titles containing the requested ticker or term."""
    cleaned_ticker = _clean_input(ticker)
    if not cleaned_ticker or not re.fullmatch(r"[\w.-]+", cleaned_ticker, re.UNICODE):
        return []
    bounded_limit = _clamp_limit(limit)
    try:
        response = requests.get(
            PTT_STOCK_URL,
            headers={"User-Agent": USER_AGENT, "Cookie": "over18=1"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        records = []
        for item in soup.select("div.r-ent"):
            anchor = item.select_one("div.title a")
            if anchor is None:
                continue
            title = _clean_text(anchor.get_text(" ", strip=True))
            if cleaned_ticker.casefold() not in title.casefold():
                continue
            date_node = item.select_one("div.date")
            record = _record(
                title=title,
                link=anchor.get("href", ""),
                published_date=_ptt_date_to_iso(date_node.get_text() if date_node else ""),
                source="PTT Stock",
                summary=title,
                base_url=PTT_STOCK_URL,
            )
            if record:
                records.append(record)
        return _dedupe(records, bounded_limit)
    except requests.RequestException as exc:
        _warn("PTT Stock", "first-page request", exc)
        return []
    except Exception as exc:
        _warn("PTT Stock", "parse", exc)
        return []
