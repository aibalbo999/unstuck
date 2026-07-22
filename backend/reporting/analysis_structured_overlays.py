"""Structured-output analysis overlays for generated reports."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text

from .numeric_text import first_finite_number
from .text_tokens import is_missing_text_token


def build_management_sentiment(context: dict) -> dict:
    output = _structured_output(context, 20)
    return {
        "tone": _text(output.get("guidance_tone"), "資料不足"),
        "confidence": _number(output.get("confidence")),
        "highlights": _highlight_rows(output.get("highlights", [])),
        "available": bool(output),
    }


def build_downside_view(context: dict) -> dict:
    output = _structured_output(context, 21)
    return {
        "summary": _text(output.get("thesis_summary"), "紅軍分析未產出可用結論。"),
        "risks": _risk_rows(output.get("downside_risks", [])),
        "available": bool(output),
    }


def _structured_output(context: dict, agent_num: int) -> dict:
    context = safe_mapping_dict(context) or {}
    outputs = safe_mapping_dict(context.get("structured_outputs")) or {}
    value = outputs.get(agent_num, outputs.get(str(agent_num), {}))
    return safe_mapping_dict(value) or {}


def _number(value: Any) -> float | None:
    number = first_finite_number(value)
    return round(number, 4) if number is not None else None


def _text(value: Any, default: str) -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


def _highlight_rows(value: Any) -> list[dict[str, str]]:
    rows = []
    for item in safe_dict_list(value):
        rows.append({
            "keyword": _text(item.get("keyword"), "亮點"),
            "quote": _text(item.get("quote"), ""),
        })
        if len(rows) >= 3:
            break
    return rows


def _risk_rows(value: Any) -> list[dict[str, str]]:
    rows = []
    for item in safe_dict_list(value):
        row = {
            "title": _text(item.get("title"), "下行風險"),
            "evidence": _text(item.get("evidence"), "資料不足"),
            "severity": _severity_class(item.get("severity")),
        }
        impact = _text(item.get("impact"), "")
        if impact:
            row["impact"] = impact
        rows.append(row)
        if len(rows) >= 5:
            break
    return rows


def _severity_class(value: Any) -> str:
    text = safe_text(value).strip().lower()
    return text if text in {"low", "medium", "high", "critical"} else "high"


__all__ = ["build_downside_view", "build_management_sentiment"]
