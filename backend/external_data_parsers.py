"""Parsers for optional external market-data HTTP payloads."""

from __future__ import annotations

from typing import Any


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


def parse_google_catalyst_payload(payload: Any) -> list[dict]:
    records = []
    if not isinstance(payload, dict):
        return records

    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        metatags = item.get("pagemap", {}).get("metatags", [{}]) or [{}]
        records.append({
            "date": metatags[0].get("article:published_time", ""),
            "title": title,
            "summary": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_search",
        })
    return records


def parse_google_peer_payload(payload: Any) -> list[dict]:
    records = []
    if not isinstance(payload, dict):
        return records

    for item in payload.get("items", []) or []:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        records.append({
            "title": title,
            "snippet": str(item.get("snippet", "")).strip(),
            "source": item.get("displayLink", "Google Search"),
            "link": item.get("link", ""),
            "source_type": "google_peer_discovery",
        })
    return dedupe_records(records, limit=5)


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
