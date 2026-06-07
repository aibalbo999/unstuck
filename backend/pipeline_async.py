"""Async DAG analysis pipeline orchestration."""

from __future__ import annotations

import asyncio
import time

from agent_catalog import AGENT_NAMES
from agent_runtime import run_agent_with_quality_gates_async
from agent_runtime.audit_repair import finalize_final_audit_async
from agent_runtime.cancellation import attach_cancel_check, raise_if_cancelled
from analysis_types import AnalysisContext, StockData
from config import API_KEYS, EMBEDDING_MODEL
from llm_client import KeyRotator
from pipeline_modes import get_pipeline_definition, normalize_pipeline_id
from rag_runtime import build_rag_index_async
from runtime_events import RUNTIME_EVENT_CALLBACK_KEY, emit_log, emit_progress_async, emit_status_async
from tear_sheet_tasks import ensure_tear_sheet_summary_async


async def run_analysis_pipeline_async(data: StockData, progress_callback=None, pipeline_id: str = "v1", cancel_check=None) -> AnalysisContext:
    """Run the selected async DAG analysis pipeline."""
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
        "execution_mode": "async",
        "pipeline_id": pipeline_def["id"],
        "pipeline_label": pipeline_def["label"],
        "agent_sequence": agent_sequence,
        "agent_positions": agent_positions,
        "agent_total": agent_total,
    }
    if progress_callback:
        context[RUNTIME_EVENT_CALLBACK_KEY] = progress_callback
    attach_cancel_check(context, cancel_check)
    raise_if_cancelled(context)

    emit_log(
        f"\n{'='*60}\n"
        f"  🚀 開始非同步分析 {ticker} {name}｜{pipeline_def['label']}\n"
        f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）\n"
        f"{'='*60}\n"
    )

    await _build_rag_index_async(data, rotator, context, progress_callback, agent_total, pipeline_def)
    await _run_agent_groups(data, context, rotator, progress_callback, agent_total, pipeline_def)
    raise_if_cancelled(context)
    await _finalize_async_pipeline(context, rotator, progress_callback, agent_total, pipeline_def)
    return context


async def _build_rag_index_async(data, rotator, context, progress_callback, agent_total, pipeline_def) -> None:
    rag_index = await build_rag_index_async(data, rotator)
    if rag_index is None:
        return
    context["rag_index"] = rag_index
    context["rag_status"] = {
        "model": EMBEDDING_MODEL,
        "chunks": len(getattr(rag_index, "chunks", []) or []),
        "embedded": bool(getattr(rag_index, "has_embeddings", False)),
    }
    emit_log(f"  🔎 RAG 長文本索引完成：{context['rag_status']['chunks']} 個片段。")
    await emit_status_async(
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


async def _run_agent_groups(data, context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    agent_groups = pipeline_def["groups"]
    for group_index, group in enumerate(agent_groups):
        raise_if_cancelled(context)
        if len(group) > 1:
            await _run_parallel_group(group, data, context, rotator, progress_callback, agent_total, pipeline_def)
        else:
            await _run_single_group_agent(group[0], data, context, rotator, progress_callback, agent_total, pipeline_def)

        if context.get("blocking_issues"):
            break



async def _run_parallel_group(group, data, context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    emit_log(f"  ⚡ 平行啟動 Agent {', '.join(str(num) for num in group)}（共享同一 DAG 依賴資料）")
    await emit_status_async(
        progress_callback,
        f"平行啟動 Agent {', '.join(str(num) for num in group)}，共享同一 DAG 依賴資料...",
        phase="agent_group",
        current=0,
        total=agent_total,
        name="平行分析",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )

    async def run_and_return(agent_num: int):
        return await run_agent_with_quality_gates_async(agent_num, data, context, rotator, progress_callback)

    tasks = [asyncio.create_task(run_and_return(agent_num)) for agent_num in group]
    for task in asyncio.as_completed(tasks):
        raise_if_cancelled(context)
        completed_agent_num, _ = await task
        await _emit_agent_completed(context, progress_callback, completed_agent_num, agent_total, pipeline_def)


async def _run_single_group_agent(agent_num, data, context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    raise_if_cancelled(context)
    completed_agent_num, _ = await run_agent_with_quality_gates_async(agent_num, data, context, rotator, progress_callback)
    await _emit_agent_completed(context, progress_callback, completed_agent_num, agent_total, pipeline_def)


async def _emit_agent_completed(context, progress_callback, agent_num, agent_total, pipeline_def) -> None:
    await emit_progress_async(
        progress_callback,
        context["agent_positions"].get(agent_num, agent_num),
        agent_total,
        AGENT_NAMES[agent_num],
        agent_num=agent_num,
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )


async def _finalize_async_pipeline(context, rotator, progress_callback, agent_total, pipeline_def) -> None:
    await emit_status_async(
        progress_callback,
        "正在執行最終跨 Agent 稽核與必要修復...",
        phase="final_audit",
        current=agent_total,
        total=agent_total,
        name="最終稽核",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    await finalize_final_audit_async(context, rotator, progress_callback=progress_callback)
    await emit_status_async(
        progress_callback,
        "正在生成一頁式摘要並整理報告素材...",
        phase="tear_sheet",
        current=agent_total,
        total=agent_total,
        name="一頁式摘要",
        pipeline_id=pipeline_def["id"],
        pipeline_label=pipeline_def["label"],
    )
    await ensure_tear_sheet_summary_async(context, rotator, progress_callback=progress_callback)
    context["total_time"] = time.time() - context["start_time"]
    emit_log(f"\n{'='*60}\n  🎉 非同步分析完成！總耗時：{context['total_time']:.1f} 秒\n{'='*60}\n")
