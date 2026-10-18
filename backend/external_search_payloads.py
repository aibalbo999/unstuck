"""Payload parsers for alternative search providers."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import parse_qs, urlparse, urlsplit
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
        title = _rss_item_text(item, "title")
        link = _rss_item_text(item, "link")
        source_text = _rss_item_text(item, "source")
        if provider == "bing_news_rss":
            link = _bing_news_original_link(link)
            source = source_text
            # Bing's aggregate host is not the article publisher. Keep only
            # records whose RSS item supplies both an original URL and source.
            if not link or not source or source.casefold() in {"bing.com", "bing news rss"}:
                continue
        else:
            source = source_text or domain(link) or fallback_source
        records.append(result_from_fields(
            title,
            _rss_item_text(item, "description"),
            link,
            source,
            published_at=_rss_item_text(item, "pubDate"),
            provider=provider,
        ))
    return [record for record in records if record.title]


def _rss_item_text(item, name: str) -> str:
    wanted = name.casefold()
    for child in item:
        if child.tag.rsplit("}", 1)[-1].casefold() == wanted:
            return str(child.text or "").strip()
    return ""


def _bing_news_original_link(value: str) -> str:
    """Unwrap only Bing's known news redirect; do not follow it."""
    try:
        parsed = urlsplit(str(value or "").strip())
        host = (parsed.hostname or "").casefold()
        if host in {"bing.com", "www.bing.com"}:
            if parsed.scheme not in {"http", "https"} or parsed.path != "/news/apiclick.aspx":
                return ""
            targets = parse_qs(parsed.query, keep_blank_values=True).get("url", [])
            if len(targets) != 1:
                return ""
            original = targets[0].strip()
            target = urlsplit(original)
        else:
            original = str(value or "").strip()
            target = parsed
        if (target.scheme not in {"http", "https"} or not target.hostname
                or target.username or target.password or target.port not in {None, 80, 443}):
            return ""
        if (target.hostname or "").casefold() in {"bing.com", "www.bing.com"}:
            return ""
        return original
    except (TypeError, ValueError):
        return ""


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


def result_dedupe_identity(record: SearchResult, verified_event_identity=None) -> tuple[str, str]:
    """A trusted caller can retain a verified POST event's identity, not a fake URL."""
    event = verified_event_identity(record) if verified_event_identity is not None else None
    if isinstance(event, str) and event.strip():
        return event.strip(), ''
    return record.link.strip().lower(), record.title.strip().lower()


def dedupe_results(records: list[SearchResult], *, limit: int,
                   verified_event_identity: Callable[[SearchResult], str | None] | None = None) -> list[SearchResult]:
    kept: list[SearchResult] = []
    seen_links: set[str] = set()
    seen_titles: set[str] = set()
    for record in records:
        link, title = result_dedupe_identity(record, verified_event_identity)
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
