"""Prompt payload sections for optional external context."""

from __future__ import annotations


def compact_list(items, limit: int) -> list:
    return list(items or [])[: max(0, int(limit))]


def prompt_global_market_context(data: dict, *, compact: bool) -> dict:
    context = data.get("global_market_context", {}) if isinstance(data.get("global_market_context"), dict) else {}
    return {
        "as_of": context.get("as_of"),
        "lookback_days": context.get("lookback_days", 5),
        "items": compact_list(context.get("items", []), 3) if compact else context.get("items", []) or [],
        "coverage_notes": compact_list(context.get("coverage_notes", []), 3),
    }


def prompt_international_news_context(data: dict, *, compact: bool) -> dict:
    context = data.get("international_news_context", {}) if isinstance(data.get("international_news_context"), dict) else {}
    return {
        "lookback_days": context.get("lookback_days", 7),
        "topics": compact_list(context.get("topics", []), 2) if compact else context.get("topics", []) or [],
        "coverage_notes": compact_list(context.get("coverage_notes", []), 3),
    }
