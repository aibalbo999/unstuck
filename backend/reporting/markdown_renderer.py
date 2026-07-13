"""Split report rendering helper."""

from __future__ import annotations

from datetime import datetime

from analysis_types import AnalysisContext
from company_display import company_display_name
from config import format_model_routes
from investment_thesis import build_investment_thesis, investment_thesis_markdown
from mapping_fields import safe_mapping_dict, safe_text
from pipeline_modes import get_pipeline_definition
from recommendation_labels import normalize_recommendation_label

from .audit_trust import build_audit_markdown, build_data_trust_markdown, build_source_audit_markdown
from .execution_summary import build_execution_summary_markdown
from .mode_templates import (
    build_mode_template_markdown,
    decision_markdown_heading,
    get_report_template_profile,
    summary_markdown_heading,
)
from .reading_notice import build_report_reading_notice_markdown
from .sections import build_agent_sections, build_tear_sheet_summary


def _display_text(value, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    if not text:
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _markdown_cell(value, default: str = "N/A") -> str:
    return _display_text(value, default).replace("|", "/").replace("\n", " ")


def generate_markdown_report(context: AnalysisContext) -> str:
    """生成 Markdown 格式報告"""
    data = safe_mapping_dict(context.get("data", {})) or {}
    analyses = context.get("analyses", {})
    parsed = safe_mapping_dict(context.get("parsed", {})) or {}
    
    ticker = _display_text(context.get("ticker", "N/A"))
    name = _display_text(company_display_name(data, context.get("company_name", ticker)))
    fetch_date = _display_text(data.get("fetch_date"), datetime.now().strftime("%Y年%m月%d日"))
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    mode_template = get_report_template_profile(pipeline_def["id"])
    report_title = pipeline_def["report_title"]
    
    price_targets = safe_mapping_dict(parsed.get("price_targets", {})) or {}
    recommendation = safe_mapping_dict(parsed.get("recommendation", {})) or {}
    
    def get_rec_val(rec_dict, target_sub, default="N/A"):
        for k, v in (safe_mapping_dict(rec_dict) or {}).items():
            if target_sub in safe_text(k):
                return _display_text(v, default)
        return default
        
    rec_text = normalize_recommendation_label(get_rec_val(recommendation, "建議", "持有"))

    target_3m = get_rec_val(recommendation, "3個月", "N/A")
    target_6m = get_rec_val(recommendation, "6個月", "N/A")
    target_12m = get_rec_val(recommendation, "12個月", "N/A")
    confidence = get_rec_val(recommendation, "信心", "N/A")
    trade_setup = safe_mapping_dict(parsed.get("trade_setup", {})) or {}
    decision_heading = decision_markdown_heading(mode_template)
    if pipeline_def["id"] == "v4":
        decision_markdown = f"""{decision_heading}
- **交易方向:** {_display_text(trade_setup.get("trade_direction"), "Neutral")}
- **進場區間:** {_display_text(trade_setup.get("entry_zone"))}
- **1-2週目標:** {_display_text(trade_setup.get("target_price"))}
- **嚴格停損:** {_display_text(trade_setup.get("stop_loss"))}
- **核心催化劑:** {_display_text(trade_setup.get("core_catalyst"))}
- **短期波動風險:** {_display_text(trade_setup.get("risk_level"), "High")}"""
    else:
        decision_markdown = f"""{decision_heading}
- **綜合建議:** {rec_text}
- **3個月目標:** {target_3m}
- **6個月目標:** {target_6m}
- **12個月目標:** {target_12m}
- **信心指數:** {confidence}"""
    audit_markdown = build_audit_markdown(context)
    report_reading_notice_markdown = build_report_reading_notice_markdown(context)
    data_trust_markdown = build_data_trust_markdown(data, context)
    model_route_summary = format_model_routes(pipeline_id=pipeline_def["id"])
    model_route_reference_cell = _markdown_cell(f"AI 分析師論述（{model_route_summary}）")
    pipeline_reference_cell = _markdown_cell(f"Pipeline {pipeline_def['id'].upper()}：{pipeline_def['label']}")
    execution_summary_markdown = build_execution_summary_markdown(context, model_routes=model_route_summary)
    mode_template_markdown = build_mode_template_markdown(mode_template)
    source_audit_markdown = build_source_audit_markdown(data, context)
    thesis_payload = safe_mapping_dict(context.get("investment_thesis"))
    if not thesis_payload:
        thesis_payload = build_investment_thesis(context)
    thesis_markdown = investment_thesis_markdown(thesis_payload)
    tear_sheet_summary = build_tear_sheet_summary(context)
    agent_sections = build_agent_sections(context, html=False)
    agent_markdown = "\n\n---\n\n".join(
        f"## {section['display_num']}. {section['title']} (Agent {section['agent_num']})\n{section['body']}"
        for section in agent_sections
    )

    md = f"""# {ticker} {name} - {report_title}
📅 分析日期：{fetch_date}

{report_reading_notice_markdown}

{audit_markdown + chr(10) + chr(10) if audit_markdown else ""}
{data_trust_markdown}

{execution_summary_markdown}

{mode_template_markdown}

{summary_markdown_heading(mode_template)}
{tear_sheet_summary}

## 📊 關鍵指標
- **股價:** {_display_text(data.get("current_price_fmt"))}
- **市值:** {_display_text(data.get("market_cap_fmt"))}
- **P/E:** {_display_text(data.get("pe_ratio"))}
- **P/B:** {_display_text(data.get("pb_ratio"))}
- **毛利率:** {_display_text(data.get("gross_margin"))}
- **ROE:** {_display_text(data.get("roe"))}
- **殖利率:** {_display_text(data.get("dividend_yield"))}
- **Beta:** {_display_text(data.get("beta"))}

---

{decision_markdown}

---

{thesis_markdown + chr(10) + chr(10) + "---" + chr(10) + chr(10) if thesis_markdown else ""}

{agent_markdown}

---

{source_audit_markdown}

---

## 📚 參考資料來源與數據誤差訴明

| 資料來源 | 涉及內容 | 註記 |
|---|---|---|
| **Yahoo Finance (yfinance)** | 市場即時資料、年度財務報表、估值指標、負債結構、分析師評等 | pypi.org/project/yfinance |
| **FinMind Open Data** | 台股每月營收、新聞、三大法人買賣超、PER/PBR 河流圖資料 | finmindtrade.com |
| **MOPS/TWSE / Free News / FMP / Yahoo News** | 法說會資料、近期新聞、供應鏈與市場催化劑 | 依環境變數與可用 API 自動 fallback |
| **Google Gemini AI** | {model_route_reference_cell} | {pipeline_reference_cell} |
| **公開資訊觀測站 (MOPS/TWSE)** | 台灣證券交易所官方財務公邖 | 可作為數據核對基準 |

> ⚠️ **數據誤差訴明**：Yahoo Finance 所提供的台股歷史財務報表有時存在年份缺失或延遲問題；`Debt to Equity` 指標已轉換為百分比形式；歷史營收、淨利、現金流等數據單位為 **Billion TWD (10億台幣)**。建議將本報告筆記的財務數據与公開資訊觀測站進行交叉比對。

> ⚠️ **免責聲明**：本報告由 AI 系統自動生成，僅供投資研究參考，不構成任何投資建議。股票投資有風險，投資前請諮詢專業財務顧問並自行評估風險承受能力。
"""
    return md
