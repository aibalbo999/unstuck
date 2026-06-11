"""GDELT optional international news client."""

from __future__ import annotations

from urllib.parse import quote

from external_data_parsers import parse_gdelt_article_payload
from external_http_client import async_client, async_json_get, log_http_warning


GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TOPIC_QUERIES = {
    "semiconductors_ai": '("artificial intelligence" OR semiconductor OR "AI chip" OR GPU)',
    "macro": '("Federal Reserve" OR inflation OR recession OR "global growth")',
    "rates_fx": '("US Treasury yields" OR "US dollar" OR "Taiwan dollar")',
    "geopolitics": '(Taiwan OR China OR "South China Sea" OR sanctions)',
    "policy_trade": '("export controls" OR tariffs OR "trade policy")',
    "energy": '(oil OR energy OR "crude prices")',
    "supply_chain": '("supply chain" OR logistics OR "factory disruption")',
}


async def fetch_gdelt_international_news_context(
    sector: str = "",
    industry: str = "",
    *,
    lookback_days: int = 7,
    max_records_per_topic: int = 3,
) -> dict:
    topics = []
    coverage_notes = []
    query_map = _topic_queries_for_context(sector, industry)
    async with async_client() as client:
        for tag, query in query_map.items():
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
                coverage_notes.append(f"{tag} 未回傳可用新聞。")
                continue
            topics.extend(parse_gdelt_article_payload(payload, tag=tag))
    return {
        "lookback_days": int(lookback_days),
        "topics": _dedupe_topics(topics, limit=8),
        "coverage_notes": coverage_notes[:6],
    }


def _topic_queries_for_context(sector: str = "", industry: str = "") -> dict[str, str]:
    signature = f"{sector} {industry}".lower()
    queries = {
        "macro": GDELT_TOPIC_QUERIES["macro"],
        "rates_fx": GDELT_TOPIC_QUERIES["rates_fx"],
        "geopolitics": GDELT_TOPIC_QUERIES["geopolitics"],
        "policy_trade": GDELT_TOPIC_QUERIES["policy_trade"],
    }
    if any(keyword in signature for keyword in ("semiconductor", "ai", "server", "electronics", "半導體", "伺服器")):
        queries["semiconductors_ai"] = GDELT_TOPIC_QUERIES["semiconductors_ai"]
        queries["supply_chain"] = GDELT_TOPIC_QUERIES["supply_chain"]
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
