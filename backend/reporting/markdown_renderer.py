"""Split report rendering helper."""

from __future__ import annotations

from datetime import datetime

from analysis_types import AnalysisContext
from company_display import company_display_name
from config import format_model_routes
from investment_thesis import investment_thesis_markdown
from pipeline_modes import get_pipeline_definition
from recommendation_labels import normalize_recommendation_label

from .audit_trust import build_audit_markdown, build_data_trust_markdown, build_source_audit_markdown
from .sections import build_agent_sections, build_tear_sheet_summary

def generate_markdown_report(context: AnalysisContext) -> str:
    """生成 Markdown 格式報告"""
    data = context.get("data", {})
    analyses = context.get("analyses", {})
    parsed = context.get("parsed", {})
    
    ticker = context.get("ticker", "N/A")
    name = company_display_name(data, context.get("company_name", ticker))
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
        
    rec_text = normalize_recommendation_label(get_rec_val(recommendation, "建議", "持有"))

    target_3m = get_rec_val(recommendation, "3個月", "N/A")
    target_6m = get_rec_val(recommendation, "6個月", "N/A")
    target_12m = get_rec_val(recommendation, "12個月", "N/A")
    confidence = get_rec_val(recommendation, "信心", "N/A")
    trade_setup = parsed.get("trade_setup", {}) or {}
    if pipeline_def["id"] == "v4" and trade_setup:
        decision_markdown = f"""## 極短線交易計畫
- **交易方向:** {trade_setup.get("trade_direction", "Neutral")}
- **進場區間:** {trade_setup.get("entry_zone", "N/A")}
- **1-2週目標:** {trade_setup.get("target_price", "N/A")}
- **嚴格停損:** {trade_setup.get("stop_loss", "N/A")}
- **核心催化劑:** {trade_setup.get("core_catalyst", "N/A")}
- **短期波動風險:** {trade_setup.get("risk_level", "High")}"""
    else:
        decision_markdown = f"""## 🎯 最終投資建議
- **綜合建議:** {rec_text}
- **3個月目標:** {target_3m}
- **6個月目標:** {target_6m}
- **12個月目標:** {target_12m}
- **信心指數:** {confidence}"""
    audit_markdown = build_audit_markdown(context)
    data_trust_markdown = build_data_trust_markdown(data, context)
    source_audit_markdown = build_source_audit_markdown(data, context)
    thesis_markdown = investment_thesis_markdown(context.get("investment_thesis") or {})
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
{data_trust_markdown}

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
| **MOPS/TWSE / Google Custom Search / FMP / Yahoo News** | 法說會資料、近期新聞、供應鏈與市場催化劑 | 依環境變數與可用 API 自動 fallback |
| **Google Gemini AI** | AI 分析師論述（{model_route_summary}） | Pipeline {pipeline_def["id"].upper()}：{pipeline_def["label"]} |
| **公開資訊觀測站 (MOPS/TWSE)** | 台灣證券交易所官方財務公邖 | 可作為數據核對基準 |

> ⚠️ **數據誤差訴明**：Yahoo Finance 所提供的台股歷史財務報表有時存在年份缺失或延遲問題；`Debt to Equity` 指標已轉換為百分比形式；歷史營收、淨利、現金流等數據單位為 **Billion TWD (10億台幣)**。建議將本報告筆記的財務數據与公開資訊觀測站進行交叉比對。

> ⚠️ **免責聲明**：本報告由 AI 系統自動生成，僅供投資研究參考，不構成任何投資建議。股票投資有風險，投資前請諮詢專業財務顧問並自行評估風險承受能力。
"""
    return md
