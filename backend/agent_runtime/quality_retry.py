"""Pre-final-audit quality retry helpers for agent outputs."""

from __future__ import annotations

import copy
from collections.abc import Awaitable, Callable

from analysis_types import AnalysisContext, StockData
from llm_client import KeyRotator
from runtime_events import emit_log
from validators import sanitize_model_output

from .cancellation import raise_if_cancelled
from .quality_drafts import AgentQualityDraftError
from .repair_reflection import build_audit_retry_instruction
from .routing import get_agent_model_sequence, get_runtime_model_sequence, is_agent_execution_failure
from .retry_policy import AgentConfigurationError


def record_agent_quality_retry(context: AnalysisContext, agent_num: int) -> None:
    counts = context.setdefault("agent_quality_retry_counts", {})
    try:
        counts[agent_num] = int(counts.get(agent_num, 0) or 0) + 1
    except AttributeError:
        context["agent_quality_retry_counts"] = {agent_num: 1}


def quality_retry_model_sequence(agent_num: int, context: AnalysisContext) -> list[str]:
    models = get_runtime_model_sequence(agent_num, context)
    if not models:
        raise AgentConfigurationError(f"Agent {agent_num} 品質重寫未設定可用模型路由。")
    return list(dict.fromkeys(models))


def install_quality_retry_context(context: AnalysisContext, agent_num: int, issues: list[str]) -> dict[str, object]:
    models = quality_retry_model_sequence(agent_num, context)
    previous = {
        "_audit_retry_instruction": context.get("_audit_retry_instruction"),
        "_model_sequence_override": context.get("_model_sequence_override"),
    }
    context["_audit_retry_instruction"] = build_audit_retry_instruction(agent_num, issues)
    model_override = dict(previous["_model_sequence_override"] or {}) if isinstance(previous["_model_sequence_override"], dict) else {}
    model_override[agent_num] = models
    context["_model_sequence_override"] = model_override
    context.setdefault("structured_outputs", {}).pop(agent_num, None)
    context.setdefault("structured_outputs", {}).pop(str(agent_num), None)
    record_agent_quality_retry(context, agent_num)
    return previous


def restore_quality_retry_context(context: AnalysisContext, previous: dict[str, object]) -> None:
    previous_retry_instruction = previous.get("_audit_retry_instruction")
    previous_model_sequence_override = previous.get("_model_sequence_override")
    if previous_retry_instruction is None:
        context.pop("_audit_retry_instruction", None)
    else:
        context["_audit_retry_instruction"] = previous_retry_instruction
    if previous_model_sequence_override is None:
        context.pop("_model_sequence_override", None)
    else:
        context["_model_sequence_override"] = previous_model_sequence_override


async def retry_after_agent_quality_issues(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    progress_callback,
    issues: list[str],
    *,
    agent_position: int,
    agent_total: int,
    agent_name: str,
    pipeline_id: str | None,
    pipeline_label: str | None,
    run_agent_async: Callable[[int, StockData, AnalysisContext, KeyRotator], Awaitable[str]],
    emit_status,
    parse_structured_output: Callable[[int, str, AnalysisContext], tuple[bool, str]],
) -> str:
    await emit_status(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）觸發品質紅線，正在帶著具體問題重寫一次...",
        phase="agent_quality_retry",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
    )
    emit_log("  🚨 Agent 輸出觸發品質紅線，退回同一 Agent 立即重寫一次...")
    for issue in issues[:5]:
        emit_log(f"     - {issue}")

    original = str((context.get("analyses") or {}).get(agent_num) or (context.get("analyses") or {}).get(str(agent_num)) or "")
    outputs = context.setdefault("structured_outputs", {})
    original_structured = {key: copy.deepcopy(outputs[key]) for key in (agent_num, str(agent_num)) if key in outputs}

    async def retain_draft(error: str) -> None:
        outputs.pop(agent_num, None)
        outputs.pop(str(agent_num), None)
        outputs.update(original_structured)
        context.setdefault("blocking_issues", []).extend(f"Agent {agent_num} {agent_name}: {issue}" for issue in issues)
        await emit_status(
            progress_callback,
            f"Agent {agent_num} 品質重寫未完成，原稿保留為未通過草稿。",
            phase="agent_quality_retry_failed", level="warning", agent_num=agent_num,
            pipeline_id=pipeline_id, pipeline_label=pipeline_label,
            metadata={"issues": issues[:20], "retry_error": error[:500], "draft_text": original[:100000], "draft_truncated": len(original) > 100000},
        )

    previous = install_quality_retry_context(context, agent_num, issues)
    try:
        raise_if_cancelled(context)
        retry_result = await run_agent_async(agent_num, data, context, rotator)
        retry_result = sanitize_model_output(retry_result)
        if is_agent_execution_failure(retry_result):
            raise AgentQualityDraftError(agent_num, retry_result)
        parsed_ok, parsed_result = parse_structured_output(agent_num, retry_result, context)
        return parsed_result if parsed_ok else retry_result
    except Exception as exc:
        if isinstance(exc, AgentQualityDraftError):
            await retain_draft(exc.detail)
        elif original:
            await retain_draft(str(exc))
        raise
    finally:
        restore_quality_retry_context(context, previous)
