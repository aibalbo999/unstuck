"""User-facing report usage and quality-status notice."""

from __future__ import annotations

from html import escape

from .reading_notice_values import build_report_reading_notice_values


def build_report_reading_notice_html(context: dict) -> str:
    """Build a prominent, deterministic usage notice for the HTML report."""
    values = build_report_reading_notice_values(context)
    checks_html = "".join(
        f'<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>'
        for label, value in values["checks"]
    )
    return f"""
        <section class="report-reading-notice report-reading-notice-{escape(values['state'])}" aria-labelledby="report-reading-notice-title">
            <div class="report-reading-notice-head">
                <div>
                    <div class="report-reading-notice-kicker">使用前先看</div>
                    <h2 id="report-reading-notice-title">報告使用範圍與判讀限制</h2>
                </div>
                <span class="report-reading-notice-status">{escape(values['state_label'])}</span>
            </div>
            <p>本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。</p>
            <ul class="report-reading-notice-checks">{checks_html}</ul>
            <p class="report-reading-notice-note">{escape(values['state_note'])}</p>
        </section>
    """


def build_report_reading_notice_markdown(context: dict) -> str:
    """Build the Markdown counterpart of the report usage notice."""
    values = build_report_reading_notice_values(context)
    checks_markdown = "\n".join(
        f"- **{label}:** {value}"
        for label, value in values["checks"]
    )
    return "\n".join(
        [
            "## 報告使用範圍與判讀限制",
            "",
            f"- **品質 gate 狀態:** {values['state_label']}",
            "- **報告用途:** 本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。",
            checks_markdown,
            f"> {values['state_note']}",
        ]
    )
