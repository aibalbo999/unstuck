# Split from legacy_agent_runner.py. Keep this module logic-only; root compatibility lives in backend/agent_runner.py.

from analysis_types import AnalysisContext, StockData
from agent_catalog import AGENT_NAMES
from assistant_tasks import _format_previous
from prompt_builder import format_data_for_prompt, render_prompt_template
from prompt_rules import (
    build_agent_rule_block,
    build_identity_guard_rule_lines,
    build_output_cleanliness_rule,
)
from structured_outputs import build_structured_output_instruction

from .prompt_config import ANALYSIS_PROMPTS

OUTPUT_CLEANLINESS_RULE = build_output_cleanliness_rule()

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


OUTPUT_CLEANLINESS_RULE = build_output_cleanliness_rule()

def build_numeric_tool_instruction(agent_num: int) -> str:
    """Prompt agents with deterministic tool usage guidance."""
    return build_agent_rule_block("numeric_tool_instructions", agent_num)


def build_data_enrichment_instruction(agent_num: int) -> str:
    """Tell agents which enriched context slices are decision-relevant."""
    return build_agent_rule_block("data_enrichment_instructions", agent_num)


def build_prompt(agent_num: int, data: StockData, context: AnalysisContext) -> str:
    """根據 Agent 編號建立分析提示詞。"""
    ticker = data["ticker"]
    name = data["company_name"]
    fin_data = format_data_for_prompt(data)
    prev = _format_previous(context, agent_num)
    rag_context = (context.get("rag_context", {}) or {}).get(agent_num, "")
    identity_guard = build_company_identity_guard(data)
    numeric_tool_instruction = build_numeric_tool_instruction(agent_num)
    enrichment_instruction = build_data_enrichment_instruction(agent_num)
    retry_instruction = context.get("_identity_retry_instruction", "")
    audit_retry_instruction = context.get("_audit_retry_instruction", "")
    audit_reflection_instruction = context.get("_audit_reflection_instruction", "")

    template = ANALYSIS_PROMPTS[agent_num]
    analysis_prompt = render_prompt_template(
        template,
        {
            "ticker": ticker,
            "name": name,
            "fin_data": fin_data,
            "prev": prev,
            "rag_context": rag_context,
            "data": data,
            "context": context,
            "agent_num": agent_num,
        },
    )

    structured_instruction = build_structured_output_instruction(agent_num)
    prompt_parts = [
        analysis_prompt,
        rag_context,
        "⚠️ 若上方任務文字包含 [護城河評分]、[目標股價]、[投資建議] 等舊式區塊格式，請忽略舊式格式；本次只遵守下方 JSON 結構化輸出規則。" if structured_instruction else "",
        structured_instruction,
        numeric_tool_instruction,
        enrichment_instruction,
        identity_guard,
        retry_instruction,
        audit_reflection_instruction,
        audit_retry_instruction,
        OUTPUT_CLEANLINESS_RULE,
    ]
    return "\n\n".join(part for part in prompt_parts if part)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 核心 Agent 執行函數
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
