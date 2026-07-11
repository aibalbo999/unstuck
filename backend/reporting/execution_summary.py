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
    data = raw_data if isinstance(raw_data := dict.get(context, "data"), dict) else {}
    pipeline_def = get_pipeline_definition(dict.get(context, "pipeline_id", "v1"))
    agent_sequence = _agent_sequence(context, pipeline_def)
    final_audit = raw_final_audit if isinstance(raw_final_audit := dict.get(context, "final_audit"), dict) else {}
    evidence_gate = raw_evidence_gate if isinstance(raw_evidence_gate := dict.get(context, "evidence_exit_gate"), dict) else {}
    report_conformance = raw_report_conformance if isinstance(raw_report_conformance := dict.get(context, "report_conformance"), dict) else {}
    report_lint = raw_report_lint if isinstance(raw_report_lint := dict.get(context, "report_lint"), dict) else {}
    data_trust = normalize_data_trust(dict.get(data, "data_trust"))
    structured_agents = raw_structured_agents if isinstance(raw_structured_agents := dict.get(pipeline_def, "structured_agents"), dict) else {}
    return {
        "pipeline": f"V{str(dict.get(pipeline_def, 'id', 'v1')).lstrip('v').upper()}",
        "pipeline_label": dict.get(pipeline_def, "label", "N/A"),
        "agent_count": len(agent_sequence),
        "agent_sequence": agent_sequence,
        "structured_agent_count": len(structured_agents),
        "model_routes": model_routes or format_model_routes(pipeline_id=dict.get(pipeline_def, "id", "v1")),
        "data_trust": trust_status_label(str(dict.get(data_trust, "status") or "unknown")),
        "data_trust_raw": str(dict.get(data_trust, "status") or "unknown"),
        "final_audit": _status(dict.get(final_audit, "status"), "not_recorded"),
        "evidence_gate": _status(dict.get(evidence_gate, "verdict"), "not_recorded"),
        "evidence_summary": _status(dict.get(evidence_gate, "summary"), ""),
        "report_conformance": _status(dict.get(report_conformance, "status"), "not_recorded"),
        "conformance_summary": _status(dict.get(report_conformance, "summary"), ""),
        "report_lint": _status(dict.get(report_lint, "status"), "not_recorded"),
        "prompt_version": _status(dict.get(context, "prompt_version"), "N/A"),
        "model_id": _status(dict.get(context, "model_id") or dict.get(context, "decision_model_id") or dict.get(context, "final_model_id"), "N/A"),
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
