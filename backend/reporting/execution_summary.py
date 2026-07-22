"""Deterministic execution trace summary for rendered reports."""

from __future__ import annotations

from html import escape

from analysis_types import AnalysisContext
from .execution_summary_values import build_execution_summary_values


def build_execution_summary_markdown(context: AnalysisContext, *, model_routes: str | None = None) -> str:
    values = build_execution_summary_values(context, model_routes=model_routes)
    sequence_text = " → ".join(f"Agent {agent}" for agent in values["agent_sequence"]) or "N/A"
    lines = [
        "## 執行邏輯與模型檢查",
        f"- **Pipeline:** {values['pipeline']}（{values['pipeline_label']}）",
        f"- **Agent 執行序列:** {sequence_text}",
        f"- **結構化輸出節點:** 共 {values['structured_agent_count']} 個",
        f"- **模型路由:** {values['model_routes']}",
        f"- **資料可信度:** {values['data_trust']}（{values['data_trust_raw']}）",
        f"- **Final audit:** {values['final_audit']}",
        f"- **Evidence gate:** {values['evidence_gate']}",
        f"- **Report conformance:** {values['report_conformance']}",
        f"- **Report lint:** {values['report_lint']}",
        f"- **Prompt / Model:** {values['prompt_version']} / {values['model_id']}",
    ]
    if values["evidence_summary"]:
        lines.append(f"- **證據抽查摘要:** {values['evidence_summary']}")
    if values["conformance_summary"]:
        lines.append(f"- **符合性摘要:** {values['conformance_summary']}")
    return "\n".join(lines)


def build_execution_summary_html(context: AnalysisContext, *, model_routes: str | None = None) -> str:
    values = build_execution_summary_values(context, model_routes=model_routes)
    sequence_text = " → ".join(f"Agent {agent}" for agent in values["agent_sequence"]) or "N/A"
    evidence_summary = (
        f"<div class=\"execution-summary-note\">{escape(values['evidence_summary'])}</div>"
        if values["evidence_summary"]
        else ""
    )
    items = [
        ("Pipeline", f"{values['pipeline']} · {values['pipeline_label']}"),
        ("Agent 執行序列", sequence_text),
        ("結構化輸出節點", f"共 {values['structured_agent_count']} 個"),
        ("模型路由", values["model_routes"]),
        ("資料可信度", f"{values['data_trust']}（{values['data_trust_raw']}）"),
        ("Final audit", values["final_audit"]),
        ("Evidence gate", values["evidence_gate"]),
        ("Report conformance", values["report_conformance"]),
        ("Report lint", values["report_lint"]),
        ("Prompt / Model", f"{values['prompt_version']} / {values['model_id']}"),
    ]
    item_parts = []
    for label, value in items:
        aria = f"{label}：{value}"
        if label == "Pipeline":
            aria = f"Pipeline {values['pipeline']}：{values['pipeline_label']}"
        item_parts.append(
            f"<div class=\"execution-summary-item\" aria-label=\"{escape(aria)}\">"
            f"<span>{escape(label)}</span>"
            f"<strong>{escape(value)}</strong>"
            "</div>"
        )
    item_html = "".join(item_parts)
    return f"""
        <div class="execution-summary-card">
            <div class="execution-summary-head">
                <span>執行邏輯與模型檢查</span>
                <strong>deterministic runtime trace</strong>
            </div>
            <div class="execution-summary-grid">{item_html}</div>
            {evidence_summary}
        </div>
    """
