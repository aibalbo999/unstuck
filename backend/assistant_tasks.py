"""Auxiliary LLM tasks used by the analysis pipeline."""

from __future__ import annotations

import json
import re

from google.genai import types

from analysis_types import AnalysisContext
from agent_catalog import AGENT_NAMES
from config import AGENT_MODELS, CONTEXT_DIGEST_MODEL
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_content,
    generate_content_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    response_text,
)
from prompt_rules import get_task_instruction_lines, get_task_system_instruction
from structured_outputs import _extract_json_payload
from validators import sanitize_model_output, strip_generated_audit_sections


CONTEXT_DIGEST_TARGET_AGENTS = {4, 7}
CONTEXT_TOTAL_CHAR_BUDGET = 11000
CONTEXT_PER_AGENT_CHAR_BUDGET = 2200

AGENT_CONTEXT_KEYWORDS = {
    4: [
        "估值", "DCF", "WACC", "FCF", "自由現金流", "本益比", "P/E", "Forward EPS",
        "目標價", "折現", "同業", "護城河", "風險", "CapEx", "產能", "淨利率",
    ],
    5: [
        "成長", "TAM", "SAM", "SOM", "市場", "催化", "AI", "技術", "產能", "CapEx",
        "營收", "市佔", "長期", "風險",
    ],
    6: [
        "多頭", "空頭", "風險", "催化", "估值", "財務", "營收", "FCF", "護城河",
        "目標價", "反方", "爭議",
    ],
    7: [
        "建議", "目標價", "估值", "DCF", "P/E", "風險", "催化", "成長", "護城河",
        "財務", "FCF", "籌碼", "短期", "長期", "信心", "避免", "買入", "持有",
    ],
}


def _format_structured_outputs_for_context(context: AnalysisContext) -> str:
    structured = context.get("structured_outputs", {}) or {}
    if not structured:
        return "{}"
    try:
        return json.dumps(structured, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        return str(structured)


def _split_context_chunks(text: str) -> list[str]:
    cleaned = strip_generated_audit_sections(str(text or "")).strip()
    if not cleaned:
        return []
    chunks = re.split(r"\n{2,}", cleaned)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _score_context_chunk(chunk: str, current_agent: int, source_agent: int, index: int) -> int:
    normalized = chunk.lower()
    keywords = AGENT_CONTEXT_KEYWORDS.get(current_agent, [])
    score = sum(normalized.count(keyword.lower()) for keyword in keywords)
    if index == 0:
        score += 2
    if re.search(r"^#{1,4}\s+", chunk):
        score += 1
    if source_agent == 2 and current_agent in {4, 7}:
        score += sum(normalized.count(term.lower()) for term in ["財務", "fcf", "roe", "營收", "淨利"])
    if source_agent == 4 and current_agent == 7:
        score += sum(normalized.count(term.lower()) for term in ["目標價", "估值", "dcf", "wacc"])
    return score


def _clip_chunk(chunk: str, max_chars: int) -> str:
    if len(chunk) <= max_chars:
        return chunk
    return chunk[: max(max_chars - 24, 0)].rstrip() + "\n...（片段截斷）"


def _select_relevant_context(text: str, current_agent: int, source_agent: int, max_chars: int) -> str:
    chunks = _split_context_chunks(text)
    if not chunks:
        return ""

    scored = [
        (_score_context_chunk(chunk, current_agent, source_agent, idx), idx, chunk)
        for idx, chunk in enumerate(chunks)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))

    selected: list[tuple[int, str]] = []
    used = 0
    for _, idx, chunk in scored:
        remaining = max_chars - used
        if remaining <= 120:
            break
        snippet = _clip_chunk(chunk, min(len(chunk), remaining))
        selected.append((idx, snippet))
        used += len(snippet) + 2
        if used >= max_chars:
            break

    selected.sort(key=lambda item: item[0])
    output = "\n\n".join(snippet for _, snippet in selected).strip()
    omitted = max(len(str(text or "")) - len(output), 0)
    if omitted > 0:
        output = f"{output}\n\n（系統已依 Agent {current_agent} 任務精選前序片段，約省略 {omitted} 字。）"
    return output


def _format_previous(
    context: AnalysisContext,
    current_agent: int,
    include_digest: bool = True,
    max_total_chars: int = CONTEXT_TOTAL_CHAR_BUDGET,
) -> str:
    """Format previous agent outputs as digest plus task-relevant slices."""
    analyses = context.get("analyses", {})
    if not analyses:
        return "（無前序分析）"

    agent_names = {
        1: "整體分析",
        2: "財務分析",
        3: "護城河評估",
        4: "估值分析",
        5: "成長潛力",
        6: "多空辯論",
    }

    parts = []
    digest = (context.get("context_digests", {}) or {}).get(current_agent)
    if include_digest and digest:
        parts.append(f"【提煉 Agent 結構化摘要】\n{digest}")

    structured_context = _format_structured_outputs_for_context(context)
    if structured_context != "{}":
        parts.append(f"【已解析結構化輸出】\n{structured_context}")

    parts.append("【前序分析精選片段（非全文，依下一位 Agent 任務檢索）】")

    for i in range(1, current_agent):
        if i in analyses:
            name = agent_names.get(i, f"Agent {i}")
            used_chars = len("\n\n".join(parts))
            if used_chars >= max_total_chars:
                parts.append("（前序片段已達系統 context 預算上限，後續 Agent 請以結構化輸出與提煉摘要為準。）")
                break
            remaining_budget = max_total_chars - used_chars
            per_agent_budget = min(CONTEXT_PER_AGENT_CHAR_BUDGET, remaining_budget)
            clean_analysis = _select_relevant_context(
                str(analyses[i]),
                current_agent=current_agent,
                source_agent=i,
                max_chars=per_agent_budget,
            )
            if clean_analysis:
                parts.append(f"【{name}｜精選片段】\n{clean_analysis}")

    return "\n\n".join(parts) if parts else "（無前序分析）"


def _context_digest_model_sequence() -> list[str]:
    return [CONTEXT_DIGEST_MODEL]


def _tear_sheet_model_sequence() -> list[str]:
    return [AGENT_MODELS[2]]


def _build_context_digest_prompt(current_agent: int, context: AnalysisContext) -> str:
    target = AGENT_NAMES.get(current_agent, f"Agent {current_agent}")
    previous = _format_previous(context, current_agent, include_digest=False, max_total_chars=16000)
    return (
        "請擔任投資研究提煉 Agent，將前序分析整理成給下一位分析師使用的結構化摘要。\n"
        f"下一位分析師：Agent {current_agent} {target}\n\n"
        "輸出請使用合法 JSON，不要 Markdown code fence。JSON schema:\n"
        "{\n"
        '  "decision_relevant_facts": ["..."],\n'
        '  "financial_cross_checks": ["..."],\n'
        '  "valuation_or_recommendation_implications": ["..."],\n'
        '  "risks_and_counterarguments": ["..."],\n'
        '  "open_data_quality_issues": ["..."]\n'
        "}\n\n"
        "已解析的結構化輸出：\n"
        f"{_format_structured_outputs_for_context(context)}\n\n"
        "前序分析精選片段（非全文，請只根據片段與結構化輸出提煉）：\n"
        f"{previous}"
    )


def _build_digest_generation_config():
    return types.GenerateContentConfig(
        temperature=0.2,
        top_p=0.9,
        max_output_tokens=4096,
        response_mime_type="application/json",
        system_instruction=get_task_system_instruction("context_digest"),
    )


def _generate_context_digest_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_digest_generation_config())


async def _generate_context_digest_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_digest_generation_config())


def _normalize_digest_text(text: str, current_agent: int, context: dict) -> str:
    payload = _extract_json_payload(text or "")
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return json.dumps(
        _fallback_context_digest_payload(current_agent, context, reason="提煉 Agent 未回傳可解析 JSON"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _fallback_context_digest_payload(current_agent: int, context: dict, reason: str) -> dict:
    completed = sorted(context.get("analyses", {}).keys())
    return {
        "digest_type": "deterministic_fallback",
        "reason": reason,
        "target_agent": current_agent,
        "completed_agents": completed,
        "structured_outputs": context.get("structured_outputs", {}),
        "instruction": "提煉摘要不可用時，下一個 Agent 必須優先使用結構化輸出與系統提供的前序精選片段，不應假設已讀全文。",
    }


def ensure_context_digest(agent_num: int, context: dict, rotator: KeyRotator):
    """Run a lightweight summarization agent before high-dependency agents."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    if agent_num in digests:
        return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in _context_digest_model_sequence():
        try:
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=4096))
            response = _generate_context_digest_content(api_key, model_id, prompt)
            digests[agent_num] = _normalize_digest_text(response_text(response), agent_num, context)
            print(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            if is_quota_or_rate_error(str(exc)):
                print(f"  ⏭️  提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}")
                break
            print(f"  ⚠️  提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}")
            break

    digests[agent_num] = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


async def ensure_context_digest_async(agent_num: int, context: dict, rotator: KeyRotator):
    """Async summarization agent before Agent 4/7."""
    if agent_num not in CONTEXT_DIGEST_TARGET_AGENTS:
        return
    digests = context.setdefault("context_digests", {})
    if agent_num in digests:
        return

    prompt = _build_context_digest_prompt(agent_num, context)
    for model_id in _context_digest_model_sequence():
        try:
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=4096))
            response = await _generate_context_digest_content_async(api_key, model_id, prompt)
            digests[agent_num] = _normalize_digest_text(response_text(response), agent_num, context)
            print(f"  🧾 Agent {agent_num} 前序提煉摘要完成。")
            return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            if is_quota_or_rate_error(str(exc)):
                print(f"  ⏭️  提煉 Agent 遇到配額限制，改用 fallback 摘要：{describe_quota_or_rate_error(exc)[:120]}")
                break
            print(f"  ⚠️  提煉 Agent 失敗，改用 fallback 摘要：{str(exc)[:120]}")
            break

    digests[agent_num] = json.dumps(
        _fallback_context_digest_payload(agent_num, context, reason="提煉 Agent 呼叫失敗"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def _build_tear_sheet_prompt(context: dict) -> str:
    data = context.get("data", {}) or {}
    parsed = context.get("parsed", {}) or {}
    analyses = context.get("analyses", {}) or {}
    compact_analyses = "\n\n".join(
        f"Agent {agent_num}: {strip_generated_audit_sections(str(text))[:1200]}"
        for agent_num, text in sorted(analyses.items())
    )
    payload = {
        "ticker": data.get("ticker"),
        "company_name": data.get("company_name"),
        "industry": data.get("industry"),
        "current_price": data.get("current_price"),
        "price_targets": parsed.get("price_targets", {}),
        "recommendation": parsed.get("recommendation", {}),
        "recent_catalysts": data.get("recent_catalysts", [])[:3],
        "institutional_trading": data.get("institutional_trading", {}),
        "pe_river_chart": data.get("pe_river_chart", {}),
    }
    instruction_text = "\n".join(get_task_instruction_lines("tear_sheet")).strip()
    instruction_block = f"{instruction_text}\n\n" if instruction_text else ""
    return (
        instruction_block
        + f"結構化資料：\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        + f"各 Agent 摘要：\n{compact_analyses}"
    )


def _build_tear_sheet_generation_config():
    return types.GenerateContentConfig(
        temperature=0.35,
        top_p=0.9,
        max_output_tokens=900,
        system_instruction=get_task_system_instruction("tear_sheet"),
    )


def _generate_tear_sheet_content(api_key: str, model_id: str, prompt: str):
    return generate_content(api_key, model_id, prompt, _build_tear_sheet_generation_config())


async def _generate_tear_sheet_content_async(api_key: str, model_id: str, prompt: str):
    return await generate_content_async(api_key, model_id, prompt, _build_tear_sheet_generation_config())


def ensure_tear_sheet_summary(context: dict, rotator: KeyRotator):
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    for model_id in _tear_sheet_model_sequence():
        try:
            api_key = rotator.get_key(model_id, estimate_text_tokens(prompt, response_budget=900))
            response = _generate_tear_sheet_content(api_key, model_id, prompt)
            summary = sanitize_model_output(response_text(response))
            if summary:
                context["tear_sheet_summary"] = summary[:900]
                print("  🧾 一頁式摘要已生成。")
                return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            print(f"  ⚠️  一頁式摘要生成失敗，報表將使用 fallback 摘要：{str(exc)[:120]}")
            return


async def ensure_tear_sheet_summary_async(context: dict, rotator: KeyRotator):
    if context.get("tear_sheet_summary") or not isinstance(rotator, KeyRotator):
        return
    prompt = _build_tear_sheet_prompt(context)
    for model_id in _tear_sheet_model_sequence():
        try:
            api_key = await rotator.async_get_key(model_id, estimate_text_tokens(prompt, response_budget=900))
            response = await _generate_tear_sheet_content_async(api_key, model_id, prompt)
            summary = sanitize_model_output(response_text(response))
            if summary:
                context["tear_sheet_summary"] = summary[:900]
                print("  🧾 一頁式摘要已生成。")
                return
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                continue
            print(f"  ⚠️  一頁式摘要生成失敗，報表將使用 fallback 摘要：{str(exc)[:120]}")
            return
