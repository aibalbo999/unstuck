"""Context selection helpers for agent prompts."""

from __future__ import annotations

import json
import re

from analysis_types import AnalysisContext
from config import BLIND_CONTEXT_AGENTS, CONTEXT_TOTAL_CHAR_BUDGET, get_agent_context_budgets
from context_dependencies import fresh_context_digest, upstream_agent_numbers, upstream_context_inputs
from mapping_fields import safe_mapping_dict, safe_text
from prompt_evidence import prompt_evidence_copy
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
    17: [
        "泡沫", "題材", "夢想", "市場情緒", "FOMO", "Forward EPS", "本益比",
        "P/E 河流圖", "估值乖離", "催化劑", "法說", "新聞", "預期",
    ],
    18: [
        "法證", "財務", "CAGR", "ROE", "杜邦", "資產周轉率", "毛利率",
        "現金流", "同業", "外資", "投信", "法人", "派發", "倒貨",
    ],
    19: [
        "泡沫狙擊", "做空", "放空", "避險", "估值乖離", "極端預期",
        "財務紅旗", "籌碼派發", "Catalyst", "Stop-loss", "目標價", "信心",
    ],
}


AGENT_CONTEXT_DEPENDENCIES = {
    5: (1, 2, 3),
    12: (11,),
    13: (11,),
    14: (11, 12, 13),
    15: (11, 12, 13, 14),
    16: (11, 12, 13, 14, 15),
    18: (17,),
    19: (17, 18),
}


def _previous_agent_numbers(current_agent: int, context: AnalysisContext | None = None) -> list[int]:
    """Return the upstream agents visible to the current agent."""
    return list(upstream_agent_numbers(current_agent, context))


def _format_structured_outputs_for_context(context: AnalysisContext, current_agent: int | None = None, max_chars: int | None = None) -> str:
    context = safe_mapping_dict(context)
    context = context if context is not None else {}
    structured = (
        upstream_context_inputs(current_agent, context)["structured_outputs"]
        if current_agent is not None
        else prompt_evidence_copy(safe_mapping_dict(context.get("structured_outputs")) or {})
    )
    if not structured:
        return "{}"
    return _bounded_context_json(structured, max_chars)


def _bounded_context_json(value: dict, max_chars: int | None) -> str:
    """Omit whole fields or entries, never cut serialized JSON or numeric evidence."""
    def encode(payload):
        return json.dumps(payload, ensure_ascii=False, indent=2, default=safe_text)

    encoded = encode(value)
    if max_chars is None or len(encoded) <= max_chars:
        return encoded
    selected = {"_context_omitted": True}
    if len(encode(selected)) > max_chars:
        return "{}"
    for key, item in value.items():
        candidate = {**selected, key: item}
        if len(encode(candidate)) <= max_chars:
            selected = candidate
        elif isinstance(item, dict):
            fields = {}
            for field, field_value in item.items():
                candidate = {**selected, key: {**fields, field: field_value}}
                if len(encode(candidate)) <= max_chars:
                    fields[field] = field_value
                    selected = candidate
    return encode(selected)


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
        if remaining <= 0:
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
        note = f"\n\n（系統已依 Agent {current_agent} 任務精選前序片段，約省略 {omitted} 字。）"
        if len(note) < max_chars:
            output = output[:max_chars - len(note)] + note
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

    context = safe_mapping_dict(context)
    context = context if context is not None else {}
    inputs = upstream_context_inputs(current_agent, context)
    analyses = inputs["analyses"]
    if not analyses and not inputs["structured_outputs"]:
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

    max_total_chars = max(0, int(max_total_chars))
    if max_total_chars < 80:
        return "（前序 context 預算不足）" if max_total_chars >= 20 else ""
    # Reserve source slices before admitting digests or structured narratives.
    source_limit = max_total_chars * 3 // 5 if inputs["structured_outputs"] or include_digest else max_total_chars
    source_parts = ["【前序分析精選片段（非全文，依下一位 Agent 任務檢索）】"]
    sources = [(agent, safe_text(analyses[agent])) for agent in _previous_agent_numbers(current_agent, context) if agent in analyses]
    for index, (agent, text) in enumerate(sources):
        name = agent_names.get(agent, f"Agent {agent}")
        header = f"【{name}｜精選片段】\n"
        remaining = source_limit - len("\n\n".join(source_parts)) - 2
        per_source = min(per_agent_char_budget, remaining // (len(sources) - index) - len(header))
        if per_source <= 0:
            break
        snippet = _select_relevant_context(text, current_agent, agent, per_source)
        if snippet:
            source_parts.append(header + snippet)

    source_text = "\n\n".join(source_parts)
    parts = []
    remaining = max_total_chars - len(source_text) - 2
    digest = fresh_context_digest(current_agent, context) if include_digest else None
    raw_digests = safe_mapping_dict(context.get("context_digests")) or {}
    if include_digest and (current_agent in raw_digests or str(current_agent) in raw_digests):
        header = "【提煉 Agent 結構化摘要】\n"
        if digest:
            digest_budget = max(0, remaining // 2 - len(header) - 2)
            digest_text = _bounded_context_json(json.loads(digest), digest_budget)
        else:
            digest_text = "（摘要版本未驗證或已過期，請使用下列來源。）"
        if len(header + digest_text) + 2 <= remaining:
            parts.append(header + digest_text)
            remaining -= len(parts[-1]) + 2
    header = "【已解析結構化輸出】\n"
    if inputs["structured_outputs"] and remaining >= len(header) + 4:
        structured_context = _format_structured_outputs_for_context(context, current_agent, remaining - len(header) - 2)
        parts.append(header + structured_context)
    parts.append(source_text)
    return "\n\n".join(parts)
