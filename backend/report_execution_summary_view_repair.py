"""View-time quality projections for report execution summaries."""

from __future__ import annotations

import re
from html import escape

from mapping_fields import safe_mapping_dict, safe_text


EXECUTION_SUMMARY_ITEM_RE = re.compile(
    r'<div class="execution-summary-item(?P<attrs>[^>]*)>\s*'
    r'<span>(?P<label>[^<]*)</span>\s*<strong>[^<]*</strong>\s*</div>',
    re.IGNORECASE,
)
EXECUTION_SUMMARY_NOTE_RE = re.compile(
    r'<div class="execution-summary-note(?P<attrs>[^>]*)>[\s\S]*?</div>',
    re.IGNORECASE,
)
EXECUTION_SUMMARY_MARKDOWN_VALUE_RE = re.compile(
    r'^(?P<prefix>-\s+\*\*)(?P<label>Evidence gate|Content credibility|Report conformance)'
    r'(?P<suffix>:\*\*)[^\r\n]*$',
    re.IGNORECASE | re.MULTILINE,
)
EXECUTION_SUMMARY_MARKDOWN_SUMMARY_RE = re.compile(
    r'^(?P<prefix>-\s+\*\*)(?P<label>證據抽查摘要|內容可信度摘要|符合性摘要)'
    r'(?P<suffix>:\*\*)[^\r\n]*$',
    re.MULTILINE,
)


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", safe_text(value)).strip()


def _current_quality_values(context: dict | None) -> tuple[dict[str, str], dict[str, str]] | None:
    if not isinstance(context, dict) or context.get("_current_quality_projection") is not True:
        return None
    evidence = safe_mapping_dict(context.get("evidence_exit_gate")) or {}
    content = safe_mapping_dict(context.get("content_credibility")) or {}
    conformance = safe_mapping_dict(context.get("report_conformance")) or {}
    statuses = {
        "Evidence gate": _clean(evidence.get("verdict")),
        "Content credibility": _clean(content.get("status")),
        "Report conformance": _clean(conformance.get("status")),
    }
    summaries = {
        "證據抽查摘要": _clean(evidence.get("summary")),
        "內容可信度摘要": _clean(content.get("summary")),
        "符合性摘要": _clean(conformance.get("summary")),
    }
    if not any(statuses.values()) and not any(summaries.values()):
        return None
    return statuses, summaries


def _current_source_attrs(attrs: str) -> str:
    if re.search(r'\bdata-quality-source="[^"]*"', attrs, re.IGNORECASE):
        return re.sub(
            r'\bdata-quality-source="[^"]*"',
            'data-quality-source="current-projection"',
            attrs,
            count=1,
            flags=re.IGNORECASE,
        )
    return f'{attrs} data-quality-source="current-projection"'


def repair_report_execution_summary_quality(html: str, context: dict | None = None) -> str:
    """Overlay current quality statuses and evidence summary onto HTML."""
    quality = _current_quality_values(context)
    if quality is None:
        return html
    statuses, summaries = quality
    if not any(statuses.values()) and not summaries.get("證據抽查摘要"):
        return html

    def replace_item(match: re.Match) -> str:
        label = re.sub(r"\s+", " ", match.group("label") or "").strip()
        value = statuses.get(label)
        if not value:
            return match.group(0)
        attrs = _current_source_attrs(match.group("attrs") or "")
        aria = escape(f"{label}：{value}")
        if re.search(r'\baria-label="[^"]*"', attrs, re.IGNORECASE):
            attrs = re.sub(
                r'\baria-label="[^"]*"',
                f'aria-label="{aria}"',
                attrs,
                count=1,
                flags=re.IGNORECASE,
            )
        else:
            attrs = f'{attrs} aria-label="{aria}"'
        return (
            f'<div class="execution-summary-item{attrs}>'
            f'<span>{escape(label)}</span><strong>{escape(value)}</strong></div>'
        )

    repaired = EXECUTION_SUMMARY_ITEM_RE.sub(replace_item, html)
    evidence_summary = summaries.get("證據抽查摘要")
    if not evidence_summary:
        return repaired

    def replace_note(match: re.Match) -> str:
        attrs = _current_source_attrs(match.group("attrs") or "")
        return f'<div class="execution-summary-note{attrs}>{escape(evidence_summary)}</div>'

    return EXECUTION_SUMMARY_NOTE_RE.sub(replace_note, repaired, count=1)


def repair_report_markdown_execution_summary_quality(markdown: str, context: dict | None = None) -> str:
    """Overlay current quality statuses and summaries onto Markdown."""
    quality = _current_quality_values(context)
    if quality is None:
        return markdown
    statuses, summaries = quality

    def replace_status(match: re.Match) -> str:
        label = match.group("label")
        value = statuses.get(label)
        if not value:
            return match.group(0)
        return f'{match.group("prefix")}{label}{match.group("suffix")} {value}'

    def replace_summary(match: re.Match) -> str:
        label = match.group("label")
        value = summaries.get(label)
        if not value:
            return match.group(0)
        return f'{match.group("prefix")}{label}{match.group("suffix")} {value}'

    repaired = EXECUTION_SUMMARY_MARKDOWN_VALUE_RE.sub(replace_status, markdown)
    return EXECUTION_SUMMARY_MARKDOWN_SUMMARY_RE.sub(replace_summary, repaired)


__all__ = [
    "repair_report_execution_summary_quality",
    "repair_report_markdown_execution_summary_quality",
]
