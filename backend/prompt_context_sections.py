"""Prompt payload sections for optional external context."""

from __future__ import annotations


def compact_list(items, limit: int) -> list:
    return list(items or [])[: max(0, int(limit))]


def compact_global_market_items(items, *, default_limit: int = 3, category_limit: int = 8) -> list:
    rows = list(items or [])
    categories = [str(item.get("category") or "") for item in rows if isinstance(item, dict)]
    if len(set(categories)) <= 2:
        return compact_list(rows, default_limit)

    kept = []
    seen_categories = set()
    for item in rows:
        category = str(item.get("category") or "") if isinstance(item, dict) else ""
        if category in seen_categories:
            continue
        kept.append(item)
        seen_categories.add(category)
        if len(kept) >= category_limit:
            return kept
    for item in rows:
        if item in kept:
            continue
        kept.append(item)
        if len(kept) >= category_limit:
            break
    return kept


def prompt_global_market_context(data: dict, *, compact: bool) -> dict:
    context = data.get("global_market_context", {}) if isinstance(data.get("global_market_context"), dict) else {}
    return {
        "as_of": context.get("as_of"),
        "lookback_days": context.get("lookback_days", 5),
        "items": compact_global_market_items(context.get("items", [])) if compact else context.get("items", []) or [],
        "coverage_notes": compact_list(context.get("coverage_notes", []), 3),
    }


def prompt_international_news_context(data: dict, *, compact: bool) -> dict:
    context = data.get("international_news_context", {}) if isinstance(data.get("international_news_context"), dict) else {}
    return {
        "lookback_days": context.get("lookback_days", 7),
        "topics": compact_list(context.get("topics", []), 2) if compact else context.get("topics", []) or [],
        "coverage_notes": compact_list(context.get("coverage_notes", []), 3),
    }
