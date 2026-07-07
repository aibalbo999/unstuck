from __future__ import annotations

from datetime import date, datetime
from typing import Any

from .utils import _int, _number, _percent_change, _text


def _events(data: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in data.get("recent_monthly_revenue") or []:
        if _text(item):
            events.append({"type": "monthly_revenue", "label": _text(item)})
    earnings_call = data.get("earnings_call")
    if isinstance(earnings_call, dict) and earnings_call:
        events.append({
            "type": "earnings_call",
            "label": _text(earnings_call.get("period")) or "法說會",
            "source": _text(earnings_call.get("source")),
            "excerpt": _text(earnings_call.get("transcript_excerpt")),
        })
    earnings_date = _text(data.get("earnings_date"))
    if earnings_date:
        events.append({"type": "earnings_date", "label": earnings_date})
    return events[:6]

def _event_calendar(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("event_calendar") if isinstance(data.get("event_calendar"), dict) else {}
    as_of = _parse_event_date(source.get("as_of_date")) or _parse_event_date(data.get("cache_generated_at")) or date.today()
    events = [_event_calendar_item(item, as_of) for item in source.get("events") or [] if isinstance(item, dict)]
    events = [item for item in events if item]
    if not events:
        return {
            "status": "insufficient_data",
            "label": "關鍵日期不足",
            "as_of_date": as_of.isoformat(),
            "next_event": {},
            "events": [],
        }

    upcoming = sorted((item for item in events if item["timing"] == "upcoming"), key=lambda item: item["date"])
    past = sorted((item for item in events if item["timing"] == "past"), key=lambda item: item["date"], reverse=True)
    ordered = [*upcoming, *past]
    next_event = upcoming[0] if upcoming else ordered[0]
    return {
        "status": "available",
        "label": f"下一事件：{next_event['label']}" if upcoming else "近期關鍵日期",
        "as_of_date": as_of.isoformat(),
        "next_event": next_event,
        "events": ordered[:6],
    }

def _alert_suggestions(
    data: dict[str, Any],
    *,
    current_price: float | None,
    analyst_target: float | None,
    event_calendar: dict[str, Any],
) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    next_event = event_calendar.get("next_event") if isinstance(event_calendar.get("next_event"), dict) else {}
    if next_event and next_event.get("timing") == "upcoming":
        event_type = _text(next_event.get("type"))
        event_date = _text(next_event.get("date"))
        event_label = _text(next_event.get("label")) or _event_type_label(event_type)
        if event_type and event_date:
            suggestions.append({
                "key": f"event_{event_type}_{event_date}",
                "category": "event",
                "label": _event_alert_label(event_type, event_label),
                "detail": f"{event_label} {event_date} 前 14 天提醒",
                "pipeline": "v4",
                "schedule_slots": ["pre_market"],
                "triggers": [
                    {
                        "type": "event_upcoming",
                        "event_type": event_type,
                        "target_date": event_date,
                        "days_before": 14,
                        "label": event_label,
                    }
                ],
            })

    if analyst_target is not None and current_price is not None:
        suggestions.append(_price_alert_suggestion(
            key="price_analyst_target",
            label="接近分析師目標價",
            target_price=analyst_target,
            threshold_pct=5.0,
        ))

    week_52_high = _number(data.get("week_52_high"))
    if week_52_high is not None:
        suggestions.append(_price_alert_suggestion(
            key="price_52w_high",
            label="接近 52 週高點",
            target_price=week_52_high,
            threshold_pct=3.0,
        ))

    if data.get("recent_monthly_revenue"):
        suggestions.append({
            "key": "monthly_revenue_record",
            "category": "fundamental",
            "label": "月營收創高提醒",
            "detail": "月營收公布後檢查是否創高並量能確認",
            "pipeline": "v2",
            "schedule_slots": ["post_market"],
            "triggers": [
                {"type": "revenue_record_high", "volume_ratio_threshold": 1.3}
            ],
        })

    if not suggestions:
        return {"status": "insufficient_data", "label": "提醒建議不足", "suggestions": []}
    suggestions = suggestions[:4]
    return {
        "status": "available",
        "label": f"建議設定 {len(suggestions)} 個提醒",
        "suggestions": suggestions,
    }

def _price_alert_suggestion(*, key: str, label: str, target_price: float, threshold_pct: float) -> dict[str, Any]:
    return {
        "key": key,
        "category": "price",
        "label": label,
        "detail": f"現價接近 {_price_text(target_price)} 時提醒",
        "pipeline": "v2",
        "schedule_slots": ["pre_market"],
        "triggers": [
            {
                "type": "price_near_level",
                "label": label,
                "target_price": target_price,
                "threshold_pct": threshold_pct,
            }
        ],
    }

def _event_alert_label(event_type: str, event_label: str) -> str:
    return {
        "earnings_date": "財報日前提醒",
        "ex_dividend_date": "除息日前提醒",
        "dividend_pay_date": "股利發放日前提醒",
    }.get(event_type, f"{event_label}前提醒")

def _price_text(value: float) -> str:
    text = f"{value:,.2f}"
    return text.rstrip("0").rstrip(".")

def _event_calendar_item(item: dict[str, Any], as_of: date) -> dict[str, Any]:
    event_date = _parse_event_date(item.get("date"))
    if event_date is None:
        return {}
    end_date = _parse_event_date(item.get("end_date"))
    days_until = (event_date - as_of).days
    return {
        "type": _text(item.get("type")),
        "label": _text(item.get("label")) or _event_type_label(_text(item.get("type"))),
        "date": event_date.isoformat(),
        "end_date": end_date.isoformat() if end_date and end_date != event_date else "",
        "date_label": _event_date_label(event_date, end_date),
        "timing": "upcoming" if days_until >= 0 else "past",
        "days_until": days_until,
        "source": _text(item.get("source")),
    }

def _event_date_label(event_date: date, end_date: date | None) -> str:
    if end_date and end_date != event_date:
        return f"{event_date.isoformat()} - {end_date.isoformat()}"
    return event_date.isoformat()

def _event_type_label(event_type: str) -> str:
    return {
        "earnings_date": "財報日",
        "ex_dividend_date": "除息日",
        "dividend_pay_date": "股利發放日",
        "most_recent_quarter": "最近財報季度",
        "fiscal_year_end": "會計年度結束",
    }.get(event_type, "事件")

def _parse_event_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text[:10]).date()
    except ValueError:
        return None

def _news(data: dict[str, Any]) -> list[dict[str, Any]]:
    records = data.get("recent_catalysts") if isinstance(data.get("recent_catalysts"), list) else []
    news = []
    for item in records[:6]:
        if not isinstance(item, dict):
            continue
        news.append({
            "title": _text(item.get("title")),
            "source": _text(item.get("source") or item.get("publisher")),
            "published_at": _text(item.get("published_at") or item.get("date")),
            "url": _text(item.get("url") or item.get("link")),
        })
    return [item for item in news if item["title"]]
