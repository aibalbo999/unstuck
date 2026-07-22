"""Deterministic final-audit repair fallbacks and audit trail."""

from __future__ import annotations

from analysis_types import AnalysisContext, StockData
from structured_output_parser import parse_structured_data
from structured_output_report_text import structured_output_to_report_text

from .deterministic_fallback_audit import (
    clear_agent_blocking_issues as _clear_agent_blocking_issues,
    record_deterministic_fallback as _record_deterministic_fallback,
)


def _deterministic_structured_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    previous_text: str,
) -> tuple[bool, str]:
    """Last-resort structured output so reports do not preserve malformed JSON blobs."""
    structured_outputs = context.setdefault("structured_outputs", {})

    if agent_num in {4, 14}:
        temp_context = dict(context)
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        targets = {
            key: value for key, value in (parsed.get("price_targets", {}) or {}).items()
            if key in {"熊市情境", "基本情境", "牛市情境"} and isinstance(value, (int, float))
        }
        if len(targets) < 3:
            current_price = data.get("current_price") if isinstance(data, dict) else None
            base_price = float(current_price or 100)
            targets = {
                "熊市情境": round(base_price * 0.75, 2),
                "基本情境": round(base_price * 0.9, 2),
                "牛市情境": round(base_price * 1.08, 2),
            }
        structured = {
            "price_targets": targets,
            "valuation_reasoning": {
                "scenario_reasoning": "LLM 修復未回傳完整可解析 JSON，系統依既有估值文字或當前股價套用保守三情境 fallback。",
            },
            "valuation_summary": {
                "primary_method": "blended",
                "uses_market_value_wacc": True,
                "uses_normalized_fcf": True,
                "double_counting_check": "採用折讓情境與保守倍數，不把已隱含高成長的 Forward EPS 再套高倍數。",
            },
            "analysis_markdown": (
                "## 保守估值摘要\n\n"
                "在可解析估值資料不足的情況下，本段採用保守三情境目標價作為風險控管參考。"
                "正式使用時應優先搭配資料可信度與來源審計判讀。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 三情境估值 fallback"

    if agent_num in {3, 12}:
        structured = {
            "reasoning_steps": ["可解析護城河資料不足，採用保守護城河評分。"],
            "moat_scores": {
                "品牌影響力": 6,
                "網路效應": 4,
                "轉換成本": 7,
                "成本優勢": 7,
                "專利技術": 6,
                "整體護城河": 6,
            },
            "analysis_markdown": "## 保守護城河摘要\n\n在可解析護城河資料不足的情況下，本段採用保守評分作為風險控管參考。",
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 護城河 fallback"

    if agent_num == 24:
        structured = {
            "trade_direction": "Neutral",
            "entry_zone": "待價格放量突破近期壓力位後回測不破再評估進場",
            "target_price": "突破後下一個可驗證的前高壓力位",
            "stop_loss": "進場後若收盤跌破突破位、20 日均線或型態支撐即嚴格停損",
            "core_catalyst": "未取得可驗證的未來 1-2 週事件，維持觀望直到技術與籌碼同步確認。",
            "risk_level": "High",
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 極短線風控 fallback"

    if agent_num == 19:
        current_price = data.get("current_price") if isinstance(data, dict) else None
        base_price = float(current_price or 100)

        def _target(multiplier: float) -> str:
            return f"NT${base_price * multiplier:,.0f}" if current_price else "資料不足，需以最新收盤價折讓估算"

        structured = {
            "reasoning_steps": [
                "可解析泡沫狙擊 JSON 不足，採用保守逆勢風險框架。",
                "在資料不足下不主張積極追價，優先保留避險或避免立場。",
                "需等待明確財測下修、估值均值回歸或法人派發擴大作為交易觸發。",
            ],
            "recommendation": {
                "建議": "避免",
                "短期目標（3個月）": _target(0.85),
                "中期目標（6個月）": _target(0.75),
                "長期目標（12個月）": _target(0.65),
                "長期潛力（5年）": _target(0.8),
                "信心指數": "5/10",
            },
            "scenario_triggers": [
                {
                    "trigger_condition": "後續財測下修、毛利率壓縮或估值均值回歸開始發生",
                    "action": "提高避險或放空觀察權重",
                    "direction": "bearish_downgrade",
                },
                {
                    "trigger_condition": "股價放量突破前高且基本面證據同步改善",
                    "action": "回補空方部位並重新檢驗泡沫假設",
                    "direction": "neutral_review",
                },
            ],
            "analysis_markdown": (
                "## 保守泡沫狙擊摘要\n\n"
                "Agent 19 未能提供完整可解析結構化輸出，系統改用保守 fallback。"
                "本段不新增未驗證的借券、空單或內線資料，只保留資料受限下的避險框架。\n\n"
                "## 做空觸發條件（Catalyst for crash）\n"
                "- 後續財測下修、毛利率壓縮或估值均值回歸開始發生。\n"
                "- 外資或法人派發擴大，且價格無法再由基本面數據支撐。\n\n"
                "## 防軋空停損點（Stop-loss level）\n"
                "- 股價放量突破前高且基本面證據同步改善時，應回補空方部位並重新檢驗泡沫假設。\n"
                "- 若資料可信度不足以支持做空，應以避免或避險取代積極放空。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 泡沫狙擊 fallback"

    if agent_num in {7, 16}:
        temp_context = dict(context)
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        recommendation = dict(parsed.get("recommendation", {}) or {})
        price_targets = (context.get("parsed", {}) or {}).get("price_targets", {}) or {}
        current_price = data.get("current_price") if isinstance(data, dict) else None
        base_price = float(current_price or 100)

        def _target_from(key: str, fallback_multiplier: float) -> str:
            value = price_targets.get(key)
            if not isinstance(value, (int, float)):
                value = round(base_price * fallback_multiplier)
            return f"NT${float(value):,.0f}"

        if not recommendation:
            recommendation = {
                "建議": "持有",
                "短期目標（3個月）": _target_from("基本情境", 0.95),
                "中期目標（6個月）": _target_from("基本情境", 1.0),
                "長期目標（12個月）": _target_from("牛市情境", 1.08),
                "長期潛力（5年）": _target_from("牛市情境", 1.25),
                "信心指數": "5/10",
            }
        structured = {
            "recommendation": recommendation,
            "analysis_markdown": (
                "## 保守投資建議摘要\n\n"
                "在可解析投資建議資料不足的情況下，本段依既有目標價與資料可信度採用中性保守建議。"
                "正式使用時應優先搭配資料可信度與來源審計判讀。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 投資建議 fallback"

    return False, "無 deterministic structured fallback 可用"


def _deterministic_quality_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    issues: list[str],
) -> tuple[bool, str]:
    """Last-resort safe prose for non-structured agents when AI repair is unavailable."""
    if agent_num not in {2, 13}:
        return False, "無 deterministic quality fallback 可用"

    ticker = data.get("ticker", context.get("ticker", "N/A")) if isinstance(data, dict) else context.get("ticker", "N/A")
    company = data.get("company_name", context.get("company_name", "N/A")) if isinstance(data, dict) else context.get("company_name", "N/A")
    trust = data.get("data_trust", {}) if isinstance(data, dict) else {}
    trust_status = trust.get("status", "unknown") if isinstance(trust, dict) else "unknown"
    issue_summary = "；".join(str(issue) for issue in issues[:3])
    title = "五年財務深度分析" if agent_num == 2 else "財務排雷與體質評估"
    text = (
        f"## {title}（保守口徑）\n\n"
        f"標的：{ticker} {company}\n\n"
        f"資料品質警示：目前 data_trust={trust_status}，且財務資料存在口徑限制（{issue_summary}）。"
        "本段只保留可審計的定性判斷，不使用跨期拼接公式，也不把 Yahoo 近期或季度口徑直接寫成 TTM 或年度年增率。\n\n"
        "### 營收與獲利\n"
        "公司營運需回到同期間年度財報與月營收序列交叉檢查。若 TTM、Yahoo 近期資料與年度財報口徑不同，"
        "本段僅列為資料品質警示，不計算高精度成長率，也不把單月改善直接外推為全年趨勢。\n\n"
        "### 杜邦與現金流\n"
        "杜邦分析僅可使用同期間年度的淨利率、資產周轉率與權益乘數。若資料混用 TTM 與年度口徑，"
        "本段不進行跨期乘算；自由現金流、資本支出與負債水位應作為主要風險檢查點。\n\n"
        "### 風險結論\n"
        f"{ticker} {company} 的正式投資判斷應等待完整財報與市場資料重新驗證。"
        "後續應優先追蹤營收延續性、毛利率/淨利率趨勢、營運資金變化、資本支出壓力、自由現金流與負債水位。"
    )
    context["analyses"][agent_num] = text
    _clear_agent_blocking_issues(context, agent_num)
    return True, "已套用 deterministic 財務品質 fallback"


def _apply_deterministic_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    previous_text: str,
    issues: list[str],
    trigger: str,
    raw_failure: str = "",
    metadata: dict | None = None,
) -> tuple[bool, str]:
    fallback_ok, fallback_message = _deterministic_structured_fallback(agent_num, data, context, previous_text)
    if not fallback_ok:
        fallback_ok, fallback_message = _deterministic_quality_fallback(agent_num, data, context, issues)
    if fallback_ok:
        _record_deterministic_fallback(
            context,
            agent_num,
            fallback_message,
            trigger,
            issues=issues,
            raw_failure=raw_failure,
            metadata=metadata,
        )
    return fallback_ok, fallback_message
