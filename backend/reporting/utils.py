"""Split report rendering helper."""

from __future__ import annotations

import re
from html import escape

from .chart_values import billion_twd_series_to_yi_twd, filter_future_price_history, normalize_moat_scores
from .common import markdown_lib
from .debate_formatter import format_debate_text
from .html_sanitizer import sanitize_report_html, sanitize_report_plain_text
from .prompt_leak_sanitizer import (
    contains_prompt_leak_residue,
    normalize_bad_number_commas,
    sanitize_report_text,
    strip_prompt_preamble,
)
from recommendation_labels import normalize_recommendation_label

SOURCE_CITATION_RE = re.compile(r"\[(?:source|cite):([A-Za-z0-9_.:-]{1,96})(?:\|([^\]\n]{1,80}))?\]")


def render_source_citation_tags(text: str) -> str:
    """Convert lightweight citation tags into sanitized HTML hooks."""
    if not text:
        return ""

    def repl(match: re.Match) -> str:
        source_id = sanitize_report_plain_text(match.group(1))
        label = sanitize_report_plain_text(match.group(2) or "來源")
        if not source_id:
            return ""
        return (
            f'<span class="source-citation" data-source-id="{escape(source_id)}" '
            f'role="button" tabindex="0" aria-label="查看來源 {escape(source_id)}">'
            f"[{escape(label)}]</span>"
        )

    return SOURCE_CITATION_RE.sub(repl, text)


def strip_structured_blocks(text: str) -> str:
    """移除已由 UI 卡片呈現的結構化區塊，避免正文重複顯示。"""
    if not text:
        return ""
    text = re.sub(r"\[護城河評分\].*?\[/護城河評分\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\[目標股價\].*?\[/目標股價\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\[投資建議\].*?\[/投資建議\]", "", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def clean_markdown(text: str) -> str:
    """Render Markdown to HTML with a standard parser."""
    if not text:
        return ""

    text = render_source_citation_tags(text)

    if markdown_lib is None:
        escaped = escape(text)
        return sanitize_report_html(f"<p>{escaped.replace(chr(10) + chr(10), '</p><p>').replace(chr(10), '<br>')}</p>")

    html = markdown_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    html = re.sub(r"<table>", '<div class="table-wrapper"><table class="data-table">', html)
    html = html.replace("</table>", "</table></div>")
    return sanitize_report_html(html)


def get_recommendation_color(rec: str) -> str:
    """根據建議返回顏色"""
    rec = normalize_recommendation_label(rec)
    if rec == "買入":
        return "#10b981"  # 綠色
    elif rec in {"避免", "放空"}:
        return "#ef4444"  # 紅色
    else:
        return "#f59e0b"  # 黃色（持有）


def get_recommendation_icon(rec: str) -> str:
    """根據建議返回圖示"""
    rec = normalize_recommendation_label(rec)
    if rec == "買入":
        return "↑"
    elif rec in {"避免", "放空"}:
        return "↓"
    else:
        return "→"
