"""Render report confidence and reproducibility controls."""

from __future__ import annotations

from html import escape

from report_reproducibility import build_data_confidence_controls, build_reproducibility_packet


def build_trust_controls_html(data: dict, context: dict | None = None) -> str:
    ctx = _context_with_data(data, context)
    trust = data.get("data_trust") if isinstance(data, dict) else {}
    controls = build_data_confidence_controls(ctx, trust)
    guardrail = controls["conclusion_guardrails"]["explicit_target_price"]
    packet = build_reproducibility_packet(ctx, trust, str(ctx.get("generated_at") or ""))
    status = "允許明確目標價" if guardrail["allowed"] else "僅允許區間或資料不足"
    providers = ", ".join(packet.get("provider_list") or []) or "N/A"
    return f"""
        <div class="data-trust-controls">
            <span>資料信心分數：{escape(str(controls["data_confidence_score"]))}/100</span>
            <span>目標價規則：{escape(status)}</span>
            <span>可重現資訊：Pipeline {escape(packet.get("pipeline_id") or "N/A")} ·
                Model {escape(packet.get("model_id") or "unknown")} ·
                Prompt 版本 {escape(packet.get("prompt_version") or "N/A")} ·
                Provider {escape(providers)} ·
                資料時間 {escape(packet.get("source_data_time") or "N/A")}
            </span>
        </div>
    """


def build_trust_controls_markdown(data: dict, context: dict | None = None) -> list[str]:
    ctx = _context_with_data(data, context)
    trust = data.get("data_trust") if isinstance(data, dict) else {}
    controls = build_data_confidence_controls(ctx, trust)
    guardrail = controls["conclusion_guardrails"]["explicit_target_price"]
    packet = build_reproducibility_packet(ctx, trust, str(ctx.get("generated_at") or ""))
    status = "允許明確目標價" if guardrail["allowed"] else "僅允許區間或資料不足"
    providers = ", ".join(packet.get("provider_list") or []) or "N/A"
    repro = (
        f"Pipeline {packet.get('pipeline_id') or 'N/A'}；"
        f"Model {packet.get('model_id') or 'unknown'}；"
        f"Prompt 版本 {packet.get('prompt_version') or 'N/A'}；"
        f"Provider {providers}；"
        f"資料時間 {packet.get('source_data_time') or 'N/A'}"
    )
    return [
        f"- **資料信心分數:** {controls['data_confidence_score']}/100",
        f"- **目標價規則:** {status}",
        f"- **可重現資訊:** {repro}",
    ]


def _context_with_data(data: dict, context: dict | None) -> dict:
    ctx = dict(context or {})
    if "data" not in ctx:
        ctx["data"] = data if isinstance(data, dict) else {}
    return ctx
