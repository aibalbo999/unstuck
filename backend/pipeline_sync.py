"""Synchronous analysis pipeline retained for CLI/RQ compatibility."""

from __future__ import annotations

import time

from agent_catalog import AGENT_NAMES
from agent_runtime.audit_repair import finalize_final_audit
from agent_runtime.routing import is_agent_execution_failure
from agent_runtime.single_agent import run_single_agent
from analysis_types import AnalysisContext, StockData
from config import AGENT_MODELS, API_KEYS, EMBEDDING_MODEL, INTER_AGENT_DELAY
from context_digest_tasks import CONTEXT_DIGEST_TARGET_AGENTS, ensure_context_digest
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from rag_runtime import build_rag_index, ensure_agent_rag_context
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, emit_log, emit_progress, emit_status
from tear_sheet_tasks import ensure_tear_sheet_summary
from validators import (
    append_identity_warnings,
    append_quality_warnings,
    build_identity_retry_instruction,
    sanitize_model_output,
    validate_company_identity,
    validate_prompt_leakage,
)


def run_analysis_pipeline(
    data: StockData,
    progress_callback=None,
    pipeline_id: str = "v1",
) -> AnalysisContext:
    """
    Run a sequential analysis pipeline.

    The sync path remains conservative and is mainly retained for CLI/RQ
    compatibility; production jobs use run_analysis_pipeline_async.
    """
    ticker = data["ticker"]
    name = data["company_name"]
    pipeline_def = get_pipeline_definition(normalize_pipeline_id(pipeline_id))
    agent_sequence = pipeline_def["agents"]
    agent_positions = {agent_num: idx + 1 for idx, agent_num in enumerate(agent_sequence)}
    agent_total = len(agent_sequence)

    rotator = KeyRotator(API_KEYS)
    context: AnalysisContext = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "structured_outputs": {},
        "start_time": time.time(),
        "pipeline_id": pipeline_def["id"],
        "pipeline_label": pipeline_def["label"],
        "agent_sequence": agent_sequence,
        "agent_positions": agent_positions,
        "agent_total": agent_total,
    }
    if progress_callback:
        context[RUNTIME_EVENT_CALLBACK_KEY] = progress_callback

    emit_log(
        f"\n{'='*60}\n"
        f"  🚀 開始分析 {ticker} {name}\n"
        f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）\n"
        f"{'='*60}\n"
    )

    _build_rag_index(data, rotator, context, progress_callback, agent_total, pipeline_def)
    for agent_num in agent_sequence:
        _run_sync_agent(agent_num, data, context, rotator, progress_callback, agent_total, pipeline_def)
        if context.get("blocking_issues"):
            break

        agent_position = agent_positions.get(agent_num, agent_num)
        if agent_position < agent_total and INTER_AGENT_DELAY > 0:
            wait = INTER_AGENT_DELAY
            emit_log(f"\n  ⏰ 額外等待 {wait:.1f} 秒後執行下一個 Agent...\n")
            time.sleep(wait)

    _finalize_sync_pipeline(context, rotator, progress_callback, agent_total, pipeline_def)
    return context


def _build_rag_index(data, rotator, context, progress_callback, agent_total, pipeline_def) -> None:
    rag_index = build_rag_index(data, rotator)
    if rag_index is None:
        return
    context["rag_index"] = rag_index
    context["rag_status"] = {
        "model": EMBEDDING_MODEL,
        "chunks": len(getattr(rag_index, "chunks", []) or []),
        "embedded": bool(getattr(rag_index, "has_embeddings", False)),
    }
    emit_log(f"  🔎 RAG 長文本索引完成：{context['rag_status']['chunks']} 個片段。")
    emit_status(
        progress_callback,
        f"RAG 長文本索引完成：{context['rag_status']['chunks']} 個片段。",
        phase="rag_index",
        current=0,
        total=agent_total,
        name="RAG 索引",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
        metadata=context["rag_status"],
    )


def _run_sync_agent(agent_num, data, context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    agent_name = AGENT_NAMES[agent_num]
    model_id = AGENT_MODELS[agent_num]
    agent_position = context["agent_positions"].get(agent_num, agent_num)

    emit_log(
        f"{'─'*60}\n"
        f"  📌 Agent {agent_num}（{agent_position}/{agent_total}）：{agent_name}\n"
        f"  🤖 模型：{model_id}\n"
        f"{'─'*60}"
    )
    emit_status(
        progress_callback,
        f"開始 Agent {agent_num}（{agent_position}/{agent_total}）：{agent_name}（{model_id}）",
        phase="started",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    start = time.time()
    context["structured_outputs"].pop(agent_num, None)
    _prepare_agent_context(agent_num, context, rotator, progress_callback, agent_position, agent_total, agent_name, pipeline_def)
    result = sanitize_model_output(run_single_agent(agent_num, data, context, rotator))
    emit_status(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在執行輸出清洗與品質檢查...",
        phase="quality_gate",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )

    result = _apply_sync_quality_gates(agent_num, agent_name, data, context, rotator, result, progress_callback, agent_position, agent_total, pipeline_def)
    if context.get("blocking_issues"):
        context["analyses"][agent_num] = result
        return

    result = append_quality_warnings(agent_num, result, data)
    context["analyses"][agent_num] = result
    _log_agent_completion(result, time.time() - start)
    emit_progress(
        progress_callback,
        agent_position,
        agent_total,
        agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )


def _prepare_agent_context(agent_num, context, rotator, progress_callback, agent_position, agent_total, agent_name, pipeline_def) -> None:
    if agent_num in CONTEXT_DIGEST_TARGET_AGENTS:
        emit_status(
            progress_callback,
            f"Agent {agent_num}（{agent_position}/{agent_total}）正在提煉前序分析摘要...",
            phase="context_digest",
            current=agent_position,
            total=agent_total,
            name=agent_name,
            agent_num=agent_num,
            pipeline_id=pipeline_def["id"],
            pipeline_label=pipeline_def["label"],
        )
    ensure_context_digest(agent_num, context, rotator, progress_callback=progress_callback)
    emit_status(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在執行 RAG 語意檢索...",
        phase="rag_retrieval",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    ensure_agent_rag_context(agent_num, context, rotator)
    emit_status(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）正在呼叫模型並生成分析...",
        phase="model_call",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )


def _apply_sync_quality_gates(agent_num, agent_name, data, context, rotator, result, progress_callback, agent_position, agent_total, pipeline_def) -> str:
    if is_agent_execution_failure(result):
        context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
        emit_log(f"  ❌ {result}")
        return result

    prompt_leak_issues = validate_prompt_leakage(result)
    if prompt_leak_issues:
        _record_agent_block(context, agent_num, agent_name, result, prompt_leak_issues, "  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
        return result

    identity_issues = validate_company_identity(result, data)
    if not identity_issues:
        return result

    emit_status(
        progress_callback,
        f"Agent {agent_num}（{agent_position}/{agent_total}）身分一致性檢查未通過，正在要求重寫...",
        phase="identity_retry",
        current=agent_position,
        total=agent_total,
        name=agent_name,
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    emit_log("  🚨 公司身分一致性檢查未通過，退回 Agent 重寫...")
    for issue in identity_issues:
        emit_log(f"     - {issue}")
    context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
    context["structured_outputs"].pop(agent_num, None)
    retry_result = sanitize_model_output(run_single_agent(agent_num, data, context, rotator))
    retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
    if retry_prompt_leak_issues:
        context.pop("_identity_retry_instruction", None)
        _record_agent_block(context, agent_num, agent_name, retry_result, retry_prompt_leak_issues, "  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
        return retry_result
    retry_issues = validate_company_identity(retry_result, data)
    context.pop("_identity_retry_instruction", None)
    if retry_issues:
        emit_log("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
        for issue in retry_issues:
            emit_log(f"     - {issue}")
        context.setdefault("blocking_issues", []).extend(f"Agent {agent_num} {agent_name}: {issue}" for issue in retry_issues)
        return append_identity_warnings(retry_result, retry_issues)
    emit_log("  ✅ 重寫後通過公司身分一致性檢查。")
    return retry_result


def _record_agent_block(context, agent_num, agent_name, result, issues, header) -> None:
    emit_log(header)
    for issue in issues:
        emit_log(f"     - {issue}")
    context.setdefault("blocking_issues", []).extend(f"Agent {agent_num} {agent_name}: {issue}" for issue in issues)
    context["analyses"][agent_num] = result


def _log_agent_completion(result: str, elapsed: float) -> None:
    preview = result[:120].replace("\n", " ")
    emit_log(
        f"  ✅ 完成！耗時 {elapsed:.1f} 秒\n"
        f"  📝 輸出長度：{len(result)} 字元\n"
        f"  💬 預覽：{preview}..."
    )


def _finalize_sync_pipeline(context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    emit_status(
        progress_callback,
        "正在執行最終跨 Agent 稽核與必要修復...",
        phase="final_audit",
        current=agent_total,
        total=agent_total,
        name="最終稽核",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    finalize_final_audit(context, rotator, progress_callback=progress_callback)
    emit_status(
        progress_callback,
        "正在生成一頁式摘要並整理報告素材...",
        phase="tear_sheet",
        current=agent_total,
        total=agent_total,
        name="一頁式摘要",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    ensure_tear_sheet_summary(context, rotator, progress_callback=progress_callback)
    context["total_time"] = time.time() - context["start_time"]
    emit_log(f"\n{'='*60}\n  🎉 分析完成！總耗時：{context['total_time']:.1f} 秒\n{'='*60}\n")
