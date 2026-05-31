# ============================================================
# report_gen.py - HTML 報告產生器
# 生成專業的金融分析報告（深色主題）
# ============================================================

import json
import re
from datetime import datetime


def sanitize_report_text(text: str) -> str:
    """移除模型把提示詞、角色設定或 scratchpad 洩漏到正文的內容。"""
    if not text:
        return ""

    leak_patterns = [
        r"^\s*(Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property)\s*:",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        if leak_re.search(line.strip()):
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
    
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{ticker} {name} - 華爾街深度研究報告</title>
    <meta name="description" content="{name}（{ticker}）完整股票研究報告，包含商業分析、財務分析、護城河評估、估值分析及投資建議">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Noto+Sans+TC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-primary: #050b1a;
            --bg-secondary: #0d1829;
            --bg-card: rgba(255,255,255,0.04);
            --bg-card-hover: rgba(255,255,255,0.07);
            --border: rgba(255,255,255,0.08);
            --border-bright: rgba(255,255,255,0.15);
            --text-primary: #e2e8f0;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-blue: #3b82f6;
            --accent-purple: #8b5cf6;
            --accent-cyan: #06b6d4;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-amber: #f59e0b;
            --gradient-1: linear-gradient(135deg, #1e3a8a 0%, #312e81 100%);
            --gradient-2: linear-gradient(135deg, #065f46 0%, #064e3b 100%);
            --gradient-3: linear-gradient(135deg, #991b1b 0%, #7f1d1d 100%);
            --nav-width: 220px;
            --sidebar-bg: rgba(13,24,41,0.95);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Inter', 'Noto Sans TC', -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}
        
        /* ─── 側邊導航欄 ─── */
        .sidebar {{
            position: fixed;
            left: 0; top: 0; bottom: 0;
            width: var(--nav-width);
            background: var(--sidebar-bg);
            backdrop-filter: blur(20px);
            border-right: 1px solid var(--border);
            z-index: 100;
            display: flex;
            flex-direction: column;
            overflow-y: auto;
        }}
        
        .sidebar-logo {{
            padding: 24px 16px 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .sidebar-ticker {{
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.5px;
        }}
        
        .sidebar-name {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 2px;
            font-weight: 400;
        }}
        
        .sidebar-rec {{
            margin: 12px 16px;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 700;
            text-align: center;
            background: {rec_color}22;
            border: 1px solid {rec_color}55;
            color: {rec_color};
        }}
        
        .nav-section {{
            padding: 8px 0;
        }}
        
        .nav-section-title {{
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            padding: 8px 16px 4px;
        }}
        
        .nav-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 9px 16px;
            cursor: pointer;
            font-size: 12.5px;
            color: var(--text-secondary);
            transition: all 0.2s;
            border-left: 3px solid transparent;
            text-decoration: none;
        }}
        
        .nav-item:hover, .nav-item.active {{
            color: var(--text-primary);
            background: rgba(59,130,246,0.1);
            border-left-color: var(--accent-blue);
        }}
        
        .nav-item .nav-num {{
            width: 20px;
            height: 20px;
            background: rgba(59,130,246,0.15);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 700;
            color: var(--accent-blue);
            flex-shrink: 0;
        }}
        
        .sidebar-footer {{
            margin-top: auto;
            padding: 12px 16px;
            border-top: 1px solid var(--border);
            font-size: 10px;
            color: var(--text-muted);
        }}
        
        /* ─── 主要內容區 ─── */
        .main {{
            margin-left: var(--nav-width);
            min-height: 100vh;
        }}
        
        /* ─── Hero 頭部 ─── */
        .hero {{
            background: linear-gradient(135deg, #0a1628 0%, #0f1f3d 50%, #0a1628 100%);
            border-bottom: 1px solid var(--border);
            padding: 48px 48px 40px;
            position: relative;
            overflow: hidden;
        }}
        
        .hero::before {{
            content: '';
            position: absolute;
            top: -50%;
            right: -10%;
            width: 500px;
            height: 500px;
            background: radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%);
            pointer-events: none;
        }}
        
        .hero::after {{
            content: '';
            position: absolute;
            bottom: -30%;
            left: 20%;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(139,92,246,0.06) 0%, transparent 70%);
            pointer-events: none;
        }}
        
        .hero-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(59,130,246,0.15);
            border: 1px solid rgba(59,130,246,0.3);
            color: var(--accent-blue);
            font-size: 11px;
            font-weight: 600;
            padding: 4px 12px;
            border-radius: 20px;
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .hero-title {{
            font-size: 42px;
            font-weight: 800;
            letter-spacing: -1px;
            line-height: 1.1;
            margin-bottom: 8px;
        }}
        
        .hero-title .ticker-highlight {{
            background: linear-gradient(135deg, #3b82f6, #8b5cf6, #06b6d4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .hero-subtitle {{
            font-size: 16px;
            color: var(--text-secondary);
            margin-bottom: 32px;
            font-weight: 300;
        }}
        
        /* ─── 關鍵指標卡片 ─── */
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            gap: 12px;
            margin-bottom: 24px;
        }}
        
        .metric-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
            transition: all 0.2s;
        }}
        
        .metric-card:hover {{
            background: var(--bg-card-hover);
            border-color: var(--border-bright);
            transform: translateY(-2px);
        }}
        
        .metric-label {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 6px;
        }}
        
        .metric-value {{
            font-size: 18px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        /* ─── 投資建議大卡片 ─── */
        .verdict-banner {{
            background: {rec_color}15;
            border: 1px solid {rec_color}40;
            border-radius: 16px;
            padding: 20px 28px;
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            margin-top: 8px;
        }}
        
        .verdict-icon {{
            width: 64px;
            height: 64px;
            background: {rec_color}25;
            border: 2px solid {rec_color};
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 28px;
            font-weight: 800;
            color: {rec_color};
            flex-shrink: 0;
        }}
        
        .verdict-text .verdict-label {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .verdict-text .verdict-main {{
            font-size: 28px;
            font-weight: 800;
            color: {rec_color};
            line-height: 1;
            margin: 4px 0;
        }}
        
        .verdict-text .verdict-sub {{
            font-size: 13px;
            color: var(--text-secondary);
        }}
        
        .verdict-meta {{
            margin-left: auto;
            text-align: right;
        }}
        
        .verdict-meta .vm-label {{
            font-size: 11px;
            color: var(--text-muted);
        }}
        
        .verdict-meta .vm-value {{
            font-size: 16px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        /* ─── 內容區段 ─── */
        .content {{
            padding: 40px 48px;
        }}
        
        .section {{
            margin-bottom: 48px;
            scroll-margin-top: 20px;
        }}
        
        .section-header {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}
        
        .section-num {{
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            font-weight: 800;
            color: white;
            flex-shrink: 0;
        }}
        
        .section-title {{
            font-size: 22px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        
        .section-model {{
            margin-left: auto;
            font-size: 11px;
            color: var(--text-muted);
            background: rgba(255,255,255,0.05);
            padding: 3px 10px;
            border-radius: 20px;
            border: 1px solid var(--border);
        }}
        
        /* ─── 分析卡片 ─── */
        .analysis-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 28px;
            line-height: 1.8;
            overflow: hidden;
        }}
        
        .analysis-card ol {{
            padding-left: 24px;
            margin-bottom: 12px;
        }}
        
        .analysis-card ol li {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 6px;
            list-style: decimal;
        }}
        
        .analysis-card h3 {{
            font-size: 16px;
            font-weight: 700;
            color: var(--accent-blue);
            margin: 20px 0 10px;
            padding-bottom: 6px;
            border-bottom: 1px solid rgba(59,130,246,0.2);
        }}
        
        .analysis-card h3:first-child {{ margin-top: 0; }}
        
        .analysis-card h4 {{
            font-size: 14px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 16px 0 8px;
        }}
        
        .analysis-card p {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }}
        
        .analysis-card strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}
        
        .analysis-card ul {{
            padding-left: 20px;
            margin-bottom: 12px;
        }}
        
        .analysis-card li {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: 6px;
            list-style: disc;
        }}
        
        /* ─── 數據表格 ─── */
        .table-wrapper {{
            overflow-x: auto;
            margin: 16px 0;
            border-radius: 12px;
            border: 1px solid var(--border);
        }}
        
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        
        .data-table th {{
            background: rgba(59,130,246,0.1);
            color: var(--accent-blue);
            font-weight: 600;
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid var(--border);
            white-space: nowrap;
        }}
        
        .data-table td {{
            padding: 10px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.04);
            color: var(--text-secondary);
            white-space: nowrap;
        }}
        
        .data-table tr:last-child td {{ border-bottom: none; }}
        .data-table tr:hover td {{ background: rgba(255,255,255,0.02); }}
        
        /* ─── 圖表區 ─── */
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 24px;
        }}
        
        .chart-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 20px;
        }}
        
        .chart-card.full-width {{
            grid-column: 1 / -1;
        }}
        
        .chart-title {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            margin-bottom: 16px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .chart-canvas-wrapper {{
            position: relative;
            height: 240px;
        }}
        
        .chart-canvas-wrapper.tall {{
            height: 300px;
        }}
        
        /* ─── 護城河評分 ─── */
        .moat-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        
        .moat-scores-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        
        .moat-score-item {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .moat-score-label {{
            font-size: 13px;
            color: var(--text-secondary);
            width: 80px;
            flex-shrink: 0;
        }}
        
        .moat-score-bar-wrapper {{
            flex: 1;
            height: 8px;
            background: rgba(255,255,255,0.08);
            border-radius: 4px;
            overflow: hidden;
        }}
        
        .moat-score-bar {{
            height: 100%;
            border-radius: 4px;
            transition: width 1s ease;
        }}
        
        .moat-score-num {{
            font-size: 14px;
            font-weight: 700;
            color: var(--text-primary);
            width: 30px;
            text-align: right;
        }}
        
        .moat-overall {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            margin-top: 12px;
        }}
        
        .moat-overall-score {{
            font-size: 48px;
            font-weight: 800;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 1;
        }}
        
        .moat-overall-label {{
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        
        /* ─── 目標股價 ─── */
        .price-targets-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }}
        
        .price-target-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            border-width: 1px;
        }}
        
        .pt-scenario {{
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}
        
        .pt-price {{
            font-size: 28px;
            font-weight: 800;
            margin-bottom: 4px;
        }}
        
        .pt-pct {{
            font-size: 13px;
            font-weight: 600;
        }}
        
        /* ─── 多空辯論 ─── */
        .debate-container {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}
        
        .debate-bubble {{
            display: flex;
            align-items: flex-start;
            gap: 12px;
            max-width: 85%;
        }}
        
        .bull-bubble {{
            align-self: flex-start;
        }}
        
        .bear-bubble {{
            align-self: flex-end;
            flex-direction: row-reverse;
        }}
        
        .debate-avatar {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 700;
            white-space: nowrap;
            flex-shrink: 0;
            margin-top: 4px;
        }}
        
        .bull-avatar {{
            background: rgba(16,185,129,0.15);
            border: 1px solid rgba(16,185,129,0.3);
            color: #10b981;
        }}
        
        .bear-avatar {{
            background: rgba(239,68,68,0.15);
            border: 1px solid rgba(239,68,68,0.3);
            color: #ef4444;
        }}
        
        .debate-content {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 14px 18px;
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.6;
        }}
        
        .bull-bubble .debate-content {{
            border-left: 3px solid #10b981;
        }}
        
        .bear-bubble .debate-content {{
            border-right: 3px solid #ef4444;
        }}
        
        .debate-conclusion {{
            background: rgba(139,92,246,0.08);
            border: 1px solid rgba(139,92,246,0.25);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            align-items: flex-start;
            gap: 12px;
            margin-top: 8px;
        }}
        
        .debate-conclusion-icon {{
            font-size: 24px;
            flex-shrink: 0;
        }}
        
        .debate-conclusion-text {{
            font-size: 14px;
            color: var(--text-secondary);
            line-height: 1.7;
        }}
        
        .debate-narration {{
            font-size: 12px;
            color: var(--text-muted);
            text-align: center;
            font-style: italic;
            margin: 4px 0;
        }}
        
        /* ─── 最終決策 ─── */
        .final-verdict {{
            background: linear-gradient(135deg, {rec_color}10 0%, transparent 100%);
            border: 1px solid {rec_color}30;
            border-radius: 20px;
            padding: 32px;
            margin-bottom: 24px;
        }}
        
        .fv-header {{
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 24px;
        }}
        
        .fv-badge {{
            font-size: 40px;
            font-weight: 900;
            color: {rec_color};
            background: {rec_color}20;
            border: 2px solid {rec_color}50;
            padding: 8px 24px;
            border-radius: 12px;
            letter-spacing: 2px;
        }}
        
        .fv-meta {{
            font-size: 14px;
            color: var(--text-secondary);
        }}
        
        /* ─── 免責聲明 ─── */
        .disclaimer {{
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            font-size: 11px;
            color: var(--text-muted);
            line-height: 1.6;
            margin-top: 32px;
        }}
        
        /* ─── 參考資料來源 ─── */
        .references {{
            background: rgba(255,255,255,0.02);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px 24px;
            margin-top: 24px;
        }}
        .references h4 {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 14px;
        }}
        .references-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 10px;
        }}
        .ref-item {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 10px 14px;
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 8px;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .ref-icon {{
            font-size: 16px;
            flex-shrink: 0;
            margin-top: 1px;
        }}
        .ref-name {{
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 2px;
        }}
        .ref-desc {{
            color: var(--text-muted);
            font-size: 11px;
            line-height: 1.5;
        }}
        
        /* ─── 進度條動畫 ─── */
        @keyframes slideIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .section {{
            animation: slideIn 0.5s ease forwards;
        }}
        
        /* ─── 響應式 ─── */
        @media (max-width: 1024px) {{
            .sidebar {{ display: none; }}
            .main {{ margin-left: 0; }}
            .hero {{ padding: 32px 24px; }}
            .content {{ padding: 24px; }}
            .charts-grid {{ grid-template-columns: 1fr; }}
            .moat-grid {{ grid-template-columns: 1fr; }}
            .price-targets-grid {{ grid-template-columns: 1fr; }}
        }}
        
        @media (max-width: 640px) {{
            .hero-title {{ font-size: 28px; }}
            .metrics-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}
    </style>
</head>
<body>

<!-- ─── 側邊導航欄 ─── -->
<nav class="sidebar">
    <div class="sidebar-logo">
        <div class="sidebar-ticker">{ticker}</div>
        <div class="sidebar-name">{name}</div>
    </div>
    
    <div class="sidebar-rec">
        {rec_icon} {rec_text}
    </div>
    
    <div class="nav-section">
        <div class="nav-section-title">分析報告</div>
        <a class="nav-item" href="#overview">
            <span class="nav-num">0</span>
            概覽總覽
        </a>
        <a class="nav-item" href="#section-1">
            <span class="nav-num">1</span>
            商業模式分析
        </a>
        <a class="nav-item" href="#section-2">
            <span class="nav-num">2</span>
            財務數據分析
        </a>
        <a class="nav-item" href="#section-3">
            <span class="nav-num">3</span>
            競爭護城河
        </a>
        <a class="nav-item" href="#section-4">
            <span class="nav-num">4</span>
            估值分析
        </a>
        <a class="nav-item" href="#section-5">
            <span class="nav-num">5</span>
            成長潛力
        </a>
        <a class="nav-item" href="#section-6">
            <span class="nav-num">6</span>
            多空辯論
        </a>
        <a class="nav-item" href="#section-7">
            <span class="nav-num">7</span>
            投資決策
        </a>
    </div>
    
    <div class="sidebar-footer">
        生成日期：{fetch_date}<br>
        分析耗時：{time_str}<br>
        <br>
        <span style="color: #374151;">⚠ 僅供研究參考，非投資建議</span>
    </div>
</nav>

<!-- ─── 主要內容 ─── -->
<main class="main">
    
    <!-- ─── Hero 頭部 ─── -->
    <div class="hero" id="overview">
        <div class="hero-badge">
            ★ 華爾街深度研究報告 ★
        </div>
        <div class="hero-title">
            <span class="ticker-highlight">{ticker}</span> {name}
        </div>
        <div class="hero-subtitle">
            {data.get("sector", "N/A")} · {data.get("industry", "N/A")} · 分析日期：{fetch_date}
        </div>
        
        <!-- 關鍵指標 -->
        <div class="metrics-grid">
            {metrics_html}
        </div>
        
        <!-- 投資建議橫幅 -->
        <div class="verdict-banner">
            <div class="verdict-icon">{rec_icon}</div>
            <div class="verdict-text">
                <div class="verdict-label">最終投資建議</div>
                <div class="verdict-main">{rec_text}</div>
                <div class="verdict-sub">基於 7 位頂級分析師完整研究</div>
            </div>
            <div class="verdict-meta">
                <div class="vm-label">3個月目標</div>
                <div class="vm-value">{target_3m}</div>
                <div class="vm-label" style="margin-top:8px">6個月目標</div>
                <div class="vm-value">{target_6m}</div>
                <div class="vm-label" style="margin-top:8px">12個月目標</div>
                <div class="vm-value">{target_12m}</div>
                <div class="vm-label" style="margin-top:8px">信心指數</div>
                <div class="vm-value">{confidence}</div>
            </div>
        </div>
    </div>
    
    <!-- ─── 內容區 ─── -->
    <div class="content">
        
        <!-- ─── 歷史數據圖表 ─── -->
        <div class="section">
            <div class="section-header">
                <div class="section-num">📈</div>
                <div class="section-title">歷史財務數據總覽</div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-card">
                    <div class="chart-title">年度營收與淨利（億元台幣）</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="revenueChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">利潤率趨勢（%）</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="marginChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">自由現金流（億元台幣）</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="fcfChart"></canvas>
                    </div>
                </div>
                <div class="chart-card">
                    <div class="chart-title">股東權益報酬率 ROE（%）</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="roeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ─── Agent 1：商業模式分析 ─── -->
        <div class="section" id="section-1">
            <div class="section-header">
                <div class="section-num">1</div>
                <div class="section-title">商業模式與整體分析</div>
                <div class="section-model">Goldman Sachs · gemini-3.5-flash</div>
            </div>
            <div class="analysis-card">
                {analysis_1}
            </div>
        </div>
        
        <!-- ─── Agent 2：財務分析 ─── -->
        <div class="section" id="section-2">
            <div class="section-header">
                <div class="section-num">2</div>
                <div class="section-title">五年財務深度分析</div>
                <div class="section-model">Morgan Stanley · gemma-4-31b-it</div>
            </div>
            <div class="analysis-card">
                {analysis_2}
            </div>
        </div>
        
        <!-- ─── Agent 3：護城河 ─── -->
        <div class="section" id="section-3">
            <div class="section-header">
                <div class="section-num">3</div>
                <div class="section-title">競爭護城河評估</div>
                <div class="section-model">BlackRock · gemma-4-31b-it</div>
            </div>
            
            <!-- 護城河雷達圖 + 評分 -->
            <div class="moat-grid" style="margin-bottom: 24px;">
                <div class="chart-card">
                    <div class="chart-title">護城河雷達圖</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="moatChart"></canvas>
                    </div>
                </div>
                <div>
                    <div class="moat-scores-list">
                        <!-- 護城河分數條 -->
                    </div>
                    <div class="moat-overall">
                        <div class="moat-overall-score" id="moat-overall-score">--</div>
                        <div class="moat-overall-label">整體護城河強度（滿分10）</div>
                    </div>
                </div>
            </div>
            
            <div class="analysis-card">
                {analysis_3}
            </div>
        </div>
        
        <!-- ─── Agent 4：估值分析 ─── -->
        <div class="section" id="section-4">
            <div class="section-header">
                <div class="section-num">4</div>
                <div class="section-title">投資銀行估值分析</div>
                <div class="section-model">JPMorgan · gemini-3.5-flash</div>
            </div>
            
            <!-- 目標股價 -->
            <div class="price-targets-grid">
                {price_targets_html}
            </div>
            
            <!-- 圖表 -->
            <div class="charts-grid" style="margin-bottom: 24px;">
                <div class="chart-card full-width">
                    <div class="chart-title">DCF 三情境估值 vs 當前股價</div>
                    <div class="chart-canvas-wrapper">
                        <canvas id="valuationChart"></canvas>
                    </div>
                </div>
            </div>
            
            <div class="analysis-card">
                {analysis_4}
            </div>
        </div>
        
        <!-- ─── Agent 5：成長潛力 ─── -->
        <div class="section" id="section-5">
            <div class="section-header">
                <div class="section-num">5</div>
                <div class="section-title">未來成長潛力分析</div>
                <div class="section-model">Fidelity · gemma-4-31b-it</div>
            </div>
            <div class="analysis-card">
                {analysis_5}
            </div>
        </div>
        
        <!-- ─── Agent 6：多空辯論 ─── -->
        <div class="section" id="section-6">
            <div class="section-header">
                <div class="section-num">6</div>
                <div class="section-title">多空辯論</div>
                <div class="section-model">Financial Media · gemini-3.5-flash</div>
            </div>
            <div class="analysis-card">
                <div class="debate-container">
                    {analysis_6}
                </div>
            </div>
        </div>
        
        <!-- ─── Agent 7：最終決策 ─── -->
        <div class="section" id="section-7">
            <div class="section-header">
                <div class="section-num">7</div>
                <div class="section-title">最終投資決策</div>
                <div class="section-model">Bridgewater · gemini-3.5-flash</div>
            </div>
            
            <div class="final-verdict">
                <div class="fv-header">
                    <div class="fv-badge">{rec_text}</div>
                    <div class="fv-meta">
                        3個月目標：{target_3m}<br>
                        6個月目標：{target_6m}<br>
                        12個月目標：{target_12m}<br>
                        信心指數：{confidence}
                    </div>
                </div>
            </div>
            
            <div class="analysis-card">
                {analysis_7}
            </div>
        </div>
        
        <!-- ─── 參考資料來源 ─── -->
        <div class="references">
            <h4>📚 參考資料來源與數據誤差訴明</h4>
            <div class="references-grid">
                <div class="ref-item">
                    <span class="ref-icon">📊</span>
                    <div>
                        <div class="ref-name">Yahoo Finance (yfinance)</div>
                        <div class="ref-desc">市場即時資料、年度財務報表、估值指標、負債結構、分析師評等<br>API：<code style="font-size:10px; color:#60a5fa;">pypi.org/project/yfinance</code></div>
                    </div>
                </div>
                <div class="ref-item">
                    <span class="ref-icon">🇹🇼</span>
                    <div>
                        <div class="ref-name">FinMind Open Data</div>
                        <div class="ref-desc">台股每月營收官方數據（來源：公開資訊觀測站 / TWSE）<br>API：<code style="font-size:10px; color:#60a5fa;">finmindtrade.com</code></div>
                    </div>
                </div>
                <div class="ref-item">
                    <span class="ref-icon">🤖</span>
                    <div>
                        <div class="ref-name">Google Gemini AI</div>
                        <div class="ref-desc">七位處於不同機構（Goldman Sachs、Morgan Stanley、BlackRock、JPMorgan、Fidelity、T. Rowe Price）的 AI 分析師論述，採用 gemini-3.5-flash 和 gemma-4-31b-it 模型</div>
                    </div>
                </div>
                <div class="ref-item">
                    <span class="ref-icon">🏷️</span>
                    <div>
                        <div class="ref-name">公開資訊觀測站 (MOPS)</div>
                        <div class="ref-desc">台灣證券交易所（台證所 TWSE）指定的官方財務公邖渠道，可作為數據核對基準</div>
                    </div>
                </div>
            </div>
            <p style="font-size:11px; color:var(--text-muted); margin-top:12px; line-height:1.5;">
                ⚠️ <strong>數據誤差訴明</strong>：Yahoo Finance 所提供的台股歷史財務報表有時存在年份缺失或延遲問題；<code>Debt to Equity</code> 指標已轉換為百分比形式；歷史營收、淨利、現金流等數據單位為 <strong>Billion TWD (10億台幣)</strong>。
                建議將本報告筆記的財務數據与公開資訊觀測站進行交叉比對。
            </p>
        </div>
        
        <!-- ─── 免責聲明 ─── -->
        <div class="disclaimer">
            ⚠️ <strong>免責聲明：</strong>本報告由 AI 系統自動生成，僅供投資研究參考，不構成任何投資建議。股票投資有風險，市場可能出現預期外的變化。投資前請諮詢專業財務顧問，並自行評估風險承受能力。本報告中的財務數據來源於公開資訊，分析結論僅代表 AI 模型的判斷，不保證準確性或完整性。
        </div>
        
    </div>
</main>

<script>
    // ─── 圖表數據 ─────────────────────────────────────────
    const CHART_DATA = {chart_data_json};
    
    // 通用圖表配置
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.06)';
    Chart.defaults.font.family = "'Inter', 'Noto Sans TC', sans-serif";
    
    function filterNulls(labels, data) {{
        const filtered = {{ labels: [], data: [] }};
        labels.forEach((l, i) => {{
            if (data[i] !== null && data[i] !== undefined) {{
                filtered.labels.push(l);
                filtered.data.push(data[i]);
            }}
        }});
        return filtered;
    }}
    
    // ─── 1. 營收與淨利圖 ────────────────────────────────────
    const revCtx = document.getElementById('revenueChart')?.getContext('2d');
    if (revCtx && CHART_DATA.years.length > 0) {{
        new Chart(revCtx, {{
            type: 'bar',
            data: {{
                labels: CHART_DATA.years,
                datasets: [
                    {{
                        label: '年度營收',
                        data: CHART_DATA.revenue,
                        backgroundColor: 'rgba(59,130,246,0.7)',
                        borderColor: '#3b82f6',
                        borderWidth: 1,
                        borderRadius: 4,
                    }},
                    {{
                        label: '淨利',
                        data: CHART_DATA.netIncome,
                        backgroundColor: 'rgba(16,185,129,0.7)',
                        borderColor: '#10b981',
                        borderWidth: 1,
                        borderRadius: 4,
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ padding: 16, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => `${{ctx.dataset.label}}: NT$${{ctx.raw}}億`
                        }}
                    }}
                }},
                scales: {{
                    x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ callback: v => `${{v}}億` }} }}
                }}
            }}
        }});
    }}
    
    // ─── 2. 利潤率圖 ─────────────────────────────────────────
    const marginCtx = document.getElementById('marginChart')?.getContext('2d');
    if (marginCtx && CHART_DATA.years.length > 0) {{
        new Chart(marginCtx, {{
            type: 'line',
            data: {{
                labels: CHART_DATA.years,
                datasets: [
                    {{
                        label: '毛利率',
                        data: CHART_DATA.grossMargin,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139,92,246,0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                    }},
                    {{
                        label: '營業利潤率',
                        data: CHART_DATA.opMargin,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59,130,246,0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 4,
                    }},
                    {{
                        label: '淨利率',
                        data: CHART_DATA.netMargin,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16,185,129,0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 4,
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'bottom', labels: {{ padding: 12, font: {{ size: 11 }} }} }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => `${{ctx.dataset.label}}: ${{ctx.raw}}%`
                        }}
                    }}
                }},
                scales: {{
                    x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ callback: v => `${{v}}%` }} }}
                }}
            }}
        }});
    }}
    
    // ─── 3. 自由現金流圖 ─────────────────────────────────────
    const fcfCtx = document.getElementById('fcfChart')?.getContext('2d');
    if (fcfCtx && CHART_DATA.years.length > 0) {{
        const fcfColors = (CHART_DATA.fcf || []).map(v => v >= 0 ? 'rgba(16,185,129,0.7)' : 'rgba(239,68,68,0.7)');
        new Chart(fcfCtx, {{
            type: 'bar',
            data: {{
                labels: CHART_DATA.years,
                datasets: [{{
                    label: '自由現金流',
                    data: CHART_DATA.fcf,
                    backgroundColor: fcfColors,
                    borderColor: fcfColors,
                    borderWidth: 1,
                    borderRadius: 4,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => `自由現金流: NT$${{ctx.raw}}億`
                        }}
                    }}
                }},
                scales: {{
                    x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ callback: v => `${{v}}億` }} }}
                }}
            }}
        }});
    }}
    
    // ─── 4. ROE 圖 ───────────────────────────────────────────
    const roeCtx = document.getElementById('roeChart')?.getContext('2d');
    if (roeCtx && CHART_DATA.years.length > 0) {{
        new Chart(roeCtx, {{
            type: 'line',
            data: {{
                labels: CHART_DATA.years,
                datasets: [{{
                    label: 'ROE (%)',
                    data: CHART_DATA.roe,
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245,158,11,0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 5,
                    pointBackgroundColor: '#f59e0b',
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        callbacks: {{
                            label: ctx => `ROE: ${{ctx.raw}}%`
                        }}
                    }}
                }},
                scales: {{
                    x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                    y: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }}, ticks: {{ callback: v => `${{v}}%` }} }}
                }}
            }}
        }});
    }}
    
    // ─── 5. 護城河雷達圖 ─────────────────────────────────────
    const moatCtx = document.getElementById('moatChart')?.getContext('2d');
    if (moatCtx && CHART_DATA.moatLabels.length > 0) {{
        // 過濾掉「整體護城河」這個維度
        const filteredLabels = CHART_DATA.moatLabels.filter(l => !l.includes('整體'));
        const filteredValues = CHART_DATA.moatValues.filter((_, i) => !CHART_DATA.moatLabels[i].includes('整體'));
        
        new Chart(moatCtx, {{
            type: 'radar',
            data: {{
                labels: filteredLabels,
                datasets: [{{
                    label: '護城河評分',
                    data: filteredValues,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139,92,246,0.15)',
                    borderWidth: 2,
                    pointBackgroundColor: '#8b5cf6',
                    pointRadius: 4,
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    r: {{
                        min: 0,
                        max: 10,
                        ticks: {{
                            stepSize: 2,
                            color: '#64748b',
                            font: {{ size: 11 }},
                        }},
                        grid: {{ color: 'rgba(255,255,255,0.08)' }},
                        angleLines: {{ color: 'rgba(255,255,255,0.08)' }},
                        pointLabels: {{ color: '#94a3b8', font: {{ size: 11 }} }},
                    }}
                }}
            }}
        }});
        
        // 動態生成護城河分數條
        const moatList = document.querySelector('.moat-scores-list');
        if (moatList) {{
            const colorMap = {{ 9: '#10b981', 8: '#22c55e', 7: '#84cc16', 6: '#f59e0b', 5: '#f97316', 4: '#ef4444', 3: '#dc2626' }};
            filteredLabels.forEach((label, i) => {{
                const val = filteredValues[i];
                const color = colorMap[Math.round(val)] || '#6b7280';
                moatList.innerHTML += `
                    <div class="moat-score-item">
                        <div class="moat-score-label">${{label}}</div>
                        <div class="moat-score-bar-wrapper">
                            <div class="moat-score-bar" style="width: ${{val*10}}%; background: ${{color}};"></div>
                        </div>
                        <div class="moat-score-num">${{val}}</div>
                    </div>`;
            }});
        }}
        
        // 整體護城河分數
        const overallEl = document.getElementById('moat-overall-score');
        if (overallEl) {{
            const overall = CHART_DATA.moatValues[CHART_DATA.moatLabels.indexOf('整體護城河')] || 
                           (filteredValues.reduce((a,b) => a+b, 0) / filteredValues.length).toFixed(1);
            overallEl.textContent = overall;
        }}
    }}
    
    // ─── 6. 估值圖 ───────────────────────────────────────────
    const valCtx = document.getElementById('valuationChart')?.getContext('2d');
    if (valCtx) {{
        const currentPrice = {data.get('current_price', 0) if isinstance(data.get('current_price', 0), (int, float)) else 0};
        const targets = CHART_DATA.priceTargets;
        
        const scenarios = Object.keys(targets);
        const prices = Object.values(targets);
        
        const colors = scenarios.map(s => {{
            if (s.includes('熊')) return 'rgba(239,68,68,0.7)';
            if (s.includes('牛')) return 'rgba(16,185,129,0.7)';
            return 'rgba(59,130,246,0.7)';
        }});
        
        const allLabels = ['當前股價', ...scenarios];
        const allPrices = [currentPrice, ...prices];
        const allColors = ['rgba(245,158,11,0.7)', ...colors];
        
        if (allPrices.some(p => p > 0)) {{
            new Chart(valCtx, {{
                type: 'bar',
                data: {{
                    labels: allLabels,
                    datasets: [{{
                        label: '股價（NT$）',
                        data: allPrices,
                        backgroundColor: allColors,
                        borderColor: allColors.map(c => c.replace('0.7', '1')),
                        borderWidth: 1,
                        borderRadius: 6,
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }},
                        tooltip: {{
                            callbacks: {{
                                label: ctx => `NT$${{ctx.raw.toFixed(0)}}`
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{ grid: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        y: {{ 
                            grid: {{ color: 'rgba(255,255,255,0.05)' }},
                            ticks: {{ callback: v => `NT$${{v}}` }},
                            beginAtZero: false,
                        }}
                    }}
                }}
            }});
        }}
    }}
    
    // ─── 導航高亮 ────────────────────────────────────────────
    const sections = document.querySelectorAll('.section[id], #overview');
    const navItems = document.querySelectorAll('.nav-item');
    
    const observer = new IntersectionObserver(entries => {{
        entries.forEach(entry => {{
            if (entry.isIntersecting) {{
                navItems.forEach(item => {{
                    item.classList.remove('active');
                    if (item.getAttribute('href') === '#' + entry.target.id) {{
                        item.classList.add('active');
                    }}
                }});
            }}
        }});
    }}, {{ threshold: 0.3 }});
    
    sections.forEach(s => observer.observe(s));
</script>

</body>
</html>'''
    
    return html

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
