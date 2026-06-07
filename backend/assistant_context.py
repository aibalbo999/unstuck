"""Context selection helpers for agent prompts."""

from __future__ import annotations

import json
import re

from analysis_types import AnalysisContext
from config import BLIND_CONTEXT_AGENTS, CONTEXT_TOTAL_CHAR_BUDGET, get_agent_context_budgets
from validators import strip_generated_audit_sections


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
    11: [
        "總經", "利率", "通膨", "地緣", "政策", "產業週期", "去庫存", "擴張",
        "供需", "順風", "逆風", "關稅", "補貼",
    ],
    12: [
        "商業模式", "護城河", "品牌", "網路效應", "轉換成本", "成本優勢",
        "專利", "毛利率", "淨利率", "競爭", "市佔",
    ],
    13: [
        "財務", "FCF", "自由現金流", "轉換率", "庫存", "應收", "CapEx",
        "杜邦", "ROE", "槓桿", "流動比率", "債務", "紅旗",
    ],
    14: [
        "估值", "成長", "DCF", "WACC", "FCF", "本益比", "P/E", "Forward EPS",
        "目標價", "TAM", "SAM", "催化", "雙重樂觀", "同業",
    ],
    15: [
        "籌碼", "三大法人", "外資", "投信", "自營商", "買賣超", "P/E 河流圖",
        "情緒", "催化", "新聞", "技術面", "動能", "擁擠交易",
    ],
    16: [
        "交易決策", "建議", "目標價", "估值", "籌碼", "總經", "排雷", "紅旗",
        "風控", "進出場", "左側交易", "動能", "買入", "持有", "避免",
    ],
}


AGENT_CONTEXT_DEPENDENCIES = {
    5: (1, 2, 3),
    12: (11,),
    13: (11,),
    14: (11, 12, 13),
    15: (11, 12, 13, 14),
    16: (11, 12, 13, 14, 15),
}


def _previous_agent_numbers(current_agent: int) -> list[int]:
    """Return the upstream agents visible to the current agent."""
    explicit_dependencies = AGENT_CONTEXT_DEPENDENCIES.get(current_agent)
    if explicit_dependencies is not None:
        return list(explicit_dependencies)
    return list(range(1, current_agent))


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
    if current_agent in BLIND_CONTEXT_AGENTS:
        return "（盲測模式：本 Agent 僅使用原始財務資料、工具結果與自身檢索資料，不引用前序 Agent 分析。）"

    analyses = context.get("analyses", {})
    if not analyses:
        return "（無前序分析）"

    dynamic_total_budget, per_agent_char_budget = get_agent_context_budgets(current_agent)
    if max_total_chars == CONTEXT_TOTAL_CHAR_BUDGET:
        max_total_chars = dynamic_total_budget

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

    for i in _previous_agent_numbers(current_agent):
        if i in analyses:
            name = agent_names.get(i, f"Agent {i}")
            used_chars = len("\n\n".join(parts))
            if used_chars >= max_total_chars:
                parts.append("（前序片段已達系統 context 預算上限，後續 Agent 請以結構化輸出與提煉摘要為準。）")
                break
            remaining_budget = max_total_chars - used_chars
            per_agent_budget = min(per_agent_char_budget, remaining_budget)
            clean_analysis = _select_relevant_context(
                str(analyses[i]),
                current_agent=current_agent,
                source_agent=i,
                max_chars=per_agent_budget,
            )
            if clean_analysis:
                parts.append(f"【{name}｜精選片段】\n{clean_analysis}")

    return "\n\n".join(parts) if parts else "（無前序分析）"
