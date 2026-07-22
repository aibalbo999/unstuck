"""Calendar and date helpers for yfinance enrichment extraction."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def read_stock_calendar(stock):
    try:
        calendar = getattr(stock, "calendar", None)
        return calendar() if callable(calendar) else calendar
    except Exception:
        return None


def calendar_value(calendar, labels: tuple[str, ...]):
    if calendar is None:
        return None
    if isinstance(calendar, dict):
        normalized = {_normalized_key(key): value for key, value in calendar.items()}
        for label in labels:
            if label in calendar:
                return calendar[label]
            value = normalized.get(_normalized_key(label))
            if value is not None:
                return value
        return None
    if isinstance(calendar, pd.Series):
        normalized = {_normalized_key(key): value for key, value in calendar.items()}
        for label in labels:
            if label in calendar.index:
                return calendar.loc[label]
            value = normalized.get(_normalized_key(label))
            if value is not None:
                return value
        return None
    if isinstance(calendar, pd.DataFrame):
        for label in labels:
            if label in calendar.index:
                row = calendar.loc[label]
                values = row.tolist() if hasattr(row, "tolist") else [row]
                return _first_present(values)
            if label in calendar.columns:
                values = calendar[label].dropna().tolist()
                return _first_present(values)
        normalized_index = {_normalized_key(key): key for key in calendar.index}
        normalized_columns = {_normalized_key(key): key for key in calendar.columns}
        for label in labels:
            key = normalized_index.get(_normalized_key(label))
            if key is not None:
                row = calendar.loc[key]
                values = row.tolist() if hasattr(row, "tolist") else [row]
                return _first_present(values)
            key = normalized_columns.get(_normalized_key(label))
            if key is not None:
                values = calendar[key].dropna().tolist()
                return _first_present(values)
    return None


def info_value(info: dict, *keys: str):
    for key in keys:
        value = info.get(key) if isinstance(info, dict) else None
        if value not in (None, "", "N/A"):
            return value
    return None


def append_calendar_event(events: list[dict], *, event_type: str, label: str, date_value: str, source: str, end_date: str | None = None) -> None:
    if any(item.get("type") == event_type and item.get("date") == date_value for item in events):
        return
    event = {"type": event_type, "label": label, "date": date_value, "source": source}
    if end_date and end_date != date_value:
        event["end_date"] = end_date
    events.append(event)


def date_range(*values) -> tuple[str, str]:
    dates = []
    for value in values:
        dates.extend(date_values(value))
    dates = sorted(set(dates))
    return (dates[0], dates[-1]) if dates else ("", "")


def date_value(*values) -> str:
    for value in values:
        dates = date_values(value)
        if dates:
            return dates[0]
    return ""


def date_values(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, pd.Series, pd.Index)):
        dates = [parsed for item in value if (parsed := parse_date(item))]
        return sorted(set(dates))
    parsed = parse_date(value)
    return [parsed] if parsed else []


def parse_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return ""
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000
        try:
            return datetime.fromtimestamp(timestamp).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return ""
    parsed = pd.to_datetime(str(value), errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.date().isoformat()


def _normalized_key(value) -> str:
    return str(value).strip().lower().replace("-", " ").replace("_", " ")


def _first_present(values):
    for value in values:
        if value not in (None, "", "N/A") and not (isinstance(value, float) and pd.isna(value)):
            return value
    return None
