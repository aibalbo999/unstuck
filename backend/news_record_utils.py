"""Shared record shaping helpers for free news fetchers."""

from __future__ import annotations

import re
from typing import Any, Iterable, TypedDict
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from news_datetime import iso_date, parse_news_datetime


MAX_RESULTS = 50
MAX_INPUT_LENGTH = 200
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref"}


class NewsRecord(TypedDict):
    title: str
    link: str
    published_date: str
    source: str
    summary: str


def clean_input(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:MAX_INPUT_LENGTH]


def clamp_limit(limit: Any) -> int:
    try:
        number = int(limit)
    except (TypeError, ValueError):
        return 10
    return max(1, min(number, MAX_RESULTS))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)


def canonical_link(value: Any, base_url: str | None = None) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 8192:
        return ""
    try:
        absolute = urljoin(base_url, raw) if base_url else raw
        parsed = urlsplit(absolute)
        if not parsed.hostname:
            return ""
    except ValueError:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    query = [
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


def news_record(
    *, title: Any, link: Any, published_date: Any, source: Any, summary: Any,
    base_url: str | None = None,
) -> NewsRecord | None:
    clean_title = clean_text(title)
    clean_link = canonical_link(link, base_url)
    if not clean_title or not clean_link:
        return None
    return {
        "title": clean_title,
        "link": clean_link,
        "published_date": iso_date(published_date),
        "source": clean_text(source),
        "summary": clean_text(summary),
    }


def dedupe_records(records: Iterable[NewsRecord], limit: int) -> list[NewsRecord]:
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


__all__ = [
    "MAX_INPUT_LENGTH", "MAX_RESULTS", "NewsRecord", "canonical_link", "clamp_limit",
    "clean_input", "clean_text", "dedupe_records", "iso_date", "news_record", "parse_news_datetime",
]
