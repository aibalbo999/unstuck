"""Payload parsers for alternative search providers."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

from external_search_types import SearchResult


def parse_brave_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in ((payload.get("web") or {}).get("results") or []):
        if isinstance(item, dict):
            records.append(result_from_fields(
                item.get("title"),
                item.get("description"),
                item.get("url"),
                item.get("profile", {}).get("name") if isinstance(item.get("profile"), dict) else "",
                provider="brave",
            ))
    return [record for record in records if record.title]


def parse_bing_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in ((payload.get("webPages") or {}).get("value") or []):
        if isinstance(item, dict):
            records.append(result_from_fields(item.get("name"), item.get("snippet"), item.get("url"), item.get("displayUrl"), provider="bing"))
    return [record for record in records if record.title]


def parse_tavily_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("results", []) or []:
        if isinstance(item, dict):
            records.append(result_from_fields(
                item.get("title"),
                item.get("content") or item.get("snippet"),
                item.get("url"),
                domain(item.get("url")),
                published_at=item.get("published_date") or "",
                provider="tavily",
            ))
    return [record for record in records if record.title]


def parse_serpapi_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("organic_results", []) or []:
        if isinstance(item, dict):
            records.append(result_from_fields(
                item.get("title"),
                item.get("snippet"),
                item.get("link"),
                item.get("source") or item.get("displayed_link"),
                published_at=item.get("date") or "",
                provider="serpapi",
            ))
    return [record for record in records if record.title]


def parse_gdelt_payload(payload: Any) -> list[SearchResult]:
    records = []
    if not isinstance(payload, dict):
        return records
    for item in payload.get("articles", []) or []:
        if isinstance(item, dict):
            records.append(result_from_fields(
                item.get("title"),
                " · ".join(part for part in (item.get("domain"), item.get("sourcecountry")) if part),
                item.get("url"),
                item.get("domain") or "GDELT",
                published_at=item.get("seendate") or item.get("date") or "",
                provider="gdelt",
            ))
    return [record for record in records if record.title]


def parse_news_rss_payload(payload: Any, *, provider: str, fallback_source: str) -> list[SearchResult]:
    text = str(payload or "").strip()
    if not text:
        return []
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError:
        return []
    records = []
    for item in root.findall(".//item"):
        title = str(item.findtext("title") or "").strip()
        link = str(item.findtext("link") or "").strip()
        source = str(item.findtext("source") or "").strip() or domain(link) or fallback_source
        records.append(result_from_fields(
            title,
            item.findtext("description") or "",
            link,
            source,
            published_at=item.findtext("pubDate") or "",
            provider=provider,
        ))
    return [record for record in records if record.title]


def result_from_fields(
    title: Any,
    snippet: Any,
    link: Any,
    source: Any,
    *,
    published_at: Any = "",
    provider: str,
) -> SearchResult:
    clean_link = str(link or "").strip()
    return SearchResult(
        title=str(title or "").strip(),
        snippet=str(snippet or "").strip(),
        link=clean_link,
        source=str(source or "").strip() or domain(clean_link) or provider,
        published_at=str(published_at or "").strip(),
        provider=provider,
    )


def dedupe_results(records: list[SearchResult], *, limit: int) -> list[SearchResult]:
    kept: list[SearchResult] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    for record in records:
        link = record.link.strip().lower()
        title = record.title.strip().lower()
        if (link and link in seen_links) or (title and title in seen_titles) or (not link and not title):
            continue
        kept.append(record)
        if link:
            seen_links.add(link)
        if title:
            seen_titles.add(title)
        if len(kept) >= limit:
            break
    return kept


def domain(url: Any) -> str:
    try:
        return urlparse(str(url or "")).netloc.replace("www.", "")
    except Exception:
        return ""
