# ============================================================
# report_gen.py - HTML 報告產生器
# 生成專業的金融分析報告（深色主題）
# ============================================================

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
JINJA_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,
)


def render_report_template(template_name: str, values: dict) -> str:
    """Render a report template with precomputed report values."""
    return JINJA_ENV.get_template(template_name).render(**values)


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|moat_scores|price_targets|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
    r"Analyze the \"Economic Moat\"|Analyze the growth potential|"
    r"Growth Scenarios \(5 years\)|Professional, data-driven)",
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
        r"^\s*(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|Specific JSON schema|analysis_markdown|moat_scores|price_targets|recommendation)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|No roleplay meta-talk|analysis_markdown|moat_scores|price_targets|recommendation)\b",
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

    cleaned = normalize_bad_number_commas("\n".join(kept_lines))
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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


def build_audit_sections(context: dict) -> list[tuple[str, list[str]]]:
    """Collect final audit and preserved abnormality notes for rendering."""
    audit = context.get("final_audit", {}) or {}
    sections = []

    critical = list(audit.get("critical", []) or [])
    blocking = [
        issue for issue in (context.get("blocking_issues", []) or [])
        if issue not in critical
    ]
    if critical or blocking:
        sections.append(("仍需注意的異常", [*critical[:10], *blocking[:6]]))

    repair_log = context.get("audit_repair_log", []) or []
    if repair_log:
        sections.append(("AI 修復紀錄", repair_log[:10]))

    corrections = audit.get("corrections", []) or []
    if corrections:
        sections.append(("系統已套用校正", corrections[:8]))

    warnings = audit.get("warnings", []) or []
    if warnings:
        sections.append(("非阻斷提醒", warnings[:8]))

    return [(title, items) for title, items in sections if items]


def build_audit_banner_html(context: dict) -> str:
    """Render a visible report warning when final audit found abnormalities."""
    sections = build_audit_sections(context)
    if not sections:
        return ""

    section_html = []
    for title, items in sections:
        lis = "".join(f"<li>{escape(str(item))}</li>" for item in items)
        section_html.append(f"<div class=\"audit-section\"><strong>{escape(title)}</strong><ul>{lis}</ul></div>")

    return f"""
        <div class="audit-banner">
            <div class="audit-title">系統異常提醒：本報告已保留供檢視</div>
            <div class="audit-subtitle">系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。</div>
            {''.join(section_html)}
        </div>
    """


def build_audit_markdown(context: dict) -> str:
    sections = build_audit_sections(context)
    if not sections:
        return ""

    lines = [
        "## ⚠️ 系統異常提醒：本報告已保留供檢視",
        "",
        "系統已嘗試自動修復可定位的 Agent 輸出；若仍有異常，請優先閱讀下列提醒再使用本報告。",
        "",
    ]
    for title, items in sections:
        lines.append(f"### {title}")
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    return "\n".join(lines).strip()


def filter_future_price_history(price_history: dict) -> dict:
    """移除標示日期晚於今天的股價點，避免圖表出現未來收盤價。"""
    if not isinstance(price_history, dict):
        return {}
    dates = price_history.get("dates", [])
    prices = price_history.get("prices", [])
    if not dates or not prices:
        return price_history

    today = datetime.now().date()
    kept_dates = []
    kept_prices = []
    for date_str, price in zip(dates, prices):
        try:
            date_val = datetime.strptime(str(date_str), "%Y-%m-%d").date()
        except ValueError:
            continue
        if date_val <= today:
            kept_dates.append(str(date_str))
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
        if key in moat_scores and isinstance(moat_scores[key], (int, float))
    }


def clean_markdown(text: str) -> str:
    """將 Markdown 文字轉換為 HTML"""
    if not text:
        return ""
    
    # 處理標題
    text = re.sub(r'^## (.*?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.*?)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^#### (.*?)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
    
    # 處理粗體
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', text)
    
    # 處理斜體
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
    
    # 處理表格
    lines = text.split('\n')
    result_lines = []
    in_table = False
    table_started = False
    
    for i, line in enumerate(lines):
        if '|' in line and line.strip().startswith('|'):
            if not in_table:
                result_lines.append('<div class="table-wrapper"><table class="data-table">')
                in_table = True
                table_started = False
            
            # 跳過分隔行
            if re.match(r'^\|[\s\-:|]+\|', line):
                table_started = True
                continue
            
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if not table_started:
                cell_html = ''.join(f'<th>{c}</th>' for c in cells)
                result_lines.append(f'<tr>{cell_html}</tr>')
            else:
                cell_html = ''.join(f'<td>{c}</td>' for c in cells)
                result_lines.append(f'<tr>{cell_html}</tr>')
        else:
            if in_table:
                result_lines.append('</table></div>')
                in_table = False
                table_started = False
            result_lines.append(line)
    
    if in_table:
        result_lines.append('</table></div>')
    
    text = '\n'.join(result_lines)
    
    # 處理列表（無序）- 使用暫時標記避免與有序列表衝突
    text = re.sub(r'^\s*[-*]\s+(.*?)$', r'<__ul_li__>\1</__ul_li__>', text, flags=re.MULTILINE)
    text = re.sub(r'(<__ul_li__>.*?</__ul_li__>\n?)+', lambda m: f'<ul>{m.group()}</ul>', text, flags=re.DOTALL)
    text = text.replace('<__ul_li__>', '<li>').replace('</__ul_li__>', '</li>')
    
    # 處理有序列表 - 使用暫時標記並正確包裹為 <ol>
    text = re.sub(r'^\s*\d+\.\s+(.*?)$', r'<__ol_li__>\1</__ol_li__>', text, flags=re.MULTILINE)
    text = re.sub(r'(<__ol_li__>.*?</__ol_li__>\n?)+', lambda m: f'<ol>{m.group()}</ol>', text, flags=re.DOTALL)
    text = text.replace('<__ol_li__>', '<li>').replace('</__ol_li__>', '</li>')
    
    # 處理換行
    text = text.replace('\n\n', '</p><p>')
    text = f'<p>{text}</p>'
    
    # 清理空段落
    text = re.sub(r'<p>\s*</p>', '', text)
    text = re.sub(r'<p>(<h[3-5]>)', r'\1', text)
    text = re.sub(r'(</h[3-5]>)</p>', r'\1', text)
    text = re.sub(r'<p>(<ul>)', r'\1', text)
    text = re.sub(r'(</ul>)</p>', r'\1', text)
    text = re.sub(r'<p>(<ol>)', r'\1', text)
    text = re.sub(r'(</ol>)</p>', r'\1', text)
    text = re.sub(r'<p>(<div class="table-wrapper">)', r'\1', text)
    text = re.sub(r'(</div>)</p>', r'\1', text)
    
    return text


def get_recommendation_color(rec: str) -> str:
    """根據建議返回顏色"""
    rec = rec.strip().lower()
    if "買入" in rec or "buy" in rec:
        return "#10b981"  # 綠色
    elif "避免" in rec or "sell" in rec or "avoid" in rec:
        return "#ef4444"  # 紅色
    else:
        return "#f59e0b"  # 黃色（持有）


def get_recommendation_icon(rec: str) -> str:
    """根據建議返回圖示"""
    rec_lower = rec.strip().lower()
    if "買入" in rec_lower or "buy" in rec_lower:
        return "↑"
    elif "避免" in rec_lower or "sell" in rec_lower or "avoid" in rec_lower:
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
            if content:
                result.append(f'''
                <div class="debate-bubble bull-bubble">
                    <div class="debate-avatar bull-avatar">🐂 多頭</div>
                    <div class="debate-content">{content}</div>
                </div>''')
        elif '🐻' in line or '李博士' in line or '空頭' in line:
            # 空頭發言
            content = re.sub(r'^[🐻]*\s*李博士[（(][^）)]*[）)]?[：:]\s*', '', line)
            content = re.sub(r'^🐻\s*', '', content)
            if content:
                result.append(f'''
                <div class="debate-bubble bear-bubble">
                    <div class="debate-content">{content}</div>
                    <div class="debate-avatar bear-avatar">🐻 空頭</div>
                </div>''')
        elif '主持人' in line or '---' in line:
            content = re.sub(r'^[*-]*\s*主持人[總結]?[：:]\s*', '', line).replace('---', '').strip()
            content = re.sub(r'^\*+\s*主持人總結[：:]\s*\*+', '', content).strip()
            content = re.sub(r'^主持人總結[：:]\s*', '', content).strip()
            if content:
                result.append(f'''
                <div class="debate-conclusion">
                    <div class="debate-conclusion-icon">⚖️</div>
                    <div class="debate-conclusion-text"><strong>主持人總結：</strong>{content}</div>
                </div>''')
        else:
            if line and not line.startswith('#') and len(line) > 10:
                result.append(f'<p class="debate-narration">{line}</p>')
    
    return '\n'.join(result)


def generate_html_report(context: dict) -> str:
    """生成完整的 HTML 報告"""
    
    data = context.get("data", {})
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = context.get("ticker", "N/A")
    name = context.get("company_name", ticker)
    fetch_date = data.get("fetch_date", datetime.now().strftime("%Y年%m月%d日"))
    
    # 準備圖表數據
    years = data.get("years", [])
    revenue_data = data.get("revenue_history", [])
    net_income_data = data.get("net_income_history", [])
    fcf_data = data.get("fcf_history", [])
    gross_margin_data = data.get("gross_margin_history", [])
    op_margin_data = data.get("op_margin_history", [])
    net_margin_data = data.get("net_margin_history", [])
    roe_data = data.get("roe_history", [])
    price_history = filter_future_price_history(data.get("price_history", {}))
    
    # 護城河評分
    moat_scores = normalize_moat_scores(parsed.get("moat_scores", {}))
    moat_labels = list(moat_scores.keys())
    moat_values = list(moat_scores.values())
    overall_moat = moat_scores.get("整體護城河", 0)
    
    # 目標股價
    price_targets = parsed.get("price_targets", {})
    recommendation = parsed.get("recommendation", {})
    
    def get_rec_val(rec_dict, target_sub, default="N/A"):
        for k, v in rec_dict.items():
            if target_sub in k:
                return v
        return default
        
    rec_text = get_rec_val(recommendation, "建議", "持有")
    if "買入" in rec_text or "Buy" in rec_text or "BUY" in rec_text: rec_text = "買入"
    elif "避免" in rec_text or "Avoid" in rec_text or "AVOID" in rec_text or "賣出" in rec_text: rec_text = "避免"
    else: rec_text = "持有"

    rec_color = get_recommendation_color(rec_text)
    rec_icon = get_recommendation_icon(rec_text)
    
    target_3m = get_rec_val(recommendation, "3個月", "N/A")
    target_6m = get_rec_val(recommendation, "6個月", "N/A")
    target_12m = get_rec_val(recommendation, "12個月", "N/A")
    confidence = get_rec_val(recommendation, "信心", "N/A")
    audit_banner_html = build_audit_banner_html(context)
    
    # 格式化各 Agent 分析文字
    analysis_1 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(1, "分析進行中..."))))
    analysis_2 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(2, "分析進行中..."))))
    analysis_3 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(3, "分析進行中..."))))
    analysis_4 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(4, "分析進行中..."))))
    analysis_5 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(5, "分析進行中..."))))
    analysis_6_raw = strip_structured_blocks(sanitize_report_text(analyses.get(6, "分析進行中...")))
    analysis_6 = format_debate_text(analysis_6_raw)
    analysis_7 = clean_markdown(strip_structured_blocks(sanitize_report_text(analyses.get(7, "分析進行中..."))))
    
    # 移除結構化標記（避免顯示在報告中）
    for tag in ["[護城河評分]", "[/護城河評分]", "[目標股價]", "[/目標股價]", 
                "[投資建議]", "[/投資建議]"]:
        analysis_3 = analysis_3.replace(tag, "")
        analysis_4 = analysis_4.replace(tag, "")
        analysis_7 = analysis_7.replace(tag, "")
    
    # 準備 JSON 數據給圖表
    chart_data = {
        "years": years,
        "revenue": [v for v in revenue_data],
        "netIncome": [v for v in net_income_data],
        "fcf": [v for v in fcf_data],
        "grossMargin": [v for v in gross_margin_data],
        "opMargin": [v for v in op_margin_data],
        "netMargin": [v for v in net_margin_data],
        "roe": [v for v in roe_data],
        "priceHistory": price_history,
        "moatLabels": moat_labels,
        "moatValues": moat_values,
        "priceTargets": price_targets,
    }
    
    chart_data_json = json.dumps(chart_data, ensure_ascii=False)
    
    # 關鍵指標卡片
    key_metrics = [
        ("股價", data.get("current_price_fmt", "N/A"), ""),
        ("市值", data.get("market_cap_fmt", "N/A"), ""),
        ("P/E", data.get("pe_ratio", "N/A"), ""),
        ("P/B", data.get("pb_ratio", "N/A"), ""),
        ("毛利率", data.get("gross_margin", "N/A"), ""),
        ("ROE", data.get("roe", "N/A"), ""),
        ("殖利率", data.get("dividend_yield", "N/A"), ""),
        ("Beta", data.get("beta", "N/A"), ""),
    ]
    
    metrics_html = ""
    for label, value, hint in key_metrics:
        metrics_html += f'''
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
            </div>'''
    
    # 目標股價卡片
    price_targets_html = ""
    for scenario, price in price_targets.items():
        if "熊" in scenario:
            color = "#ef4444"
            icon = "↓"
        elif "牛" in scenario:
            color = "#10b981"
            icon = "↑"
        else:
            color = "#3b82f6"
            icon = "→"
        
        current = data.get("current_price", 0)
        if isinstance(current, (int, float)) and current > 0:
            pct = ((price - current) / current) * 100
            pct_str = f"({'+' if pct > 0 else ''}{pct:.1f}%)"
        else:
            pct_str = ""
        
        price_targets_html += f'''
            <div class="price-target-card" style="border-color: {color};">
                <div class="pt-scenario">{scenario}</div>
                <div class="pt-price" style="color: {color};">{icon} NT${price:.0f}</div>
                <div class="pt-pct" style="color: {color};">{pct_str}</div>
            </div>'''
    
    # 競爭對手比較表格中的值
    comp_pe = data.get("pe_ratio", "N/A")
    comp_pb = data.get("pb_ratio", "N/A")
    comp_ev_ebitda = data.get("ev_ebitda", "N/A")
    
    total_time = context.get("total_time", 0)
    time_str = f"{total_time:.0f} 秒" if total_time else "N/A"
    
    current_price_numeric = data.get("current_price", 0) if isinstance(data.get("current_price", 0), (int, float)) else 0
    template_context = dict(locals())
    return render_report_template("report.html.j2", template_context)

def generate_markdown_report(context: dict) -> str:
    """生成 Markdown 格式報告"""
    data = context.get("data", {})
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = context.get("ticker", "N/A")
    name = context.get("company_name", ticker)
    fetch_date = data.get("fetch_date", datetime.now().strftime("%Y年%m月%d日"))
    
    price_targets = parsed.get("price_targets", {})
    recommendation = parsed.get("recommendation", {})
    
    def get_rec_val(rec_dict, target_sub, default="N/A"):
        for k, v in rec_dict.items():
            if target_sub in k:
                return v
        return default
        
    rec_text = get_rec_val(recommendation, "建議", "持有")
    if "買入" in rec_text or "Buy" in rec_text or "BUY" in rec_text: rec_text = "買入"
    elif "避免" in rec_text or "Avoid" in rec_text or "AVOID" in rec_text or "賣出" in rec_text: rec_text = "避免"
    else: rec_text = "持有"

    target_3m = get_rec_val(recommendation, "3個月", "N/A")
    target_6m = get_rec_val(recommendation, "6個月", "N/A")
    target_12m = get_rec_val(recommendation, "12個月", "N/A")
    confidence = get_rec_val(recommendation, "信心", "N/A")
    audit_markdown = build_audit_markdown(context)
    
    analysis_1 = strip_structured_blocks(sanitize_report_text(analyses.get(1, "分析進行中...")))
    analysis_2 = strip_structured_blocks(sanitize_report_text(analyses.get(2, "分析進行中...")))
    analysis_3 = strip_structured_blocks(sanitize_report_text(analyses.get(3, "分析進行中...")))
    analysis_4 = strip_structured_blocks(sanitize_report_text(analyses.get(4, "分析進行中...")))
    analysis_5 = strip_structured_blocks(sanitize_report_text(analyses.get(5, "分析進行中...")))
    analysis_6 = strip_structured_blocks(sanitize_report_text(analyses.get(6, "分析進行中...")))
    analysis_7 = strip_structured_blocks(sanitize_report_text(analyses.get(7, "分析進行中...")))
    
    for tag in ["[護城河評分]", "[/護城河評分]", "[目標股價]", "[/目標股價]", 
                "[投資建議]", "[/投資建議]"]:
        analysis_3 = analysis_3.replace(tag, "")
        analysis_4 = analysis_4.replace(tag, "")
        analysis_7 = analysis_7.replace(tag, "")
    
    md = f"""# {ticker} {name} - 華爾街深度研究報告
📅 分析日期：{fetch_date}

{audit_markdown + chr(10) + chr(10) if audit_markdown else ""}
## 📊 關鍵指標
- **股價:** {data.get("current_price_fmt", "N/A")}
- **市值:** {data.get("market_cap_fmt", "N/A")}
- **P/E:** {data.get("pe_ratio", "N/A")}
- **P/B:** {data.get("pb_ratio", "N/A")}
- **毛利率:** {data.get("gross_margin", "N/A")}
- **ROE:** {data.get("roe", "N/A")}
- **殖利率:** {data.get("dividend_yield", "N/A")}
- **Beta:** {data.get("beta", "N/A")}

---

## 🎯 最終投資建議
- **綜合建議:** {rec_text}
- **3個月目標:** {target_3m}
- **6個月目標:** {target_6m}
- **12個月目標:** {target_12m}
- **信心指數:** {confidence}

---

## 1. 商業模式與整體分析 (Agent 1)
{analysis_1}

---

## 2. 財務深度分析 (Agent 2)
{analysis_2}

---

## 3. 競爭護城河評估 (Agent 3)
{analysis_3}

---

## 4. 投資銀行估值分析 (Agent 4)
{analysis_4}

---

## 5. 未來成長潛力 (Agent 5)
{analysis_5}

---

## 6. 多空辯論 (Agent 6)
{analysis_6}

---

## 7. 最終投資決策 (Agent 7)
{analysis_7}

---

## 📚 參考資料來源與數據誤差訴明

| 資料來源 | 涉及內容 | 註記 |
|---|---|---|
| **Yahoo Finance (yfinance)** | 市場即時資料、年度財務報表、估值指標、負債結構、分析師評等 | pypi.org/project/yfinance |
| **FinMind Open Data** | 台股每月營收官方數據（公開資訊觀測站 / TWSE） | finmindtrade.com |
| **Google Gemini AI** | 七位 AI 分析師論述（gemini-3.5-flash 、gemma-4-31b-it） | Goldman Sachs / Morgan Stanley / BlackRock / JPMorgan / Fidelity / T. Rowe Price 人設 |
| **公開資訊觀測站 (MOPS/TWSE)** | 台灣證券交易所官方財務公邖 | 可作為數據核對基準 |

> ⚠️ **數據誤差訴明**：Yahoo Finance 所提供的台股歷史財務報表有時存在年份缺失或延遲問題；`Debt to Equity` 指標已轉換為百分比形式；歷史營收、淨利、現金流等數據單位為 **Billion TWD (10億台幣)**。建議將本報告筆記的財務數據与公開資訊觀測站進行交叉比對。

> ⚠️ **免責聲明**：本報告由 AI 系統自動生成，僅供投資研究參考，不構成任何投資建議。股票投資有風險，投資前請諮詢專業財務顧問並自行評估風險承受能力。
"""
    return md
