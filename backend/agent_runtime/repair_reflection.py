"""Reflection and retry-instruction helpers for final-audit repair."""

from __future__ import annotations

from google.genai import types

from analysis_types import StockData
from agent_catalog import AGENT_NAMES
from llm_client import (
    KeyRotator,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
)
from prompt_rules import get_task_system_instruction
from runtime_events import emit_log
from validators import sanitize_model_output, strip_generated_audit_sections

from .llm_calls import _response_text
from .routing import get_audit_model_sequence


def _build_reflection_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=1200,
        system_instruction=get_task_system_instruction("audit_reflection"),
    )


def _build_audit_reflection_prompt(agent_num: int, issues: list[str], previous_text: str, data: StockData) -> str:
    issue_lines = "\n".join(f"- {issue}" for issue in issues[:8])
    previous_clean = strip_generated_audit_sections(previous_text or "")
    return (
        f"Agent {agent_num}「{AGENT_NAMES.get(agent_num, f'Agent {agent_num}')}」前次輸出被退件。\n"
        "請先輸出一段繁體中文反思，回答：\n"
        "1. 前次輸出可能在哪個資料口徑、公式或單位步驟出錯？\n"
        "2. 這次重寫應如何改用提供的 JSON、deterministic_financial_tool_results 或 Python 工具？\n"
        "3. 哪些結論需要降低信心或改列資料品質限制？\n\n"
        f"退件原因：\n{issue_lines}\n\n"
        f"標的：{data.get('ticker', 'N/A')} {data.get('company_name', 'N/A')}\n\n"
        "前次輸出：\n"
        f"{previous_clean}"
    )


def _fallback_audit_reflection(agent_num: int, issues: list[str]) -> str:
    issue_lines = "；".join(str(issue) for issue in issues[:4])
    return (
        f"反思摘要：Agent {agent_num} 前次輸出觸發紅線（{issue_lines}）。"
        "重寫時應回到財務 JSON 與 deterministic_financial_tool_results，逐項校準單位、公式與資料口徑；"
        "若數字互斥，改列資料品質限制，不把錯誤公式包裝成結論。"
    )


def _generate_reflection_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_reflection_generation_config())


async def _generate_reflection_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_reflection_generation_config())


def generate_audit_reflection(agent_num: int, issues: list[str], previous_text: str, data: StockData, rotator: KeyRotator) -> str:
    """Generate a pre-rewrite reflection, falling back deterministically if needed."""
    if not isinstance(rotator, KeyRotator):
        return _fallback_audit_reflection(agent_num, issues)

    prompt = _build_audit_reflection_prompt(agent_num, issues, previous_text, data)
    for model_id in get_audit_model_sequence():
        try:
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=1200))
            response = _generate_reflection_content(api_key, model_id, prompt)
            text = sanitize_model_output(_response_text(response))
            return text or _fallback_audit_reflection(agent_num, issues)
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            emit_log(f"       ↳ 反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
            break
    return _fallback_audit_reflection(agent_num, issues)


async def generate_audit_reflection_async(agent_num: int, issues: list[str], previous_text: str, data: StockData, rotator: KeyRotator) -> str:
    """Async pre-rewrite reflection."""
    if not isinstance(rotator, KeyRotator):
        return _fallback_audit_reflection(agent_num, issues)

    prompt = _build_audit_reflection_prompt(agent_num, issues, previous_text, data)
    for model_id in get_audit_model_sequence():
        try:
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=1200))
            response = await _generate_reflection_content_async(api_key, model_id, prompt)
            text = sanitize_model_output(_response_text(response))
            return text or _fallback_audit_reflection(agent_num, issues)
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            emit_log(f"       ↳ 非同步反思步驟呼叫失敗，改用 deterministic reflection：{str(exc)[:100]}")
            break
    return _fallback_audit_reflection(agent_num, issues)


def build_audit_reflection_instruction(reflection: str) -> str:
    if not reflection:
        return ""
    return (
        "【前次退件反思摘要（供重寫使用，不可輸出到正式報告）】\n"
        f"{reflection}\n"
        "請根據此反思修正下一版內容；正式輸出不得提及反思步驟或退件流程。"
    )


def build_audit_retry_instruction(agent_num: int, issues: list[str]) -> str:
    """Build a focused rewrite instruction for final audit failures."""
    issue_lines = "\n".join(f"- {issue}" for issue in issues[:8])
    return (
        "🚨【最終跨 Agent 稽核要求重寫本段】\n"
        "系統在正式報告存檔前發現以下問題，請完全重寫或補跑本 Agent 的輸出正文，"
        "保留原本段落任務，但必須修正所有問題：\n"
        f"{issue_lines}\n\n"
        "修復規則：\n"
        "- 若前次輸出缺失、失敗或仍是佔位文字，請從零生成本 Agent 的完整正式輸出。\n"
        "- 只使用資料摘要中明確提供的數字；若資料口徑衝突，請列為資料品質警示，不可硬湊公式。\n"
        "- 杜邦分析只能使用同期間年度杜邦恒等式；不可混用 Yahoo TTM ROE/ROA/淨利率與最新年度資產周轉率或權益乘數。\n"
        "- Yahoo revenueGrowth/earningsGrowth 若被標為近期或季度口徑，不可寫成年度或 TTM 年增率。\n"
        "- 若原始 Yahoo 淨利率與 EPS/P/E 推回淨利互斥，正式分析必須採用校準後淨利率，原始值只能作為資料源對照。\n"
        "- 不要提及你在修復、不要輸出本段修復指令、不要保留錯誤原文。"
    )
