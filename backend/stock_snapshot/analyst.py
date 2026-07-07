from __future__ import annotations

from typing import Any

from .utils import _int, _label, _metric, _number, _pct_points, _percent_change, _signed_percent_label, _text


def _valuation(data: dict[str, Any], *, current_price: float | None, analyst_target: float | None) -> dict[str, Any]:
    return {
        "pe_ratio": _metric(data.get("pe_ratio_raw"), data.get("pe_ratio")),
        "forward_pe": _metric(data.get("forward_pe_raw"), data.get("forward_pe")),
        "pb_ratio": _metric(data.get("pb_ratio_raw"), data.get("pb_ratio")),
        "ps_ratio": _metric(data.get("ps_ratio_raw"), data.get("ps_ratio")),
        "analyst_target": {
            "price": analyst_target,
            "label": _label(data.get("analyst_target"), analyst_target),
            "recommendation": _text(data.get("analyst_rec")),
            "analyst_count": _int(data.get("analyst_count")),
            "upside_pct": _percent_change(analyst_target, current_price),
        },
        "pe_river_chart": data.get("pe_river_chart") if isinstance(data.get("pe_river_chart"), dict) else {},
    }

def _analyst_outlook(data: dict[str, Any], *, current_price: float | None, analyst_target: float | None) -> dict[str, Any]:
    recommendation = _text(data.get("analyst_rec"))
    recommendation_label = _recommendation_label(recommendation)
    analyst_count = _int(data.get("analyst_count"))
    upside_pct = _percent_change(analyst_target, current_price)
    forward_pe = _metric(data.get("forward_pe_raw"), data.get("forward_pe"))
    earnings_growth = _percent_metric(data.get("yahoo_earnings_growth_raw"), data.get("yahoo_earnings_growth") or data.get("earnings_growth"))
    revenue_growth = _percent_metric(data.get("latest_annual_revenue_growth_raw"), data.get("latest_annual_revenue_growth") or data.get("revenue_growth"))
    has_data = any(
        value not in (None, "")
        for value in (
            analyst_target,
            upside_pct,
            recommendation,
            analyst_count,
            forward_pe.get("value"),
            earnings_growth.get("value"),
            revenue_growth.get("value"),
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "分析師資料不足",
            "target": {},
            "consensus": {},
            "valuation": {},
            "growth": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _analyst_outlook_label(upside_pct, recommendation_label),
        "target": {
            "price": analyst_target,
            "label": _label(data.get("analyst_target"), analyst_target),
            "upside_pct": upside_pct,
        },
        "consensus": {
            "recommendation": recommendation,
            "recommendation_label": recommendation_label,
            "analyst_count": analyst_count,
        },
        "valuation": {
            "forward_pe": forward_pe,
        },
        "growth": {
            "earnings_growth": earnings_growth,
            "revenue_growth": revenue_growth,
        },
        "signals": _analyst_signals(upside_pct, analyst_count, recommendation_label, earnings_growth),
    }

def _percent_metric(raw: Any, label: Any) -> dict[str, Any]:
    value = _pct_points(raw, label)
    label_text = _text(label)
    if label_text and label_text.upper() not in {"N/A", "NA", "NONE", "NULL"}:
        return {"value": value, "label": label_text}
    return {"value": value, "label": "" if value is None else f"{value:g}%"}

def _recommendation_label(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return {
        "strong_buy": "強力買進",
        "buy": "買進",
        "outperform": "優於大盤",
        "overweight": "加碼",
        "hold": "持有",
        "neutral": "中立",
        "underperform": "劣於大盤",
        "underweight": "減碼",
        "sell": "賣出",
        "strong_sell": "強力賣出",
    }.get(normalized, value.strip())

def _analyst_outlook_label(upside_pct: float | None, recommendation_label: str) -> str:
    if upside_pct is not None:
        if upside_pct >= 5:
            return "目標價上行"
        if upside_pct <= -5:
            return "目標價下行"
        return "接近目標價"
    if recommendation_label:
        return f"共識{recommendation_label}"
    return "分析師展望"

def _analyst_signals(
    upside_pct: float | None,
    analyst_count: int | None,
    recommendation_label: str,
    earnings_growth: dict[str, Any],
) -> list[str]:
    signals = []
    if upside_pct is not None:
        direction = "上行" if upside_pct >= 0 else "下行"
        signals.append(f"目標價{direction} {_signed_percent_label(upside_pct)}")
    if analyst_count is not None and recommendation_label:
        signals.append(f"{analyst_count} 位分析師共識{recommendation_label}")
    elif recommendation_label:
        signals.append(f"分析師共識{recommendation_label}")
    elif analyst_count is not None:
        signals.append(f"{analyst_count} 位分析師覆蓋")
    earnings_growth_value = _number(earnings_growth.get("value"))
    if earnings_growth_value is not None:
        signals.append(f"EPS 成長 {_signed_percent_label(earnings_growth_value).lstrip('+')}")
    return signals[:3]

def _earnings_forecast(data: dict[str, Any], *, event_calendar: dict[str, Any]) -> dict[str, Any]:
    trailing_eps = _eps_metric(data.get("trailing_eps_raw"), data.get("trailing_eps"))
    forward_eps = _eps_metric(data.get("forward_eps_raw"), data.get("forward_eps"))
    forward_change = _percent_change(forward_eps.get("value"), trailing_eps.get("value"))
    earnings_growth = _percent_metric(
        data.get("yahoo_earnings_growth_raw"),
        data.get("yahoo_earnings_growth") or data.get("earnings_growth"),
    )
    revenue_growth = _percent_metric(
        data.get("yahoo_revenue_growth_raw"),
        data.get("yahoo_revenue_growth") or data.get("latest_annual_revenue_growth") or data.get("revenue_growth"),
    )
    analyst_count = _int(data.get("analyst_count"))
    next_earnings = _next_earnings_event(event_calendar)
    has_data = any(
        value not in (None, "", {})
        for value in (
            trailing_eps.get("value"),
            forward_eps.get("value"),
            forward_change,
            earnings_growth.get("value"),
            revenue_growth.get("value"),
            analyst_count,
            next_earnings,
        )
    )
    if not has_data:
        return {
            "status": "insufficient_data",
            "label": "盈餘預估不足",
            "trailing_eps": {},
            "forward_eps": {},
            "forward_eps_change_pct": None,
            "growth": {},
            "analyst_count": None,
            "next_earnings": {},
            "signals": [],
        }
    return {
        "status": "available",
        "label": _earnings_forecast_label(forward_change, earnings_growth.get("value")),
        "trailing_eps": trailing_eps,
        "forward_eps": forward_eps,
        "forward_eps_change_pct": forward_change,
        "growth": {
            "earnings_growth": earnings_growth,
            "revenue_growth": revenue_growth,
        },
        "analyst_count": analyst_count,
        "next_earnings": next_earnings,
        "signals": _earnings_forecast_signals(forward_change, earnings_growth.get("value"), analyst_count, next_earnings),
    }

def _eps_metric(*values: Any) -> dict[str, Any]:
    value = _number(*values)
    return {"value": value, "label": "" if value is None else f"{value:.2f}"}

def _next_earnings_event(event_calendar: dict[str, Any]) -> dict[str, Any]:
    events = event_calendar.get("events") if isinstance(event_calendar.get("events"), list) else []
    for event in events:
        if not isinstance(event, dict) or event.get("type") != "earnings_date":
            continue
        return {
            "type": _text(event.get("type")),
            "label": _text(event.get("label")) or "財報日",
            "date": _text(event.get("date")),
            "days_until": _int(event.get("days_until")),
        }
    return {}

def _earnings_forecast_label(forward_change: float | None, earnings_growth: float | None) -> str:
    growth = forward_change if forward_change is not None else earnings_growth
    if growth is None:
        return "盈餘預估"
    if growth >= 5:
        return "EPS 預期成長"
    if growth <= -5:
        return "EPS 預期下滑"
    return "EPS 持平觀察"

def _earnings_forecast_signals(
    forward_change: float | None,
    earnings_growth: float | None,
    analyst_count: int | None,
    next_earnings: dict[str, Any],
) -> list[str]:
    signals = []
    if forward_change is not None:
        signals.append(f"Forward EPS {_signed_percent_label(forward_change)}")
    if earnings_growth is not None:
        signals.append(f"EPS 成長 {_signed_percent_label(earnings_growth).lstrip('+')}")
    if analyst_count is not None:
        signals.append(f"{analyst_count} 位分析師覆蓋")
    elif next_earnings.get("date"):
        signals.append(f"下次財報 {next_earnings['date']}")
    return signals[:3]
