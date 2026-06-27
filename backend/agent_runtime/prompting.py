# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

import json
import copy

from analysis_types import AnalysisContext, StockData
from agent_catalog import AGENT_NAMES
from assistant_context import _format_previous
from config import PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET, PRIMARY_PROMPT_RAG_CONTEXT_CHARS
from prompt_builder import format_data_for_prompt, render_prompt_template
from prompt_rules import (
    build_agent_rule_block,
    build_final_audit_preflight_rule,
    build_identity_guard_rule_lines,
    build_output_cleanliness_rule,
)
from state_memory import state_view_for
from structured_outputs import build_structured_output_instruction

from .prompt_config import ANALYSIS_PROMPTS

OUTPUT_CLEANLINESS_RULE = build_output_cleanliness_rule()

ROUTED_EXTERNAL_CONTEXT_KEYS = {
    "macro_indicators": {11},
    "macro_context": {11},
    "chip_data": {15, 18, 23, 24},
    "tdcc_shareholder_distribution": {15, 18, 23, 24},
    "twse_margin_short_sales": {15, 18, 23, 24},
    "alternative_data": {13, 14},
    "sentiment_context": {17},
    "earnings_call": {20},
    "dcard_sentiment": {17},
    "ptt_sentiment": {17},
    "temporal_memory": {7, 16, 19, 21, 24},
}


def data_for_agent_prompt(agent_num: int, data: StockData) -> StockData:
    """Return prompt data with newly added external contexts routed by agent role."""
    agent_id = int(agent_num)
    prompt_data = copy.deepcopy(data)
    for key, allowed_agents in ROUTED_EXTERNAL_CONTEXT_KEYS.items():
        if agent_id not in allowed_agents:
            prompt_data.pop(key, None)
    return prompt_data


def build_company_identity_guard(data: StockData) -> str:
    """Build a hard identity lock so agents do not assign peer facts to the target company."""
    identity = data.get("company_identity", {}) or {}
    if not identity:
        return ""

    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    stock_id = identity.get("stock_id", ticker)
    official_name = identity.get("official_name") or data.get("company_name", ticker)
    legal_name = identity.get("legal_name")
    english_names = identity.get("english_names", [])
    forbidden_aliases = identity.get("forbidden_aliases", [])

    lines = build_identity_guard_rule_lines({
        "ticker": ticker,
        "stock_id": stock_id,
        "official_name": official_name,
        "legal_name": legal_name,
        "english_names": ", ".join(english_names[:3]),
        "forbidden_aliases": ", ".join(forbidden_aliases),
    })

    return "\n".join(lines)


def build_numeric_tool_instruction(agent_num: int) -> str:
    """Prompt agents with deterministic tool usage guidance."""
    return build_agent_rule_block("numeric_tool_instructions", agent_num)


def build_data_enrichment_instruction(agent_num: int) -> str:
    """Tell agents which enriched context slices are decision-relevant."""
    return build_agent_rule_block("data_enrichment_instructions", agent_num)


def build_state_view_section(agent_num: int, context: AnalysisContext) -> str:
    """Expose the role-specific Blackboard slice as the primary evidence source."""
    state = context.get("agent_state")
    if state is None:
        return ""

    view = state_view_for(agent_num, state)
    return "\n".join(
        [
            "【AgentState view】",
            "你不再讀取前序摘要作為主要資料來源；請直接引用下列 State path。",
            json.dumps(view, ensure_ascii=False, indent=2, allow_nan=False),
        ]
    )


def build_temporal_memory_section(agent_num: int, data: StockData) -> str:
    if int(agent_num) not in {7, 16, 19, 24}:
        return ""
    memory = data.get("temporal_memory") if isinstance(data.get("temporal_memory"), dict) else {}
    prompt = str(memory.get("reflection_prompt") or "").strip()
    if not prompt:
        return ""
    backtests = memory.get("backtests", [])
    return "\n".join([
        prompt,
        "到期回測紀錄：",
        json.dumps(backtests[:6], ensure_ascii=False, indent=2, allow_nan=False),
    ])


def build_prompt(agent_num: int, data: StockData, context: AnalysisContext) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    compact_primary = bool(context.get("_primary_probe_prompt"))
    prompt_data = data_for_agent_prompt(agent_num, data)
    fin_data = format_data_for_prompt(prompt_data, compact=compact_primary)
    prev = (
        _format_previous(context, agent_num, max_total_chars=PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET)
        if compact_primary
        else _format_previous(context, agent_num)
    )
    rag_context = (context.get("rag_context", {}) or {}).get(agent_num, "")
    if compact_primary and len(rag_context) > PRIMARY_PROMPT_RAG_CONTEXT_CHARS:
        rag_context = rag_context[: max(PRIMARY_PROMPT_RAG_CONTEXT_CHARS - 32, 0)].rstrip() + "\n...（RAG 片段截斷）"
    identity_guard = build_company_identity_guard(data)
    numeric_tool_instruction = build_numeric_tool_instruction(agent_num)
    enrichment_instruction = build_data_enrichment_instruction(agent_num)
    retry_instruction = context.get("_identity_retry_instruction", "")
    audit_retry_instruction = context.get("_audit_retry_instruction", "")
    audit_reflection_instruction = context.get("_audit_reflection_instruction", "")
    state_view_section = build_state_view_section(agent_num, context)
    temporal_memory_section = build_temporal_memory_section(agent_num, prompt_data)
    final_audit_preflight_rule = build_final_audit_preflight_rule(agent_num, context.get("pipeline_id", ""))

    # v2 Agent 14：注入財務排雷品質警示
    forensic_warning = ""
    if agent_num == 14 and context.get("_v2_forensic_warning"):
        forensic_warning = f"【財務排雷品質警示】{context['_v2_forensic_warning']}"

    template = ANALYSIS_PROMPTS[agent_num]
    analysis_prompt = render_prompt_template(
        template,
        {
            "ticker": ticker,
            "name": name,
            "fin_data": fin_data,
            "prev": prev,
            "rag_context": rag_context,
            "data": prompt_data,
            "context": context,
            "agent_num": agent_num,
        },
    )

    structured_instruction = build_structured_output_instruction(agent_num)
    prompt_parts = [
        analysis_prompt,
        forensic_warning,   # v2 Agent 14 財務排雷品質警示
        state_view_section,
        rag_context,
        "⚠️ 若上方任務文字包含 [護城河評分]、[目標股價]、[投資建議] 等舊式區塊格式，請忽略舊式格式；本次只遵守下方 JSON 結構化輸出規則。" if structured_instruction else "",
        structured_instruction,
        numeric_tool_instruction,
        enrichment_instruction,
        temporal_memory_section,
        identity_guard,
        retry_instruction,
        audit_reflection_instruction,
        audit_retry_instruction,
        final_audit_preflight_rule,
        OUTPUT_CLEANLINESS_RULE,
    ]
    return "\n\n".join(part for part in prompt_parts if part)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心 Agent 執行函數
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
