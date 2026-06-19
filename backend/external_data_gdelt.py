"""GDELT optional international news client."""

from __future__ import annotations

import asyncio
import os
import re
import time
from urllib.parse import quote

from external_data_parsers import parse_gdelt_article_payload, parse_google_news_rss_payload
from external_http_client import async_client, async_json_get, log_http_warning


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"
GDELT_TOPIC_QUERIES = {
    "semiconductors_ai": '(semiconductor OR "AI chip")',
    "macro": '("Federal Reserve" OR inflation)',
    "rates_fx": '("US Treasury yields" OR "US dollar")',
    "geopolitics": '(Taiwan OR China OR sanctions)',
    "policy_trade": '("export controls" OR tariffs)',
    "energy": '(oil OR energy OR "crude prices")',
    "supply_chain": '("supply chain" OR logistics OR "factory disruption")',
}
GDELT_RATE_LIMIT_RE = re.compile(r"(?:\b429\b|too many requests|rate\s*limit)", re.IGNORECASE)
DEFAULT_GDELT_RATE_LIMIT_COOLDOWN_SECONDS = 15 * 60

_gdelt_cooldown_until = 0.0


async def fetch_gdelt_international_news_context(
    sector: str = "",
    industry: str = "",
    *,
    lookback_days: int = 7,
    max_records_per_topic: int = 3,
    max_topics: int = 2,
    request_spacing_seconds: float = 5.1,
    rate_limit_cooldown_seconds: float | None = None,
) -> dict:
    topics = []
    coverage_notes = []
    query_items = list(_topic_queries_for_context(sector, industry).items())[: max(1, int(max_topics))]
    gdelt_attempts = 0
    cooldown_seconds = _rate_limit_cooldown_seconds(rate_limit_cooldown_seconds)
    async with async_client() as client:
        for tag, query in query_items:
            payload = {}
            fallback_reason = ""
            if _gdelt_rate_limited():
                fallback_reason = "GDELT 429 cooldown"
            else:
                if gdelt_attempts and request_spacing_seconds > 0:
                    await asyncio.sleep(request_spacing_seconds)
                gdelt_attempts += 1
                try:
                    payload = await async_json_get(
                        client,
                        GDELT_DOC_URL,
                        {
                            "query": query,
                            "mode": "artlist",
                            "format": "json",
                            "maxrecords": str(max_records_per_topic),
                            "timespan": f"{max(1, int(lookback_days))}d",
                            "sort": "datedesc",
                        },
                    )
                except Exception as exc:
                    log_http_warning("GDELT", f"international news {quote(tag)}", exc)
                    if _is_gdelt_rate_limit_error(exc):
                        _mark_gdelt_rate_limited(cooldown_seconds)
                        fallback_reason = "GDELT 429 rate limited"
            parsed_topics = parse_gdelt_article_payload(payload, tag=tag)
            if not parsed_topics:
                parsed_topics = await _fetch_google_news_rss_fallback(client, tag, query)
                if parsed_topics:
                    if fallback_reason:
                        coverage_notes.append(f"{tag} {fallback_reason}，使用 Google News RSS 備援。")
                    else:
                        coverage_notes.append(f"{tag} 使用 Google News RSS 備援。")
                else:
                    coverage_notes.append(f"{tag} 未回傳可用新聞。")
            topics.extend(parsed_topics)
    return {
        "lookback_days": int(lookback_days),
        "topics": _dedupe_topics(topics, limit=8),
        "coverage_notes": coverage_notes[:6],
    }


async def _fetch_google_news_rss_fallback(client, tag: str, query: str) -> list[dict]:
    try:
        response = await client.get(
            GOOGLE_NEWS_RSS_URL,
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
        )
        response.raise_for_status()
    except Exception as exc:
        log_http_warning("Google News RSS", f"international news {quote(tag)}", exc)
        return []
    return parse_google_news_rss_payload(response.text, tag=tag)


def _now() -> float:
    return time.time()


def _rate_limit_cooldown_seconds(explicit: float | None = None) -> float:
    if explicit is not None:
        return max(float(explicit), 0.0)
    try:
        configured = os.getenv("GDELT_RATE_LIMIT_COOLDOWN_SECONDS", str(DEFAULT_GDELT_RATE_LIMIT_COOLDOWN_SECONDS))
        return max(float(configured), 0.0)
    except ValueError:
        return float(DEFAULT_GDELT_RATE_LIMIT_COOLDOWN_SECONDS)


def _gdelt_rate_limited() -> bool:
    return _now() < _gdelt_cooldown_until


def _mark_gdelt_rate_limited(cooldown_seconds: float) -> None:
    global _gdelt_cooldown_until
    _gdelt_cooldown_until = max(_gdelt_cooldown_until, _now() + max(float(cooldown_seconds), 0.0))


def _is_gdelt_rate_limit_error(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    return bool(GDELT_RATE_LIMIT_RE.search(str(exc or "")))


def _topic_queries_for_context(sector: str = "", industry: str = "") -> dict[str, str]:
    signature = f"{sector} {industry}".lower()
    queries = {}
    if any(keyword in signature for keyword in ("semiconductor", "ai", "server", "electronics", "半導體", "伺服器")):
        queries["semiconductors_ai"] = GDELT_TOPIC_QUERIES["semiconductors_ai"]
        queries["supply_chain"] = GDELT_TOPIC_QUERIES["supply_chain"]
    queries.update({
        "macro": GDELT_TOPIC_QUERIES["macro"],
        "rates_fx": GDELT_TOPIC_QUERIES["rates_fx"],
        "geopolitics": GDELT_TOPIC_QUERIES["geopolitics"],
        "policy_trade": GDELT_TOPIC_QUERIES["policy_trade"],
    })
    return queries


def _dedupe_topics(records: list[dict], limit: int = 8) -> list[dict]:
    kept = []
    seen = set()
    for record in records:
        marker = str(record.get("url") or record.get("headline") or "").strip().lower()
        if not marker or marker in seen:
            continue
        seen.add(marker)
        kept.append(record)
        if len(kept) >= limit:
            break
    return kept
