"""GDELT optional international news client."""

from __future__ import annotations

import asyncio
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


async def fetch_gdelt_international_news_context(
    sector: str = "",
    industry: str = "",
    *,
    lookback_days: int = 7,
    max_records_per_topic: int = 3,
    max_topics: int = 2,
    request_spacing_seconds: float = 5.1,
) -> dict:
    topics = []
    coverage_notes = []
    query_items = list(_topic_queries_for_context(sector, industry).items())[: max(1, int(max_topics))]
    async with async_client() as client:
        for index, (tag, query) in enumerate(query_items):
            if index and request_spacing_seconds > 0:
                await asyncio.sleep(request_spacing_seconds)
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
                payload = {}
            parsed_topics = parse_gdelt_article_payload(payload, tag=tag)
            if not parsed_topics:
                parsed_topics = await _fetch_google_news_rss_fallback(client, tag, query)
                if parsed_topics:
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
