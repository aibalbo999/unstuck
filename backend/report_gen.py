# ============================================================
# report_gen.py - HTML 報告產生器
# 生成專業的金融分析報告（深色主題）
# ============================================================

from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from html import escape
from pathlib import Path

from google.genai import types
from jinja2 import Environment, FileSystemLoader

from analysis_types import AnalysisContext
from agent_catalog import AGENT_NAMES
from config import (
    AGENT_MODELS,
    API_KEYS,
    ENABLE_REPORT_COVER,
    REPORT_COVER_ASPECT_RATIO,
    REPORT_COVER_FALLBACK_MODELS,
    REPORT_COVER_IMAGE_SIZE,
    REPORT_COVER_MODEL,
    format_model_routes,
)
from llm_client import (
    KeyRotator,
    describe_quota_or_rate_error,
    estimate_text_tokens,
    generate_images_async,
    is_missing_model_error,
    is_quota_or_rate_error,
    retry_delay_seconds,
)
from pipeline_modes import get_pipeline_definition

try:
    import markdown as markdown_lib
except Exception:  # pragma: no cover - dependency fallback for older local installs
    markdown_lib = None


TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
JINJA_ENV = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=False,
)


AGENT_INSTITUTIONS = {
    1: "Goldman Sachs",
    2: "Morgan Stanley",
    3: "BlackRock",
    4: "JPMorgan",
    5: "Fidelity",
    6: "Financial Media",
    7: "Bridgewater",
    11: "Macro Hedge Fund",
    12: "Morningstar / BlackRock",
    13: "Muddy Waters / Morgan Stanley",
    14: "Goldman Sachs",
    15: "Point72",
    16: "Citadel",
}


def build_agent_model_labels() -> dict[int, str]:
    return {
        agent_num: f"{institution} · {AGENT_MODELS.get(agent_num, 'N/A')}"
        for agent_num, institution in AGENT_INSTITUTIONS.items()
    }


def render_report_template(template_name: str, values: dict) -> str:
    """Render a report template with precomputed report values."""
    return JINJA_ENV.get_template(template_name).render(**values)


def build_report_cover_prompt(context: AnalysisContext) -> str:
    """Build a professional Imagen prompt with Chinese company identity first."""
    data = context.get("data", {}) or {}
    identity = data.get("company_identity", {}) if isinstance(data.get("company_identity"), dict) else {}
    company_name = (
        identity.get("official_name")
        or data.get("company_name")
        or context.get("company_name")
        or context.get("ticker")
        or "目標公司"
    )
    industry = data.get("industry") or data.get("sector") or "global equities"
    ticker = data.get("ticker") or context.get("ticker") or ""
    return (
        "A professional Wall Street equity research report cover for "
        f"{company_name} {ticker}, high-tech visual background representing {industry}, "
        "institutional investment bank style, clean premium editorial layout, "
        "cinematic lighting, detailed market data texture, 8k, no logos, no watermark, "
        "no readable text inside the image."
    )


def _build_cover_generation_config():
    kwargs = {
        "number_of_images": 1,
        "aspect_ratio": REPORT_COVER_ASPECT_RATIO,
        "output_mime_type": "image/jpeg",
        "image_size": REPORT_COVER_IMAGE_SIZE,
        "enhance_prompt": True,
    }
    try:
        return types.GenerateImagesConfig(**kwargs)
    except TypeError:
        kwargs.pop("image_size", None)
        kwargs.pop("enhance_prompt", None)
        return types.GenerateImagesConfig(**kwargs)


def _extract_image_source(response) -> str:
    generated_images = getattr(response, "generated_images", None) or []
    for generated in generated_images:
        image = getattr(generated, "image", None)
        if not image:
            continue
        gcs_uri = getattr(image, "gcs_uri", None)
        if gcs_uri:
            return str(gcs_uri)
        image_bytes = getattr(image, "image_bytes", None)
        if image_bytes:
            mime_type = getattr(image, "mime_type", None) or "image/jpeg"
            encoded = base64.b64encode(bytes(image_bytes)).decode("ascii")
            return f"data:{mime_type};base64,{encoded}"
    return ""


async def prepare_report_cover_async(context: AnalysisContext, rotator: KeyRotator | None = None) -> dict:
    """Generate a report cover when Imagen quota is available; otherwise skip."""
    existing = context.get("report_cover", {}) or {}
    if existing.get("image"):
        return existing

    if not ENABLE_REPORT_COVER or not API_KEYS:
        return {}

    prompt = build_report_cover_prompt(context)
    try:
        local_rotator = rotator if isinstance(rotator, KeyRotator) else KeyRotator(API_KEYS)
    except Exception:
        return {}

    model_sequence = list(dict.fromkeys([REPORT_COVER_MODEL, *REPORT_COVER_FALLBACK_MODELS]))
    for model_id in model_sequence:
        if not model_id:
            continue
        api_key = None
        try:
            api_key = await local_rotator.async_get_key(model_id, estimate_text_tokens(prompt))
            response = await generate_images_async(api_key, model_id, prompt, _build_cover_generation_config())
            image_source = _extract_image_source(response)
            if image_source:
                cover = {"image": image_source, "prompt": prompt, "model": model_id}
                context["report_cover"] = cover
                print(f"  🖼️  報告封面已生成：{model_id}")
                return cover
        except Exception as exc:
            if is_missing_model_error(str(exc)):
                print(f"  ⚠️  Imagen 模型 {model_id} 不可用，改試下一個封面模型。")
                continue
            if is_quota_or_rate_error(str(exc)):
                if api_key:
                    local_rotator.penalize(api_key, model_id, retry_delay_seconds(exc, default=60))
                print(f"  ⏭️  Imagen 封面額度不足，略過封面：{describe_quota_or_rate_error(exc)[:120]}")
                break
            print(f"  ⚠️  Imagen 封面生成失敗，略過封面：{str(exc)[:120]}")
            break
    return {}


async def generate_html_report_async(context: AnalysisContext) -> str:
    """Async HTML report renderer that can optionally generate an Imagen cover."""
    await prepare_report_cover_async(context)
    return generate_html_report(context)


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Taiwan Stock Research Report Editor|Compress a full research report|Investment recommendation, target price|"
    r"No title, no Markdown|Just one single paragraph of summary text|Ticker/Company:|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|reasoning_steps|valuation_reasoning|hard_metrics|moat_weakness_matrix|moat_scores|price_targets|dcf_reasoning|peer_reasoning|scenario_reasoning|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
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
        r"^\s*(Taiwan Stock Research Report Editor|Compress a full research report|Investment recommendation, target price|No title, no Markdown|Just one single paragraph of summary text|Ticker/Company:)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
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


def build_audit_sections(context: AnalysisContext) -> list[tuple[str, list[str]]]:
    """Collect final audit and preserved abnormality notes for rendering."""
    audit = context.get("final_audit", {}) or {}
    sections = []

    critical = list(audit.get("critical", []) or [])
    blocking = [
        issue for issue in (context.get("blocking_issues", []) or [])
        if issue not in critical
    ]
    if not critical and not blocking:
        return []

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


def build_audit_banner_html(context: AnalysisContext) -> str:
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


def build_audit_markdown(context: AnalysisContext) -> str:
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

    if markdown_lib is None:
        escaped = escape(text)
        return f"<p>{escaped.replace(chr(10) + chr(10), '</p><p>').replace(chr(10), '<br>')}</p>"

    html = markdown_lib.markdown(
        text,
        extensions=["extra", "sane_lists", "nl2br"],
        output_format="html5",
    )
    html = re.sub(r"<table>", '<div class="table-wrapper"><table class="data-table">', html)
    html = html.replace("</table>", "</table></div>")
    return html


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


def _strip_legacy_structured_tags(text: str) -> str:
    for tag in [
        "[護城河評分]",
        "[/護城河評分]",
        "[目標股價]",
        "[/目標股價]",
        "[投資建議]",
        "[/投資建議]",
    ]:
        text = text.replace(tag, "")
    return text.strip()


def build_agent_sections(context: AnalysisContext, *, html: bool = True) -> list[dict]:
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    analyses = context.get("analyses", {}) or {}
    agent_model_labels = build_agent_model_labels()
    structured_agents = pipeline_def["structured_agents"]
    debate_agents = set(pipeline_def.get("debate_agents", ()))
    sections = []

    for display_num, agent_num in enumerate(pipeline_def["agents"], 1):
        raw = strip_structured_blocks(sanitize_report_text(analyses.get(agent_num, "分析進行中...")))
        raw = _strip_legacy_structured_tags(raw)
        if html:
            body = format_debate_text(raw) if agent_num in debate_agents else clean_markdown(raw)
        else:
            body = raw

        kind = "standard"
        if agent_num == structured_agents.get("moat"):
            kind = "moat"
        elif agent_num == structured_agents.get("valuation"):
            kind = "valuation"
        elif agent_num == structured_agents.get("recommendation"):
            kind = "final"

        sections.append({
            "display_num": display_num,
            "agent_num": agent_num,
            "title": AGENT_NAMES.get(agent_num, f"Agent {agent_num}"),
            "model_label": agent_model_labels.get(agent_num, AGENT_MODELS.get(agent_num, "N/A")),
            "body": body,
            "kind": kind,
            "is_debate": agent_num in debate_agents,
        })

    return sections


def build_tear_sheet_summary(context: AnalysisContext) -> str:
    """Build a one-page style summary, preferring model output when available."""
    model_summary = str(context.get("tear_sheet_summary", "") or "").strip()
    if model_summary:
        sanitized = sanitize_report_text(model_summary)
        if sanitized and not contains_prompt_leak_residue(sanitized):
            return sanitized[:900]

    data = context.get("data", {}) or {}
    parsed = context.get("parsed", {}) or {}
    recommendation = parsed.get("recommendation", {}) or {}
    price_targets = parsed.get("price_targets", {}) or {}

    rec = next((str(v) for k, v in recommendation.items() if "建議" in str(k)), "持有")
    confidence = next((str(v) for k, v in recommendation.items() if "信心" in str(k)), "N/A")
    base_target = price_targets.get("基本情境", "N/A")
    catalysts = data.get("recent_catalysts", []) or []
    top_catalyst = catalysts[0]["title"] if catalysts and catalysts[0].get("title") else "近期催化劑資料不足"
    institutional = data.get("institutional_trading", {}) or {}
    chip_trend = institutional.get("trend", "N/A")
    chip_net = institutional.get("total_net_buy_thousand_shares", "N/A")
    pe_river = data.get("pe_river_chart", {}) or {}
    pe_source = pe_river.get("source", "N/A")

    return (
        f"一頁式摘要：{data.get('ticker', 'N/A')} {data.get('company_name', '')} 的綜合建議為「{rec}」，"
        f"信心指數 {confidence}，基本情境目標價為 NT${base_target if base_target != 'N/A' else 'N/A'}。"
        f"基本面重點在於 {data.get('industry', 'N/A')} 景氣、獲利品質與現金流能否支撐估值；"
        f"近 30 日關鍵催化劑為「{top_catalyst}」。"
        f"籌碼面顯示三大法人趨勢為 {chip_trend}，累計買賣超約 {chip_net} 張。"
        f"台股在地估值另以 P/E 河流圖檢視位階（來源：{pe_source}），"
        "若基本面、籌碼與河流圖位階互相背離，短線操作應降低部位與信心。"
    )


def generate_html_report(context: AnalysisContext) -> str:
    """生成完整的 HTML 報告"""
    
    data = context.get("data", {})
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = context.get("ticker", "N/A")
    name = context.get("company_name", ticker)
    fetch_date = data.get("fetch_date", datetime.now().strftime("%Y年%m月%d日"))
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    report_title = pipeline_def["report_title"]
    report_subtitle = pipeline_def["report_subtitle"]
    pipeline_label = pipeline_def["label"]
    
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
    pe_river = data.get("pe_river_chart", {}) or {}
    pe_river_source = str(pe_river.get("source", "") or "")
    pe_river_title = (
        "P/E 河流圖（EPS × 預設本益比通道）"
        if "default" in pe_river_source.lower()
        else "P/E 河流圖（EPS × 歷史本益比通道）"
    )
    
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
    tear_sheet_summary = clean_markdown(build_tear_sheet_summary(context))
    report_cover = context.get("report_cover", {}) or {}
    report_cover_image = report_cover.get("image", "")
    report_cover_model = report_cover.get("model", "")
    
    agent_sections = build_agent_sections(context, html=True)
    
    # 準備 JSON 數據給圖表
    chart_data = {
        "years": years,
        "moneyUnit": "hundred_million_twd",
        "sourceMoneyUnit": "billion_twd",
        "revenue": billion_twd_series_to_yi_twd(revenue_data),
        "netIncome": billion_twd_series_to_yi_twd(net_income_data),
        "fcf": billion_twd_series_to_yi_twd(fcf_data),
        "grossMargin": [v for v in gross_margin_data],
        "opMargin": [v for v in op_margin_data],
        "netMargin": [v for v in net_margin_data],
        "roe": [v for v in roe_data],
        "priceHistory": price_history,
        "moatLabels": moat_labels,
        "moatValues": moat_values,
        "priceTargets": price_targets,
        "peRiver": pe_river,
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
    agent_model_labels = build_agent_model_labels()
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    
    current_price_numeric = data.get("current_price", 0) if isinstance(data.get("current_price", 0), (int, float)) else 0
    template_context = dict(locals())
    return render_report_template("report.html.j2", template_context)

def generate_markdown_report(context: AnalysisContext) -> str:
    """生成 Markdown 格式報告"""
    data = context.get("data", {})
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = context.get("ticker", "N/A")
    name = context.get("company_name", ticker)
    fetch_date = data.get("fetch_date", datetime.now().strftime("%Y年%m月%d日"))
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    report_title = pipeline_def["report_title"]
    
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
    tear_sheet_summary = build_tear_sheet_summary(context)
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    agent_sections = build_agent_sections(context, html=False)
    agent_markdown = "\n\n---\n\n".join(
        f"## {section['display_num']}. {section['title']} (Agent {section['agent_num']})\n{section['body']}"
        for section in agent_sections
    )

    md = f"""# {ticker} {name} - {report_title}
📅 分析日期：{fetch_date}

{audit_markdown + chr(10) + chr(10) if audit_markdown else ""}
## 一頁式摘要
{tear_sheet_summary}

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

{agent_markdown}

---

## 📚 參考資料來源與數據誤差訴明

| 資料來源 | 涉及內容 | 註記 |
|---|---|---|
| **Yahoo Finance (yfinance)** | 市場即時資料、年度財務報表、估值指標、負債結構、分析師評等 | pypi.org/project/yfinance |
| **FinMind Open Data** | 台股每月營收、新聞、三大法人買賣超、PER/PBR 河流圖資料 | finmindtrade.com |
| **Google Custom Search / FMP / Yahoo News** | 近期新聞、法說會、供應鏈與市場催化劑 | 依環境變數與可用 API 自動 fallback |
| **Google Gemini AI** | AI 分析師論述（{model_route_summary}） | Pipeline {pipeline_def["id"].upper()}：{pipeline_def["label"]} |
| **公開資訊觀測站 (MOPS/TWSE)** | 台灣證券交易所官方財務公邖 | 可作為數據核對基準 |

> ⚠️ **數據誤差訴明**：Yahoo Finance 所提供的台股歷史財務報表有時存在年份缺失或延遲問題；`Debt to Equity` 指標已轉換為百分比形式；歷史營收、淨利、現金流等數據單位為 **Billion TWD (10億台幣)**。建議將本報告筆記的財務數據与公開資訊觀測站進行交叉比對。

> ⚠️ **免責聲明**：本報告由 AI 系統自動生成，僅供投資研究參考，不構成任何投資建議。股票投資有風險，投資前請諮詢專業財務顧問並自行評估風險承受能力。
"""
    return md
