"""Prompt leak detection and cleanup for generated report text."""

from __future__ import annotations

import re


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"歡迎收看|大家好|🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Senior Financial Media Host|Bull\s*\(Dr\.|Bear\s*\(Dr\.|Fixed prefixes|Use provided Target Prices|"
    r"Ensure the tone is professional|Ensure the \"respond-to-previous\"|"
    r"Taiwan Stock Research Report Editor|Compress a full research report|Investment recommendation, target price|"
    r"No title, no Markdown|Just one single paragraph of summary text|Ticker/Company:|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|reasoning_steps|valuation_reasoning|hard_metrics|moat_weakness_matrix|moat_scores|price_targets|dcf_reasoning|peer_reasoning|scenario_reasoning|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
    r"Analyze the \"Economic Moat\"|Analyze the growth potential|"
    r"Growth Scenarios \(5 years\)|Professional, data-driven|"
    r"Chief Economist and Industry Strategist|Macro Hedge Fund|Forensic Accountant|Financial Risk Specialist|"
    r"Analyze \d{4}\.TW|Financial JSON and previous agent summaries|Strict company identity|"
    r"No target prices?|No buy/sell/hold recommendations|Ensure no|Correction:|"
    r"Check constraints:|Ensure all numbers are traced|reserved for Agent \d+|"
    r"Only use provided data|Strictly 1-2 week horizon|No final trade directions|No meta-talk, no roleplay|"
    r"Explicitly state.*Data Insufficient|1-2 weeks technical momentum analysis|1-2 Week Technical Scenarios|"
    r"Moving Averages.*Trend Structure|Breakouts.*Volume.*Price Confirmation|RSI.*MACD.*ATR Momentum|"
    r"Price History.*AgentState|AgentState view.*Current price|"
    r"Check constraints.*No trade direction|Check constraints.*No stop loss)",
    re.IGNORECASE,
)


def strip_prompt_preamble(text: str) -> str:
    """Drop leaked role/task setup before the first formal report section."""
    if not text:
        return ""

    if "\\n" in text and (
        "analysis_markdown" in text
        or "\\n##" in text
        or "\\n###" in text
        or re.search(r"^#{1,4}\s+.+\\n", text, re.MULTILINE)
    ):
        text = text.replace("\\n", "\n")

    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        if REPORT_CONTENT_START_RE.match(line.strip()):
            start_index = idx
            break

    if start_index and any(PROMPT_LEAK_RESIDUE_RE.search(line) for line in lines[:start_index]):
        lines = lines[start_index:]

    while lines and lines[-1].strip() in {'"', '"}', '}', '},', "```"}:
        lines.pop()

    return "\n".join(lines)


def sanitize_report_text(text: str) -> str:
    """移除模型把提示詞、角色設定或 scratchpad 洩漏到正文的內容。"""
    if not text:
        return ""

    text = strip_prompt_preamble(text)
    leak_patterns = [
        r"^\s*(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher|Chief Economist and Industry Strategist|Senior Financial Media Host|Forensic Accountant|Financial Risk Specialist)\b",
        r"^\s*\*?\*?\s*分析師[：:].*(高盛|Goldman Sachs|Morgan Stanley|BlackRock|Fidelity|摩根士丹利|貝萊德|富達)",
        r"^\s*(Taiwan Stock Research Report Editor|Compress a full research report|Investment recommendation, target price|No title, no Markdown|Just one single paragraph of summary text|Ticker/Company:)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*Bull\s*\([^)]+\)\s+vs\.\s+Bear\s*\([^)]+\)\s+on\b",
        r"^\s*\*?\s*[🐂🐻]?\s*Dr\.\s+(Chen|Li)\s*:",
        r"^\s*\*?\s*\*?(Round\s+\d+|Each analyst|Must reference|Must respond|Neutral balanced conclusion|Fixed prefixes|No final buy/sell/hold recommendation|Use provided Target Prices and Growth Scenarios|Company|Current Price|Forward P/E|Forward EPS|ROE|Net Margin|FCF|Net Debt|Asset Turnover|Recent Revenue|Target Prices|Moat|Risks|Ensure the tone|Check that all numbers|Ensure the \"respond-to-previous\")\b",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Analyze \d{4}\.TW|Financial data provided|Financial JSON and previous agent summaries)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|Specific JSON schema|analysis_markdown|reasoning_steps|valuation_reasoning|hard_metrics|moat_weakness_matrix|moat_scores|price_targets|dcf_reasoning|peer_reasoning|scenario_reasoning|recommendation)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|No roleplay meta-talk|analysis_markdown|reasoning_steps|valuation_reasoning|hard_metrics|moat_weakness_matrix|moat_scores|price_targets|dcf_reasoning|peer_reasoning|scenario_reasoning|recommendation)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property|Financials|Cash Flow|Identity|Check)\s*:",
        r"^\s*(Professional, data-driven|Company Overview & Business Model|Macroeconomics & Industry Trends|Supply Chain Position & Competitive Landscape|Key Risk Factors|Analyze the \"Economic Moat\"|Analyze the growth potential)\b",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
        r"^\s*\*?\s*Check constraints:\s*(No trade direction|No stop loss|Traditional Chinese|Refined tone)",
        r"^\s*\*?\s*Ensure all numbers are traced\.?\s*$",
        r"^\s*\*?\s*(?:52-Week (?:High|Low)|May \d+ Price|June \d+ Price):\s*[\d,.]+ \(.*\)\s*$",
        r"^\s*\*?\s*(Check constraints|Ensure all numbers|reserved for Agent \d+|Only use provided data|Strictly 1-2 week horizon)",
        r"^\s*\*?\s*No final trade directions.*reserved for Agent \d+",
        r"^\s*\*?\s*Explicitly state.*Data Insufficient.*if fields are missing",
        r"^\s*\*?\s*No meta-talk,\s*no roleplay greetings",
        r"^\s{4,}\*\s{1,3}[IVX]+\.\s+(Moving Averages|Breakouts|RSI|MACD|ATR|1-2 Week)",
        r"^\s{4,}\*\s{1,3}(Financial JSON|AgentState view|RAG snippets)\s*\(",
        r"^\s{4,}\*\s{1,3}(Only use provided data|Strictly 1-2 week horizon|No final trade directions|Explicitly state|No meta-talk)",
        r"^\s*\*?\s*Check constraints:\s*No trade direction\? Yes",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {'"', '"}', '}', '},', "```"}:
            continue
        if leak_re.search(stripped):
            continue
        kept_lines.append(line)

    cleaned = normalize_bad_number_commas("\n".join(kept_lines))
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def contains_prompt_leak_residue(text: str) -> bool:
    """Return True when a rendered report fragment still looks like leaked instructions."""
    return bool(PROMPT_LEAK_RESIDUE_RE.search(text or ""))


def normalize_bad_number_commas(text: str) -> str:
    """修正 1,0064.8億 這類錯位千分位格式。"""
    def repl(match):
        raw = f"{match.group(1)}{match.group(2)}"
        decimal = match.group(3) or ""
        return f"{int(raw):,}{decimal}"

    return re.sub(r"(?<!\d)(\d),(\d{4})(\.\d+)?(?=億)", repl, text or "")


__all__ = [
    "contains_prompt_leak_residue",
    "normalize_bad_number_commas",
    "sanitize_report_text",
    "strip_prompt_preamble",
]
