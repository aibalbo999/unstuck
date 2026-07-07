"""Pure trigger evaluation for event-driven watchlist radar."""

from __future__ import annotations

import re
from datetime import date, datetime
from statistics import mean
from typing import Any

from pipeline_modes import normalize_pipeline_run_id


BEARISH_TRIGGERS = {"price_below_sma", "foreign_sell_streak", "vix_above"}
TRIGGER_LABELS = {
    "price_below_sma": "股價跌破均線",
    "foreign_sell_streak": "外資連續賣超",
    "vix_above": "VIX 飆升",
    "revenue_record_high": "營收創高",
    "report_catalyst": "報告催化條件",
    "daily_screener": "每日市場掃描",
    "event_upcoming": "關鍵日期提醒",
    "price_near_level": "價格接近關鍵價位",
}


def evaluate_watchlist_triggers(item: dict, data: dict, *, evaluation_date: str | None = None) -> list[dict[str, Any]]:
    ticker = str(item.get("ticker") or data.get("ticker") or "").strip().upper()
    source_pipeline = normalize_pipeline_run_id(item.get("pipeline") or "v1")
    events = []
    for trigger in item.get("triggers") or []:
        if not isinstance(trigger, dict) or trigger.get("enabled") is False:
            continue
        trigger_type = str(trigger.get("type") or "").strip()
        evaluator = {
            "price_below_sma": _price_below_sma,
            "foreign_sell_streak": _foreign_sell_streak,
            "vix_above": _vix_above,
            "revenue_record_high": _revenue_record_high,
            "report_catalyst": _report_catalyst,
            "daily_screener": _daily_screener,
            "event_upcoming": _event_upcoming,
            "price_near_level": _price_near_level,
        }.get(trigger_type)
        if evaluator is None:
            continue
        actual_evaluation_date = _monthly_evaluation_date(trigger_type, evaluation_date)
        trigger_for_eval = {**trigger, "evaluation_date": actual_evaluation_date}
        matched, message, metrics = evaluator(trigger_for_eval, data)
        selected = _selected_pipeline(trigger_type, trigger, source_pipeline)
        events.append({
            "ticker": ticker,
            "pipeline": source_pipeline,
            "trigger_key": str(trigger.get("key") or trigger_type),
            "trigger_type": trigger_type,
            "evaluation_date": actual_evaluation_date,
            "matched": bool(matched),
            "pipeline_selected": selected if matched else source_pipeline,
            "message": message,
            "metrics": metrics,
            "label": TRIGGER_LABELS.get(trigger_type, trigger_type),
        })
    return events


def _monthly_evaluation_date(trigger_type: str, evaluation_date: str | None) -> str:
    base = evaluation_date or date.today().isoformat()
    if trigger_type != "revenue_record_high":
        return base
    match = re.match(r"^(\d{4})-(\d{2})", str(base or ""))
    if not match:
        return base
    return f"{match.group(1)}-{match.group(2)}-01"


def _selected_pipeline(trigger_type: str, trigger: dict, source_pipeline: str) -> str:
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


def _prices(data: dict) -> list[float]:
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


def _price_below_sma(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    period = max(2, int(trigger.get("sma_days") or trigger.get("period") or 60))
    prices = _prices(data)
    if len(prices) < period:
        return False, f"價格資料不足，無法計算 {period} 日均線", {"period": period, "samples": len(prices)}
    current = float(data.get("current_price") or prices[-1])
    sma = mean(prices[-period:])
    matched = current < sma
    return matched, f"現價 {current:.2f} {'跌破' if matched else '仍高於'} {period} 日均線 {sma:.2f}", {"price": current, "sma": round(sma, 4), "period": period}


def _foreign_sell_streak(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    days = max(1, int(trigger.get("days") or 3))
    min_lots = abs(float(trigger.get("min_lots") or trigger.get("threshold") or 0))
    trading = data.get("institutional_trading") if isinstance(data.get("institutional_trading"), dict) else {}
    rows = trading.get("daily_total_net_buy_last_10") if isinstance(trading.get("daily_total_net_buy_last_10"), list) else []
    values = []
    for row in rows[-days:]:
        if not isinstance(row, dict):
            continue
        try:
            values.append(float(row.get("net_buy_thousand_shares")))
        except (TypeError, ValueError):
            continue
    matched = len(values) == days and all(value <= -min_lots for value in values)
    total = sum(values) if values else 0
    return matched, f"外資近 {days} 日合計 {total:.0f} 張", {"days": days, "min_lots": min_lots, "values": values}


def _vix_above(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    threshold = float(trigger.get("threshold") or 30)
    macro = data.get("macro_indicators") if isinstance(data.get("macro_indicators"), dict) else {}
    indicators = macro.get("indicators") if isinstance(macro.get("indicators"), dict) else {}
    vix = indicators.get("vix") if isinstance(indicators.get("vix"), dict) else {}
    value = _safe_float(vix.get("value"))
    matched = value is not None and value > threshold
    label = f"VIX {value:.2f}" if value is not None else "VIX 無資料"
    return matched, f"{label} {'高於' if matched else '未高於'} {threshold:.2f}", {"vix": value, "threshold": threshold}


def _revenue_record_high(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    revenues = [_parse_revenue_value(item) for item in data.get("recent_monthly_revenue") or []]
    values = [value for value in revenues if value is not None]
    if len(values) < 2:
        return False, "月營收資料不足，無法判定創高", {"samples": len(values)}
    latest, previous_max = values[-1], max(values[:-1])
    revenue_record = latest >= previous_max
    volume_ratio, volume_threshold, volume_confirmed = _volume_confirmation(trigger, data)
    matched = revenue_record and volume_confirmed
    volume_note = ""
    if volume_ratio is not None:
        volume_note = f"，量能 {volume_ratio:.2f}x {'確認' if volume_confirmed else '未確認'}"
    return (
        matched,
        f"最新月營收 {latest:.2f} {'創近期高' if revenue_record else '未創高'}{volume_note}",
        {
            "latest": latest,
            "previous_max": previous_max,
            "revenue_record": revenue_record,
            "volume_ratio": volume_ratio,
            "volume_threshold": volume_threshold,
            "volume_confirmed": volume_confirmed,
        },
    )


def _volume_confirmation(trigger: dict, data: dict) -> tuple[float | None, float, bool]:
    threshold = float(trigger.get("volume_ratio_threshold") or 1.3)
    volumes = _volumes(data)
    if len(volumes) < 5:
        return None, threshold, True
    sample = volumes[-20:]
    avg_volume = mean(sample)
    if avg_volume <= 0:
        return None, threshold, True
    ratio = sample[-1] / avg_volume
    return round(ratio, 4), threshold, ratio >= threshold


def _volumes(data: dict) -> list[float]:
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


def _report_catalyst(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    condition = str(trigger.get("trigger_condition") or "").strip()
    if not condition:
        return False, "報告催化條件未設定", {"condition": ""}
    haystack = _flatten_text(data)
    matched = bool(haystack and condition in haystack)
    status = "已在新資料中出現" if matched else "尚未在新資料中出現"
    return matched, f"報告催化條件「{condition[:80]}」{status}", {"condition": condition}


def _daily_screener(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    del data
    reason = str(trigger.get("reason") or "Daily Market Screener 命中").strip()
    metrics = trigger.get("metrics") if isinstance(trigger.get("metrics"), dict) else {}
    payload = {
        **metrics,
        "category": str(trigger.get("category") or ""),
        "categories": trigger.get("categories") if isinstance(trigger.get("categories"), list) else [],
        "screen_date": str(trigger.get("screen_date") or ""),
        "score": trigger.get("score"),
    }
    return True, reason[:240], payload


def _event_upcoming(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    event_type = str(trigger.get("event_type") or "").strip()
    days_before = max(0, int(trigger.get("days_before") or 14))
    evaluation_date = _parse_iso_date(trigger.get("evaluation_date")) or date.today()
    target_date = _parse_iso_date(trigger.get("target_date"))
    event = _matching_calendar_event(data, event_type, target_date)
    event_date = _parse_iso_date(event.get("date")) if event else target_date
    label = str(trigger.get("label") or event.get("label") if event else trigger.get("label") or event_type or "事件").strip()
    if event_date is None:
        return False, f"{label} 日期資料不足，無法建立提醒", {"event_type": event_type, "days_before": days_before}
    days_until = (event_date - evaluation_date).days
    matched = 0 <= days_until <= days_before
    window_text = f"{days_before} 天提醒窗口"
    status = "已進入" if matched else "尚未進入"
    return (
        matched,
        f"{label} {event_date.isoformat()} {status} {window_text}",
        {
            "event_type": event_type,
            "target_date": event_date.isoformat(),
            "days_before": days_before,
            "days_until": days_until,
        },
    )


def _price_near_level(trigger: dict, data: dict) -> tuple[bool, str, dict]:
    target = _safe_float(trigger.get("target_price"))
    threshold = abs(_safe_float(trigger.get("threshold_pct")) or 5.0)
    current = _safe_float(data.get("current_price"))
    if current is None:
        prices = _prices(data)
        current = prices[-1] if prices else None
    label = str(trigger.get("label") or "關鍵價位").strip()
    if current is None or target is None or target == 0:
        return False, f"{label} 價格資料不足", {"price": current, "target_price": target, "threshold_pct": threshold}
    distance = round((current / target - 1) * 100, 2)
    matched = abs(distance) <= threshold
    status = "已接近" if matched else "尚未接近"
    return (
        matched,
        f"{label}：現價 {current:.2f} {status} {target:.2f}（距離 {distance:+.2f}%）",
        {
            "price": current,
            "target_price": target,
            "threshold_pct": threshold,
            "distance_pct": distance,
        },
    )


def _matching_calendar_event(data: dict, event_type: str, target_date: date | None) -> dict:
    calendar = data.get("event_calendar") if isinstance(data.get("event_calendar"), dict) else {}
    events = calendar.get("events") if isinstance(calendar.get("events"), list) else []
    for item in events:
        if not isinstance(item, dict):
            continue
        if event_type and str(item.get("type") or "") != event_type:
            continue
        item_date = _parse_iso_date(item.get("date"))
        if target_date and item_date != target_date:
            continue
        return item
    return {}


def _parse_iso_date(value: object) -> date | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_text(item) for item in value)
    return str(value or "")


def _parse_revenue_value(value: object) -> float | None:
    if isinstance(value, dict):
        value = value.get("revenue") or value.get("value")
    text = str(value or "")
    match = re.search(r"([-+]?\d+(?:\.\d+)?)", text.replace(",", ""))
    number = _safe_float(match.group(1)) if match else _safe_float(value)
    if number is None:
        return None
    if "億" in text:
        return number * 100_000_000
    if "萬" in text:
        return number * 10_000
    return number


def _safe_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
