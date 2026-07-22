"""Render report confidence and reproducibility controls."""

from __future__ import annotations

from html import escape

from mapping_fields import safe_mapping_dict, safe_text, safe_text_list
from report_reproducibility import build_data_confidence_controls, build_reproducibility_packet

from .text_tokens import is_missing_text_token


def build_trust_controls_html(data: dict, context: dict | None = None) -> str:
    data = safe_mapping_dict(data) or {}
    ctx = _context_with_data(data, context)
    trust = data.get("data_trust")
    controls = build_data_confidence_controls(ctx, trust)
    guardrail = controls["conclusion_guardrails"]["explicit_target_price"]
    packet = build_reproducibility_packet(ctx, trust, _generated_at_text(ctx))
    status = "允許明確目標價" if guardrail["allowed"] else "僅允許區間或資料不足"
    providers = _provider_list_text(packet)
    code_status = _code_status(packet)
    return f"""
        <div class="data-trust-controls">
            <span>資料信心分數：{escape(str(controls["data_confidence_score"]))}/100</span>
            <span>目標價規則：{escape(status)}</span>
            <span>可重現資訊：Pipeline {escape(_packet_text(packet, "pipeline_id"))} ·
                Model {escape(_packet_text(packet, "model_id", "unknown"))} ·
                Prompt 版本 {escape(_packet_text(packet, "prompt_version"))} ·
                {escape(code_status)} ·
                Provider {escape(providers)} ·
                資料時間 {escape(_packet_text(packet, "source_data_time"))}
            </span>
        </div>
    """


def build_trust_controls_markdown(data: dict, context: dict | None = None) -> list[str]:
    data = safe_mapping_dict(data) or {}
    ctx = _context_with_data(data, context)
    trust = data.get("data_trust")
    controls = build_data_confidence_controls(ctx, trust)
    guardrail = controls["conclusion_guardrails"]["explicit_target_price"]
    packet = build_reproducibility_packet(ctx, trust, _generated_at_text(ctx))
    status = "允許明確目標價" if guardrail["allowed"] else "僅允許區間或資料不足"
    providers = _provider_list_text(packet)
    code_status = _code_status(packet)
    repro = (
        f"Pipeline {_packet_text(packet, 'pipeline_id')}；"
        f"Model {_packet_text(packet, 'model_id', 'unknown')}；"
        f"Prompt 版本 {_packet_text(packet, 'prompt_version')}；"
        f"{code_status}；"
        f"Provider {providers}；"
        f"資料時間 {_packet_text(packet, 'source_data_time')}"
    )
    return [
        f"- **資料信心分數:** {controls['data_confidence_score']}/100",
        f"- **目標價規則:** {status}",
        f"- **可重現資訊:** {repro}",
    ]


def _code_status(packet: dict) -> str:
    commit = _packet_text(packet, "code_commit")[:12] or "N/A"
    dirty = packet.get("code_dirty")
    if dirty is True:
        return f"程式碼狀態：{commit}（含未提交變更）"
    if dirty is False:
        return f"程式碼狀態：{commit}（乾淨）"
    return f"程式碼狀態：{commit}（工作樹狀態未知）"


def _generated_at_text(context: dict) -> str:
    return _line_text(context.get("generated_at"), "")


def _packet_text(packet: dict, key: str, default: str = "N/A") -> str:
    return _line_text(packet.get(key), default)


def _provider_list_text(packet: dict) -> str:
    providers = [_line_text(provider, "") for provider in safe_text_list(packet.get("provider_list"))]
    providers = [provider for provider in providers if provider]
    return ", ".join(providers) or "N/A"


def _line_text(value, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    if is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _context_with_data(data: dict, context: dict | None) -> dict:
    ctx = safe_mapping_dict(context) or {}
    ctx["data"] = safe_mapping_dict(ctx.get("data")) or data
    return ctx
