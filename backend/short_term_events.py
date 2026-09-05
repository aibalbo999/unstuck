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
    for raw in raw_events:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or raw.get("event_name") or raw.get("type") or "").strip()
        if not label:
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
    return {
        "as_of": as_of.isoformat(), "window_end": end.isoformat(), "horizon_calendar_days": horizon_days,
        "source_as_of": str(calendar.get("as_of_date") or calendar.get("as_of") or "")[:40],
        "availability": "available" if events else "date_unknown" if undated else "unavailable",
        "events": events[:limit], "undated_events": undated[:limit],
        "excluded_outside_window_count": excluded,
        "notes": ["日期未定事件不得視為已確認的未來 14 日催化劑；歷史新聞日期不是事件發生日。"],
    }
