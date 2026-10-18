"""User-facing report usage and quality-status notice."""

from __future__ import annotations

from html import escape
from report_analysis_completeness import assess_report_analysis_completeness

from .reading_notice_values import build_report_reading_notice_values


def build_report_reading_notice_html(context: dict) -> str:
    """Build a prominent, deterministic usage notice for the HTML report."""
    values = build_report_reading_notice_values(context)
    completeness = assess_report_analysis_completeness(context)
    derived = [item for item in (context.get("evidence_exit_gate") or {}).get("sampled_claims", []) if item.get("claim_type") == "derived_calculation" and item.get("status") == "mismatch"]
    if derived:
        values["checks"].append(("算式與期間", "發現衍生算式或年度／TTM 期間矛盾，原敘述保留供查核，不可引用該估值結論"))
    checks_html = "".join(
        f'<li><span>{escape(label)}</span><strong>{escape(value)}</strong></li>'
        for label, value in values["checks"]
    )
    from report_publication_identity import replay_notice, publication_identity
    notice = replay_notice(context)
    replay_html = f'<p class="report-reading-notice-note" data-publication-kind="{escape(publication_identity(context)["kind"])}">{escape(notice)}</p>' if notice else ""
    return f"""
        <section class="report-reading-notice report-reading-notice-{escape(values['state'])}" aria-labelledby="report-reading-notice-title">
            <div class="report-reading-notice-head">
                <div>
                    <div class="report-reading-notice-kicker">使用前先看</div>
                    <h2 id="report-reading-notice-title">報告使用範圍與判讀限制</h2>
                </div>
                <span class="report-reading-notice-status">{escape(values['state_label'])}</span>
            </div>
            {replay_html}
            <p>本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。</p>
            <ul class="report-reading-notice-checks">{checks_html}</ul>
            <p class="report-reading-notice-note" data-analysis-completeness="{escape(completeness['status'])}"><strong>分析完整度：{escape(completeness['label'])}</strong> — {escape(completeness['summary'])}</p>
            <p class="report-reading-notice-note">{escape(values['state_note'])}</p>
        </section>
    """


def build_report_reading_notice_markdown(context: dict) -> str:
    """Build the Markdown counterpart of the report usage notice."""
    values = build_report_reading_notice_values(context)
    completeness = assess_report_analysis_completeness(context)
    checks_markdown = "\n".join(
        f"- **{label}:** {value}"
        for label, value in values["checks"]
    )
    from report_publication_identity import replay_notice, publication_identity
    notice = replay_notice(context)
    return "\n".join(
        [
            "## 報告使用範圍與判讀限制",
            notice,
            "",
            f"- **品質 gate 狀態:** {values['state_label']}",
            "- **報告用途:** 本報告提供研究摘要、資料整理與情境分析，不是即時下單訊號，也不保證未來報酬。",
            checks_markdown,
            f"- **分析完整度:** {completeness['label']} — {completeness['summary']}",
            f"> {values['state_note']}",
        ]
    )
