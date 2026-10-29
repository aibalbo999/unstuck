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


def normalize_daily_market_data(rows, *, as_of=None, source="yfinance 5y history", volume_unit=None, ticker=None) -> dict:
    as_of = parse_market_date(as_of) or date.today()
    rows = rows if isinstance(rows, (list, tuple)) else []
    grouped = {}
    invalid_by_date = {}
    excluded = 0
    for row in rows:
        bar = _valid_bar(row, as_of)
        if bar is None:
            excluded += 1
            day = parse_market_date(row.get("date")) if isinstance(row, dict) else None
            if day is not None and day <= as_of:
                invalid_by_date[day.isoformat()] = invalid_by_date.get(day.isoformat(), 0) + 1
            continue
        grouped.setdefault(bar["date"], []).append(bar)
    valid = {}
    quarantined = []
    for day, observations in grouped.items():
        unique = []
        for observation in observations:
            if observation not in unique:
                unique.append(observation)
        invalid_count = invalid_by_date.get(day, 0)
        if len(unique) > 1 or invalid_count:
            # Neither input order nor valid-looking arithmetic establishes which
            # source row is correct. Keep all candidates outside admitted bars.
            excluded += len(observations)
            unique.sort(key=lambda item: tuple(float("-inf") if item[key] is None else item[key]
                                               for key in ("open", "high", "low", "close", "volume")))
            quarantined.append({"date": day, "state": "unknown",
                                "reason": "duplicate_session_evidence_unusable" if invalid_count else "conflicting_duplicate_session",
                                "observations": unique, "input_row_count": len(observations) + invalid_count,
                                "invalid_observation_count": invalid_count,
                                "source_selection_evidence_status": "missing"})
            continue
        excluded += len(observations) - 1
        valid[day] = unique[0]
    bars = [valid[key] for key in sorted(valid)]
    from market_session_admission import assess_daily_session_integrity, market_for_ticker
    if market_for_ticker(ticker) == "tw":
        from market_calendar_store import load_market_calendar, session_day_status
        calendars = {}
        accepted = []
        for bar in bars:
            day = date.fromisoformat(bar["date"])
            if day.year not in calendars:
                calendars[day.year] = load_market_calendar("tw", day.year)
            session = session_day_status(day, market="tw", calendar=calendars[day.year],
                                         exchange="TPEX" if str(ticker).upper().endswith(".TWO") else "TWSE")
            if session["state"] == "open":
                accepted.append(bar)
            else:
                excluded += 1
                quarantined.append({"date": bar["date"], "reason": session["reason"],
                                    "state": session["state"]})
        bars = accepted
    bars = bars[-MAX_DAILY_BARS:]
    missing = sorted({key for bar in bars for key in ("open", "high", "low", "volume") if bar[key] is None})
    result = {
        "as_of": bars[-1]["date"] if bars else None,
        "requested_as_of": as_of.isoformat(), "source": str(source or "unavailable")[:240],
        "volume_unit": volume_unit if volume_unit in ("shares", "lots") else None,
        "interval": "1d", "sample_count": len(bars), "max_samples": MAX_DAILY_BARS,
        "availability": "unavailable" if not bars else "partial" if missing else "available",
        "missing_fields": missing, "excluded_row_count": excluded, "bars": bars,
    }
    if ticker:
        result["ticker"] = str(ticker).upper()
        raw_start = next(iter(sorted(set(grouped) | set(invalid_by_date))[-MAX_DAILY_BARS:]), None)
        starts = [value for value in (bars[0]["date"] if bars else None, raw_start) if value is not None]
        start = min(starts) if starts else None
        result["quarantined_session_rows"] = sorted(
            [row for row in quarantined if start is None or row["date"] >= start], key=lambda row: row["date"])
        result["session_integrity"] = assess_daily_session_integrity(result, ticker=ticker)
        result["calendar_admission_applied"] = market_for_ticker(ticker) == "tw"
        if result["calendar_admission_applied"] and not result["session_integrity"]["eligible"]:
            result["availability"] = "partial" if bars else "unavailable"
    return result


def daily_market_data_from_frame(frame, *, as_of=None, source="yfinance 5y history", volume_unit=None, ticker=None) -> dict:
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
    return normalize_daily_market_data(rows, as_of=as_of, source=source, volume_unit=volume_unit, ticker=ticker)


def build_short_term_market_context(data: dict, *, as_of=None, compact=False) -> dict:
    as_of = parse_market_date(as_of) or date.today()
    raw_daily = data.get("daily_market_data")
    raw_daily = raw_daily if isinstance(raw_daily, dict) else {}
    daily = normalize_daily_market_data(raw_daily.get("bars"), as_of=as_of, source=raw_daily.get("source"),
                                        volume_unit=raw_daily.get("volume_unit"),
                                        ticker=data.get("ticker") or raw_daily.get("ticker"))
    from copy import deepcopy
    from market_price_reconciliation import reconcile
    for key in ("price_adjustment_basis", "price_basis_contract", "volume_basis", "retrieved_at", "history_query", "session_recovery", "provider_raw_observation", "official_observation"):
        if key in raw_daily:
            value=raw_daily[key]
            if key in ("provider_raw_observation", "official_observation") and isinstance(value,dict):
                observation_day=parse_market_date(value.get("date"))
                if observation_day and observation_day>as_of:continue
            daily[key]=deepcopy(value)
    if "quarantined_session_rows" in raw_daily:
        prior = raw_daily["quarantined_session_rows"]
        existing = daily.setdefault("quarantined_session_rows", [])
        entries = prior if isinstance(prior, list) else [
            {"date": None, "state": "unknown", "reason": "quarantine_metadata_invalid", "unparsed_value": deepcopy(prior)}]
        for row in entries:
            retained = deepcopy(row) if isinstance(row, dict) else {
                "date": None, "state": "unknown", "reason": "quarantine_metadata_invalid", "unparsed_value": deepcopy(row)}
            observation_day = parse_market_date(retained.get("date"))
            # A malformed date cannot establish that an unresolved row lies
            # outside this projection. Preserve it rather than silently upgrade.
            if observation_day is not None and observation_day > as_of:
                continue
            if retained not in existing:
                existing.append(retained)
        from market_session_admission import assess_daily_session_integrity
        daily["session_integrity"] = assess_daily_session_integrity(daily, ticker=data.get("ticker"))
        if daily.get("calendar_admission_applied") and not daily["session_integrity"]["eligible"]:
            daily["availability"] = "partial" if daily["bars"] else "unavailable"
    original_excluded = raw_daily.get("excluded_row_count")
    if type(original_excluded) is int and original_excluded >= 0:
        daily["excluded_row_count"] = max(daily["excluded_row_count"], original_excluded)
    daily["price_reconciliation"]=reconcile(daily)
    admitted = not daily.get("calendar_admission_applied") or daily.get("session_integrity", {}).get("eligible")
    indicators = calculate_technical_indicators(daily if admitted else {**daily, "bars": []})
    if not admitted:
        indicators["session_admission_status"] = "unverifiable"
    displayed = daily["bars"][-(5 if compact else 20):]
    return {
        "as_of": as_of.isoformat(),
        "daily_market_data": {**daily, "bars": displayed, "displayed_sample_count": len(displayed)},
        "technical_indicators": indicators,
        "event_calendar": future_event_context(data.get("event_calendar"), as_of=as_of),
    }
