"""Pure, bounded daily-market evidence shared by providers and mode-D prompts."""

from __future__ import annotations

from datetime import date
import math

import pandas as pd

from short_term_events import future_event_context, parse_market_date
from short_term_technical_indicators import calculate_technical_indicators


MAX_DAILY_BARS = 120


def _number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None


def _valid_bar(raw, as_of):
    if not isinstance(raw, dict):
        return None
    day = parse_market_date(raw.get("date"))
    if day is None or day > as_of:
        return None
    numbers = {key: _number(raw.get(key)) for key in ("open", "high", "low", "close", "volume")}
    if numbers["close"] is None or numbers["close"] <= 0:
        return None
    for key in ("open", "high", "low"):
        if numbers[key] is not None and numbers[key] <= 0:
            return None
        if raw.get(key) is not None and numbers[key] is None:
            return None
    if raw.get("volume") is not None and (numbers["volume"] is None or numbers["volume"] < 0):
        return None
    high, low, opening, closing = (numbers[key] for key in ("high", "low", "open", "close"))
    if high is not None and high < max(value for value in (opening, closing, low) if value is not None):
        return None
    if low is not None and low > min(value for value in (opening, closing, high) if value is not None):
        return None
    return {"date": day.isoformat(), **numbers}


def normalize_daily_market_data(rows, *, as_of=None, source="yfinance 5y history") -> dict:
    as_of = parse_market_date(as_of) or date.today()
    rows = rows if isinstance(rows, (list, tuple)) else []
    valid = {}
    excluded = 0
    for row in rows:
        bar = _valid_bar(row, as_of)
        if bar is None:
            excluded += 1
            continue
        if bar["date"] in valid:
            excluded += 1
        valid[bar["date"]] = bar
    bars = [valid[key] for key in sorted(valid)][-MAX_DAILY_BARS:]
    missing = sorted({key for bar in bars for key in ("open", "high", "low", "volume") if bar[key] is None})
    return {
        "as_of": bars[-1]["date"] if bars else None,
        "requested_as_of": as_of.isoformat(), "source": str(source or "unavailable")[:240],
        "interval": "1d", "sample_count": len(bars), "max_samples": MAX_DAILY_BARS,
        "availability": "unavailable" if not bars else "partial" if missing else "available",
        "missing_fields": missing, "excluded_row_count": excluded, "bars": bars,
    }


def daily_market_data_from_frame(frame, *, as_of=None, source="yfinance 5y history") -> dict:
    rows = []
    if frame is not None and hasattr(frame, "iterrows"):
        for index, row in frame.iterrows():
            day = parse_market_date(index)
            values = {key.lower(): row.get(key) for key in ("Open", "High", "Low", "Close", "Volume")}
            # pandas NaN represents a missing cell, not a zero or a made-up price.
            values = {key: None if value is pd.NA or value is pd.NaT or (
                          isinstance(value, (int, float)) and math.isnan(value)) else value
                      for key, value in values.items()}
            rows.append({"date": day.isoformat() if day else None, **values})
    return normalize_daily_market_data(rows, as_of=as_of, source=source)


def build_short_term_market_context(data: dict, *, as_of=None, compact=False) -> dict:
    as_of = parse_market_date(as_of) or date.today()
    raw_daily = data.get("daily_market_data")
    raw_daily = raw_daily if isinstance(raw_daily, dict) else {}
    daily = normalize_daily_market_data(raw_daily.get("bars"), as_of=as_of, source=raw_daily.get("source"))
    indicators = calculate_technical_indicators(daily)
    displayed = daily["bars"][-(5 if compact else 20):]
    return {
        "as_of": as_of.isoformat(),
        "daily_market_data": {**daily, "bars": displayed, "displayed_sample_count": len(displayed)},
        "technical_indicators": indicators,
        "event_calendar": future_event_context(data.get("event_calendar"), as_of=as_of),
    }
