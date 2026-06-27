"""GDELT optional international news client."""

from __future__ import annotations

import asyncio
import os
import re
import time
from urllib.parse import quote

from cache_store import get_cache_json, set_cache_json
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
DEFAULT_GDELT_TOPIC_CACHE_SECONDS = 6 * 60 * 60
GDELT_RATE_LIMIT_CACHE_KEY = "gdelt_rate_limit_cooldown:v1"

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
    topic_cache_seconds: int = DEFAULT_GDELT_TOPIC_CACHE_SECONDS,
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
            cache_key = _gdelt_topic_cache_key(tag, query, lookback_days, max_records_per_topic)
            parsed_topics = _cached_gdelt_topics(cache_key)
            if parsed_topics:
                topics.extend(parsed_topics)
                coverage_notes.append(f"{tag} 使用 GDELT 快取。")
                continue
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
                    if _is_gdelt_rate_limit_error(exc):
                        _mark_gdelt_rate_limited(cooldown_seconds)
                        fallback_reason = "GDELT 429 rate limited"
                        parsed_topics = _cached_gdelt_topics(cache_key)
                    else:
                        log_http_warning("GDELT", f"international news {quote(tag)}", exc)
            if not parsed_topics:
                parsed_topics = parse_gdelt_article_payload(payload, tag=tag)
                if parsed_topics:
                    _cache_gdelt_topics(cache_key, parsed_topics, topic_cache_seconds)
            if not parsed_topics:
                parsed_topics = await _fetch_google_news_rss_fallback(client, tag, query)
                if parsed_topics:
                    if fallback_reason:
                        coverage_notes.append(f"{tag} {fallback_reason}，使用 Google News RSS 備援。")
                    else:
                        coverage_notes.append(f"{tag} 使用 Google News RSS 備援。")
                else:
                    coverage_notes.append(f"{tag} 未回傳可用新聞。")
            elif fallback_reason:
                coverage_notes.append(f"{tag} {fallback_reason}，使用 GDELT 快取。")
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
    return _now() < _active_gdelt_cooldown_until()


def _mark_gdelt_rate_limited(cooldown_seconds: float) -> None:
    global _gdelt_cooldown_until
    now = _now()
    cooldown = max(float(cooldown_seconds), 0.0)
    _gdelt_cooldown_until = max(_gdelt_cooldown_until, now + cooldown)
    if _gdelt_cooldown_until <= now:
        return
    try:
        set_cache_json(
            GDELT_RATE_LIMIT_CACHE_KEY,
            {"cooldown_until": _gdelt_cooldown_until},
            ttl_seconds=max(int(_gdelt_cooldown_until - now), 1),
        )
    except Exception:
        return


def _active_gdelt_cooldown_until() -> float:
    return max(_gdelt_cooldown_until, _persisted_gdelt_cooldown_until())


def _persisted_gdelt_cooldown_until() -> float:
    try:
        payload = get_cache_json(GDELT_RATE_LIMIT_CACHE_KEY)
    except Exception:
        return 0.0
    if not isinstance(payload, dict):
        return 0.0
    try:
        return max(float(payload.get("cooldown_until") or 0.0), 0.0)
    except (TypeError, ValueError):
        return 0.0


def _is_gdelt_rate_limit_error(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 429:
        return True
    return bool(GDELT_RATE_LIMIT_RE.search(str(exc or "")))


def _gdelt_topic_cache_key(tag: str, query: str, lookback_days: int, max_records: int) -> str:
    return f"gdelt_topic:v1:{tag}:{max(1, int(lookback_days))}d:{max(1, int(max_records))}:{query}"


def _cached_gdelt_topics(cache_key: str) -> list[dict]:
    cached = get_cache_json(cache_key)
    if not isinstance(cached, dict):
        return []
    topics = cached.get("topics")
    return topics if isinstance(topics, list) else []


def _cache_gdelt_topics(cache_key: str, topics: list[dict], ttl_seconds: int) -> None:
    if topics and ttl_seconds > 0:
        set_cache_json(cache_key, {"topics": topics}, int(ttl_seconds))


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
