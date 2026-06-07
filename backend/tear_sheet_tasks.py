"""Tear-sheet generation helpers for report summaries."""

from __future__ import annotations

import json

from google.genai import types

from config import TEAR_SHEET_MODEL
from llm_client import (
    KeyRotator,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    response_text,
)
from prompt_rules import get_task_instruction_lines, get_task_system_instruction
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from validators import sanitize_model_output, strip_generated_audit_sections


def _tear_sheet_model_sequence() -> list[str]:
    return [TEAR_SHEET_MODEL]


def _build_tear_sheet_prompt(context: dict) -> str:
    data = context.get("data", {}) or {}
    parsed = context.get("parsed", {}) or {}
    analyses = context.get("analyses", {}) or {}
    compact_analyses = "\n\n".join(
        f"Agent {agent_num}: {strip_generated_audit_sections(str(text))[:1200]}"
        for agent_num, text in sorted(analyses.items())
    )
    payload = {
        "ticker": data.get("ticker"),
        "company_name": data.get("company_name"),
        "industry": data.get("industry"),
        "current_price": data.get("current_price"),
        "price_targets": parsed.get("price_targets", {}),
        "recommendation": parsed.get("recommendation", {}),
        "recent_catalysts": data.get("recent_catalysts", [])[:3],
        "institutional_trading": data.get("institutional_trading", {}),
        "pe_river_chart": data.get("pe_river_chart", {}),
    }
    instruction_text = "\n".join(get_task_instruction_lines("tear_sheet")).strip()
    instruction_block = f"{instruction_text}\n\n" if instruction_text else ""
    return (
        instruction_block
        + f"結構化資料：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        + f"各 Agent 摘要：\n{compact_analyses}"
    )


def _build_tear_sheet_generation_config():
    return types.GenerateContentConfig(
        temperature=0.35,
        top_p=0.9,
        max_output_tokens=900,
        system_instruction=get_task_system_instruction("tear_sheet"),
    )


def _generate_tear_sheet_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_tear_sheet_generation_config())


async def _generate_tear_sheet_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_tear_sheet_generation_config())


def _tear_sheet_event_kwargs(context: dict, model_id: str, phase: str, message: str, level: str = "info") -> dict:
    return dict(
        phase=phase,
        level=level,
        message=message,
        current=context.get("agent_total"),
        total=context.get("agent_total"),
        name="一頁式摘要",
        pipeline_id=context.get("pipeline_id"),
        pipeline_label=context.get("pipeline_label"),
        metadata={"model_id": model_id, "task": "tear_sheet"},
    )


def ensure_tear_sheet_summary(context: dict, rotator: KeyRotator, progress_callback=None):
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    for model_id in _tear_sheet_model_sequence():
        try:
            emit_context_event(
                context,
                make_runtime_event(
                    "status",
                    **_tear_sheet_event_kwargs(
                        context,
                        model_id,
                        "tear_sheet_model_call",
                        f"一頁式摘要正在呼叫模型 {model_id}...",
                    ),
                ),
                progress_callback,
            )
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=900))
            response = _generate_tear_sheet_content(api_key, model_id, prompt)
            summary = sanitize_model_output(response_text(response))
            if summary:
                context["tear_sheet_summary"] = summary[:900]
                emit_log("  🧾 一頁式摘要已生成。")
                emit_context_event(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(context, model_id, "tear_sheet_done", "一頁式摘要已生成。"),
                    ),
                    progress_callback,
                )
                return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                emit_context_event(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(
                            context,
                            model_id,
                            "model_fallback",
                            f"一頁式摘要模型 {model_id} 不可用，嘗試備援模型。",
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                continue
            message = f"一頁式摘要生成失敗，報表將使用 fallback 摘要：{str(exc)[:120]}"
            emit_log(f"  ⚠️  {message}")
            event = _tear_sheet_event_kwargs(context, model_id, "tear_sheet_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
            emit_context_event(context, make_runtime_event("status", **event), progress_callback)
            return


async def ensure_tear_sheet_summary_async(context: dict, rotator: KeyRotator, progress_callback=None):
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    for model_id in _tear_sheet_model_sequence():
        try:
            await emit_context_event_async(
                context,
                make_runtime_event(
                    "status",
                    **_tear_sheet_event_kwargs(
                        context,
                        model_id,
                        "tear_sheet_model_call",
                        f"一頁式摘要正在呼叫模型 {model_id}...",
                    ),
                ),
                progress_callback,
            )
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=900))
            response = await _generate_tear_sheet_content_async(api_key, model_id, prompt)
            summary = sanitize_model_output(response_text(response))
            if summary:
                context["tear_sheet_summary"] = summary[:900]
                emit_log("  🧾 一頁式摘要已生成。")
                await emit_context_event_async(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(context, model_id, "tear_sheet_done", "一頁式摘要已生成。"),
                    ),
                    progress_callback,
                )
                return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                await emit_context_event_async(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(
                            context,
                            model_id,
                            "model_fallback",
                            f"一頁式摘要模型 {model_id} 不可用，嘗試備援模型。",
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                continue
            message = f"一頁式摘要生成失敗，報表將使用 fallback 摘要：{str(exc)[:120]}"
            emit_log(f"  ⚠️  {message}")
            event = _tear_sheet_event_kwargs(context, model_id, "tear_sheet_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], "error_kind": exc.__class__.__name__}
            await emit_context_event_async(context, make_runtime_event("status", **event), progress_callback)
            return
