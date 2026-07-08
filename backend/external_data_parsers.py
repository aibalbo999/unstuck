"""Parsers for optional external market-data HTTP payloads."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree


def dedupe_records(records: list[dict], key: str = "title", limit: int = 6) -> list[dict]:
    kept = []
    seen = set()
    for record in records:
        marker = str(record.get(key) or record.get("link") or "").strip().lower()
        if not marker or marker in seen:
            continue
        kept.append(record)
        seen.add(marker)
        if len(kept) >= limit:
            break
    return kept


def parse_fmp_quote_payload(payload: Any) -> dict:
    if isinstance(payload, list) and payload:
        return payload[0] if isinstance(payload[0], dict) else {}
    return payload if isinstance(payload, dict) else {}


def parse_fmp_news_payload(payload: Any) -> list[dict]:
    if not isinstance(payload, list):
        return []

    records = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("title"):
            continue
        records.append({
            "date": item.get("publishedDate") or item.get("date") or "",
            "title": str(item.get("title", "")).strip(),
            "summary": str(item.get("text") or item.get("summary") or "")[:280],
            "source": item.get("site") or "FMP",
            "link": item.get("url") or "",
            "source_type": "fmp_news",
        })
    return records


def parse_gdelt_article_payload(payload: Any, *, tag: str) -> list[dict]:
    if not isinstance(payload, dict):
        return []

    records = []
    for item in payload.get("articles", []) or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        domain = str(item.get("domain") or "").strip()
        country = str(item.get("sourcecountry") or "").strip()
        summary_parts = [part for part in (domain, country) if part]
        records.append({
            "tag": str(tag or "macro"),
            "headline": title,
            "summary": " · ".join(summary_parts),
            "published_at": item.get("seendate") or item.get("date") or "",
            "source": "GDELT",
            "url": item.get("url") or "",
        })
    return dedupe_records(records, key="headline", limit=8)


def parse_google_news_rss_payload(payload: Any, *, tag: str) -> list[dict]:
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
        if not title:
            continue
        source = str(item.findtext("source") or "").strip()
        records.append({
            "tag": str(tag or "macro"),
            "headline": title,
            "summary": source,
            "published_at": str(item.findtext("pubDate") or "").strip(),
            "source": "Google News RSS",
            "url": str(item.findtext("link") or "").strip(),
        })
    return dedupe_records(records, key="headline", limit=8)
