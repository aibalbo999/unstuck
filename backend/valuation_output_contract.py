"""Canonicalize valuation output against deterministic quant evidence."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_mapping_dict
from quant_metric_contract import trusted_dcf_scenarios


_DCF_UNAVAILABLE_REASON = (
    "DCF 來源不可用；本報告不採用 DCF 目標價，僅保留有來源的相對估值。"
)


def _canonical_dcf_rows(quant: Any) -> list[dict[str, Any]]:
    scenarios = trusted_dcf_scenarios(quant)
    rows = []
    for name in ("bear", "base", "bull"):
        source = scenarios.get(name)
        if not isinstance(source, dict):
            continue
        rows.append({
            "scenario": name,
            "method": source["method"],
            "unit": source["unit"],
            "source_ref": f"quant_metrics.dcf_scenarios.{name}",
            "revenue_growth_bias_pct": source.get(
                "revenue_growth_bias_pct",
                source.get("growth_bias_pct", 0.0),
            ),
            "margin_bias_pct": source.get("margin_bias_pct", 0.0),
            "wacc_pct": source.get("wacc_pct"),
            "intrinsic_value": source.get("intrinsic_value"),
        })
    return rows


def canonicalize_valuation_output(structured: dict[str, Any], data: Any) -> dict[str, Any]:
    """Replace model-authored DCF rows with the deterministic quant contract."""
    result = dict(structured)
    data_map = safe_mapping_dict(data) or {}
    quant = safe_mapping_dict(data_map.get("quant_metrics")) or {}
    rows = _canonical_dcf_rows(quant)

    summary = dict(safe_mapping_dict(result.get("valuation_summary")) or {})
    reasoning = dict(safe_mapping_dict(result.get("valuation_reasoning")) or {})
    result["dcf_scenarios"] = rows

    if not rows:
        if summary.get("primary_method") in {"normalized_dcf", "blended"}:
            summary["primary_method"] = "relative_valuation"
        summary["uses_market_value_wacc"] = False
        summary["uses_normalized_fcf"] = False
        reasoning["dcf_reasoning"] = _DCF_UNAVAILABLE_REASON
    else:
        assumptions = safe_mapping_dict(quant.get("assumptions")) or {}
        dcf_assumptions = safe_mapping_dict(assumptions.get("dcf")) or {}
        base_note = str(dcf_assumptions.get("base_fcf_note") or "latest available FCF")
        summary["uses_market_value_wacc"] = True
        summary["uses_normalized_fcf"] = "normalized" in base_note.lower()
        reasoning["dcf_reasoning"] = (
            "DCF 僅採用 quant_metrics.v2 的 bear/base/bull 三情境結果；"
            f"基礎 FCF：{base_note}；WACC 採市場價值法。"
        )

    result["valuation_summary"] = summary
    result["valuation_reasoning"] = reasoning
    return result
