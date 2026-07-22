"""Shared helpers for watchlist trigger evaluation."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pipeline_modes import normalize_pipeline_run_id


BEARISH_TRIGGERS = {"price_below_sma", "foreign_sell_streak", "vix_above"}


def monthly_evaluation_date(trigger_type: str, evaluation_date: str | None) -> str:
    base = evaluation_date or date.today().isoformat()
    if trigger_type != "revenue_record_high":
        return base
    match = re.match(r"^(\d{4})-(\d{2})", str(base or ""))
    if not match:
        return base
    return f"{match.group(1)}-{match.group(2)}-01"


def selected_pipeline(trigger_type: str, trigger: dict, source_pipeline: str) -> str:
    if trigger_type in BEARISH_TRIGGERS:
        return "v3"
    if trigger_type == "revenue_record_high":
        return "v2"
    if trigger_type == "report_catalyst":
        direction = str(trigger.get("impact_direction") or "").strip().lower()
        if direction == "bearish":
            return "v3"
        if direction == "bullish":
            return "v2"
    if trigger_type == "daily_screener":
        return "v4"
    if trigger_type == "event_upcoming":
        return "v4"
    if trigger_type == "price_near_level":
        return "v2"
    return source_pipeline


def prices(data: dict) -> list[float]:
    daily = data.get("daily_prices") or data.get("price_history_daily")
    if isinstance(daily, list):
        values = [row.get("close") if isinstance(row, dict) else row for row in daily]
    else:
        history = data.get("price_history") if isinstance(data.get("price_history"), dict) else {}
        values = history.get("prices") if isinstance(history.get("prices"), list) else []
    result = []
    for value in values:
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return result


def volumes(data: dict) -> list[float]:
    daily = data.get("daily_prices") or data.get("price_history_daily")
    if not isinstance(daily, list):
        return []
    result = []
    for row in daily:
        value = row.get("volume") if isinstance(row, dict) else None
        try:
            result.append(float(value))
        except (TypeError, ValueError):
            continue
    return result


def matching_calendar_event(data: dict, event_type: str, target_date: date | None) -> dict:
    calendar = data.get("event_calendar") if isinstance(data.get("event_calendar"), dict) else {}
    events = calendar.get("events") if isinstance(calendar.get("events"), list) else []
    for item in events:
        if not isinstance(item, dict):
            continue
        if event_type and str(item.get("type") or "") != event_type:
            continue
        item_date = parse_iso_date(item.get("date"))
        if target_date and item_date != target_date:
            continue
        return item
    return {}


def parse_iso_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    return str(value or "")


def parse_revenue_value(value: object) -> float | None:
    if isinstance(value, dict):
        value = value.get("revenue") or value.get("value")
    text = str(value or "")
    normalized = text.replace(",", "")
    matches = list(re.finditer(r"([-+]?\d+(?:\.\d+)?)", normalized))
    unit_positions = [pos for pos in (normalized.find("億"), normalized.find("萬")) if pos >= 0]
    if unit_positions and matches:
        unit_position = min(unit_positions)
        number_match = next((match for match in reversed(matches) if match.start() < unit_position), None)
    else:
        number_match = matches[0] if matches else None
    number = safe_float(number_match.group(1)) if number_match else safe_float(value)
    if number is None:
        return None
    if "億" in text:
        return number * 100_000_000
    if "萬" in text:
        return number * 10_000
    return number


def safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
