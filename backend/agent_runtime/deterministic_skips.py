"""Deterministic results for agents whose required source evidence is absent."""

from __future__ import annotations

import json
from typing import Any

from analysis_types import AnalysisContext, StockData
from runtime_events import emit_log
from structured_output_runtime import process_agent_response

from .single_agent_events import emit_async_model_event


def deterministic_agent_result(agent_num: int, data: StockData, context: AnalysisContext) -> str | None:
    if agent_num != 20 or _earnings_call_transcript(data, context):
        return None

    payload = {
        "guidance_tone": "資料不足",
        "confidence": 0.0,
        "highlights": [
            {"keyword": "逐字稿", "quote": "資料不足"},
            {"keyword": "Guidance", "quote": "資料不足"},
            {"keyword": "管理層語氣", "quote": "資料不足"},
        ],
        "analysis_markdown": (
            "## 管理層語氣與法說會分析\n"
            "法說會逐字稿缺漏，無法可靠判斷管理層 Guidance 語氣或引用管理層原話。"
            "本節未使用新聞標題或前序摘要替代逐字稿，待取得可追溯逐字稿後再評估。"
        ),
    }
    return process_agent_response(agent_num, json.dumps(payload, ensure_ascii=False), context)


async def apply_deterministic_agent_skip(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
) -> str | None:
    result = deterministic_agent_result(agent_num, data, context)
    if result is None:
        return None
    context["analyses"][agent_num] = result
    await emit_async_model_event(
        context,
        agent_num,
        "agent_deterministic_result",
        "info",
        "Agent 20 缺少法說會逐字稿，已產生不可評估結果並略過模型呼叫。",
        "deterministic:earnings-call-unavailable",
        skipped_llm=True,
    )
    emit_log("  ℹ️  法說會逐字稿缺漏；略過 RAG 與 LLM，保留可追溯的資料不足結論。")
    return result


def _earnings_call_transcript(data: StockData, context: AnalysisContext) -> str:
    state = context.get("agent_state")
    normalized = getattr(state, "normalized_financials", None)
    sources: list[Any] = [
        normalized.get("earnings_call") if isinstance(normalized, dict) else None,
        data.get("earnings_call") if isinstance(data, dict) else None,
    ]
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("transcript_excerpt", "transcript", "content"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


__all__ = ["apply_deterministic_agent_skip", "deterministic_agent_result"]
