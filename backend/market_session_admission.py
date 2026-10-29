"""Pure daily session admission; internal consistency is not price verification."""
from datetime import date, timedelta

from market_calendar_store import load_market_calendar, session_day_status


MAX_SESSION_WINDOW_CALENDAR_DAYS = 370
UNRESOLVED_SOURCE_REASONS = {"conflicting_duplicate_session", "duplicate_session_evidence_unusable",
                             "quarantine_metadata_invalid"}


def _diagnostic_date(value):
    return value if isinstance(value, (str, type(None))) else str(value)[:100]


def _quarantine_issues(daily, *, market, ticker):
    """Keep unresolved source defects even after normalization removes a row."""
    if "quarantined_session_rows" not in daily:
        return [], []
    rows = daily["quarantined_session_rows"]
    if not isinstance(rows, list):
        return [None], ["quarantine_metadata_invalid"]
    dates, reasons = [], []
    for row in rows:
        if not isinstance(row, dict):
            dates.append(None)
            reasons.append("quarantine_metadata_invalid")
            continue
        value = row.get("date")
        reason = row.get("reason")
        if isinstance(reason, str) and reason in UNRESOLVED_SOURCE_REASONS:
            dates.append(_diagnostic_date(value))
            reasons.append(reason)
            continue
        if row.get("state") not in ("unknown", "closed"):
            dates.append(_diagnostic_date(value))
            reasons.append("quarantine_metadata_invalid")
            continue
        assessment = session_day_status(value, market=market,
                                        exchange="TPEX" if str(ticker).upper().endswith(".TWO") else "TWSE")
        if assessment["state"] != "closed":
            dates.append(_diagnostic_date(value))
            reasons.append(assessment["reason"] if assessment["state"] == "unknown"
                           else "excluded_session_requires_reacquisition")
    return dates, reasons


def market_for_ticker(ticker):
    value = str(ticker or "").strip().upper()
    if value.endswith((".TW", ".TWO")):
        return "tw"
    # A bare symbol can represent several exchanges. Do not guess a calendar.
    return None


def assess_daily_session_integrity(daily, *, ticker=None):
    """Recheck every supplied date; ignore any stored admission/verified flags.

    eligible is confined to calendar admission. It proves neither prices nor
    whole-window exchange evidence, and does not remove/rewrite supplied bars.
    """
    daily = daily if isinstance(daily, dict) else {}
    raw = daily.get("provider_raw_observation")
    ticker = ticker or daily.get("ticker") or (raw.get("ticker") if isinstance(raw, dict) else None)
    market = market_for_ticker(ticker)
    result = {"status": "unverifiable", "eligible": False, "market": market,
              "reason_codes": [], "rejected_dates": [], "closed_dates": [], "unverified_dates": [],
              "missing_expected_dates": [],
              "calendar_provenance": [], "verification_scope": "session_calendar_admission_only",
              "official_price_verified": False, "historical_point_in_time_verified": False}
    unresolved_dates, unresolved_reasons = _quarantine_issues(daily, market=market, ticker=ticker)
    result["unverified_dates"].extend(unresolved_dates)
    result["reason_codes"].extend(unresolved_reasons)
    bars = daily.get("bars")
    if not isinstance(bars, list) or not bars:
        result["reason_codes"].append("session_bars_missing")
        return result
    if market is None:
        result["reason_codes"].append("session_market_unbound")
        return result
    calendars = {}
    previous = None
    provided_dates = set()
    for bar in bars:
        value = bar.get("date") if isinstance(bar, dict) else None
        try:
            day = date.fromisoformat(value)
        except (TypeError, ValueError):
            result["reason_codes"].append("invalid_session_date")
            result["rejected_dates"].append(value if isinstance(value, (str, type(None))) else str(value)[:100])
            continue
        if previous is not None and day <= previous:
            result["reason_codes"].append("session_dates_not_strictly_ordered")
            result["rejected_dates"].append(value)
        previous = day
        provided_dates.add(day)
        if day.year not in calendars:
            calendars[day.year] = load_market_calendar(market, day.year)
        assessment = session_day_status(day, market=market, calendar=calendars[day.year],
                                        exchange="TPEX" if str(ticker).upper().endswith(".TWO") else "TWSE")
        if assessment["state"] != "open":
            target = "rejected_dates" if assessment["state"] == "closed" else "unverified_dates"
            result[target].append(value)
            result["reason_codes"].append(assessment["reason"])
            if assessment["state"] == "closed":
                result["closed_dates"].append(value)
    # A list containing only legal dates can still omit a trading session.
    # Check the bounded observed window, not dates before the first bar or
    # after the last one. An absent security quote is not evidence of a market
    # holiday or issuer suspension, and is never filled with a zero row.
    if provided_dates:
        first, last = min(provided_dates), max(provided_dates)
        span = (last - first).days
        if span > MAX_SESSION_WINDOW_CALENDAR_DAYS:
            result["unverified_dates"].append(first.isoformat())
            result["reason_codes"].append("session_window_exceeds_bounded_calendar_check")
        else:
            for offset in range(span + 1):
                day = first + timedelta(days=offset)
                if day in provided_dates:
                    continue
                if day.year not in calendars:
                    calendars[day.year] = load_market_calendar(market, day.year)
                assessment = session_day_status(day, market=market, calendar=calendars[day.year],
                                                exchange="TPEX" if str(ticker).upper().endswith(".TWO") else "TWSE")
                if assessment["state"] == "open":
                    result["missing_expected_dates"].append(day.isoformat())
                    result["unverified_dates"].append(day.isoformat())
                    result["reason_codes"].append("expected_session_bar_missing")
                elif assessment["state"] == "unknown":
                    result["unverified_dates"].append(day.isoformat())
                    result["reason_codes"].append(assessment["reason"])
    last_day = bars[-1].get("date") if isinstance(bars[-1], dict) else None
    if not daily.get("as_of"):
        result["reason_codes"].append("session_as_of_unbound")
        value = daily.get("as_of")
        result["unverified_dates"].append(value if isinstance(value, (str, type(None))) else str(value)[:100])
    elif daily.get("as_of") != last_day:
        result["reason_codes"].append("session_as_of_mismatch")
        value = daily.get("as_of")
        result["rejected_dates"].append(value if isinstance(value, str) else str(value)[:100])
    result["reason_codes"] = sorted(set(result["reason_codes"]))
    result["rejected_dates"] = list(dict.fromkeys(result["rejected_dates"]))
    result["unverified_dates"] = list(dict.fromkeys(result["unverified_dates"]))
    for year, calendar in sorted(calendars.items()):
        result["calendar_provenance"].append({"year": year, **{key: calendar.get(key) for key in
            ("source", "coverage_status", "calendar_version", "calendar_reference_url", "session_exceptions")}})
    result["status"] = ("invalid" if result["rejected_dates"] else "unverifiable" if result["unverified_dates"] else "consistent")
    result["eligible"] = result["status"] == "consistent"
    return result
