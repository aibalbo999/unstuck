"""Split report rendering helper."""

from __future__ import annotations

import re
from datetime import datetime
from html import escape

from mapping_fields import safe_sequence_items, safe_text
from .common import markdown_lib
from .html_sanitizer import sanitize_report_html, sanitize_report_plain_text
from recommendation_labels import normalize_recommendation_label

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
    # Agent 22/23/24 (v4) CoT scratchpad leakage signatures
    r"Check constraints:|Ensure all numbers are traced|reserved for Agent \d+|"
    r"Only use provided data|Strictly 1-2 week horizon|No final trade directions|No meta-talk, no roleplay|"
    r"Explicitly state.*Data Insufficient|1-2 weeks technical momentum analysis|1-2 Week Technical Scenarios|"
    r"Moving Averages.*Trend Structure|Breakouts.*Volume.*Price Confirmation|RSI.*MACD.*ATR Momentum|"
    r"Price History.*AgentState|AgentState view.*Current price|"
    r"Check constraints.*No trade direction|Check constraints.*No stop loss)",
    re.IGNORECASE,
)

SOURCE_CITATION_RE = re.compile(r"\[(?:source|cite):([A-Za-z0-9_.:-]{1,96})(?:\|([^\]\n]{1,80}))?\]")


def render_source_citation_tags(text: str) -> str:
    """Convert lightweight citation tags into sanitized HTML hooks."""
    if not text:
        return ""

    def repl(match: re.Match) -> str:
        source_id = sanitize_report_plain_text(match.group(1))
        label = sanitize_report_plain_text(match.group(2) or "來源")
        if not source_id:
            return ""
        return (
            f'<span class="source-citation" data-source-id="{escape(source_id)}" '
            f'role="button" tabindex="0" aria-label="查看來源 {escape(source_id)}">'
            f"[{escape(label)}]</span>"
        )

    return SOURCE_CITATION_RE.sub(repl, text)


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
        # --- Agent 22/23/24 (v4 pipeline) CoT scratchpad leakage ---
        # Self-check lines that appear after the main analysis body
        r"^\s*\*?\s*Check constraints:\s*(No trade direction|No stop loss|Traditional Chinese|Refined tone)",
        r"^\s*\*?\s*Ensure all numbers are traced\.?\s*$",
        r"^\s*\*?\s*(?:52-Week (?:High|Low)|May \d+ Price|June \d+ Price):\s*[\d,.]+ \(.*\)\s*$",
        r"^\s*\*?\s*(Check constraints|Ensure all numbers|reserved for Agent \d+|Only use provided data|Strictly 1-2 week horizon)",
        r"^\s*\*?\s*No final trade directions.*reserved for Agent \d+",
        r"^\s*\*?\s*Explicitly state.*Data Insufficient.*if fields are missing",
        r"^\s*\*?\s*No meta-talk,\s*no roleplay greetings",
        # Preamble bullet outlines (e.g. "*   I. Moving Averages & Trend Structure.")
        r"^\s{4,}\*\s{1,3}[IVX]+\.\s+(Moving Averages|Breakouts|RSI|MACD|ATR|1-2 Week)",
        # Data-source bullet lines in scratchpad ("*   Financial JSON (...)", "*   AgentState view (...)")
        r"^\s{4,}\*\s{1,3}(Financial JSON|AgentState view|RAG snippets)\s*\(",
        # Constraint reminders
        r"^\s{4,}\*\s{1,3}(Only use provided data|Strictly 1-2 week horizon|No final trade directions|Explicitly state|No meta-talk)",
        # Trailing CoT verification lines after the body
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


def strip_structured_blocks(text: str) -> str:
    """移除已由 UI 卡片呈現的結構化區塊，避免正文重複顯示。"""
    if not text:
        return ""
    text = re.sub(r"\[護城河評分\].*?\[/護城河評分\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\[目標股價\].*?\[/目標股價\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\[投資建議\].*?\[/投資建議\]", "", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def filter_future_price_history(price_history: dict) -> dict:
    """移除標示日期晚於今天的股價點，避免圖表出現未來收盤價。"""
    if not isinstance(price_history, dict):
        return {}
    dates = safe_sequence_items(price_history.get("dates", []))
    prices = safe_sequence_items(price_history.get("prices", []))
    today = datetime.now().date()
    if len(dates) == 0 or len(prices) == 0:
        kept = {}
        for raw_date, price in price_history.items():
            date_text = safe_text(raw_date).strip()
            try:
                date_val = datetime.strptime(date_text, "%Y-%m-%d").date()
            except ValueError:
                continue
            if date_val <= today:
                kept[date_text] = price
        return kept

    kept_dates = []
    kept_prices = []
    for date_str, price in zip(dates, prices):
        date_text = safe_text(date_str).strip()
        try:
            date_val = datetime.strptime(date_text, "%Y-%m-%d").date()
        except ValueError:
            continue
        if date_val <= today:
            kept_dates.append(date_text)
            kept_prices.append(price)
    return {"dates": kept_dates, "prices": kept_prices}


def normalize_moat_scores(moat_scores: dict) -> dict:
    """只保留雷達圖允許的護城河維度，避免草稿筆記被解析成圖表軸。"""
    allowed = ["品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"]
    if not isinstance(moat_scores, dict):
        return {}
    return {
        key: moat_scores[key]
        for key in allowed
        if key in moat_scores
        and isinstance(moat_scores[key], (int, float))
        and not isinstance(moat_scores[key], bool)
    }


def billion_twd_series_to_yi_twd(values: list) -> list:
    """Convert chart money series from billion_twd to 億台幣 for display."""
    converted = []
    for value in values or []:
        if isinstance(value, bool) or value is None:
            converted.append(value)
            continue
        if isinstance(value, (int, float)):
            converted.append(round(value * 10, 4))
            continue
        try:
            converted.append(round(float(str(value).replace(",", "")) * 10, 4))
        except (TypeError, ValueError):
            converted.append(value)
    return converted


def clean_markdown(text: str) -> str:
    """Render Markdown to HTML with a standard parser."""
    if not text:
        return ""

    text = render_source_citation_tags(text)

    if markdown_lib is None:
        escaped = escape(text)
        return sanitize_report_html(f"<p>{escaped.replace(chr(10) + chr(10), '</p><p>').replace(chr(10), '<br>')}</p>")

    html = markdown_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    html = re.sub(r"<table>", '<div class="table-wrapper"><table class="data-table">', html)
    html = html.replace("</table>", "</table></div>")
    return sanitize_report_html(html)


def get_recommendation_color(rec: str) -> str:
    """根據建議返回顏色"""
    rec = normalize_recommendation_label(rec)
    if rec == "買入":
        return "#10b981"  # 綠色
    elif rec in {"避免", "放空"}:
        return "#ef4444"  # 紅色
    else:
        return "#f59e0b"  # 黃色（持有）


def get_recommendation_icon(rec: str) -> str:
    """根據建議返回圖示"""
    rec = normalize_recommendation_label(rec)
    if rec == "買入":
        return "↑"
    elif rec in {"避免", "放空"}:
        return "↓"
    else:
        return "→"


def format_debate_text(text: str) -> str:
    """格式化多空辯論文字為 HTML 對話氣泡"""
    if not text:
        return ""
    
    lines = text.split('\n')
    result = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        if '🐂' in line or '陳博士' in line or '多頭' in line:
            # 多頭發言
            content = re.sub(r'^[🐂]*\s*陳博士[（(][^）)]*[）)]?[：:]\s*', '', line)
            content = re.sub(r'^🐂\s*', '', content)
            content = sanitize_report_plain_text(content)
            if content:
                result.append(f'''
                <div class="debate-bubble bull-bubble">
                    <div class="debate-avatar bull-avatar">🐂 多頭</div>
                    <div class="debate-content">{escape(content)}</div>
                </div>''')
        elif '🐻' in line or '李博士' in line or '空頭' in line:
            # 空頭發言
            content = re.sub(r'^[🐻]*\s*李博士[（(][^）)]*[）)]?[：:]\s*', '', line)
            content = re.sub(r'^🐻\s*', '', content)
            content = sanitize_report_plain_text(content)
            if content:
                result.append(f'''
                <div class="debate-bubble bear-bubble">
                    <div class="debate-content">{escape(content)}</div>
                    <div class="debate-avatar bear-avatar">🐻 空頭</div>
                </div>''')
        elif '主持人' in line or '---' in line:
            content = re.sub(r'^[*-]*\s*主持人[總結]?[：:]\s*', '', line).replace('---', '').strip()
            content = re.sub(r'^\*+\s*主持人總結[：:]\s*\*+', '', content).strip()
            content = re.sub(r'^主持人總結[：:]\s*', '', content).strip()
            content = sanitize_report_plain_text(content)
            if content:
                result.append(f'''
                <div class="debate-conclusion">
                    <div class="debate-conclusion-icon">⚖️</div>
                    <div class="debate-conclusion-text"><strong>主持人總結：</strong>{escape(content)}</div>
                </div>''')
        else:
            if line and not line.startswith('#') and len(line) > 10:
                line = sanitize_report_plain_text(line)
                if line:
                    result.append(f'<p class="debate-narration">{escape(line)}</p>')
    
    return sanitize_report_html('\n'.join(result))
