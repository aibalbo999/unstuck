"""Prompt leakage stripping and model-output sanitization."""

from __future__ import annotations

import re


def strip_generated_audit_sections(text: str) -> str:
    """Remove system-generated warning/audit tails before re-validating model text."""
    if not text:
        return ""
    generated_headers = [
        "\n## 系統品質檢查警示",
        "\n## 系統身分一致性警示",
        "\n## 系統最終稽核",
        "\n### 系統品質檢查警示",
        "\n### 系統身分一致性警示",
        "\n### 系統最終稽核",
    ]
    indexes = [text.find(header) for header in generated_headers if text.find(header) != -1]
    if not indexes:
        return text
    return text[:min(indexes)].rstrip()


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"歡迎收看|大家好|🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Senior Financial Media Host|Bull\s*\(Dr\.|Bear\s*\(Dr\.|Fixed prefixes|Use provided Target Prices|"
    r"Ensure the tone is professional|Ensure the \"respond-to-previous\"|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|reasoning_steps|valuation_reasoning|hard_metrics|moat_weakness_matrix|moat_scores|price_targets|dcf_reasoning|peer_reasoning|scenario_reasoning|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
    r"Analyze the \"Economic Moat\"|Analyze the growth potential|"
    r"Growth Scenarios \(5 years\)|Professional, data-driven|"
    r"Chief Economist and Industry Strategist|Macro Hedge Fund|Forensic Accountant|Financial Risk Specialist|"
    r"Analyze \d{4}\.TW|Financial JSON and previous agent summaries|Strict company identity|"
    r"No target prices?|No buy/sell/hold recommendations|Ensure no|Correction:)",
    re.IGNORECASE,
)


def strip_prompt_preamble(text: str) -> str:
    """Drop leaked role/task setup before the first formal report section."""
    if not text:
        return ""

    if "\\n" in text and ("analysis_markdown" in text or "\\n##" in text or "\\n###" in text):
        text = text.replace("\\n", "\n")

    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if REPORT_CONTENT_START_RE.match(stripped):
            start_index = idx
            break

    if start_index and any(PROMPT_LEAK_RESIDUE_RE.search(line) for line in lines[:start_index]):
        lines = lines[start_index:]

    while lines and lines[-1].strip() in {'"', '"}', '}', '},', "```"}:
        lines.pop()

    return "\n".join(lines)


def validate_prompt_leakage(text: str) -> list[str]:
    """Return high-confidence prompt leakage findings after sanitization."""
    if not text:
        return []
    findings = []
    for pattern in [
        "Senior Analyst at Goldman Sachs",
        "高盛 (Goldman Sachs) 股票研究部門",
        "Chief Economist and Industry Strategist",
        "Senior Financial Media Host",
        "Bull (Dr.",
        "Fixed prefixes",
        "Forensic Accountant",
        "Valid parseable JSON only",
        "No markdown code fences",
        "Specific JSON schema",
        "Strict company identity",
        "Financial JSON and previous agent summaries",
        "Check: Did I",
        "No roleplay meta-talk",
    ]:
        if pattern.lower() in text.lower():
            findings.append(f"輸出仍包含內部提示詞片段：{pattern}")
    return findings


def sanitize_model_output(text: str) -> str:
    """Remove prompt/scratchpad leakage before it enters reports or later-agent context."""
    if not text:
        return ""

    text = strip_prompt_preamble(text)
    leak_patterns = [
        r"^\s*(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher|Chief Economist and Industry Strategist|Senior Financial Media Host|Forensic Accountant|Financial Risk Specialist)\b",
        r"^\s*\*?\*?\s*分析師[：:].*(高盛|Goldman Sachs|Morgan Stanley|BlackRock|Fidelity|摩根士丹利|貝萊德|富達)",
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

    cleaned = "\n".join(kept_lines)
    cleaned = normalize_bad_number_commas(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def normalize_bad_number_commas(text: str) -> str:
    """Fix values like 1,0064.8億 -> 10,064.8億."""
    def repl(match):
        raw = f"{match.group(1)}{match.group(2)}"
        decimal = match.group(3) or ""
        return f"{int(raw):,}{decimal}"

    return re.sub(r"(?<!\d)(\d),(\d{4})(\.\d+)?(?=億)", repl, text or "")
