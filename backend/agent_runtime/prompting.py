# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

import json
import copy

from analysis_types import AnalysisContext, StockData
from agent_catalog import AGENT_NAMES
from assistant_context import _format_previous
from config import (
    PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET,
    PRIMARY_PROMPT_RAG_CONTEXT_CHARS,
)
from prompt_builder import format_data_for_prompt, render_prompt_template
from prompt_rules import (
    build_agent_rule_block,
    build_final_audit_preflight_rule,
    build_identity_guard_rule_lines,
    build_output_cleanliness_rule,
)
from state_memory import state_view_for
from structured_output_models import build_structured_output_instruction
from temporal_memory_service import build_valuation_memory_slice

from .prompt_budget import (
    enforce_prompt_token_budget as _enforce_prompt_token_budget,
    get_agent_prompt_token_budget as _base_agent_prompt_token_budget,
)
from .prompt_config import ANALYSIS_PROMPTS
from .prompt_safety import (
    _safe_bool_flag,
    _safe_prompt_json_item,
    _safe_prompt_json_list,
    _safe_prompt_text,
    _safe_prompt_text_list,
)

OUTPUT_CLEANLINESS_RULE = build_output_cleanliness_rule()

ROUTED_EXTERNAL_CONTEXT_KEYS = {
    "macro_indicators": {11},
    "macro_context": {11},
    "chip_data": {15, 18, 23, 24},
    "tdcc_shareholder_distribution": {15, 18, 23, 24},
    "twse_margin_short_sales": {15, 18, 23, 24},
    "alternative_data": {13, 14},
    "sentiment_context": {17},
    "social_sentiment": {17},
    "sec_edgar": {13, 14, 21},
    "taiwan_open_data": {11},
    "earnings_call": {20},
    "dcard_sentiment": {17},
    "ptt_sentiment": {17},
    "temporal_memory": {7, 16, 19, 21, 24},
    "valuation_memory": {4, 14},
}

AGENT_HISTORY_YEARS = {
    11: 3,
    1: 5,
    2: 5,
    3: 5,
    4: 10,
    5: 5,
    6: 5,
    7: 5,
    12: 5,
    13: 5,
    14: 10,
    15: 5,
    16: 5,
    17: 3,
    18: 5,
    19: 5,
    20: 3,
    21: 5,
    22: 3,
    23: 3,
    24: 3,
}


def get_agent_prompt_token_budget(agent_num: int) -> int:
    return _base_agent_prompt_token_budget(agent_num)


def data_for_agent_prompt(agent_num: int, data: StockData) -> StockData:
    """Return prompt data with newly added external contexts routed by agent role."""
    agent_id = int(agent_num)
    prompt_data = copy.deepcopy(data)
    temporal_memory = prompt_data.get("temporal_memory") if agent_id in {4, 14} else None
    for key, allowed_agents in ROUTED_EXTERNAL_CONTEXT_KEYS.items():
        if agent_id not in allowed_agents:
            prompt_data.pop(key, None)
    if agent_id in AGENT_HISTORY_YEARS:
        prompt_data["_prompt_history_year_limit"] = AGENT_HISTORY_YEARS[agent_id]
    if agent_id in {4, 14} and isinstance(temporal_memory, dict):
        prompt_data["valuation_memory"] = build_valuation_memory_slice(temporal_memory)
        prompt_data.pop("temporal_memory", None)
    return prompt_data


def build_company_identity_guard(data: StockData) -> str:
    """Build a hard identity lock so agents do not assign peer facts to the target company."""
    identity = raw_identity if isinstance(raw_identity := dict.get(data, "company_identity"), dict) else {}
    try:
        if len(identity) == 0:
            return ""
    except (TypeError, ValueError, ArithmeticError, RuntimeError, AttributeError):
        pass

    identity_ticker = _safe_prompt_text(dict.get(identity, "ticker"), "N/A")
    ticker = _safe_prompt_text(dict.get(data, "ticker"), identity_ticker)
    stock_id = _safe_prompt_text(dict.get(identity, "stock_id"), ticker)
    company_name = _safe_prompt_text(dict.get(data, "company_name"), ticker)
    official_name = _safe_prompt_text(dict.get(identity, "official_name"), company_name)
    legal_name = _safe_prompt_text(dict.get(identity, "legal_name"))
    english_names = _safe_prompt_text_list(dict.get(identity, "english_names", []), limit=3)
    forbidden_aliases = _safe_prompt_text_list(dict.get(identity, "forbidden_aliases", []))

    lines = build_identity_guard_rule_lines({
        "ticker": ticker,
        "stock_id": stock_id,
        "official_name": official_name,
        "legal_name": legal_name,
        "english_names": ", ".join(english_names),
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

    view = _safe_prompt_json_item(state_view_for(agent_num, state))
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
    raw_reflection_prompt = memory.get("reflection_prompt")
    prompt = "" if raw_reflection_prompt is None else _safe_prompt_text(raw_reflection_prompt)
    if not prompt:
        return ""
    backtests = _safe_prompt_json_list(memory.get("backtests", []), limit=6)
    return "\n".join([
        prompt,
        "到期回測紀錄：",
        json.dumps(backtests, ensure_ascii=False, indent=2, allow_nan=False),
    ])


def build_prompt(agent_num: int, data: StockData, context: AnalysisContext) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    compact_primary = _safe_bool_flag(context.get("_primary_probe_prompt"))
    prompt_data = data_for_agent_prompt(agent_num, data)
    fin_data = format_data_for_prompt(prompt_data, compact=compact_primary)
    prev = (
        _format_previous(context, agent_num, max_total_chars=PRIMARY_PROMPT_CONTEXT_TOTAL_CHAR_BUDGET)
        if compact_primary
        else _format_previous(context, agent_num)
    )
    raw_rag_context = context.get("rag_context")
    rag_contexts = raw_rag_context if isinstance(raw_rag_context, dict) else {}
    raw_agent_rag_context = rag_contexts.get(agent_num, "")
    rag_context = "" if raw_agent_rag_context is None else _safe_prompt_text(raw_agent_rag_context)
    if compact_primary and len(rag_context) > PRIMARY_PROMPT_RAG_CONTEXT_CHARS:
        rag_context = rag_context[: max(PRIMARY_PROMPT_RAG_CONTEXT_CHARS - 32, 0)].rstrip() + "\n...（RAG 片段截斷）"
    identity_guard = build_company_identity_guard(data)
    numeric_tool_instruction = build_numeric_tool_instruction(agent_num)
    enrichment_instruction = build_data_enrichment_instruction(agent_num)
    retry_instruction = _safe_prompt_text(context.get("_identity_retry_instruction", ""))
    audit_retry_instruction = _safe_prompt_text(context.get("_audit_retry_instruction", ""))
    audit_reflection_instruction = _safe_prompt_text(context.get("_audit_reflection_instruction", ""))
    state_view_section = build_state_view_section(agent_num, context)
    temporal_memory_section = build_temporal_memory_section(agent_num, prompt_data)
    final_audit_preflight_rule = build_final_audit_preflight_rule(agent_num, context.get("pipeline_id", ""))

    # v2 Agent 14：注入財務排雷品質警示
    forensic_warning = ""
    if agent_num == 14:
        raw_forensic_warning = context.get("_v2_forensic_warning")
        forensic_warning_text = "" if raw_forensic_warning is None else _safe_prompt_text(raw_forensic_warning)
        if forensic_warning_text:
            forensic_warning = f"【財務排雷品質警示】{forensic_warning_text}"

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
    return _enforce_prompt_token_budget(
        "\n\n".join(part for part in prompt_parts if part),
        agent_num,
        token_budget_func=get_agent_prompt_token_budget,
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心 Agent 執行函數
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
