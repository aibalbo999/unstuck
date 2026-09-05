"""Deterministic daily indicators; missing samples are never synthesized."""

from __future__ import annotations

import math


def _finite(value):
    return round(value, 8) if value is not None and math.isfinite(value) else None


def _mean_tail(values, period):
    tail = values[-period:]
    return sum(tail) / period if len(tail) == period and all(v is not None for v in tail) else None


def _ema(values, period):
    """EMA seeded with the first period's SMA, then alpha=2/(period+1)."""
    result = [None] * len(values)
    if len(values) < period:
        return result
    average = sum(values[:period]) / period
    result[period - 1] = average
    alpha = 2 / (period + 1)
    for index in range(period, len(values)):
        average += alpha * (values[index] - average)
        result[index] = average
    return result


def _wilder(values, period):
    if len(values) < period or any(v is None for v in values):
        return None
    average = sum(values[:period]) / period
    for value in values[period:]:
        average = (average * (period - 1) + value) / period
    return average


def _rsi(closes, period=14):
    differences = [b - a for a, b in zip(closes, closes[1:])]
    gain = _wilder([max(v, 0) for v in differences], period)
    loss = _wilder([max(-v, 0) for v in differences], period)
    if gain is None or loss is None:
        return None
    if gain == loss == 0:
        return 50.0
    return 100.0 if loss == 0 else 100 - 100 / (1 + gain / loss)


def calculate_technical_indicators(daily: dict) -> dict:
    """Compute exclusively from the validated, stored daily bars (at most 120)."""
    bars = daily.get("bars") or []
    closes = [bar["close"] for bar in bars]
    volumes = [bar["volume"] for bar in bars]
    fast, slow = _ema(closes, 12), _ema(closes, 26)
    macd_series = [f - s for f, s in zip(fast, slow) if f is not None and s is not None]
    macd = macd_series[-1] if macd_series else None
    signal_series = _ema(macd_series, 9)
    signal = signal_series[-1] if signal_series else None
    true_ranges = []
    for previous, current in zip(bars, bars[1:]):
        high, low = current["high"], current["low"]
        true_ranges.append(None if high is None or low is None else max(
            high - low, abs(high - previous["close"]), abs(low - previous["close"]),
        ))
    volume_average = _mean_tail(volumes, 20)
    values = {
        **{f"sma_{period}": _mean_tail(closes, period) for period in (5, 10, 20, 60)},
        "rsi_14": _rsi(closes),
        "macd": macd,
        "macd_signal": signal,
        "macd_histogram": macd - signal if macd is not None and signal is not None else None,
        "atr_14": _wilder(true_ranges, 14),
        "volume_latest": volumes[-1] if volumes else None,
        "volume_sma_5": _mean_tail(volumes, 5),
        "volume_sma_20": volume_average,
        "volume_ratio_20": volumes[-1] / volume_average if volume_average and volumes[-1] is not None else None,
    }
    values = {key: _finite(value) for key, value in values.items()}
    missing = [key for key, value in values.items() if value is None]
    return {
        "as_of": daily.get("as_of"), "sample_count": len(bars),
        "source": daily.get("source"),
        "availability": "unavailable" if not bars else "partial" if missing else "available",
        "missing_indicators": missing,
        "calculation_policy": {
            "input": "daily_market_data.bars; no missing-session or OHLC interpolation",
            "sma": "Arithmetic mean of final N closes",
            "rsi_14": "14 price changes; SMA seed then Wilder smoothing; flat=50, zero loss=100",
            "macd": "EMA12-EMA26; SMA-seeded EMAs; signal EMA9 requires 34 closes",
            "atr_14": "14 true ranges using previous close; SMA seed then Wilder smoothing; requires 15 bars",
            "volume_ratio_20": "Latest volume / mean of final 20 volumes; zero mean yields null",
        },
        **values,
    }
