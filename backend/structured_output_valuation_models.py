"""Moat and valuation structured output models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_model_base import (
    _ANALYSIS_MARKDOWN_FALLBACK,
    _DCF_SCENARIOS,
    _MOAT_SCORE_FIELDS,
    _VALUATION_PRIMARY_METHODS,
    _safe_bool,
    _safe_mapping_value,
    _safe_number,
    _safe_required_text_list,
    _safe_string_text,
    AnalysisMarkdownMixin,
    StructuredModel,
)


class MoatScores(StructuredModel):
    brand_influence: float = Field(..., ge=1, le=10, alias="品牌影響力")
    network_effect: float = Field(..., ge=1, le=10, alias="網路效應")
    switching_cost: float = Field(..., ge=1, le=10, alias="轉換成本")
    cost_advantage: float = Field(..., ge=1, le=10, alias="成本優勢")
    patent_technology: float = Field(..., ge=1, le=10, alias="專利技術")
    overall_moat: float = Field(..., ge=1, le=10, alias="整體護城河")

    @model_validator(mode="before")
    @classmethod
    def sanitize_score_fields(cls, payload):
        scores = safe_mapping_dict(payload)
        if scores is None:
            scores = {}
        normalized = {**scores}
        for alias, field_name in _MOAT_SCORE_FIELDS:
            score = _safe_mapping_value(scores, alias, field_name)
            normalized[alias] = _safe_number(score, default=1.0, minimum=1, maximum=10)
        return normalized


class MoatStructuredOutput(AnalysisMarkdownMixin):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個可稽核推論步驟，逐步連結證據、反證與評分邏輯。",
    )
    moat_scores: MoatScores
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_reasoning_steps(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"],
                "moat_scores": {},
                "analysis_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
            }
        normalized = root if "moat_scores" in root else {**root, "moat_scores": {}}
        raw_steps = normalized.get("reasoning_steps")
        if not isinstance(raw_steps, (list, tuple)):
            return {**normalized, "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"]}
        return {**normalized, "reasoning_steps": _safe_required_text_list(raw_steps, 3, "待補推論步驟")}


class PriceTargets(StructuredModel):
    dcf_reasoning: str = Field(..., min_length=1, description="DCF 假設、normalized FCF、WACC 與終值推論摘要。")
    peer_reasoning: str = Field(..., min_length=1, description="同業本益比、P/B 或 EV/EBITDA 比較推論摘要。")
    scenario_reasoning: str = Field(..., min_length=1, description="熊市、基本與牛市情境差異及風險折讓推論摘要。")
    bear_case: float = Field(..., ge=0, alias="熊市情境")
    base_case: float = Field(..., ge=0, alias="基本情境")
    bull_case: float = Field(..., ge=0, alias="牛市情境")

    @model_validator(mode="before")
    @classmethod
    def sanitize_reasoning_fields(cls, payload):
        targets = safe_mapping_dict(payload)
        if targets is None:
            targets = {}
        bear_case = _safe_mapping_value(targets, "熊市情境", "bear_case")
        base_case = _safe_mapping_value(targets, "基本情境", "base_case")
        bull_case = _safe_mapping_value(targets, "牛市情境", "bull_case")
        return {
            **targets,
            "dcf_reasoning": _safe_string_text(_safe_mapping_value(targets, "dcf_reasoning"), "資料不足"),
            "peer_reasoning": _safe_string_text(_safe_mapping_value(targets, "peer_reasoning"), "資料不足"),
            "scenario_reasoning": _safe_string_text(_safe_mapping_value(targets, "scenario_reasoning"), "資料不足"),
            "熊市情境": _safe_number(bear_case, minimum=0),
            "基本情境": _safe_number(base_case, minimum=0),
            "牛市情境": _safe_number(bull_case, minimum=0),
        }


class ValuationSummary(StructuredModel):
    primary_method: Literal["normalized_dcf", "relative_valuation", "blended"]
    uses_market_value_wacc: bool
    uses_normalized_fcf: bool
    double_counting_check: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        summary = safe_mapping_dict(payload)
        if summary is None:
            summary = {}
        primary_method = _safe_string_text(_safe_mapping_value(summary, "primary_method"))
        return {
            **summary,
            "primary_method": primary_method if primary_method in _VALUATION_PRIMARY_METHODS else "blended",
            "uses_market_value_wacc": _safe_bool(_safe_mapping_value(summary, "uses_market_value_wacc")),
            "uses_normalized_fcf": _safe_bool(_safe_mapping_value(summary, "uses_normalized_fcf")),
            "double_counting_check": _safe_string_text(
                _safe_mapping_value(summary, "double_counting_check"),
                "資料不足",
            ),
        }


class DcfScenarioOutput(StructuredModel):
    scenario: Literal["bear", "base", "bull"]
    revenue_growth_bias_pct: float
    margin_bias_pct: float
    wacc_pct: float = Field(..., gt=0)
    intrinsic_value: float = Field(..., ge=0)

    @model_validator(mode="before")
    @classmethod
    def sanitize_numeric_fields(cls, payload):
        scenario = safe_mapping_dict(payload)
        if scenario is None:
            return {
                "scenario": "base",
                "revenue_growth_bias_pct": 0,
                "margin_bias_pct": 0,
                "wacc_pct": 1.0,
                "intrinsic_value": 0,
            }
        scenario_name = _safe_string_text(_safe_mapping_value(scenario, "scenario")).lower()
        return {
            **scenario,
            "scenario": scenario_name if scenario_name in _DCF_SCENARIOS else "base",
            "revenue_growth_bias_pct": _safe_number(_safe_mapping_value(scenario, "revenue_growth_bias_pct")),
            "margin_bias_pct": _safe_number(_safe_mapping_value(scenario, "margin_bias_pct")),
            "wacc_pct": _safe_number(_safe_mapping_value(scenario, "wacc_pct"), default=1.0, minimum=0.01),
            "intrinsic_value": _safe_number(_safe_mapping_value(scenario, "intrinsic_value"), minimum=0),
        }


def _safe_dcf_scenarios(value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return []
    scenarios = []
    for item in safe_sequence_items(value):
        if isinstance(item, DcfScenarioOutput):
            scenarios.append(item)
        else:
            scenario = safe_mapping_dict(item)
            if scenario is None:
                continue
            scenario_name = _safe_string_text(_safe_mapping_value(scenario, "scenario")).lower()
            if scenario_name not in _DCF_SCENARIOS:
                continue
            scenarios.append({**scenario, "scenario": scenario_name})
        if len(scenarios) >= 3:
            break
    return scenarios


class PriceTargetStructuredOutput(AnalysisMarkdownMixin):
    price_targets: PriceTargets
    valuation_summary: ValuationSummary
    dcf_scenarios: list[DcfScenarioOutput] = Field(default_factory=list, max_length=3)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_nested_fields(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "price_targets": {},
                "valuation_summary": {},
                "dcf_scenarios": [],
                "analysis_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
            }
        normalized = {**root}
        if "price_targets" not in root:
            normalized["price_targets"] = {}
        elif not isinstance(root.get("price_targets"), PriceTargets):
            if safe_mapping_dict(root.get("price_targets")) is None:
                normalized["price_targets"] = {}
        if "valuation_summary" not in root:
            normalized["valuation_summary"] = {}
        elif safe_mapping_dict(root.get("valuation_summary")) is None:
            normalized["valuation_summary"] = {}
        if "dcf_scenarios" in root:
            normalized["dcf_scenarios"] = _safe_dcf_scenarios(root.get("dcf_scenarios"))
        return normalized
