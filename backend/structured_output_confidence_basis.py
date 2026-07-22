"""Confidence-basis structured output primitives."""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from mapping_fields import safe_mapping_dict, safe_sequence_items
from structured_output_model_base import StructuredModel, _safe_string_text as _base_safe_string_text


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
            "data_gaps": _safe_string_text_list(basis.get("data_gaps")),
        }


def _safe_required_text_collection(value: Any, minimum: int, fallback: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return [fallback for _ in range(minimum)]
    return _safe_required_text_list(value, minimum, fallback)


def _safe_required_text_list(value: Any, minimum: int, fallback: str) -> list[str]:
    texts = _safe_string_text_list(value)
    if not isinstance(value, (list, tuple)):
        return texts
    while len(texts) < minimum:
        texts.append(fallback)
    return texts


def _safe_string_text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    texts = []
    for item in safe_sequence_items(value):
        text = _safe_string_text(item)
        if text:
            texts.append(text)
    return texts


def _safe_string_text(value: Any, default: str = "") -> str:
    if not isinstance(value, str):
        return default
    return _base_safe_string_text(value, default)
