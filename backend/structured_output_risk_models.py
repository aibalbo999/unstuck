"""Management, risk, and trade setup structured output schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import ConfigDict, Field, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_model_base import (
    _DOWNSIDE_RISK_SEVERITIES,
    _MANAGEMENT_GUIDANCE_TONES,
    _safe_mapping_has_key,
    _safe_mapping_value,
    _safe_number,
    _safe_string_text,
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
            "keyword": _safe_string_text(highlight.get("keyword"), "亮點"),
            "quote": _safe_string_text(highlight.get("quote"), "資料不足"),
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
    severity = _safe_string_text(risk.get("severity"))
    return {
        **risk,
        "title": _safe_string_text(risk.get("title"), "下行風險"),
        "evidence": _safe_string_text(risk.get("evidence"), "資料不足"),
        "impact": _safe_string_text(risk.get("impact")),
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
            "thesis_summary": _safe_string_text(root.get("thesis_summary"), "資料不足"),
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
        normalized = {**setup}
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
        if _safe_mapping_has_key(setup, "core_catalyst"):
            normalized["core_catalyst"] = _safe_string_text(_safe_mapping_value(setup, "core_catalyst"), "N/A")
        if _safe_mapping_has_key(setup, "risk_level"):
            raw_risk_level = _safe_mapping_value(setup, "risk_level")
            if not isinstance(raw_risk_level, str):
                normalized["risk_level"] = "High"
        return normalized
