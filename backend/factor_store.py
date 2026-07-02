"""Qlib-lite factor snapshot helpers.

The project does not need a full quant research platform to start measuring
decisions. These helpers derive deterministic factors from local/free inputs so
reports, watchlists, and backtests can share one compact artifact.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from typing import Any


SCHEMA_VERSION = "factor_snapshot.v1"


def build_factor_snapshot(
    ticker: str,
    price_history: list[dict[str, Any]],
    fundamentals: dict[str, Any] | None = None,
    *,
    as_of: date | str | None = None,
) -> dict[str, Any]:
    """Build deterministic factors from caller-supplied price/fundamental data."""
    prices = _clean_prices(price_history)
    fundamentals = dict(fundamentals or {})
    first_close = prices[0]["close"] if prices else None
    last_close = prices[-1]["close"] if prices else None
    returns = _period_returns([row["close"] for row in prices])

    factors = {
        "momentum_total_pct": _round_pct(_return_pct(first_close, last_close)),
        "volatility_pct": _round_pct(_sample_volatility_pct(returns)),
        "average_volume": _round_number(_average([row["volume"] for row in prices if row.get("volume") is not None])),
        "quality_score": _quality_score(fundamentals),
        "valuation_pe": _optional_float(fundamentals.get("pe_ratio_raw")),
        "fcf_net_income_ratio": _round_number(
            _safe_ratio(fundamentals.get("free_cash_flow_raw"), fundamentals.get("net_income_ttm_raw"))
        ),
    }
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "ticker": str(ticker or "").strip().upper(),
        "as_of": _as_of_text(as_of, prices),
        "source_mode": "free_local",
        "observation_count": len(prices),
        "price_start": prices[0]["date"] if prices else None,
        "price_end": prices[-1]["date"] if prices else None,
        "factors": factors,
    }
    snapshot["id"] = factor_snapshot_id(snapshot)
    return snapshot


def factor_snapshot_id(snapshot: dict[str, Any]) -> str:
    """Return a stable content hash, excluding any preexisting id field."""
    payload = {key: value for key, value in dict(snapshot or {}).items() if key != "id"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _clean_prices(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned = []
    for row in rows or []:
        close = _optional_float((row or {}).get("close"))
        if close is None or close <= 0:
            continue
        cleaned.append({
            "date": str((row or {}).get("date") or ""),
            "close": close,
            "volume": _optional_float((row or {}).get("volume")),
        })
    return sorted(cleaned, key=lambda item: item["date"])


def _as_of_text(value: date | str | None, prices: list[dict[str, Any]]) -> str:
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if text:
        return text
    return str((prices[-1] or {}).get("date") or "") if prices else ""


def _period_returns(closes: list[float]) -> list[float]:
    returns = []
    for prev, current in zip(closes, closes[1:]):
        if prev > 0 and current > 0:
            returns.append(current / prev - 1)
    return returns


def _return_pct(first: float | None, last: float | None) -> float | None:
    if first is None or last is None or first <= 0:
        return None
    return (last / first - 1) * 100


def _sample_volatility_pct(returns: list[float]) -> float | None:
    if len(returns) < 2:
        return None
    avg = sum(returns) / len(returns)
    variance = sum((value - avg) ** 2 for value in returns) / (len(returns) - 1)
    return math.sqrt(variance) * 100


def _quality_score(fundamentals: dict[str, Any]) -> float:
    roe = _optional_float(fundamentals.get("roe_pct")) or 0.0
    fcf = _optional_float(fundamentals.get("free_cash_flow_raw")) or 0.0
    net_income = _optional_float(fundamentals.get("net_income_ttm_raw")) or 0.0
    pe = _optional_float(fundamentals.get("pe_ratio_raw"))
    score = 45.0
    score += min(max(roe, 0.0), 30.0)
    if fcf > 0:
        score += 15.0
    ratio = _safe_ratio(fcf, net_income)
    if ratio is not None and ratio >= 0.8:
        score += 15.0
    if pe is not None and 0 < pe <= 35:
        score += 5.0
    return round(max(0.0, min(100.0, score)), 2)


def _safe_ratio(numerator: Any, denominator: Any) -> float | None:
    top = _optional_float(numerator)
    bottom = _optional_float(denominator)
    if top is None or bottom in (None, 0):
        return None
    return top / bottom


def _average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _optional_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _round_pct(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _round_number(value: float | None) -> float | None:
    return round(value, 6) if value is not None else None


__all__ = ["SCHEMA_VERSION", "build_factor_snapshot", "factor_snapshot_id"]
