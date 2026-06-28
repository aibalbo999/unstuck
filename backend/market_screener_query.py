"""Query, pagination, and watchlist annotations for market screener."""

from __future__ import annotations

import json
from datetime import date, datetime

from market_screener_utils import TAIPEI, provider_name
import watchlist_service


DAILY_SCREENER_SOURCE = "daily_screener"


def normalize_screener_filters(filters: dict | None = None) -> dict:
    raw = filters if isinstance(filters, dict) else {}
    fundamental = raw.get("fundamental") if isinstance(raw.get("fundamental"), dict) else {}
    technical = raw.get("technical") if isinstance(raw.get("technical"), dict) else {}
    institutional = raw.get("institutional") if isinstance(raw.get("institutional"), dict) else {}
    return {
        "categories": [str(item).strip() for item in raw.get("categories") or [] if str(item).strip()],
        "min_score": _optional_float(raw.get("min_score")),
        "fundamental": _compact_none({
            "revenue_growth_yoy_pct_min": _optional_float(fundamental.get("revenue_growth_yoy_pct_min")),
            "revenue_growth_yoy_pct_max": _optional_float(fundamental.get("revenue_growth_yoy_pct_max")),
        }),
        "technical": _compact_none({
            "rsi_min": _optional_float(technical.get("rsi_min")),
            "rsi_max": _optional_float(technical.get("rsi_max")),
            "macd_min": _optional_float(technical.get("macd_min")),
            "macd_histogram_min": _optional_float(technical.get("macd_histogram_min")),
        }),
        "institutional": _compact_none({
            "foreign_net_buy_shares_min": _optional_float(institutional.get("foreign_net_buy_shares_min")),
            "investment_trust_net_buy_shares_min": _optional_float(institutional.get("investment_trust_net_buy_shares_min")),
            "dealer_net_buy_shares_min": _optional_float(institutional.get("dealer_net_buy_shares_min")),
            "total_net_buy_shares_min": _optional_float(institutional.get("total_net_buy_shares_min")),
        }),
    }


def annotate_watchlist_status(candidates: list[dict]) -> list[dict]:
    lookup = _watchlist_status_lookup()
    annotated = []
    for candidate in candidates:
        ticker = str(candidate.get("ticker") or "").strip().upper()
        status = lookup.get(ticker, _empty_watchlist_status())
        annotated.append({
            **candidate,
            "watchlist_status": status,
            "is_in_watchlist": status["in_watchlist"],
            "has_trigger": status["has_triggers"],
        })
    return annotated


def with_screener_item_metadata(item: dict) -> dict:
    trigger = daily_screener_trigger(item)
    metrics = trigger.get("metrics") if isinstance(trigger.get("metrics"), dict) else {}
    categories = trigger.get("categories") if isinstance(trigger.get("categories"), list) else [trigger.get("category")]
    categories = [str(category) for category in categories if category]
    watchlist_status = {
        "in_watchlist": True,
        "pipelines": [item.get("pipeline")] if item.get("pipeline") else [],
        "has_triggers": bool(item.get("triggers")),
        "has_daily_screener_trigger": bool(trigger),
    }
    return {
        **item,
        "category": trigger.get("category") or (categories[0] if categories else ""),
        "categories": categories,
        "company_name": item.get("company_name") or trigger.get("company_name") or metrics.get("company_name") or "",
        "reason": trigger.get("reason") or item.get("latest_trigger_event", {}).get("message") or "",
        "score": trigger.get("score"),
        "screen_date": trigger.get("screen_date") or "",
        "metrics": metrics,
        "watchlist_status": watchlist_status,
        "is_in_watchlist": True,
        "has_trigger": watchlist_status["has_triggers"],
    }


def daily_screener_trigger(item: dict) -> dict:
    for trigger in item.get("triggers") or []:
        if isinstance(trigger, dict) and trigger.get("type") == DAILY_SCREENER_SOURCE:
            return trigger
    return {}


def last_updated_time(candidates: list[dict], fallback_date: date) -> str:
    dates = [str(candidate.get("screen_date") or "") for candidate in candidates if candidate.get("screen_date")]
    latest = max(dates) if dates else fallback_date.isoformat()
    return latest if "T" in latest else f"{latest}T00:00:00+08:00"


def scan_cache_key(
    scan_date: date,
    sources: list,
    top_n: int,
    filters: dict,
    limit: int | None,
    offset: int,
    sort_by: str,
    sort_direction: str,
) -> str:
    payload = {
        "date": scan_date.isoformat(),
        "sources": [provider_name(source) for source in sources],
        "top_n": int(top_n or 0),
        "filters": filters,
        "limit": limit,
        "offset": int(offset or 0),
        "sort_by": str(sort_by or "score"),
        "sort_direction": str(sort_direction or "desc"),
    }
    return "market_screener:scan:v2:" + json.dumps(payload, ensure_ascii=False, sort_keys=True)


def payload_last_updated(payload: dict, fallback_items: list[dict]) -> str:
    return payload.get("updated_at") or last_updated_time(fallback_items, datetime.now(TAIPEI).date())


def _watchlist_status_lookup() -> dict[str, dict]:
    try:
        items = watchlist_service.list_watchlist().get("items", [])
    except Exception:
        items = []
    lookup: dict[str, dict] = {}
    for item in items:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker:
            continue
        status = lookup.setdefault(ticker, _empty_watchlist_status())
        status["in_watchlist"] = True
        pipeline = str(item.get("pipeline") or "").strip()
        if pipeline and pipeline not in status["pipelines"]:
            status["pipelines"].append(pipeline)
        triggers = item.get("triggers") if isinstance(item.get("triggers"), list) else []
        status["has_triggers"] = status["has_triggers"] or bool(triggers)
        status["has_daily_screener_trigger"] = status["has_daily_screener_trigger"] or any(
            trigger.get("type") == DAILY_SCREENER_SOURCE for trigger in triggers if isinstance(trigger, dict)
        )
    return lookup


def _empty_watchlist_status() -> dict:
    return {"in_watchlist": False, "pipelines": [], "has_triggers": False, "has_daily_screener_trigger": False}


def _optional_float(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compact_none(value: dict) -> dict:
    return {key: item for key, item in value.items() if item is not None}
