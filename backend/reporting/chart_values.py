"""Chart value normalization helpers for report rendering."""

from __future__ import annotations

from datetime import datetime

from mapping_fields import safe_sequence_items, safe_text
from numeric_safety import is_non_finite_number


def filter_future_price_history(price_history: dict) -> dict:
    """移除標示日期晚於今天的股價點，避免圖表出現未來收盤價。"""
    if not isinstance(price_history, dict):
        return {}
    dates = safe_sequence_items(price_history.get("dates", []))
    prices = safe_sequence_items(price_history.get("prices", []))
    today = datetime.now().date()
    if len(dates) == 0 or len(prices) == 0:
        kept = {}
        for raw_date, price in price_history.items():
            date_text = safe_text(raw_date).strip()
            try:
                date_val = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                continue
            if date_val <= today:
                kept[date_text] = price
        return kept

    kept_dates = []
    kept_prices = []
    for date_str, price in zip(dates, prices):
        date_text = safe_text(date_str).strip()
        try:
            date_val = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            continue
        if date_val <= today:
            kept_dates.append(date_text)
            kept_prices.append(price)
    return {"dates": kept_dates, "prices": kept_prices}


def normalize_moat_scores(moat_scores: dict) -> dict:
    """只保留雷達圖允許的護城河維度，避免草稿筆記被解析成圖表軸。"""
    allowed = ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"]
    if not isinstance(moat_scores, dict):
        return {}
    return {
        key: moat_scores[key]
        for key in allowed
        if key in moat_scores
        and isinstance(moat_scores[key], (int, float))
        and not isinstance(moat_scores[key], bool)
    }


def billion_twd_series_to_yi_twd(values: list) -> list:
    """Convert chart money series from billion_twd to 億台幣 for display."""
    converted = []
    for value in safe_sequence_items(values):
        if isinstance(value, bool) or value is None:
            converted.append(value)
            continue
        if is_non_finite_number(value):
            converted.append(None)
            continue
        if isinstance(value, (int, float)):
            converted.append(round(value * 10, 4))
            continue
        try:
            number = float(str(value).replace(",", ""))
            converted.append(None if is_non_finite_number(number) else round(number * 10, 4))
        except (TypeError, ValueError):
            converted.append(value)
    return converted
