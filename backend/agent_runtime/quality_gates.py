"""Agent execution plus quality-gate workflow."""

from __future__ import annotations

import time

from agent_catalog import AGENT_NAMES
from analysis_types import AnalysisContext, StockData
from context_digest_tasks import CONTEXT_DIGEST_TARGET_AGENTS, ensure_context_digest_async
from llm_client import KeyRotator
from rag_runtime import ensure_agent_rag_context_async
from runtime_events import emit_log, emit_status_async
from validators import (
    append_identity_warnings,
    append_quality_warnings,
    build_identity_retry_instruction,
    sanitize_model_output,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)
from .cancellation import raise_if_cancelled
from .quality_retry import retry_after_agent_quality_issues
from .quality_structured_outputs import try_parse_structured_output as _try_parse_structured_output
from .routing import get_runtime_model_sequence, is_agent_execution_failure
from .single_agent import run_single_agent_async

async def run_agent_with_quality_gates_async(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    progress_callback=None,
) -> tuple[int, str]:
    agent_name = AGENT_NAMES[agent_num]
    model_id = get_runtime_model_sequence(agent_num, context)[0]
    agent_positions = context.get("agent_positions", {}) or {}
    agent_position = agent_positions.get(agent_num, agent_num)
    agent_total = int(context.get("agent_total") or len(context.get("agent_sequence", []) or []) or 7)
    pipeline_id = context.get("pipeline_id")
    pipeline_label = context.get("pipeline_label")
    raise_if_cancelled(context)

    emit_log(
        f"{'─'*60}\n"
        f"  📌 Agent {agent_num}（{agent_position}/{agent_total}）：{agent_name}\n"
        f"  🤖 模型：{model_id}\n"
        f"{'─'*60}"
    )

    start = time.time()
    await emit_status_async(
        progress_callback,
        f"開始 Agent {agent_num}（{agent_position}/{agent_total}）：{agent_name}（{model_id}）",
        phase="started",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
    )
    context["structured_outputs"].pop(agent_num, None)
    raise_if_cancelled(context)
    if agent_num in CONTEXT_DIGEST_TARGET_AGENTS:
        await emit_status_async(
            progress_callback,
            f"Agent {agent_num}（{agent_position}/{agent_total}）正在提煉前序分析摘要...",
            phase="context_digest",
            current=agent_position,
            total=agent_total,
            name=agent_name,
            agent_num=agent_num,
            pipeline_id=pipeline_id,
            pipeline_label=pipeline_label,
        )
    await ensure_context_digest_async(agent_num, context, rotator, progress_callback=progress_callback)
    raise_if_cancelled(context)
    await emit_status_async(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在執行 RAG 語意檢索...",
        phase="rag_retrieval",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
    )
    await ensure_agent_rag_context_async(agent_num, context, rotator)
    raise_if_cancelled(context)
    await emit_status_async(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在呼叫模型並生成分析...",
        phase="model_call",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
    )
    result = await run_single_agent_async(agent_num, data, context, rotator)
    raise_if_cancelled(context)
    result = sanitize_model_output(result)
    try:
        parsed_ok, parsed_result = _try_parse_structured_output(agent_num, result, context)
        if parsed_ok:
            result = parsed_result
        else:
            await emit_status_async(
                progress_callback,
                f"Agent {agent_num} 結構化輸出解析失敗，立即重試（1/1）...",
                phase="structured_retry",
                current=agent_position,
                total=agent_total,
                name=agent_name,
                agent_num=agent_num,
                pipeline_id=pipeline_id,
                pipeline_label=pipeline_label,
            )
            context.setdefault("structured_outputs", {}).pop(agent_num, None)
            context.setdefault("structured_outputs", {}).pop(str(agent_num), None)
            raise_if_cancelled(context)
            result = await run_single_agent_async(agent_num, data, context, rotator)
            raise_if_cancelled(context)
            result = sanitize_model_output(result)
            _retry_ok, result = _try_parse_structured_output(agent_num, result, context)
    except Exception as exc:
        emit_log(f"  ⚠️  Agent {agent_num} 結構化輸出即時驗證失敗，略過同節點重試：{str(exc)[:120]}")
    await emit_status_async(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在執行輸出清洗與品質檢查...",
        phase="quality_gate",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_id,
        pipeline_label=pipeline_label,
    )

    if is_agent_execution_failure(result):
        context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
        context["analyses"][agent_num] = result
        emit_log(f"  ❌ {result}")
        return agent_num, result

    prompt_leak_issues = validate_prompt_leakage(result)
    if prompt_leak_issues:
        emit_log("  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
        for issue in prompt_leak_issues:
            emit_log(f"     - {issue}")
        context.setdefault("blocking_issues", []).extend(
            f"Agent {agent_num} {agent_name}: {issue}" for issue in prompt_leak_issues
        )
        context["analyses"][agent_num] = result
        return agent_num, result

    identity_issues = validate_company_identity(result, data)
    if identity_issues:
        await emit_status_async(
            progress_callback,
            f"Agent {agent_num}（{agent_position}/{agent_total}）身分一致性檢查未通過，正在要求重寫...",
            phase="identity_retry",
            current=agent_position,
            total=agent_total,
            name=agent_name,
            agent_num=agent_num,
            pipeline_id=pipeline_id,
            pipeline_label=pipeline_label,
        )
        emit_log("  🚨 公司身分一致性檢查未通過，退回 Agent 非同步重寫...")
        for issue in identity_issues:
            emit_log(f"     - {issue}")
        context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
        context["structured_outputs"].pop(agent_num, None)
        raise_if_cancelled(context)
        retry_result = await run_single_agent_async(agent_num, data, context, rotator)
        retry_result = sanitize_model_output(retry_result)
        retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
        if retry_prompt_leak_issues:
            emit_log("  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}" for issue in retry_prompt_leak_issues
            )
            context.pop("_identity_retry_instruction", None)
            context["analyses"][agent_num] = retry_result
            return agent_num, retry_result

        retry_issues = validate_company_identity(retry_result, data)
        context.pop("_identity_retry_instruction", None)
        result = retry_result
        identity_issues = retry_issues
        if identity_issues:
            emit_log("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
            for issue in identity_issues:
                emit_log(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}" for issue in identity_issues
            )
            result = append_identity_warnings(result, identity_issues)
        else:
            emit_log("  ✅ 重寫後通過公司身分一致性檢查。")

    quality_issues = validate_analysis_output(agent_num, result, data)
    if quality_issues:
        result = await retry_after_agent_quality_issues(
            agent_num,
            data,
            context,
            rotator,
            progress_callback,
            quality_issues,
            agent_position=agent_position,
            agent_total=agent_total,
            agent_name=agent_name,
            pipeline_id=pipeline_id,
            pipeline_label=pipeline_label,
            run_agent_async=run_single_agent_async,
            emit_status=emit_status_async,
            parse_structured_output=_try_parse_structured_output,
        )
        if is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            emit_log(f"  ❌ {result}")
            return agent_num, result

        retry_prompt_leak_issues = validate_prompt_leakage(result)
        if retry_prompt_leak_issues:
            emit_log("  🚨 品質重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}" for issue in retry_prompt_leak_issues
            )
            context["analyses"][agent_num] = result
            return agent_num, result

        retry_identity_issues = validate_company_identity(result, data)
        if retry_identity_issues:
            emit_log("  ❌ 品質重寫後出現公司身分一致性問題，停止產生正式報告。")
            for issue in retry_identity_issues:
                emit_log(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}" for issue in retry_identity_issues
            )
            result = append_identity_warnings(result, retry_identity_issues)

    result = append_quality_warnings(agent_num, result, data)
    elapsed = time.time() - start
    context["analyses"][agent_num] = result

    preview = result[:120].replace("\n", " ")
    emit_log(
        f"  ✅ 完成！耗時 {elapsed:.1f} 秒\n"
        f"  📝 輸出長度：{len(result)} 字元\n"
        f"  💬 預覽：{preview}..."
    )
    return agent_num, result
