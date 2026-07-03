"""Prompt-facing source audit summaries."""

from __future__ import annotations

from data_trust import source_record_count


PROMPT_COUNT_COMPARABLE_SOURCES = {
    "financial_statements",
    "monthly_revenue",
    "recent_catalysts",
    "institutional_trading",
    "dynamic_peer_metrics",
    "pe_river_chart",
    "peer_discovery",
    "global_market_context",
    "international_news_context",
    "macro_indicators",
    "chip_data",
    "alternative_data",
    "social_sentiment",
    "sec_edgar",
    "taiwan_open_data",
    "earnings_call",
    "twse_official",
}


def prompt_source_audit_summary(data: dict) -> list[dict]:
    entries = data.get("source_audit", []) if isinstance(data.get("source_audit"), list) else []
    latest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = str(entry.get("source") or "")
        if source:
            latest[source] = entry

    summary = []
    for source, entry in sorted(latest.items()):
        merged_record_count = source_record_count(source, data)
        audit_record_count = _optional_int(entry.get("record_count"))
        summary.append({
            "source": source,
            "provider": entry.get("provider"),
            "status": entry.get("status"),
            "record_count": entry.get("record_count"),
            "merged_record_count": merged_record_count,
            "record_count_mismatch": (
                source in PROMPT_COUNT_COMPARABLE_SOURCES
                and audit_record_count is not None
                and merged_record_count != audit_record_count
            ),
            "cache_hit": entry.get("cache_hit"),
            "stale": entry.get("stale"),
            "message": str(entry.get("message") or entry.get("error_kind") or "")[:160],
        })
    return summary


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
