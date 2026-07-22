"""Visible-section checks for report conformance."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text

from .mode_templates import decision_markdown_heading, summary_markdown_heading
from .text_tokens import is_missing_text_token


_REQUIRED_VISIBLE_MARKERS = (
    {"id": "data_trust", "label": "本報告資料可信度", "html": "本報告資料可信度", "markdown": "## 本報告資料可信度"},
    {"id": "execution_summary", "label": "執行邏輯與模型檢查", "html": "執行邏輯與模型檢查", "markdown": "## 執行邏輯與模型檢查"},
    {"id": "mode_template", "label": "報告模板與閱讀路徑", "html": "報告模板與閱讀路徑", "markdown": "## 報告模板與閱讀路徑"},
    {"id": "source_matrix", "label": "關鍵數據來源對照", "html": "關鍵數據來源對照", "markdown": "## 關鍵數據來源對照"},
    {"id": "source_audit", "label": "來源審計", "html": "來源審計", "markdown": "## 來源審計"},
)


def _text(value: Any, default: str = "") -> str:
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def missing_visible_markers(html: str, markdown: str, profile: dict[str, Any]) -> list[dict[str, str]]:
    """Return required report sections missing from either HTML or Markdown artifacts."""
    missing = []
    html_text = _text(html)
    markdown_text = _text(markdown)
    for marker in _REQUIRED_VISIBLE_MARKERS:
        if marker["html"] not in html_text or marker["markdown"] not in markdown_text:
            missing.append({"id": marker["id"], "label": marker["label"]})
    summary_heading = _text(dict.get(profile, "summary_heading"), "一頁式摘要")
    if summary_heading not in html_text or summary_markdown_heading(profile) not in markdown_text:
        missing.append({"id": "tear_sheet", "label": summary_heading})
    decision_heading = _text(dict.get(profile, "decision_heading"), "最終投資建議")
    if decision_heading not in html_text or decision_markdown_heading(profile) not in markdown_text:
        missing.append({"id": "decision", "label": decision_heading})
    discipline_heading = _text(dict.get(profile, "discipline_heading"))
    if discipline_heading and (discipline_heading not in html_text or f"## {discipline_heading}" not in markdown_text):
        missing.append({"id": "decision_discipline", "label": discipline_heading})
    return missing
