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
from pipeline_modes import normalize_pipeline_id
from prompt_rules import get_task_instruction_lines, get_task_system_instruction
from llm_key_admission import propagate_admission_cancel
from runtime_events import emit_context_event, emit_context_event_async, emit_log, make_runtime_event
from validators import sanitize_model_output, strip_generated_audit_sections
from summary_consistency import accept_summary, summary_reference_prompt
from llm_response_diagnostics import response_diagnostics
from llm_quota_details import extract_quota_details
from llm_observation_context import observe_purpose
from agent_runtime.llm_call_metadata import _key_slot_fields
from agent_runtime.retry_error_classification import provider_status_code


def _tear_sheet_model_sequence() -> list[str]:
    from agent_runtime.routing import get_audit_model_sequence
    from llm_provider_routes import split_model_provider
    # Reuse configured Google routes; do not introduce a paid provider or new key.
    models = []
    for route in [TEAR_SHEET_MODEL, *get_audit_model_sequence()]:
        provider, model = split_model_provider(route)
        if provider == 'google' and model not in models:
            models.append(model)
    return models


def _summary_can_use_backup(error, model_index, models):
    return model_index + 1 < len(models) and (
        provider_status_code(error) in {429, 500, 502, 503, 504}
        or isinstance(error, TimeoutError))


def _build_tear_sheet_prompt(context: dict) -> str:
    data = context.get("data", {}) or {}
    parsed = context.get("parsed", {}) or {}
    analyses = context.get("analyses", {}) or {}
    compact_analyses = "\n\n".join(
        f"Agent {agent_num}: {strip_generated_audit_sections(str(text))[:1200]}"
        for agent_num, text in sorted(analyses.items())
    )
    payload = {
        "pipeline_id": context.get("pipeline_id"),
        "ticker": data.get("ticker"),
        "company_name": data.get("company_name"),
        "industry": data.get("industry"),
        "current_price": data.get("current_price"),
        "price_targets": parsed.get("price_targets", {}),
        "recommendation": parsed.get("recommendation", {}),
        "position_plan": parsed.get("position_plan", {}),
        "short_setup": parsed.get("short_setup", {}),
        "trade_setup": parsed.get("trade_setup", {}),
        "recent_catalysts": data.get("recent_catalysts", [])[:3],
        "institutional_trading": data.get("institutional_trading", {}),
        "pe_river_chart": data.get("pe_river_chart", {}),
    }
    instruction_text = "\n".join(get_task_instruction_lines("tear_sheet")).strip()
    instruction_block = f"{instruction_text}\n\n" if instruction_text else ""
    return (
        instruction_block
        + summary_reference_prompt(context) + '\n\n'
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


@observe_purpose('tear_sheet')
def _generate_tear_sheet_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_tear_sheet_generation_config())


@observe_purpose('tear_sheet')
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


def _tear_sheet_error_metadata(rotator, api_key, error):
    return {
        'error_kind': error.__class__.__name__,
        'provider_status_code': provider_status_code(error),
        'provider_quota': extract_quota_details(error),
        **_key_slot_fields(rotator, api_key),
    }


def ensure_tear_sheet_summary(context: dict, rotator: KeyRotator, progress_callback=None):
    from agent_runtime.llm_waiting import acquire_key, acquire_key_async
    if normalize_pipeline_id(context.get("pipeline_id")) != "v1":
        return
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    models = _tear_sheet_model_sequence()
    for model_index, model_id in enumerate(models):
        api_key = None
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
            api_key = acquire_key(rotator, model_id, estimate_text_tokens(prompt, response_budget=900), context, None)
            response = _generate_tear_sheet_content(api_key, model_id, prompt)
            raw_text = response_text(response)
            summary = sanitize_model_output(raw_text)
            if summary:
                accepted = accept_summary(summary, context, diagnostics=response_diagnostics(response), raw_text=raw_text)
                if not accepted:
                    event = _tear_sheet_event_kwargs(context, model_id, 'tear_sheet_rejected',
                        '模型摘要未通過金額／分類或完整性核對；有已設定備援時繼續同一檢查，否則使用既有欄位摘要。', level='warning')
                    event['metadata']['validation'] = context['tear_sheet_validation']
                    event['metadata']['candidate_text'] = raw_text[:16000]
                    event['metadata']['candidate_truncated'] = len(raw_text) > 16000
                    emit_context_event(context, make_runtime_event('status', **event), progress_callback)
                    if model_index + 1 < len(models):
                        continue
                    return
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
            propagate_admission_cancel(exc)
            if is_missing_model_error(str(exc)):
                has_fallback = model_index + 1 < len(models)
                emit_context_event(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(
                            context,
                            model_id,
                            "model_fallback" if has_fallback else "tear_sheet_fallback",
                            (
                                f"一頁式摘要模型 {model_id} 不可用，嘗試備援模型。"
                                if has_fallback
                                else f"一頁式摘要模型 {model_id} 不可用，改用 deterministic fallback 摘要。"
                            ),
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                if not has_fallback:
                    return
                continue
            has_fallback = _summary_can_use_backup(exc, model_index, models)
            message = ("一頁式摘要遇到額度或暫時服務錯誤，嘗試已設定備援模型。" if has_fallback
                       else "一頁式摘要生成失敗，報表將使用 fallback 摘要。")
            emit_log(f"  ⚠️  {message}")
            event = _tear_sheet_event_kwargs(context, model_id, "model_fallback" if has_fallback else "tear_sheet_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], **_tear_sheet_error_metadata(rotator, api_key, exc)}
            emit_context_event(context, make_runtime_event("status", **event), progress_callback)
            if has_fallback:
                continue
            return


async def ensure_tear_sheet_summary_async(context: dict, rotator: KeyRotator, progress_callback=None):
    from agent_runtime.llm_waiting import acquire_key, acquire_key_async
    if normalize_pipeline_id(context.get("pipeline_id")) != "v1":
        return
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    models = _tear_sheet_model_sequence()
    for model_index, model_id in enumerate(models):
        api_key = None
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
            api_key = await acquire_key_async(rotator, model_id, estimate_text_tokens(prompt, response_budget=900), context, None)
            response = await _generate_tear_sheet_content_async(api_key, model_id, prompt)
            raw_text = response_text(response)
            summary = sanitize_model_output(raw_text)
            if summary:
                accepted = accept_summary(summary, context, diagnostics=response_diagnostics(response), raw_text=raw_text)
                if not accepted:
                    event = _tear_sheet_event_kwargs(context, model_id, 'tear_sheet_rejected',
                        '模型摘要未通過金額／分類或完整性核對；有已設定備援時繼續同一檢查，否則使用既有欄位摘要。', level='warning')
                    event['metadata']['validation'] = context['tear_sheet_validation']
                    event['metadata']['candidate_text'] = raw_text[:16000]
                    event['metadata']['candidate_truncated'] = len(raw_text) > 16000
                    await emit_context_event_async(context, make_runtime_event('status', **event), progress_callback)
                    if model_index + 1 < len(models):
                        continue
                    return
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
            propagate_admission_cancel(exc)
            if is_missing_model_error(str(exc)):
                has_fallback = model_index + 1 < len(models)
                await emit_context_event_async(
                    context,
                    make_runtime_event(
                        "status",
                        **_tear_sheet_event_kwargs(
                            context,
                            model_id,
                            "model_fallback" if has_fallback else "tear_sheet_fallback",
                            (
                                f"一頁式摘要模型 {model_id} 不可用，嘗試備援模型。"
                                if has_fallback
                                else f"一頁式摘要模型 {model_id} 不可用，改用 deterministic fallback 摘要。"
                            ),
                            level="warning",
                        ),
                    ),
                    progress_callback,
                )
                if not has_fallback:
                    return
                continue
            has_fallback = _summary_can_use_backup(exc, model_index, models)
            message = ("一頁式摘要遇到額度或暫時服務錯誤，嘗試已設定備援模型。" if has_fallback
                       else "一頁式摘要生成失敗，報表將使用 fallback 摘要。")
            emit_log(f"  ⚠️  {message}")
            event = _tear_sheet_event_kwargs(context, model_id, "model_fallback" if has_fallback else "tear_sheet_fallback", message, level="warning")
            event["metadata"] = {**event["metadata"], **_tear_sheet_error_metadata(rotator, api_key, exc)}
            await emit_context_event_async(context, make_runtime_event("status", **event), progress_callback)
            if has_fallback:
                continue
            return
