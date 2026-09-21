"""Bounded event-calendar projection with explicit date certainty."""

from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_market_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def future_event_context(calendar, *, as_of: date, horizon_days=14, limit=12) -> dict:
    calendar = calendar if isinstance(calendar, dict) else {}
    raw_events = calendar.get("events")
    raw_events = raw_events if isinstance(raw_events, (list, tuple)) else []
    end = as_of + timedelta(days=horizon_days)
    events, undated = [], []
    excluded = 0
    invalid = 0
    sourced_dated = 0
    for raw in raw_events:
        if not isinstance(raw, dict):
            invalid += 1
            continue
        label = str(raw.get("label") or raw.get("event_name") or raw.get("type") or "").strip()
        if not label:
            invalid += 1
            continue
        start_date, end_date = parse_market_date(raw.get("date")), parse_market_date(raw.get("end_date"))
        event = {"type": str(raw.get("type") or "")[:80], "label": label[:240],
                 "source": str(raw.get("source") or "")[:240],
                 "source_url": str(raw.get("source_url") or raw.get("url") or "")[:1000]}
        if start_date is None:
            undated.append({**event, "date": None, "date_status": "date_unknown"})
            continue
        if end_date and end_date < start_date:
            undated.append({**event, "date": None, "date_status": "date_unknown", "date_issue": "invalid_date_range"})
            continue
        if event["source"]:
            sourced_dated += 1
        else:
            invalid += 1
        if (end_date or start_date) < as_of or start_date > end:
            excluded += 1
            continue
        # A provider's single date is scheduled, not proof that an issuer confirmed it.
        status = "date_range" if end_date and end_date != start_date else (
            "confirmed" if raw.get("date_status") == "confirmed" or raw.get("confirmed") is True else "scheduled"
        )
        events.append({**event, "date": start_date.isoformat(),
                       "end_date": end_date.isoformat() if end_date else None, "date_status": status})
    events.sort(key=lambda item: (item["date"], item["label"]))
    source_failed = str(calendar.get("status") or "").lower() in {
        "failed", "error", "timeout", "unavailable", "unsupported",
    }
    source_date = parse_market_date(calendar.get("as_of_date") or calendar.get("as_of"))
    source_date_future = source_date is not None and source_date > as_of
    source_invalid = source_failed or source_date_future
    explicit_empty_success = (calendar.get("status") == "success" and
        bool(calendar.get("source")) and
        source_date is not None and
        isinstance(calendar.get("events"), (list, tuple)) and not raw_events)
    known_empty = (not events and not undated and not source_invalid and not invalid and
                   (sourced_dated > 0 or explicit_empty_success))
    availability = ("partial" if source_invalid and events else "unavailable" if source_invalid
                    else "available" if events else "date_unknown" if undated
                    else "known_empty" if known_empty else "unavailable")
    reasons = (["event_source_failed"] if source_failed else
               ["event_source_date_future"] if source_date_future else
               ["no_events_in_provided_calendar_window"] if known_empty else
               ["event_dates_unknown"] if undated else
               ["event_source_unknown"] if not events else [])
    return {
        "as_of": as_of.isoformat(), "window_end": end.isoformat(), "horizon_calendar_days": horizon_days,
        "source_as_of": str(calendar.get("as_of_date") or calendar.get("as_of") or "")[:40],
        "availability": availability,
        "reason_codes": reasons,
        "empty_scope": "provided_calendar_window" if known_empty else None,
        "events": events[:limit], "undated_events": undated[:limit],
        "excluded_outside_window_count": excluded,
        "notes": ["日期未定事件不得視為已確認的未來 14 日催化劑；歷史新聞日期不是事件發生日。"],
    }
