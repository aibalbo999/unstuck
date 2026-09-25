"""Management, risk, and trade setup structured output schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from trade_price_inputs import optional_execution_text
from structured_output_model_base import (
    _DOWNSIDE_RISK_SEVERITIES,
    _MANAGEMENT_GUIDANCE_TONES,
    _safe_mapping_has_key,
    _safe_mapping_value,
    _safe_number,
    _safe_string_text,
    _safe_string_text_list,
    AnalysisMarkdownMixin,
    StructuredModel,
)


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
            "keyword": _safe_string_text(highlight.get("keyword"), "亮點"),
            "quote": _safe_string_text(highlight.get("quote"), "資料不足"),
        }


def _safe_management_highlights(value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return []
    highlights = []
    items = safe_sequence_items(value)
    for item in items:
        highlight = safe_mapping_dict(item)
        if highlight is None:
            continue
        if not _safe_string_text(highlight.get("quote")):
            continue
        highlights.append({
            **highlight,
            "keyword": _safe_string_text(highlight.get("keyword"), "亮點"),
            "quote": _safe_string_text(highlight.get("quote"), "資料不足"),
        })
        if len(highlights) == 3:
            break
    return highlights


class ManagementSentimentStructuredOutput(AnalysisMarkdownMixin):
    guidance_tone: Literal["樂觀", "中立", "保守", "資料不足"]
    confidence: float = Field(..., ge=0, le=1)
    highlights: list[ManagementHighlight] = Field(..., max_length=3)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_root_fields(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "guidance_tone": "資料不足",
                "confidence": 0.0,
                "highlights": [],
                "analysis_markdown": "資料不足",
            }
        tone = _safe_string_text(root.get("guidance_tone"))
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
    falsifier: str = Field(..., min_length=1)
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
                "falsifier": "資料不足，待補可證偽條件",
                "severity": "warning",
                "confidence": 0.7,
            }
        return _safe_downside_risk_fields(risk)


def _safe_downside_risk_fields(risk: dict[str, Any]) -> dict[str, Any]:
    severity = _safe_string_text(risk.get("severity"))
    return {
        **risk,
        "title": _safe_string_text(risk.get("title"), "下行風險"),
        "evidence": _safe_string_text(risk.get("evidence"), "資料不足"),
        "impact": _safe_string_text(risk.get("impact")),
        "falsifier": _safe_string_text(
            risk.get("falsifier"),
            "資料不足，待補可證偽條件",
        ),
        "severity": severity if severity in _DOWNSIDE_RISK_SEVERITIES else "warning",
        "confidence": _safe_number(risk.get("confidence"), default=0.7, minimum=0, maximum=1),
    }


def _safe_downside_risks(value: Any) -> Any:
    if not isinstance(value, (list, tuple)):
        return []
    risks = []
    items = safe_sequence_items(value)[:5]
    for item in items:
        risk = safe_mapping_dict(item)
        if risk is None:
            continue
        risks.append(_safe_downside_risk_fields(risk))
    return risks


class BearAdvocateStructuredOutput(AnalysisMarkdownMixin):
    thesis_summary: str = Field(..., min_length=1)
    downside_risks: list[DownsideRisk] = Field(..., max_length=5)
    analysis_markdown: str = Field(..., min_length=1)

    @model_validator(mode="before")
    @classmethod
    def sanitize_thesis_summary(cls, payload):
        root = safe_mapping_dict(payload)
        if root is None:
            return {
                "thesis_summary": "資料不足",
                "downside_risks": [],
                "analysis_markdown": "資料不足",
            }
        normalized = {
            **root,
            "thesis_summary": _safe_string_text(root.get("thesis_summary"), "資料不足"),
        }
        if "downside_risks" not in root:
            normalized["downside_risks"] = _safe_downside_risks(None)
        else:
            normalized["downside_risks"] = _safe_downside_risks(root.get("downside_risks"))
        return normalized


class TradeEventCatalyst(StructuredModel):
    """An exact source calendar record, or explicit unknown; never news dates."""

    description: str | None = None
    date: str | None = None
    end_date: str | None = None
    timezone: str | None = None
    status: Literal["unknown", "scheduled", "confirmed", "date_range"] = "unknown"
    source_refs: list[str] = Field(default_factory=list, max_length=6)


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
    support_level: str = Field(..., min_length=1)
    resistance_level: str = Field(..., min_length=1)
    core_catalyst: str = Field(..., min_length=1)
    risk_level: Literal["High", "Medium", "Low"]
    support_source_refs: list[str] = Field(
        ...,
        max_length=6,
        description="支撐位僅引用本次完整可見 trade-source 清單中 support_source_refs 的確切 short_term_market_context 路徑；Neutral 且無價位時可為空陣列。",
    )
    resistance_source_refs: list[str] = Field(
        ...,
        max_length=6,
        description="壓力位僅引用本次完整可見 trade-source 清單中 resistance_source_refs 的確切 short_term_market_context 路徑；Neutral 且無價位時可為空陣列。",
    )
    catalyst_source_refs: list[str] = Field(
        ...,
        max_length=6,
        description="催化劑僅引用本次完整可見 trade-source 清單中 catalyst_source_refs 的確切 short_term_market_context 路徑；無支持證據時可為空陣列。",
    )
    transaction_cost: str | None = Field(default=None, description="每股來回交易成本金額，含費稅與滑價；未知為 null，明確免費才為 0。")
    observed_signal: str | None = Field(default=None, description="已觀測事實，保留日期、期間、主體、數值與單位；未知為 null。")
    observed_source_refs: list[str] = Field(default_factory=list, max_length=6, description="observed_signal 自有的完整可見來源路徑；不可借摘要或事件的引用。")
    event_catalyst: TradeEventCatalyst | None = Field(default=None, description="逐字對應 event_calendar record 的事件、日期、時區與狀態；缺資料為 null，不得把新聞日期當事件日。")
    recheck_condition: str | None = Field(default=None, description="純未來條件，使用『等待…後再重新評估』；不含已发生事實或交易指令。")
    financial_risk_flags: list[str] = Field(default_factory=list, max_length=6, description="模型輸出空陣列；由系統根據可驗證原始財務資料填入風險警示，不混入催化文字。")

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
                "support_level": "N/A",
                "resistance_level": "N/A",
                "core_catalyst": "N/A",
                "risk_level": "High",
                "support_source_refs": [],
                "resistance_source_refs": [],
                "catalyst_source_refs": [],
            }
        normalized = {**setup}
        from trade_catalyst_semantics import normalize_trade_catalyst_fields
        normalized.update(normalize_trade_catalyst_fields(setup))
        normalized["transaction_cost"] = optional_execution_text(setup.get("transaction_cost"))
        if _safe_mapping_has_key(setup, "trade_direction"):
            raw_trade_direction = _safe_mapping_value(setup, "trade_direction")
            if not isinstance(raw_trade_direction, str):
                normalized["trade_direction"] = "Neutral"
        if _safe_mapping_has_key(setup, "entry_zone"):
            normalized["entry_zone"] = _safe_string_text(_safe_mapping_value(setup, "entry_zone"), "N/A")
        if _safe_mapping_has_key(setup, "target_price"):
            normalized["target_price"] = _safe_string_text(_safe_mapping_value(setup, "target_price"), "N/A")
        if _safe_mapping_has_key(setup, "stop_loss"):
            normalized["stop_loss"] = _safe_string_text(_safe_mapping_value(setup, "stop_loss"), "N/A")
        if not _safe_mapping_has_key(setup, "support_level"):
            normalized["support_level"] = "N/A"
        else:
            normalized["support_level"] = _safe_string_text(_safe_mapping_value(setup, "support_level"), "N/A")
        if not _safe_mapping_has_key(setup, "resistance_level"):
            normalized["resistance_level"] = "N/A"
        else:
            normalized["resistance_level"] = _safe_string_text(_safe_mapping_value(setup, "resistance_level"), "N/A")
        if _safe_mapping_has_key(setup, "core_catalyst"):
            normalized["core_catalyst"] = _safe_string_text(_safe_mapping_value(setup, "core_catalyst"), "N/A")
        if _safe_mapping_has_key(setup, "risk_level"):
            raw_risk_level = _safe_mapping_value(setup, "risk_level")
            if not isinstance(raw_risk_level, str):
                normalized["risk_level"] = "High"
        for key in (
            "support_source_refs",
            "resistance_source_refs",
            "catalyst_source_refs",
        ):
            normalized[key] = _safe_string_text_list(setup.get(key))[:6]
        return normalized
