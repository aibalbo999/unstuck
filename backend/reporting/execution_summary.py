"""Deterministic execution trace summary for rendered reports."""

from __future__ import annotations

from html import escape
from typing import Any

from analysis_types import AnalysisContext
from config import format_model_routes
from data_trust import normalize_data_trust, trust_status_label
from pipeline_modes import get_pipeline_definition


def _agent_sequence(context: AnalysisContext, pipeline_def: dict) -> list[int]:
    raw_sequence = context.get("agent_sequence") or pipeline_def.get("agents") or []
    sequence: list[int] = []
    for item in raw_sequence:
        try:
            sequence.append(int(item))
        except (TypeError, ValueError):
            continue
    return sequence


def _status(value: Any, default: str = "N/A") -> str:
    text = str(value or "").strip()
    return text or default


def _execution_summary_values(context: AnalysisContext, *, model_routes: str | None = None) -> dict:
    data = context.get("data", {}) if isinstance(context.get("data"), dict) else {}
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    agent_sequence = _agent_sequence(context, pipeline_def)
    final_audit = context.get("final_audit") if isinstance(context.get("final_audit"), dict) else {}
    evidence_gate = context.get("evidence_exit_gate") if isinstance(context.get("evidence_exit_gate"), dict) else {}
    report_conformance = context.get("report_conformance") if isinstance(context.get("report_conformance"), dict) else {}
    report_lint = context.get("report_lint") if isinstance(context.get("report_lint"), dict) else {}
    data_trust = normalize_data_trust(data.get("data_trust"))
    structured_agents = pipeline_def.get("structured_agents") if isinstance(pipeline_def.get("structured_agents"), dict) else {}
    return {
        "pipeline": f"V{str(pipeline_def.get('id', 'v1')).lstrip('v').upper()}",
        "pipeline_label": pipeline_def.get("label", "N/A"),
        "agent_count": len(agent_sequence),
        "agent_sequence": agent_sequence,
        "structured_agent_count": len(structured_agents),
        "model_routes": model_routes or format_model_routes(pipeline_id=pipeline_def.get("id", "v1")),
        "data_trust": trust_status_label(str(data_trust.get("status") or "unknown")),
        "data_trust_raw": str(data_trust.get("status") or "unknown"),
        "final_audit": _status(final_audit.get("status"), "not_recorded"),
        "evidence_gate": _status(evidence_gate.get("verdict"), "not_recorded"),
        "evidence_summary": _status(evidence_gate.get("summary"), ""),
        "report_conformance": _status(report_conformance.get("status"), "not_recorded"),
        "conformance_summary": _status(report_conformance.get("summary"), ""),
        "report_lint": _status(report_lint.get("status"), "not_recorded"),
        "prompt_version": _status(context.get("prompt_version"), "N/A"),
        "model_id": _status(context.get("model_id") or context.get("decision_model_id") or context.get("final_model_id"), "N/A"),
    }


def build_execution_summary_markdown(context: AnalysisContext, *, model_routes: str | None = None) -> str:
    values = _execution_summary_values(context, model_routes=model_routes)
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
    values = _execution_summary_values(context, model_routes=model_routes)
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
