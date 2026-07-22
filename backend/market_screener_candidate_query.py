"""Filtering, sorting, and pagination helpers for market screener candidates."""

from __future__ import annotations

from market_screener_utils import safe_float


def filter_candidates(candidates: list[dict], filters: dict | None = None) -> list[dict]:
    normalized = filters if isinstance(filters, dict) else {}
    categories = {str(item).strip() for item in normalized.get("categories") or [] if str(item).strip()}
    return [
        candidate for candidate in candidates
        if _candidate_matches_categories(candidate, categories) and _candidate_matches_metric_filters(candidate, normalized)
    ]


def sort_candidates(candidates: list[dict], sort_by: str = "score", sort_direction: str = "desc") -> list[dict]:
    key = str(sort_by or "score").strip()
    reverse = str(sort_direction or "desc").strip().lower() != "asc"

    def sort_value(candidate: dict):
        metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
        value = metrics.get(key, candidate.get(key))
        if isinstance(value, (int, float)):
            return (1, float(value))
        try:
            return (1, float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return (0, str(value or ""))

    return sorted(candidates, key=sort_value, reverse=reverse)


def paginate_candidates(candidates: list[dict], *, limit: int | None = None, offset: int = 0) -> tuple[list[dict], dict]:
    total = len(candidates)
    safe_offset = max(0, int(offset or 0))
    safe_limit = max(1, min(int(limit or total or 1), 100))
    page = candidates[safe_offset:safe_offset + safe_limit]
    return page, {
        "limit": safe_limit,
        "offset": safe_offset,
        "total": total,
        "has_more": safe_offset + safe_limit < total,
    }


def _candidate_matches_categories(candidate: dict, categories: set[str]) -> bool:
    if not categories:
        return True
    candidate_categories = {
        str(category).strip()
        for category in [candidate.get("category"), *(candidate.get("categories") or [])]
        if str(category).strip()
    }
    return bool(candidate_categories & categories)


def _candidate_matches_metric_filters(candidate: dict, filters: dict) -> bool:
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    checks = [
        ("fundamental", "revenue_growth_yoy_pct_min", "revenue_growth_yoy_pct", "min"),
        ("fundamental", "revenue_growth_yoy_pct_max", "revenue_growth_yoy_pct", "max"),
        ("technical", "rsi_min", "rsi_14", "min"),
        ("technical", "rsi_max", "rsi_14", "max"),
        ("technical", "macd_min", "macd", "min"),
        ("technical", "macd_histogram_min", "macd_histogram", "min"),
        ("institutional", "foreign_net_buy_shares_min", "foreign_net_buy_shares", "min"),
        ("institutional", "investment_trust_net_buy_shares_min", "investment_trust_net_buy_shares", "min"),
        ("institutional", "dealer_net_buy_shares_min", "dealer_net_buy_shares", "min"),
        ("institutional", "total_net_buy_shares_min", "total_net_buy_shares", "min"),
    ]
    for section, filter_key, metric_key, mode in checks:
        section_filters = filters.get(section) if isinstance(filters.get(section), dict) else {}
        if filter_key not in section_filters:
            continue
        threshold = safe_float(section_filters.get(filter_key))
        if metric_key not in metrics:
            return False
        value = safe_float(metrics.get(metric_key))
        if mode == "min" and value < threshold:
            return False
        if mode == "max" and value > threshold:
            return False
    min_score = filters.get("min_score")
    return min_score is None or safe_float(candidate.get("score")) >= safe_float(min_score)
