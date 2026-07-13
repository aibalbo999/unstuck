"""Prompt-facing source audit summaries."""

from __future__ import annotations

from data_trust import source_record_count
from mapping_fields import safe_text


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
    raw_entries = dict.get(data, "source_audit", [])
    entries = raw_entries if isinstance(raw_entries, list) else []
    latest = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        source = _safe_text(dict.get(entry, "source")).strip()
        if source:
            latest[source] = entry

    summary = []
    for source, entry in sorted(latest.items()):
        merged_record_count = source_record_count(source, data)
        audit_record_count = _optional_int(dict.get(entry, "record_count"))
        message = _safe_text(dict.get(entry, "message")) or _safe_text(dict.get(entry, "error_kind"))
        summary.append({
            "source": source,
            "provider": _safe_text(dict.get(entry, "provider")).strip(),
            "status": _safe_text(dict.get(entry, "status")).strip(),
            "record_count": audit_record_count,
            "merged_record_count": merged_record_count,
            "record_count_mismatch": (
                source in PROMPT_COUNT_COMPARABLE_SOURCES
                and audit_record_count is not None
                and merged_record_count != audit_record_count
            ),
            "cache_hit": _optional_bool(dict.get(entry, "cache_hit")),
            "stale": _optional_bool(dict.get(entry, "stale")),
            "message": message[:160],
        })
    return summary


def _optional_int(value):
    try:
        return int(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None


def _optional_bool(value):
    if value is None:
        return None
    try:
        return bool(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        return None


def _safe_text(value):
    return safe_text(value)
