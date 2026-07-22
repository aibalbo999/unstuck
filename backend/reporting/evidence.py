"""Key data evidence tables for rendered reports."""

from __future__ import annotations

from html import escape

from mapping_fields import safe_text
from numeric_safety import is_non_finite_number

from .evidence_rows import build_key_evidence_rows
from .text_tokens import is_missing_text_token


def _cell_text(value, default: str = "N/A") -> str:
    if is_non_finite_number(value):
        return default
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return text or default


def build_key_evidence_html(data: dict) -> str:
    rows = build_key_evidence_rows(data)
    if not rows:
        return ""
    body = "".join(
        "<tr>"
        f"<td>{escape(_cell_text(row['label']))}</td>"
        f"<td>{escape(_cell_text(row['source_label']))}</td>"
        f"<td>{escape(_cell_text(row['provider']))}</td>"
        f"<td><span class=\"audit-status audit-status-{escape(_cell_text(row['status'], 'unknown'))}\">{escape(_cell_text(row['status_label']))}</span></td>"
        f"<td>{escape(_cell_text(row['fetched_at']))}</td>"
        f"<td>{escape(_cell_text(row['record_count']))}</td>"
        f"<td>{'是' if row['stale'] else '否'}</td>"
        "</tr>"
        for row in rows
    )
    return f"""
        <div class="source-audit-block">
            <h4>關鍵數據來源對照</h4>
            <div class="source-audit-scroll">
                <table class="source-audit-table">
                    <thead>
                        <tr>
                            <th>數據</th><th>來源</th><th>Provider</th><th>狀態</th>
                            <th>抓取時間</th><th>筆數</th><th>過期</th>
                        </tr>
                    </thead>
                    <tbody>{body}</tbody>
                </table>
            </div>
        </div>
    """


def _markdown_cell(value) -> str:
    text = _cell_text(value)
    return text.replace("|", "/").replace("\n", " ")


def build_key_evidence_markdown(data: dict) -> list[str]:
    rows = build_key_evidence_rows(data)
    if not rows:
        return []
    lines = [
        "## 關鍵數據來源對照",
        "",
        "| 數據 | 來源 | Provider | 狀態 | 抓取時間 | 筆數 | 過期 |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            f"{_markdown_cell(row['label'])} | "
            f"{_markdown_cell(row['source_label'])} | "
            f"{_markdown_cell(row['provider'])} | "
            f"{_markdown_cell(row['status_label'])} | "
            f"{_markdown_cell(row['fetched_at'])} | "
            f"{_markdown_cell(row['record_count'])} | "
            f"{'是' if row['stale'] else '否'} |"
        )
    lines.append("")
    return lines
