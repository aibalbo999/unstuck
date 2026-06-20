"""Pure trigger evaluation for event-driven watchlist radar."""

from __future__ import annotations

import re
from datetime import date
from statistics import mean
from typing import Any

from pipeline_modes import normalize_pipeline_run_id


BEARISH_TRIGGERS = {"price_below_sma", "foreign_sell_streak", "vix_above"}
TRIGGER_LABELS = {
    "price_below_sma": "股價跌破均線",
    "foreign_sell_streak": "外資連續賣超",
    "vix_above": "VIX 飆升",
    "revenue_record_high": "營收創高",
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
        }.get(trigger_type)
        if evaluator is None:
            continue
        matched, message, metrics = evaluator(trigger, data)
        selected = "v3" if trigger_type in BEARISH_TRIGGERS else ("v2" if trigger_type == "revenue_record_high" else source_pipeline)
        events.append({
            "ticker": ticker,
            "pipeline": source_pipeline,
            "trigger_key": str(trigger.get("key") or trigger_type),
            "trigger_type": trigger_type,
            "evaluation_date": evaluation_date or date.today().isoformat(),
            "matched": bool(matched),
            "pipeline_selected": selected if matched else source_pipeline,
            "message": message,
            "metrics": metrics,
            "label": TRIGGER_LABELS.get(trigger_type, trigger_type),
        })
    return events


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
    del trigger
    revenues = [_parse_revenue_value(item) for item in data.get("recent_monthly_revenue") or []]
    values = [value for value in revenues if value is not None]
    if len(values) < 2:
        return False, "月營收資料不足，無法判定創高", {"samples": len(values)}
    latest, previous_max = values[-1], max(values[:-1])
    matched = latest >= previous_max
    return matched, f"最新月營收 {latest:.2f} {'創近期高' if matched else '未創高'}", {"latest": latest, "previous_max": previous_max}


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
