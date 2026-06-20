"""Prepare deterministic scenario, sentiment, peer, and downside report data."""

from __future__ import annotations

import re
from typing import Any


SCENARIO_META = {
    "bear": ("熊市情境", "悲觀"),
    "base": ("基準情境", "基準"),
    "bull": ("牛市情境", "樂觀"),
}


def build_dcf_scenario_rows(data: dict) -> list[dict]:
    quant = data.get("quant_metrics") if isinstance(data.get("quant_metrics"), dict) else {}
    raw = quant.get("dcf_scenarios") if isinstance(quant, dict) else None
    if not isinstance(raw, dict):
        tools = data.get("deterministic_financial_tool_results")
        calculations = tools.get("calculations", {}) if isinstance(tools, dict) else {}
        default = calculations.get("dcf_scenarios_default", {}) if isinstance(calculations, dict) else {}
        raw = default.get("scenarios", {}) if isinstance(default, dict) else {}
    rows = []
    for key in ("bear", "base", "bull"):
        item = raw.get(key) if isinstance(raw, dict) else None
        if not isinstance(item, dict):
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


def build_management_sentiment(context: dict) -> dict:
    output = _structured_output(context, 20)
    return {
        "tone": str(output.get("guidance_tone") or "資料不足"),
        "confidence": _number(output.get("confidence")),
        "highlights": [item for item in output.get("highlights", []) if isinstance(item, dict)][:3],
        "available": bool(output),
    }


def build_downside_view(context: dict) -> dict:
    output = _structured_output(context, 21)
    return {
        "summary": str(output.get("thesis_summary") or "紅軍分析未產出可用結論。"),
        "risks": [item for item in output.get("downside_risks", []) if isinstance(item, dict)][:5],
        "available": bool(output),
    }


def build_peer_comparison_rows(data: dict) -> list[dict]:
    rows = [_target_peer_row(data)]
    for item in list(data.get("dynamic_peer_metrics") or [])[:5]:
        if not isinstance(item, dict):
            continue
        rows.append({
            "name": str(item.get("name") or item.get("ticker") or "同業"),
            "ticker": str(item.get("ticker") or ""),
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
        "name": str(data.get("company_name") or data.get("ticker") or "目標公司"),
        "ticker": str(data.get("ticker") or ""),
        "is_target": True,
        "gross_margin_pct": _pct(data.get("gross_margin_raw", data.get("gross_margin"))),
        "roe_pct": _pct(data.get("roe_raw", data.get("roe"))),
        "asset_turnover": round(asset_turnover, 4) if asset_turnover is not None else None,
        "pe_ttm": _number(data.get("pe_ratio_raw", data.get("pe_ratio"))),
        "ps_ttm": _number(data.get("ps_ratio_raw", data.get("ps_ratio"))),
    }


def _structured_output(context: dict, agent_num: int) -> dict:
    outputs = context.get("structured_outputs") if isinstance(context.get("structured_outputs"), dict) else {}
    value = outputs.get(agent_num, outputs.get(str(agent_num), {}))
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or "").replace(",", ""))
    return round(float(match.group()), 4) if match else None


def _pct(value: Any) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number * 100 if abs(number) <= 1 else number, 4)


def _last_number(value: Any) -> float | None:
    if not isinstance(value, list):
        return None
    for item in reversed(value):
        number = _number(item)
        if number is not None:
            return number
    return None
