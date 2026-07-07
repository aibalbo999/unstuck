from __future__ import annotations

from typing import Any
from statistics import median

from .utils import _label, _metric, _number, _pct_points, _percent_change, _text


def _peer_comparison(data: dict[str, Any]) -> dict[str, Any]:
    peers = []
    for item in data.get("dynamic_peer_metrics") or []:
        if not isinstance(item, dict):
            continue
        row = _peer_row(item, is_target=False)
        if _peer_has_metrics(row):
            peers.append(row)
        if len(peers) >= 4:
            break
    target = _target_peer_row(data)
    peer_pe_values = [value for value in (_number(row.get("pe_ttm")) for row in peers) if value is not None]
    peer_gross_values = [value for value in (_number(row.get("gross_margin_pct")) for row in peers) if value is not None]
    target_pe = _number(target.get("pe_ttm"))
    target_gross = _number(target.get("gross_margin_pct"))
    pe_median = median(peer_pe_values) if peer_pe_values else None
    gross_median = median(peer_gross_values) if peer_gross_values else None
    pe_vs_median = _percent_change(target_pe, pe_median)
    gross_spread = round(target_gross - gross_median, 2) if target_gross is not None and gross_median is not None else None
    return {
        "summary": {
            "peer_count": len(peers),
            "valuation_label": _peer_valuation_label(pe_vs_median),
            "peer_pe_median": pe_median,
            "pe_vs_peer_median_pct": pe_vs_median,
            "peer_gross_margin_median": gross_median,
            "gross_margin_spread_pct": gross_spread,
        },
        "target": target,
        "peers": peers,
    }

def _target_peer_row(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": _text(data.get("company_name")) or _text(data.get("ticker")),
        "ticker": _text(data.get("ticker")),
        "is_target": True,
        "gross_margin_pct": _pct_points(data.get("gross_margin_raw"), data.get("gross_margin")),
        "profit_margin_pct": _pct_points(data.get("profit_margin_raw"), data.get("profit_margin")),
        "roe_pct": _pct_points(data.get("roe_raw"), data.get("roe")),
        "pe_ttm": _number(data.get("pe_ratio_raw"), data.get("pe_ratio")),
        "ps_ttm": _number(data.get("ps_ratio_raw"), data.get("ps_ratio")),
    }

def _peer_row(item: dict[str, Any], *, is_target: bool) -> dict[str, Any]:
    return {
        "name": _text(item.get("name") or item.get("company_name") or item.get("ticker")),
        "ticker": _text(item.get("ticker")),
        "is_target": is_target,
        "gross_margin_pct": _number(item.get("gross_margin_pct")),
        "profit_margin_pct": _number(item.get("profit_margin_pct")),
        "roe_pct": _number(item.get("roe_pct")),
        "asset_turnover": _number(item.get("asset_turnover")),
        "pe_ttm": _number(item.get("pe_ttm")),
        "ps_ttm": _number(item.get("ps_ttm")),
        "source": _text(item.get("source")),
    }

def _peer_has_metrics(row: dict[str, Any]) -> bool:
    return any(row.get(key) is not None for key in ("gross_margin_pct", "roe_pct", "pe_ttm", "ps_ttm"))

def _peer_valuation_label(pe_vs_median: float | None) -> str:
    if pe_vs_median is None:
        return "同業資料不足"
    if pe_vs_median >= 15:
        return "同業溢價"
    if pe_vs_median <= -15:
        return "同業折價"
    return "接近同業"

def _valuation_range(data: dict[str, Any], *, current_price: float | None) -> dict[str, Any]:
    chart = data.get("pe_river_chart") if isinstance(data.get("pe_river_chart"), dict) else {}
    bands = chart.get("bands") if isinstance(chart.get("bands"), dict) else {}
    latest_bands = []
    for label, series in bands.items():
        values = list(series or []) if isinstance(series, list) else []
        price = next((_number(value) for value in reversed(values) if _number(value) is not None), None)
        if price is None:
            continue
        latest_bands.append({
            "label": _text(label),
            "multiple": _number(label),
            "price": price,
        })
    latest_bands.sort(key=lambda item: (item["price"], item["multiple"] or 0))
    prices = [item["price"] for item in latest_bands]
    mid_price = median(prices) if prices else None
    status = "available" if current_price is not None and len(latest_bands) >= 2 else "unavailable"
    return {
        "status": status,
        "label": _valuation_range_label(current_price, prices),
        "current_price": current_price,
        "mid_price": mid_price,
        "price_vs_mid_pct": _percent_change(current_price, mid_price),
        "bands": latest_bands,
        "source": _text(chart.get("source")),
    }

def _valuation_range_label(current_price: float | None, prices: list[float]) -> str:
    if current_price is None or len(prices) < 2:
        return "估值資料不足"
    low, high = min(prices), max(prices)
    if current_price < low:
        return "低於區間"
    if current_price > high:
        return "高於區間"
    return "合理區間"
