"""Quant fallback warning rendering for report trust sections."""

from __future__ import annotations

from html import escape

from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from numeric_safety import is_non_finite_number
from .text_tokens import is_missing_text_token


def _safe_text(value, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return text or default


def _markdown_cell(value, default: str = "N/A") -> str:
    text = _safe_text(value, default).replace("|", "/")
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _quant_metrics(data: dict) -> dict | None:
    data = safe_mapping_dict(data) or {}
    return safe_mapping_dict(data.get("quant_metrics"))


def _fallback_fields(data: dict) -> list[str]:
    quant = _quant_metrics(data)
    if quant is None:
        return []
    return [
        text
        for field in safe_sequence_items(quant.get("fallback_fields"))
        if (text := _safe_text(field))
    ]


def _warning_message(data: dict) -> str:
    quant = _quant_metrics(data)
    if quant is None:
        return ""
    return _safe_text(quant.get("data_quality_warning"))


def build_quant_warning_html(data: dict) -> str:
    fallback_fields = _fallback_fields(data)
    if not fallback_fields:
        return ""
    warning_msg = _warning_message(data)
    if warning_msg:
        msg = escape(warning_msg)
    else:
        fields_str = "、".join(escape(field) for field in fallback_fields[:6])
        msg = f"以下欄位使用預設假設，DCF/WACC 結論僅供參考：{fields_str}"
    return f'<div class="data-trust-quant-warning">⚠️ <strong>量化模型警示：</strong>{msg}</div>'


def build_quant_warning_markdown(data: dict) -> str:
    fallback_fields = _fallback_fields(data)
    if not fallback_fields:
        return ""
    warning_msg = _warning_message(data)
    if warning_msg:
        msg = _markdown_cell(warning_msg, "")
    else:
        fields = [_markdown_cell(field, "") for field in fallback_fields[:6]]
        fields_str = "、".join(field for field in fields if field)
        msg = f"以下欄位使用預設假設，DCF/WACC 結論僅供參考：{fields_str}"
    return f"- **⚠️ 量化模型警示:** {msg}"
