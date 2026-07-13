"""Pydantic schemas and prompt instructions for structured agents."""

from __future__ import annotations

import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from json_utils import extract_json_payload
from mapping_fields import safe_dict_list, safe_mapping_dict, safe_sequence_items, safe_text, safe_text_list
from prompt_rules import build_structured_agent_instructions
from recommendation_labels import normalize_recommendation_label


STRUCTURED_AGENT_INSTRUCTIONS = build_structured_agent_instructions()


class StructuredModel(BaseModel):
    """Base model for native Google GenAI response_schema payloads."""

    model_config = ConfigDict(populate_by_name=True)


_ANALYSIS_MARKDOWN_FALLBACK = "資料不足"
_VALUATION_PRIMARY_METHODS = {"normalized_dcf", "relative_valuation", "blended"}
_MANAGEMENT_GUIDANCE_TONES = {"樂觀", "中立", "保守", "資料不足"}
_DOWNSIDE_RISK_SEVERITIES = {"warning", "high", "critical"}
_DCF_SCENARIOS = {"bear", "base", "bull"}
_TRADE_DIRECTIONS = {"Long", "Short", "Neutral"}
_TRADE_RISK_LEVELS = {"High", "Medium", "Low"}
_MOAT_SCORE_FIELDS = (
    ("品牌影響力", "brand_influence"),
    ("網路效應", "network_effect"),
    ("轉換成本", "switching_cost"),
    ("成本優勢", "cost_advantage"),
    ("專利技術", "patent_technology"),
    ("整體護城河", "overall_moat"),
)


def _safe_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = safe_text(value).strip().lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    return default


def _safe_number(
    value,
    *,
    default: float = 0.0,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
        try:
            number = float(safe_text(value).replace(",", "").strip())
        except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError, LookupError):
            return default
    if not math.isfinite(number):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return round(number, 2)


class AnalysisMarkdownMixin(StructuredModel):
    @model_validator(mode="before")
    @classmethod
    def sanitize_analysis_markdown(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return payload
        return {
            **root,
            "analysis_markdown": safe_text(root.get("analysis_markdown")).strip() or _ANALYSIS_MARKDOWN_FALLBACK,
        }


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
            score = scores.get(alias, scores.get(field_name))
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
        bear_case = targets.get("熊市情境", targets.get("bear_case"))
        base_case = targets.get("基本情境", targets.get("base_case"))
        bull_case = targets.get("牛市情境", targets.get("bull_case"))
        return {
            **targets,
            "dcf_reasoning": safe_text(targets.get("dcf_reasoning")).strip() or "資料不足",
            "peer_reasoning": safe_text(targets.get("peer_reasoning")).strip() or "資料不足",
            "scenario_reasoning": safe_text(targets.get("scenario_reasoning")).strip() or "資料不足",
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
        primary_method = safe_text(summary.get("primary_method")).strip()
        return {
            **summary,
            "primary_method": primary_method if primary_method in _VALUATION_PRIMARY_METHODS else "blended",
            "uses_market_value_wacc": _safe_bool(summary.get("uses_market_value_wacc")),
            "uses_normalized_fcf": _safe_bool(summary.get("uses_normalized_fcf")),
            "double_counting_check": safe_text(summary.get("double_counting_check")).strip() or "資料不足",
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
        scenario_name = safe_text(scenario.get("scenario")).strip().lower()
        return {
            **scenario,
            "scenario": scenario_name if scenario_name in _DCF_SCENARIOS else "base",
            "revenue_growth_bias_pct": _safe_number(scenario.get("revenue_growth_bias_pct")),
            "margin_bias_pct": _safe_number(scenario.get("margin_bias_pct")),
            "wacc_pct": _safe_number(scenario.get("wacc_pct"), default=1.0, minimum=0.01),
            "intrinsic_value": _safe_number(scenario.get("intrinsic_value"), minimum=0),
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
            scenario_name = safe_text(scenario.get("scenario")).strip().lower()
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


class ConfidenceBasis(StructuredModel):
    """信心依據：要求 AI 明確說明信心分數來自哪些具體佐證。"""
    evidence_items: list[str] = Field(
        ...,
        min_length=3,
        description=(
            "支持此信心分數的具體佐證，至少 3 項。每項需引用具體數據或事件，"
            "不可僅寫「因為AI趨勢」等泛泛措辭。例如："
            "['TTM 毛利率 52.3% 優於同業均值 38%（來源：財務JSON）',"
            " '近三年 FCF/淨利轉換率均超過 90%（來源：deterministic_tool_results）',"
            " '2024Q4 法說會法人共識上修目標價']。"
        ),
    )
    key_risks_acknowledged: list[str] = Field(
        ...,
        min_length=2,
        description="已納入信心評估的關鍵風險，至少 2 項。必須是具體風險，非通用語句。",
    )
    data_gaps: list[str] = Field(
        default_factory=list,
        description="已知資料缺口。若無缺口，可填空列表，但不可省略此欄位。",
    )

    @model_validator(mode="before")
    @classmethod
    def sanitize_list_items(cls, payload):
        basis = safe_mapping_dict(payload)
        if basis is None:
            return {
                "evidence_items": ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
                "key_risks_acknowledged": ["待補已納入風險", "待補已納入風險"],
                "data_gaps": [],
            }
        return {
            **basis,
            "evidence_items": _safe_required_text_collection(basis.get("evidence_items"), 3, "待補具體佐證"),
            "key_risks_acknowledged": _safe_required_text_collection(
                basis.get("key_risks_acknowledged"),
                2,
                "待補已納入風險",
            ),
            "data_gaps": safe_text_list(basis.get("data_gaps")),
        }


def _safe_required_text_collection(value: Any, minimum: int, fallback: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return [fallback for _ in range(minimum)]
    return _safe_required_text_list(value, minimum, fallback)


def _safe_required_text_list(value: Any, minimum: int, fallback: str) -> list[str]:
    texts = safe_text_list(value)
    if not isinstance(value, (list, tuple)) or not safe_sequence_items(value):
        return texts
    while len(texts) < minimum:
        texts.append(fallback)
    return texts


class ScenarioTrigger(StructuredModel):
    """情境觸發器：定義需重新評估投資結論的具體條件。"""
    trigger_condition: str = Field(
        ...,
        min_length=10,
        description="需要重新評估的具體觸發條件，例如：「季度毛利率低於 43%」或「競爭對手取得關鍵大客戶訂單」。",
    )
    action: str = Field(
        ...,
        min_length=5,
        description="觸發後建議的行動，例如：「下調至持有，重新評估目標價」。",
    )
    direction: Literal["bullish_upgrade", "bearish_downgrade", "neutral_review"] = Field(
        ...,
        description="觸發後對結論的影響方向。",
    )

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        trigger = safe_mapping_dict(payload)
        if trigger is None:
            return dict(_SCENARIO_TRIGGER_FALLBACK)
        condition = safe_text(trigger.get("trigger_condition")).strip()
        action = safe_text(trigger.get("action")).strip()
        direction = safe_text(trigger.get("direction")).strip()
        return {
            **trigger,
            "trigger_condition": (
                condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"]
            ),
            "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
            "direction": direction if direction in _SCENARIO_TRIGGER_DIRECTIONS else "neutral_review",
        }


class Catalyst(StructuredModel):
    event_name: str = Field(..., min_length=1)
    expected_timeframe: str = Field(..., min_length=1, description="例如 Q3 2026、下個月法說會或下一次月營收。")
    impact_direction: Literal["bullish", "bearish", "volatile"]
    trigger_condition: str = Field(..., min_length=5)

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        catalyst = safe_mapping_dict(payload)
        if catalyst is None:
            return {
                "event_name": "待確認催化事件",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": "待後續資料確認",
            }
        impact_direction = safe_text(catalyst.get("impact_direction")).strip()
        trigger_condition = safe_text(catalyst.get("trigger_condition")).strip()
        return {
            **catalyst,
            "event_name": safe_text(catalyst.get("event_name")).strip() or "待確認催化事件",
            "expected_timeframe": safe_text(catalyst.get("expected_timeframe")).strip() or "待後續資料確認",
            "impact_direction": (
                impact_direction if impact_direction in _NEXT_CATALYST_IMPACT_DIRECTIONS else "volatile"
            ),
            "trigger_condition": trigger_condition if len(trigger_condition) >= 5 else "待後續資料確認",
        }


class ExecutiveThesisOutput(StructuredModel):
    core_thesis: str = Field(..., min_length=1)
    bull_case_summary: str = Field(..., min_length=1)
    bear_case_summary: str = Field(..., min_length=1)
    resolved_contradictions: list[str] = Field(default_factory=list)
    smoothed_markdown: str = Field(default="", description="總編輯潤飾後的統一敘事 Markdown。")

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_payload(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "core_thesis": "資料不足",
                "bull_case_summary": "資料不足",
                "bear_case_summary": "資料不足",
                "resolved_contradictions": [],
                "smoothed_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
            }
        return {
            **root,
            "core_thesis": safe_text(root.get("core_thesis")).strip() or "資料不足",
            "bull_case_summary": safe_text(root.get("bull_case_summary")).strip() or "資料不足",
            "bear_case_summary": safe_text(root.get("bear_case_summary")).strip() or "資料不足",
            "resolved_contradictions": [
                safe_text(item).strip() or "資料不足"
                for item in safe_sequence_items(root.get("resolved_contradictions"))
            ],
            "smoothed_markdown": safe_text(root.get("smoothed_markdown")).strip() or _ANALYSIS_MARKDOWN_FALLBACK,
        }

    @field_validator("core_thesis")
    @classmethod
    def core_thesis_max_300_words(cls, value: str) -> str:
        if len(str(value).split()) > 300:
            raise ValueError("core_thesis must be 300 words or fewer")
        return value


_SCENARIO_TRIGGER_DIRECTIONS = {"bullish_upgrade", "bearish_downgrade", "neutral_review"}
_NEXT_CATALYST_IMPACT_DIRECTIONS = {"bullish", "bearish", "volatile"}
_MAX_SCENARIO_TRIGGERS = 5
_MIN_SCENARIO_TRIGGERS = 2
_SCENARIO_TRIGGER_FALLBACK = {
    "trigger_condition": "待後續資料確認觸發條件",
    "action": "重新檢查投資結論",
    "direction": "neutral_review",
}
_RECOMMENDATION_KEY_ALIASES = {
    "recommendation": "建議",
    "target_3m": "短期目標（3個月）",
    "target_6m": "中期目標（6個月）",
    "target_12m": "長期目標（12個月）",
    "long_term_potential_5y": "長期潛力（5年）",
    "confidence": "信心指數",
}
_RECOMMENDATION_TEXT_DEFAULTS = {
    "短期目標（3個月）": "N/A",
    "中期目標（6個月）": "N/A",
    "長期目標（12個月）": "N/A",
    "長期潛力（5年）": "N/A",
    "信心指數": "N/A",
}


def _recommendation_field_fallback(recommendation_label: str) -> dict:
    return {
        "建議": recommendation_label,
        "短期目標（3個月）": "N/A",
        "中期目標（6個月）": "N/A",
        "長期目標（12個月）": "N/A",
        "長期潛力（5年）": "N/A",
        "信心指數": "N/A",
    }


def _confidence_basis_fallback() -> dict:
    return {
        "evidence_items": ["待補具體佐證", "待補具體佐證", "待補具體佐證"],
        "key_risks_acknowledged": ["待補已納入風險", "待補已納入風險"],
        "data_gaps": [],
    }


def _scenario_triggers_fallback() -> list[dict]:
    return [dict(_SCENARIO_TRIGGER_FALLBACK), dict(_SCENARIO_TRIGGER_FALLBACK)]


def _recommendation_root_fallback(recommendation_label: str = "持有") -> dict:
    return {
        "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"],
        "recommendation": _recommendation_field_fallback(recommendation_label),
        "confidence_basis": _confidence_basis_fallback(),
        "scenario_triggers": _scenario_triggers_fallback(),
        "next_catalysts": [
            {
                "event_name": "Scenario trigger 1",
                "expected_timeframe": "待後續資料確認",
                "impact_direction": "volatile",
                "trigger_condition": _SCENARIO_TRIGGER_FALLBACK["trigger_condition"],
            }
        ],
        "analysis_markdown": _ANALYSIS_MARKDOWN_FALLBACK,
    }


class ReasoningStepsMixin(AnalysisMarkdownMixin):
    @model_validator(mode="before")
    @classmethod
    def sanitize_reasoning_steps(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return payload
        raw_steps = root.get("reasoning_steps")
        if not isinstance(raw_steps, (list, tuple)):
            return {**root, "reasoning_steps": ["待補推論步驟", "待補推論步驟", "待補推論步驟"]}
        return {**root, "reasoning_steps": _safe_required_text_list(raw_steps, 3, "待補推論步驟")}


def _safe_scenario_triggers(payload) -> list[dict]:
    root = safe_mapping_dict(payload)
    if root is None:
        return []
    raw_trigger_items = root.get("scenario_triggers")
    if "scenario_triggers" in root and not isinstance(raw_trigger_items, (list, tuple)):
        return _scenario_triggers_fallback()
    trigger_items = safe_sequence_items(raw_trigger_items)
    safe_triggers = []
    fallbacks = []
    for item in trigger_items:
        trigger = safe_mapping_dict(item)
        if trigger is None:
            fallbacks.append(dict(_SCENARIO_TRIGGER_FALLBACK))
            continue
        condition = safe_text(trigger.get("trigger_condition")).strip()
        action = safe_text(trigger.get("action")).strip()
        direction = safe_text(trigger.get("direction")).strip()
        if direction not in _SCENARIO_TRIGGER_DIRECTIONS:
            direction = "neutral_review"
        if len(condition) < 10 or len(action) < 5:
            fallbacks.append({
                "trigger_condition": (
                    condition if len(condition) >= 10 else _SCENARIO_TRIGGER_FALLBACK["trigger_condition"]
                ),
                "action": action if len(action) >= 5 else _SCENARIO_TRIGGER_FALLBACK["action"],
                "direction": direction,
            })
            continue
        safe_triggers.append({
            "trigger_condition": condition,
            "action": action,
            "direction": direction,
        })
        if len(safe_triggers) >= _MAX_SCENARIO_TRIGGERS:
            break
    while len(trigger_items) >= _MIN_SCENARIO_TRIGGERS and len(safe_triggers) < _MIN_SCENARIO_TRIGGERS and fallbacks:
        safe_triggers.append(fallbacks.pop(0))
    return safe_triggers


def _catalysts_from_scenario_triggers(payload) -> list[dict]:
    catalysts = []
    for idx, trigger in enumerate(_safe_scenario_triggers(payload)[:3], start=1):
        condition = trigger["trigger_condition"]
        direction = trigger["direction"]
        if "bullish" in direction:
            impact = "bullish"
        elif "bearish" in direction:
            impact = "bearish"
        else:
            impact = "volatile"
        catalysts.append({
            "event_name": f"Scenario trigger {idx}",
            "expected_timeframe": "待後續資料確認",
            "impact_direction": impact,
            "trigger_condition": condition,
        })
    return catalysts


def _should_derive_next_catalysts(root: dict, safe_existing_catalysts: list[dict]) -> bool:
    if "next_catalysts" not in root:
        return True
    raw_next_catalysts = root.get("next_catalysts")
    if raw_next_catalysts is None:
        return True
    if not isinstance(raw_next_catalysts, (list, tuple)):
        return True
    return bool(raw_next_catalysts) and not safe_existing_catalysts


def _safe_existing_next_catalysts(root: dict) -> list[dict]:
    raw_next_catalysts = root.get("next_catalysts")
    if not isinstance(raw_next_catalysts, (list, tuple)):
        return []
    safe_rows = []
    for catalyst in safe_dict_list(raw_next_catalysts):
        event_name = safe_text(catalyst.get("event_name")).strip()
        expected_timeframe = safe_text(catalyst.get("expected_timeframe")).strip()
        impact_direction = safe_text(catalyst.get("impact_direction")).strip()
        trigger_condition = safe_text(catalyst.get("trigger_condition")).strip()
        if (
            not event_name
            or not expected_timeframe
            or impact_direction not in _NEXT_CATALYST_IMPACT_DIRECTIONS
            or len(trigger_condition) < 5
        ):
            continue
        safe_rows.append({
            "event_name": event_name,
            "expected_timeframe": expected_timeframe,
            "impact_direction": impact_direction,
            "trigger_condition": trigger_condition,
        })
    return safe_rows


def _populate_safe_next_catalysts(payload):
    root = safe_mapping_dict(payload)
    if root is None:
        return payload
    safe_triggers = _safe_scenario_triggers(root)
    if not safe_triggers:
        return payload
    normalized_payload = {**root, "scenario_triggers": safe_triggers}
    safe_existing_catalysts = _safe_existing_next_catalysts(root)
    if safe_existing_catalysts:
        normalized_payload = {**normalized_payload, "next_catalysts": safe_existing_catalysts}
    elif _should_derive_next_catalysts(root, safe_existing_catalysts):
        catalysts = _catalysts_from_scenario_triggers(normalized_payload)
        if catalysts:
            normalized_payload = {**normalized_payload, "next_catalysts": catalysts}
    return normalized_payload


class NextCatalystsMixin(ReasoningStepsMixin):
    next_catalysts: list[Catalyst] = Field(default_factory=list, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def populate_next_catalysts_from_scenario_triggers(cls, payload):
        return _populate_safe_next_catalysts(payload)


def _normalize_recommendation_field(payload, default_label: str):
    recommendation = safe_mapping_dict(payload)
    if recommendation is None:
        return payload
    normalized = {**recommendation}
    for raw_key, raw_value in recommendation.items():
        key_text = safe_text(raw_key).strip()
        key = _RECOMMENDATION_KEY_ALIASES.get(key_text, key_text)
        if key == "建議":
            normalized[key] = normalize_recommendation_label(raw_value)
        elif key in _RECOMMENDATION_TEXT_DEFAULTS:
            normalized[key] = safe_text(raw_value).strip() or _RECOMMENDATION_TEXT_DEFAULTS[key]
    normalized["建議"] = normalize_recommendation_label(normalized.get("建議")) or default_label
    if normalized["建議"] == "N/A":
        normalized["建議"] = default_label
    for key, default in _RECOMMENDATION_TEXT_DEFAULTS.items():
        normalized[key] = safe_text(normalized.get(key)).strip() or default
    return normalized


class RecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免", "放空"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")

    @model_validator(mode="before")
    @classmethod
    def normalize_label(cls, payload):
        if safe_mapping_dict(payload) is None:
            return {
                "建議": "持有",
                "短期目標（3個月）": "N/A",
                "中期目標（6個月）": "N/A",
                "長期目標（12個月）": "N/A",
                "長期潛力（5年）": "N/A",
                "信心指數": "N/A",
            }
        return _normalize_recommendation_field(payload, "持有")


class RecommendationStructuredOutput(NextCatalystsMixin):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個決策推論步驟，逐步連結估值、財務、護城河、成長、風險與籌碼。",
    )
    recommendation: RecommendationFields
    confidence_basis: ConfidenceBasis = Field(
        ...,
        description="信心依據：必須列出至少 3 項具體佐證與 2 項已納入考量的風險。",
    )
    scenario_triggers: list[ScenarioTrigger] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="情境觸發器：列出 2-5 個需要重新評估投資結論的具體條件。",
    )
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_payload(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return _recommendation_root_fallback()
        if "recommendation" not in root:
            root = {**root, "recommendation": _recommendation_field_fallback("持有")}
        if "confidence_basis" not in root:
            root = {**root, "confidence_basis": _confidence_basis_fallback()}
        if "scenario_triggers" not in root:
            root = {**root, "scenario_triggers": _scenario_triggers_fallback()}
        return root


class BubbleSniperRecommendationFields(StructuredModel):
    recommendation: Literal["買入", "持有", "避免", "放空"] = Field(..., alias="建議")
    target_3m: str = Field(..., min_length=1, alias="短期目標（3個月）")
    target_6m: str = Field(..., min_length=1, alias="中期目標（6個月）")
    target_12m: str = Field(..., min_length=1, alias="長期目標（12個月）")
    long_term_potential_5y: str = Field(..., min_length=1, alias="長期潛力（5年）")
    confidence: str = Field(..., min_length=1, alias="信心指數")

    @model_validator(mode="before")
    @classmethod
    def normalize_label(cls, payload):
        if safe_mapping_dict(payload) is None:
            return {
                "建議": "避免",
                "短期目標（3個月）": "N/A",
                "中期目標（6個月）": "N/A",
                "長期目標（12個月）": "N/A",
                "長期潛力（5年）": "N/A",
                "信心指數": "N/A",
            }
        return _normalize_recommendation_field(payload, "避免")


class BubbleSniperStructuredOutput(ReasoningStepsMixin):
    reasoning_steps: list[str] = Field(
        ...,
        min_length=3,
        description="先列出 3-6 個逆勢交易推論步驟，逐步連結市場泡沫、財務漏洞、籌碼派發、崩盤催化與停損風控。",
    )
    recommendation: BubbleSniperRecommendationFields
    confidence_basis: ConfidenceBasis = Field(
        ...,
        description="信心依據：必須列出至少 3 項具體佐證與 2 項已納入考量的軋空或資料風險。",
    )
    scenario_triggers: list[ScenarioTrigger] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="情境觸發器：列出 2-5 個崩盤催化、軋空停損或重新評估條件。",
    )
    next_catalysts: list[Catalyst] = Field(default_factory=list, min_length=1)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def populate_next_catalysts_from_scenario_triggers(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return _recommendation_root_fallback("避免")
        if "scenario_triggers" not in root:
            root = {**root, "scenario_triggers": _scenario_triggers_fallback()}
        normalized = _populate_safe_next_catalysts(root)
        normalized_root = safe_mapping_dict(normalized)
        if normalized_root is None:
            return normalized
        if "recommendation" not in normalized_root:
            normalized_root = {**normalized_root, "recommendation": _recommendation_field_fallback("避免")}
        if "confidence_basis" not in normalized_root:
            normalized_root = {**normalized_root, "confidence_basis": _confidence_basis_fallback()}
        return normalized_root


class ManagementHighlight(StructuredModel):
    keyword: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        highlight = safe_mapping_dict(payload)
        if highlight is None:
            return {"keyword": "亮點", "quote": "資料不足"}
        return {
            **highlight,
            "keyword": safe_text(highlight.get("keyword")).strip() or "亮點",
            "quote": safe_text(highlight.get("quote")).strip() or "資料不足",
        }


def _safe_management_highlights(value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return [{"keyword": "亮點", "quote": "資料不足"} for _ in range(3)]
    highlights = []
    items = safe_sequence_items(value)[:3]
    for item in items:
        highlight = safe_mapping_dict(item)
        if highlight is None:
            highlights.append({"keyword": "亮點", "quote": "資料不足"})
            continue
        highlights.append({
            **highlight,
            "keyword": safe_text(highlight.get("keyword")).strip() or "亮點",
            "quote": safe_text(highlight.get("quote")).strip() or "資料不足",
        })
    if items:
        while len(highlights) < 3:
            highlights.append({"keyword": "亮點", "quote": "資料不足"})
    return highlights


class ManagementSentimentStructuredOutput(AnalysisMarkdownMixin):
    guidance_tone: Literal["樂觀", "中立", "保守", "資料不足"]
    confidence: float = Field(..., ge=0, le=1)
    highlights: list[ManagementHighlight] = Field(..., min_length=3, max_length=3)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_fields(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "guidance_tone": "資料不足",
                "confidence": 0.0,
                "highlights": [{"keyword": "亮點", "quote": "資料不足"} for _ in range(3)],
                "analysis_markdown": "資料不足",
            }
        tone = safe_text(root.get("guidance_tone")).strip()
        normalized = {
            **root,
            "guidance_tone": tone if tone in _MANAGEMENT_GUIDANCE_TONES else "資料不足",
            "confidence": _safe_number(root.get("confidence"), default=0.0, minimum=0, maximum=1),
        }
        if "highlights" not in root:
            normalized["highlights"] = _safe_management_highlights(None)
        else:
            normalized["highlights"] = _safe_management_highlights(root.get("highlights"))
        return normalized


class DownsideRisk(StructuredModel):
    title: str = Field(..., min_length=1)
    evidence: str = Field(..., min_length=1)
    impact: str = ""
    severity: Literal["warning", "high", "critical"]
    confidence: float = Field(default=0.7, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        risk = safe_mapping_dict(payload)
        if risk is None:
            return {
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            }
        return _safe_downside_risk_fields(risk)


def _safe_downside_risk_fields(risk: dict[str, Any]) -> dict[str, Any]:
    severity = safe_text(risk.get("severity")).strip()
    return {
        **risk,
        "title": safe_text(risk.get("title")).strip() or "下行風險",
        "evidence": safe_text(risk.get("evidence")).strip() or "資料不足",
        "impact": safe_text(risk.get("impact")).strip(),
        "severity": severity if severity in _DOWNSIDE_RISK_SEVERITIES else "warning",
        "confidence": _safe_number(risk.get("confidence"), default=0.7, minimum=0, maximum=1),
    }


def _safe_downside_risks(value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return [
            {
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            }
            for _ in range(3)
        ]
    risks = []
    items = safe_sequence_items(value)[:5]
    for item in items:
        risk = safe_mapping_dict(item)
        if risk is None:
            risks.append({
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            })
            continue
        risks.append(_safe_downside_risk_fields(risk))
    if items:
        while len(risks) < 3:
            risks.append({
                "title": "下行風險",
                "evidence": "資料不足",
                "impact": "",
                "severity": "warning",
                "confidence": 0.7,
            })
    return risks


class BearAdvocateStructuredOutput(AnalysisMarkdownMixin):
    thesis_summary: str = Field(..., min_length=1)
    downside_risks: list[DownsideRisk] = Field(..., min_length=3, max_length=5)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_thesis_summary(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "thesis_summary": "資料不足",
                "downside_risks": [
                    {
                        "title": "下行風險",
                        "evidence": "資料不足",
                        "impact": "",
                        "severity": "warning",
                        "confidence": 0.7,
                    }
                    for _ in range(3)
                ],
                "analysis_markdown": "資料不足",
            }
        normalized = {
            **root,
            "thesis_summary": safe_text(root.get("thesis_summary")).strip() or "資料不足",
        }
        if "downside_risks" not in root:
            normalized["downside_risks"] = _safe_downside_risks(None)
        else:
            normalized["downside_risks"] = _safe_downside_risks(root.get("downside_risks"))
        return normalized


class SwingTradeSetup(StructuredModel):
    """Strict 1-2 week trade plan emitted by the v4 decision agent."""

    # NOTE: Do NOT use extra="forbid" here. Pydantic emits additionalProperties:false
    # in the JSON schema, which Google GenAI's response_schema API rejects with
    # 400 INVALID_ARGUMENT: Unknown name "additional_properties".
    model_config = ConfigDict(populate_by_name=True)

    trade_direction: Literal["Long", "Short", "Neutral"]
    entry_zone: str = Field(..., min_length=1)
    target_price: str = Field(..., min_length=1)
    stop_loss: str = Field(..., min_length=1)
    core_catalyst: str = Field(..., min_length=1)
    risk_level: Literal["High", "Medium", "Low"]

    @model_validator(mode="before")
    @classmethod
    def sanitize_text_fields(cls, payload):
        setup = safe_mapping_dict(payload)
        if setup is None:
            return {
                "trade_direction": "Neutral",
                "entry_zone": "N/A",
                "target_price": "N/A",
                "stop_loss": "N/A",
                "core_catalyst": "N/A",
                "risk_level": "High",
            }
        trade_direction = safe_text(setup.get("trade_direction")).strip()
        risk_level = safe_text(setup.get("risk_level")).strip()
        return {
            **setup,
            "trade_direction": trade_direction if trade_direction in _TRADE_DIRECTIONS else "Neutral",
            "entry_zone": safe_text(setup.get("entry_zone")).strip() or "N/A",
            "target_price": safe_text(setup.get("target_price")).strip() or "N/A",
            "stop_loss": safe_text(setup.get("stop_loss")).strip() or "N/A",
            "core_catalyst": safe_text(setup.get("core_catalyst")).strip() or "N/A",
            "risk_level": risk_level if risk_level in _TRADE_RISK_LEVELS else "High",
        }


STRUCTURED_AGENT_RESPONSE_SCHEMAS: dict[int, type[StructuredModel]] = {
    3: MoatStructuredOutput,
    4: PriceTargetStructuredOutput,
    7: RecommendationStructuredOutput,
    12: MoatStructuredOutput,
    14: PriceTargetStructuredOutput,
    16: RecommendationStructuredOutput,
    19: BubbleSniperStructuredOutput,
    20: ManagementSentimentStructuredOutput,
    21: BearAdvocateStructuredOutput,
    24: SwingTradeSetup,
}


def get_structured_response_schema(agent_num: int) -> Optional[type[StructuredModel]]:
    """Return the native response schema model for structured agents."""
    return STRUCTURED_AGENT_RESPONSE_SCHEMAS.get(agent_num)


def build_structured_output_instruction(agent_num: int) -> str:
    """Return JSON-only output instructions for agents with machine-read fields."""
    return STRUCTURED_AGENT_INSTRUCTIONS.get(agent_num, "")


def _extract_json_payload(raw_text: str) -> Optional[dict]:
    return extract_json_payload(raw_text)
