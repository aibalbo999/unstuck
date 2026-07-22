"""HTML and Markdown rendering for evidence matrix rows."""

from __future__ import annotations

from html import escape
from typing import Any

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number

from .html_sanitizer import sanitize_report_plain_text
from .text_tokens import is_missing_text_token


def render_evidence_matrix_html(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{_html_cell(row['claim'])}</td>"
        f"<td>{_html_cell(row['basis'])}</td>"
        f"<td>{_html_cell(row['source'])}</td>"
        f"<td>{_html_cell(row['provider'])}</td>"
        f"<td><span class=\"audit-status audit-status-{_html_cell(row['status'])}\">{_html_cell(row['status_label'])}</span></td>"
        f"<td>{_html_cell(row['fetched_at'])}</td>"
        f"<td>{_html_cell(row['limitation'])}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
        <div class="source-audit-block">
            <h4>報告證據矩陣</h4>
            <div class="source-audit-scroll">
                <table class="source-audit-table">
                    <thead>
                        <tr>
                            <th>結論</th><th>報告依據</th><th>資料來源</th><th>Provider</th>
                            <th>狀態</th><th>抓取時間</th><th>資料限制</th>
                        </tr>
                    </thead>
                    <tbody>{body}</tbody>
                </table>
            </div>
        </div>
    """


def render_evidence_matrix_markdown(rows: list[dict]) -> list[str]:
    if not rows:
        return []
    lines = [
        "## 報告證據矩陣",
        "",
        "| 結論 | 報告依據 | 資料來源 | Provider | 狀態 | 抓取時間 | 資料限制 |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{_markdown_cell(row['claim'])} | "
            f"{_markdown_cell(row['basis'])} | "
            f"{_markdown_cell(row['source'])} | "
            f"{_markdown_cell(row['provider'])} | "
            f"{_markdown_cell(row['status_label'])} | "
            f"{_markdown_cell(row['fetched_at'])} | "
            f"{_markdown_cell(row['limitation'])} |"
        )
    lines.append("")
    return lines


def _html_cell(value: Any) -> str:
    return escape(_text(value))


def _markdown_cell(value: Any) -> str:
    return _text(value).replace("|", "/").replace("\n", " ")


def _text(value: Any, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = sanitize_report_plain_text(safe_text(value)).strip()
    if is_missing_text_token(text):
        return default
    return text or default
