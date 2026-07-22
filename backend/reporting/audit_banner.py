"""System abnormality banner rendering for generated reports."""

from __future__ import annotations

from html import escape

from analysis_types import AnalysisContext
from mapping_fields import safe_mapping_dict, safe_sequence_items, safe_text
from numeric_safety import is_non_finite_number

from .text_tokens import is_missing_text_token


_LINT_MASK = [
    ("[Agent ", "[分析模組 "),
    ("執行失敗", "分析中止"),
    ("所有模型/Key 不可用", "API不可用"),
    ("RESOURCE_EXHAUSTED", "額度耗盡"),
    ("Too Many Requests", "請求過多"),
    ("HTTP 429", "請求過多"),
    ("503 UNAVAILABLE", "模型服務暫時不可用"),
    ("429 RESOURCE_EXHAUSTED", "模型額度暫時不足"),
]


def build_audit_sections(context: AnalysisContext) -> list[tuple[str, list[str]]]:
    """Collect final audit and preserved abnormality notes for rendering."""
    context = safe_mapping_dict(context) or {}
    audit = safe_mapping_dict(context.get("final_audit")) or {}
    sections = []

    critical = _mask_items(audit.get("critical"))
    blocking = [issue for issue in _mask_items(context.get("blocking_issues")) if issue not in critical]
    if not critical and not blocking:
        return []

    if critical or blocking:
        sections.append(("仍需注意的異常", [*critical[:10], *blocking[:6]]))

    repair_log = _mask_items(context.get("audit_repair_log"))
    if repair_log:
        sections.append(("自動修復紀錄", repair_log[:10]))

    corrections = _mask_items(audit.get("corrections"))
    if corrections:
        sections.append(("系統已套用校正", corrections[:8]))

    warnings = _mask_items(audit.get("warnings"))
    if warnings:
        sections.append(("非阻斷提醒", warnings[:8]))

    return [(title, items) for title, items in sections if items]


def build_audit_banner_html(context: AnalysisContext) -> str:
    """Render a visible report warning when final audit found abnormalities."""
    sections = build_audit_sections(context)
    if not sections:
        return ""

    section_html = []
    for title, items in sections:
        lis = "".join(f"<li>{escape(item)}</li>" for item in items)
        section_html.append(f"<div class=\"audit-section\"><strong>{escape(title)}</strong><ul>{lis}</ul></div>")

    return f"""
        <div class="audit-banner">
            <div class="audit-title">系統異常提醒：本報告已保留供檢視</div>
            <div class="audit-subtitle">系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。</div>
            {''.join(section_html)}
        </div>
    """


def build_audit_markdown(context: AnalysisContext) -> str:
    sections = build_audit_sections(context)
    if not sections:
        return ""

    lines = [
        "## ⚠️ 系統異常提醒：本報告已保留供檢視",
        "",
        "系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。",
        "",
    ]
    for title, items in sections:
        lines.append(f"### {title}")
        lines.extend(f"- {item_text}" for item in items if (item_text := _markdown_cell(item, "")))
        lines.append("")
    return "\n".join(lines).strip()


def _mask_items(items) -> list[str]:
    return [
        masked
        for item in safe_sequence_items(items)
        if (masked := _mask_blocking_issue(item))
    ]


def _mask_blocking_issue(text: str) -> str:
    """Sanitize lint-triggering substrings before rendering into the report."""
    text = _safe_text(text)
    for old, new in _LINT_MASK:
        text = text.replace(old, new)
    return text


def _safe_text(value, default: str = "") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return text


def _markdown_cell(value, default: str = "N/A") -> str:
    text = _safe_text(value, default).replace("|", "/")
    return " ".join(line.strip() for line in text.splitlines() if line.strip()) or default


__all__ = ["build_audit_banner_html", "build_audit_markdown", "build_audit_sections"]
