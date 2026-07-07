from __future__ import annotations

from typing import Any

from .utils import _number, _percent_change, _signed_percent_label, _text, _trend_return


def _price_trend(data: dict[str, Any]) -> dict[str, Any]:
    history = data.get("price_history") if isinstance(data.get("price_history"), dict) else {}
    points = _price_points(data)[-12:]
    latest = points[-1]["price"] if points else None
    first = points[0]["price"] if points else None
    return {
        "label": "近一年月收盤",
        "source": _text(history.get("source")) or "price_history",
        "latest_price": latest,
        "start_price": first,
        "returns": {
            "1m": _trend_return(points, 1),
            "3m": _trend_return(points, 3),
            "1y": _trend_return(points, len(points) - 1),
        },
        "sparkline": points,
    }

def _performance_history(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("price_history_ranges") if isinstance(data.get("price_history_ranges"), dict) else {}
    ranges_source = source.get("ranges") if isinstance(source.get("ranges"), dict) else {}
    ranges = []
    for key in ("1m", "3m", "6m", "1y", "3y", "5y"):
        item = ranges_source.get(key) if isinstance(ranges_source.get(key), dict) else {}
        entry = _performance_range(key, item)
        if entry:
            ranges.append(entry)
    if not ranges:
        fallback = _performance_range_from_price_history(data)
        if fallback:
            ranges.append(fallback)
    if not ranges:
        return {
            "status": "insufficient_data",
            "label": "多週期走勢不足",
            "default_range": "",
            "ranges": [],
            "source": "",
        }
    default_range = "1y" if any(item["key"] == "1y" for item in ranges) else ranges[0]["key"]
    return {
        "status": "available",
        "label": "多週期走勢",
        "default_range": default_range,
        "ranges": ranges,
        "source": _text(source.get("source")) or "price_history",
    }

def _performance_range(key: str, item: dict[str, Any]) -> dict[str, Any]:
    dates = list(item.get("dates") or [])
    prices = list(item.get("prices") or [])
    points = []
    for date_text, price in zip(dates, prices, strict=False):
        number = _number(price)
        if number is not None and _text(date_text):
            points.append({"date": _text(date_text), "price": number})
    if len(points) < 2:
        return {}
    return_pct = _number(item.get("return_pct"))
    if return_pct is None:
        return_pct = _percent_change(points[-1]["price"], points[0]["price"])
    return {
        "key": key,
        "label": _text(item.get("label")) or key.upper(),
        "start_price": points[0]["price"],
        "end_price": points[-1]["price"],
        "return_pct": return_pct,
        "points": points,
    }

def _performance_range_from_price_history(data: dict[str, Any]) -> dict[str, Any]:
    points = _price_points(data)
    if len(points) < 2:
        return {}
    return {
        "key": "1y",
        "label": "1Y",
        "start_price": points[0]["price"],
        "end_price": points[-1]["price"],
        "return_pct": _percent_change(points[-1]["price"], points[0]["price"]),
        "points": points,
    }

def _technical_summary(data: dict[str, Any]) -> dict[str, Any]:
    points = _price_points(data)[-12:]
    prices = [point["price"] for point in points]
    current_price = _number(data.get("current_price"), prices[-1] if prices else None)
    if current_price is None or len(prices) < 3:
        return {
            "status": "insufficient_data",
            "label": "技術資料不足",
            "moving_averages": {},
            "range_52w": {},
            "momentum": {},
            "signals": [],
        }

    momentum = {
        "1m": _trend_return(points, 1),
        "3m": _trend_return(points, 3),
        "1y": _trend_return(points, len(points) - 1),
    }
    moving_averages = {
        "ma_3m": _moving_average_entry("3M 均線", prices, 3, current_price),
        "ma_6m": _moving_average_entry("6M 均線", prices, 6, current_price),
        "ma_12m": _moving_average_entry("12M 均線", prices, 12, current_price),
    }
    range_52w = _technical_range(data, prices, current_price)
    return {
        "status": "available",
        "label": _technical_label(
            current_price,
            moving_averages["ma_3m"]["value"],
            moving_averages["ma_6m"]["value"],
            momentum.get("3m"),
        ),
        "latest_price": current_price,
        "moving_averages": moving_averages,
        "range_52w": range_52w,
        "momentum": momentum,
        "signals": _technical_signals(current_price, moving_averages, range_52w, momentum),
    }

def _price_points(data: dict[str, Any]) -> list[dict[str, Any]]:
    history = data.get("price_history") if isinstance(data.get("price_history"), dict) else {}
    dates = list(history.get("dates") or [])
    prices = list(history.get("prices") or [])
    points = []
    for date, price in zip(dates, prices, strict=False):
        number = _number(price)
        if number is not None and _text(date):
            points.append({"date": _text(date), "price": number})
    return points

def _moving_average_entry(label: str, prices: list[float], period: int, current_price: float) -> dict[str, Any]:
    average = _moving_average(prices, period)
    return {
        "label": label,
        "value": average,
        "distance_pct": _percent_change(current_price, average),
    }

def _moving_average(prices: list[float], period: int) -> float | None:
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 2)

def _technical_range(data: dict[str, Any], prices: list[float], current_price: float) -> dict[str, Any]:
    low = _number(data.get("week_52_low"), min(prices) if prices else None)
    high = _number(data.get("week_52_high"), max(prices) if prices else None)
    if low is None or high is None:
        return {"low": low, "high": high, "position_pct": None, "drawdown_from_high_pct": None}
    low = min(low, current_price)
    high = max(high, current_price)
    span = high - low
    position_pct = round(((current_price - low) / span) * 100, 2) if span > 0 else None
    return {
        "low": low,
        "high": high,
        "position_pct": position_pct,
        "drawdown_from_high_pct": _percent_change(current_price, high),
    }

def _technical_label(
    current_price: float,
    ma_3m: float | None,
    ma_6m: float | None,
    momentum_3m: float | None,
) -> str:
    if ma_3m is None or ma_6m is None or momentum_3m is None:
        return "技術資料不足"
    if current_price >= ma_3m and ma_3m >= ma_6m and momentum_3m >= 0:
        return "上升趨勢"
    if current_price <= ma_3m and ma_3m <= ma_6m and momentum_3m <= 0:
        return "轉弱"
    return "震盪整理"

def _technical_signals(
    current_price: float,
    moving_averages: dict[str, dict[str, Any]],
    range_52w: dict[str, Any],
    momentum: dict[str, float | None],
) -> list[str]:
    signals = []
    ma_3m = _number(moving_averages.get("ma_3m", {}).get("value"))
    ma_6m = _number(moving_averages.get("ma_6m", {}).get("value"))
    if ma_3m is not None and ma_6m is not None:
        if current_price >= ma_3m and current_price >= ma_6m:
            signals.append("現價高於 3M / 6M 均線")
        elif current_price <= ma_3m and current_price <= ma_6m:
            signals.append("現價低於 3M / 6M 均線")
        else:
            signals.append("均線訊號分歧")

    position = _number(range_52w.get("position_pct"))
    if position is not None:
        if position >= 80:
            signals.append("接近 52 週高檔")
        elif position <= 20:
            signals.append("接近 52 週低檔")
        else:
            signals.append("位於 52 週中段")

    momentum_3m = _number(momentum.get("3m"))
    if momentum_3m is not None:
        signals.append(f"3M 動能 {_signed_percent_label(momentum_3m)}")
    return signals[:3]
