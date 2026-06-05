"""Seven-agent analysis pipeline orchestration."""

from __future__ import annotations

import asyncio
import inspect
import time

import agent_runner as ar
from analysis_types import AnalysisContext, StockData
from config import AGENT_MODELS, API_KEYS, EMBEDDING_MODEL, INTER_AGENT_DELAY
from llm_client import KeyRotator
from rag_service import (
    build_rag_index,
    build_rag_index_async,
    ensure_agent_rag_context,
    ensure_agent_rag_context_async,
)
from validators import (
    append_identity_warnings,
    append_quality_warnings,
    build_identity_retry_instruction,
    sanitize_model_output,
    validate_company_identity,
    validate_prompt_leakage,
)


def _call_progress_callback_sync(
    progress_callback,
    current: int,
    total: int,
    name: str,
    phase: str = "completed",
    message: str | None = None,
):
    if not progress_callback:
        return
    try:
        result = progress_callback(current, total, name, phase, message)
    except TypeError:
        if phase == "completed":
            result = progress_callback(current, total, name)
        else:
            return
    if inspect.isawaitable(result):
        return


def run_analysis_pipeline(data: StockData, progress_callback=None) -> AnalysisContext:
    """
    Run the full 7-agent sequential analysis pipeline.

    The sync path remains conservative and is mainly retained for CLI/RQ
    compatibility; production jobs use run_analysis_pipeline_async.
    """
    ticker = data["ticker"]
    name = data["company_name"]

    rotator = KeyRotator(API_KEYS)
    context: AnalysisContext = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "structured_outputs": {},
        "start_time": time.time(),
    }

    print(f"\n{'='*60}")
    print(f"  🚀 開始分析 {ticker} {name}")
    print(f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）")
    print(f"{'='*60}\n")

    rag_index = build_rag_index(data, rotator)
    if rag_index is not None:
        context["rag_index"] = rag_index
        context["rag_status"] = {
            "model": EMBEDDING_MODEL,
            "chunks": len(getattr(rag_index, "chunks", []) or []),
            "embedded": bool(getattr(rag_index, "has_embeddings", False)),
        }
        print(f"  🔎 RAG 長文本索引完成：{context['rag_status']['chunks']} 個片段。")

    for agent_num in range(1, 8):
        agent_name = ar.AGENT_NAMES[agent_num]
        model_id = AGENT_MODELS[agent_num]

        print(f"{'─'*60}")
        print(f"  📌 Agent {agent_num}/7：{agent_name}")
        print(f"  🤖 模型：{model_id}")
        print(f"{'─'*60}")

        start = time.time()

        _call_progress_callback_sync(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "started",
            f"開始 Agent {agent_num}/7：{agent_name}（{model_id}）",
        )
        context["structured_outputs"].pop(agent_num, None)
        if agent_num in ar.CONTEXT_DIGEST_TARGET_AGENTS:
            _call_progress_callback_sync(
                progress_callback,
                agent_num,
                7,
                agent_name,
                "context_digest",
                f"Agent {agent_num}/7 正在提煉前序分析摘要...",
            )
        ar.ensure_context_digest(agent_num, context, rotator)
        _call_progress_callback_sync(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "rag_retrieval",
            f"Agent {agent_num}/7 正在執行 RAG 語意檢索...",
        )
        ensure_agent_rag_context(agent_num, context, rotator)
        _call_progress_callback_sync(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "model_call",
            f"Agent {agent_num}/7 正在呼叫模型並生成分析...",
        )
        result = ar.run_single_agent(agent_num, data, context, rotator)
        result = sanitize_model_output(result)
        _call_progress_callback_sync(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "quality_gate",
            f"Agent {agent_num}/7 正在執行輸出清洗與品質檢查...",
        )

        if ar.is_agent_execution_failure(result):
            context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
            context["analyses"][agent_num] = result
            print(f"  ❌ {result}")
            break

        prompt_leak_issues = validate_prompt_leakage(result)
        if prompt_leak_issues:
            print("  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
            for issue in prompt_leak_issues:
                print(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}"
                for issue in prompt_leak_issues
            )
            context["analyses"][agent_num] = result
            break

        identity_issues = validate_company_identity(result, data)
        if identity_issues:
            _call_progress_callback_sync(
                progress_callback,
                agent_num,
                7,
                agent_name,
                "identity_retry",
                f"Agent {agent_num}/7 身分一致性檢查未通過，正在要求重寫...",
            )
            print("  🚨 公司身分一致性檢查未通過，退回 Agent 重寫...")
            for issue in identity_issues:
                print(f"     - {issue}")
            context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
            context["structured_outputs"].pop(agent_num, None)
            retry_result = ar.run_single_agent(agent_num, data, context, rotator)
            retry_result = sanitize_model_output(retry_result)
            retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
            if retry_prompt_leak_issues:
                print("  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in retry_prompt_leak_issues
                )
                context.pop("_identity_retry_instruction", None)
                result = retry_result
                context["analyses"][agent_num] = result
                break
            retry_issues = validate_company_identity(retry_result, data)
            context.pop("_identity_retry_instruction", None)

            result = retry_result
            identity_issues = retry_issues
            if identity_issues:
                print("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
                for issue in identity_issues:
                    print(f"     - {issue}")
                context.setdefault("blocking_issues", []).extend(
                    f"Agent {agent_num} {agent_name}: {issue}"
                    for issue in identity_issues
                )
                result = append_identity_warnings(result, identity_issues)
            else:
                print("  ✅ 重寫後通過公司身分一致性檢查。")

        result = append_quality_warnings(agent_num, result, data)

        elapsed = time.time() - start
        context["analyses"][agent_num] = result

        print(f"  ✅ 完成！耗時 {elapsed:.1f} 秒")
        print(f"  📝 輸出長度：{len(result)} 字元")

        preview = result[:120].replace("\n", " ")
        print(f"  💬 預覽：{preview}...")

        _call_progress_callback_sync(progress_callback, agent_num, 7, agent_name)

        if context.get("blocking_issues"):
            break

        if agent_num < 7 and INTER_AGENT_DELAY > 0:
            wait = INTER_AGENT_DELAY
            print(f"\n  ⏰ 額外等待 {wait:.1f} 秒後執行下一個 Agent...\n")
            time.sleep(wait)

    _call_progress_callback_sync(
        progress_callback,
        7,
        7,
        "最終稽核",
        "final_audit",
        "正在執行最終跨 Agent 稽核與必要修復...",
    )
    ar.finalize_final_audit(context, rotator)
    _call_progress_callback_sync(
        progress_callback,
        7,
        7,
        "一頁式摘要",
        "tear_sheet",
        "正在生成一頁式摘要並整理報告素材...",
    )
    ar.ensure_tear_sheet_summary(context, rotator)
    context["total_time"] = time.time() - context["start_time"]

    print(f"\n{'='*60}")
    print(f"  🎉 分析完成！總耗時：{context['total_time']:.1f} 秒")
    print(f"{'='*60}\n")

    return context


async def _call_progress_callback(
    progress_callback,
    current: int,
    total: int,
    name: str,
    phase: str = "completed",
    message: str | None = None,
):
    if not progress_callback:
        return
    try:
        result = progress_callback(current, total, name, phase, message)
    except TypeError:
        if phase != "completed":
            return
        result = progress_callback(current, total, name)
    if inspect.isawaitable(result):
        await result


async def _run_agent_with_quality_gates_async(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    rotator: KeyRotator,
    progress_callback=None,
) -> tuple[int, str]:
    """Run one async agent and apply the same output gates as the sequential pipeline."""
    agent_name = ar.AGENT_NAMES[agent_num]
    model_id = ar.get_runtime_model_sequence(agent_num, context)[0]

    print(f"{'─'*60}")
    print(f"  📌 Agent {agent_num}/7：{agent_name}")
    print(f"  🤖 模型：{model_id}")
    print(f"{'─'*60}")

    start = time.time()

    await _call_progress_callback(
        progress_callback,
        agent_num,
        7,
        agent_name,
        "started",
        f"開始 Agent {agent_num}/7：{agent_name}（{model_id}）",
    )
    context["structured_outputs"].pop(agent_num, None)
    if agent_num in ar.CONTEXT_DIGEST_TARGET_AGENTS:
        await _call_progress_callback(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "context_digest",
            f"Agent {agent_num}/7 正在提煉前序分析摘要...",
        )
    await ar.ensure_context_digest_async(agent_num, context, rotator)
    await _call_progress_callback(
        progress_callback,
        agent_num,
        7,
        agent_name,
        "rag_retrieval",
        f"Agent {agent_num}/7 正在執行 RAG 語意檢索...",
    )
    await ensure_agent_rag_context_async(agent_num, context, rotator)
    await _call_progress_callback(
        progress_callback,
        agent_num,
        7,
        agent_name,
        "model_call",
        f"Agent {agent_num}/7 正在呼叫模型並生成分析...",
    )
    result = await ar.run_single_agent_async(agent_num, data, context, rotator)
    result = sanitize_model_output(result)
    await _call_progress_callback(
        progress_callback,
        agent_num,
        7,
        agent_name,
        "quality_gate",
        f"Agent {agent_num}/7 正在執行輸出清洗與品質檢查...",
    )

    if ar.is_agent_execution_failure(result):
        context.setdefault("blocking_issues", []).append(f"Agent {agent_num} {agent_name}: {result}")
        context["analyses"][agent_num] = result
        print(f"  ❌ {result}")
        return agent_num, result

    prompt_leak_issues = validate_prompt_leakage(result)
    if prompt_leak_issues:
        print("  🚨 輸出清洗後仍偵測到 prompt 洩漏，停止產生正式報告。")
        for issue in prompt_leak_issues:
            print(f"     - {issue}")
        context.setdefault("blocking_issues", []).extend(
            f"Agent {agent_num} {agent_name}: {issue}"
            for issue in prompt_leak_issues
        )
        context["analyses"][agent_num] = result
        return agent_num, result

    identity_issues = validate_company_identity(result, data)
    if identity_issues:
        await _call_progress_callback(
            progress_callback,
            agent_num,
            7,
            agent_name,
            "identity_retry",
            f"Agent {agent_num}/7 身分一致性檢查未通過，正在要求重寫...",
        )
        print("  🚨 公司身分一致性檢查未通過，退回 Agent 非同步重寫...")
        for issue in identity_issues:
            print(f"     - {issue}")
        context["_identity_retry_instruction"] = build_identity_retry_instruction(data, identity_issues)
        context["structured_outputs"].pop(agent_num, None)
        retry_result = await ar.run_single_agent_async(agent_num, data, context, rotator)
        retry_result = sanitize_model_output(retry_result)
        retry_prompt_leak_issues = validate_prompt_leakage(retry_result)
        if retry_prompt_leak_issues:
            print("  🚨 重寫輸出仍偵測到 prompt 洩漏，停止產生正式報告。")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}"
                for issue in retry_prompt_leak_issues
            )
            context.pop("_identity_retry_instruction", None)
            result = retry_result
            context["analyses"][agent_num] = result
            return agent_num, result

        retry_issues = validate_company_identity(retry_result, data)
        context.pop("_identity_retry_instruction", None)

        result = retry_result
        identity_issues = retry_issues
        if identity_issues:
            print("  ❌ 重寫後仍未通過公司身分一致性檢查，停止產生正式報告。")
            for issue in identity_issues:
                print(f"     - {issue}")
            context.setdefault("blocking_issues", []).extend(
                f"Agent {agent_num} {agent_name}: {issue}"
                for issue in identity_issues
            )
            result = append_identity_warnings(result, identity_issues)
        else:
            print("  ✅ 重寫後通過公司身分一致性檢查。")

    result = append_quality_warnings(agent_num, result, data)

    elapsed = time.time() - start
    context["analyses"][agent_num] = result

    print(f"  ✅ 完成！耗時 {elapsed:.1f} 秒")
    print(f"  📝 輸出長度：{len(result)} 字元")

    preview = result[:120].replace("\n", " ")
    print(f"  💬 預覽：{preview}...")

    return agent_num, result


async def run_analysis_pipeline_async(data: StockData, progress_callback=None) -> AnalysisContext:
    """Run the full 7-agent async DAG pipeline."""
    ticker = data["ticker"]
    name = data["company_name"]

    rotator = KeyRotator(API_KEYS)
    context: AnalysisContext = {
        "ticker": ticker,
        "company_name": name,
        "data": data,
        "analyses": {},
        "structured_outputs": {},
        "start_time": time.time(),
        "execution_mode": "async",
    }

    print(f"\n{'='*60}")
    print(f"  🚀 開始非同步分析 {ticker} {name}")
    print(f"  📅 時間：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  🔑 可用 API Keys：{len(API_KEYS)} 組（輪調中）")
    print(f"{'='*60}\n")

    rag_index = await build_rag_index_async(data, rotator)
    if rag_index is not None:
        context["rag_index"] = rag_index
        context["rag_status"] = {
            "model": EMBEDDING_MODEL,
            "chunks": len(getattr(rag_index, "chunks", []) or []),
            "embedded": bool(getattr(rag_index, "has_embeddings", False)),
        }
        print(f"  🔎 RAG 長文本索引完成：{context['rag_status']['chunks']} 個片段。")

    agent_groups = [(1, 2, 3), (4,), (5,), (6,), (7,)]
    for group in agent_groups:
        if len(group) > 1:
            print(f"  ⚡ 平行啟動 Agent {', '.join(str(num) for num in group)}（共享初始財務資料）")
            await _call_progress_callback(
                progress_callback,
                0,
                7,
                "平行分析",
                "agent_group",
                f"平行啟動 Agent {', '.join(str(num) for num in group)}，共享初始財務資料...",
            )

            async def run_and_return(agent_num: int):
                return await _run_agent_with_quality_gates_async(agent_num, data, context, rotator, progress_callback)

            tasks = [asyncio.create_task(run_and_return(agent_num)) for agent_num in group]
            for task in asyncio.as_completed(tasks):
                completed_agent_num, _ = await task
                await _call_progress_callback(
                    progress_callback,
                    completed_agent_num,
                    7,
                    ar.AGENT_NAMES[completed_agent_num],
                )
        else:
            agent_num = group[0]
            completed_agent_num, _ = await _run_agent_with_quality_gates_async(agent_num, data, context, rotator, progress_callback)
            await _call_progress_callback(
                progress_callback,
                completed_agent_num,
                7,
                ar.AGENT_NAMES[completed_agent_num],
            )

        if context.get("blocking_issues"):
            break

        if group[-1] < 7 and INTER_AGENT_DELAY > 0:
            print(f"\n  ⏰ 額外等待 {INTER_AGENT_DELAY:.1f} 秒後執行下一階段...\n")
            await asyncio.sleep(INTER_AGENT_DELAY)

    await _call_progress_callback(
        progress_callback,
        7,
        7,
        "最終稽核",
        "final_audit",
        "正在執行最終跨 Agent 稽核與必要修復...",
    )
    await ar.finalize_final_audit_async(context, rotator)
    await _call_progress_callback(
        progress_callback,
        7,
        7,
        "一頁式摘要",
        "tear_sheet",
        "正在生成一頁式摘要並整理報告素材...",
    )
    await ar.ensure_tear_sheet_summary_async(context, rotator)
    context["total_time"] = time.time() - context["start_time"]

    print(f"\n{'='*60}")
    print(f"  🎉 非同步分析完成！總耗時：{context['total_time']:.1f} 秒")
    print(f"{'='*60}\n")

    return context
