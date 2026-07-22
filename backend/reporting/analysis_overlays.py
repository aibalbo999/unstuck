"""Prepare deterministic scenario, sentiment, peer, and downside report data."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text

from .analysis_structured_overlays import build_downside_view, build_management_sentiment
from .numeric_text import first_finite_number
from .text_tokens import is_missing_text_token


SCENARIO_META = {
    "bear": ("熊市情境", "悲觀"),
    "base": ("基準情境", "基準"),
    "bull": ("牛市情境", "樂觀"),
}


def build_dcf_scenario_rows(data: dict) -> list[dict]:
    data = safe_mapping_dict(data) or {}
    quant = safe_mapping_dict(data.get("quant_metrics")) or {}
    raw = safe_mapping_dict(quant.get("dcf_scenarios"))
    if raw is None:
        tools = safe_mapping_dict(data.get("deterministic_financial_tool_results")) or {}
        calculations = safe_mapping_dict(tools.get("calculations")) or {}
        default = safe_mapping_dict(calculations.get("dcf_scenarios_default")) or {}
        raw = safe_mapping_dict(default.get("scenarios")) or {}
    rows = []
    for key in ("bear", "base", "bull"):
        item = safe_mapping_dict(raw.get(key)) if isinstance(raw, dict) else None
        if item is None:
            continue
        price = _number(item.get("intrinsic_value", item.get("price_per_share_twd")))
        wacc = _number(item.get("wacc_pct"))
        if wacc is None:
            ratio_wacc = _number(item.get("wacc"))
            wacc = ratio_wacc * 100 if ratio_wacc is not None and ratio_wacc <= 1 else ratio_wacc
        rows.append({
            "key": key,
            "label": SCENARIO_META[key][0],
            "stance": SCENARIO_META[key][1],
            "growth_bias_pct": _number(item.get("growth_bias_pct", item.get("revenue_growth_bias_pct"))),
            "margin_bias_pct": _number(item.get("margin_bias_pct")),
            "wacc_pct": wacc,
            "intrinsic_value": price,
        })
    return rows


def build_peer_comparison_rows(data: dict) -> list[dict]:
    data = safe_mapping_dict(data) or {}
    rows = [_target_peer_row(data)]
    for item in safe_dict_list(data.get("dynamic_peer_metrics"))[:5]:
        rows.append({
            "name": _text(item.get("name") or item.get("ticker"), "同業"),
            "ticker": _text(item.get("ticker"), ""),
            "is_target": False,
            "gross_margin_pct": _number(item.get("gross_margin_pct")),
            "roe_pct": _number(item.get("roe_pct")),
            "asset_turnover": _number(item.get("asset_turnover")),
            "pe_ttm": _number(item.get("pe_ttm")),
            "ps_ttm": _number(item.get("ps_ttm")),
        })
    return rows


def _target_peer_row(data: dict) -> dict:
    assets = _last_number(data.get("total_assets_history"))
    revenue_raw = _number(data.get("revenue_ttm_raw"))
    asset_turnover = revenue_raw / (assets * 1e9) if revenue_raw and assets else None
    return {
        "name": _text(data.get("company_name") or data.get("ticker"), "目標公司"),
        "ticker": _text(data.get("ticker"), ""),
        "is_target": True,
        "gross_margin_pct": _pct(data.get("gross_margin_raw", data.get("gross_margin"))),
        "roe_pct": _pct(data.get("roe_raw", data.get("roe"))),
        "asset_turnover": round(asset_turnover, 4) if asset_turnover is not None else None,
        "pe_ttm": _number(data.get("pe_ratio_raw", data.get("pe_ratio"))),
        "ps_ttm": _number(data.get("ps_ratio_raw", data.get("ps_ratio"))),
    }


def _number(value: Any) -> float | None:
    number = first_finite_number(value)
    return round(number, 4) if number is not None else None


def _pct(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number * 100 if abs(number) <= 1 else number, 4)


def _last_number(value: Any) -> float | None:
    for item in reversed(safe_sequence_items(value)):
        number = _number(item)
        if number is not None:
            return number
    return None


def _text(value: Any, default: str) -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default
