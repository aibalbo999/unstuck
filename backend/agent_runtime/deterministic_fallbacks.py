"""Deterministic final-audit repair fallbacks and audit trail."""

from __future__ import annotations

import math

from analysis_types import AnalysisContext, StockData
from structured_output_parser import parse_structured_data
from structured_output_report_text import structured_output_to_report_text

from .deterministic_fallback_audit import (
    clear_agent_blocking_issues as _clear_agent_blocking_issues,
    record_deterministic_fallback as _record_deterministic_fallback,
)
from .deterministic_fallback_evidence import financial_evidence_fallback
from .deterministic_fallback_mode_contracts import position_plan_fallback, short_setup_fallback
from .deterministic_fallback_trade_evidence import attributed_event_swing_fallback


def _deterministic_structured_fallback(
    agent_num: int,
    data: StockData,
    context: AnalysisContext,
    previous_text: str,
) -> tuple[bool, str]:
    """Last-resort structured output so reports do not preserve malformed JSON blobs."""
    structured_outputs = context.setdefault("structured_outputs", {})

    if agent_num in {2, 13, 18}:
        structured = financial_evidence_fallback(agent_num, data, context)
        structured_outputs[agent_num] = structured
        context.setdefault("analyses", {})[agent_num] = structured_output_to_report_text(
            agent_num, structured, ""
        )
        _clear_agent_blocking_issues(context, agent_num)
        return True, (
            "已套用 deterministic 財務品質 fallback"
            if agent_num == 2
            else "已套用 deterministic 財務證據 fallback"
        )

    if agent_num in {4, 14}:
        temp_context = dict(context)
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        targets = {
            key: value for key, value in (parsed.get("price_targets", {}) or {}).items()
            if key in {"熊市情境", "基本情境", "牛市情境"}
            and type(value) in {int, float} and math.isfinite(value) and value > 0
        }
        missing = [key for key in ("熊市情境", "基本情境", "牛市情境") if key not in targets]
        structured = {
            "price_targets": targets,
            "valuation_assessment": {
                "status": "unassessed", "missing_scenarios": missing,
                "origin": "existing_analysis_only", "recalculated": False,
                "reason": "只保留本角色既有文字中可解析的目標；缺項未評估，來源與假設尚須查核，未重算。",
            },
            "valuation_reasoning": {
                "scenario_reasoning": "LLM 修復未回傳完整可解析 JSON；僅整理既有估值文字，未重算，也未使用現價或預設倍率補造目標。",
            },
            "valuation_summary": {
                "uses_market_value_wacc": False,
                "uses_normalized_fcf": False,
                "double_counting_check": "未評估；尚未完成假設查核，不代表已排除重複計價。",
            },
            "analysis_markdown": (
                "## 估值資料限制\n\n"
                "可解析估值資料不足，缺少的情境保留未評估；只整理既有分析可解析的目標，未重算。"
                "本段不能證明既有目標已完成來源、期間或假設驗證；須補齊證據後重新評估。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 三情境估值 fallback"

    if agent_num in {3, 12}:
        from moat_assessment import MOAT_FIELDS

        structured = {
            "reasoning_steps": [
                "可解析護城河證據不足，各項評分保留未評估。",
                "未完成來源及反證查核，缺少證據不代表護城河較弱。",
                "趨勢須有跨期證據；本次不判定擴張、穩定或收縮。",
            ],
            "moat_scores": dict.fromkeys(MOAT_FIELDS),
            "moat_evidence": {
                key: {"finding": "資料不足，未評估", "source_refs": [], "counterevidence": "反證尚未完成查核"}
                for key in MOAT_FIELDS
            },
            "moat_trend": "unassessed",
            "moat_trend_reason": "缺少可驗證的跨期護城河證據，趨勢未評估。",
            "analysis_markdown": "## 護城河資料限制\n\n可解析證據不足，各維度與整體分數均未評估；沒有新增評分、來源或已查核結論。",
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 護城河 fallback"

    if agent_num == 24:
        structured = attributed_event_swing_fallback(data, context)
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 極短線風控 fallback"

    if agent_num == 19:
        unavailable_target = "資料不足，需重新產生可驗證目標"

        structured = {
            "reasoning_steps": [
                "可解析泡沫狙擊 JSON 不足，採用保守逆勢風險框架。",
                "在資料不足下維持避免立場，目前觀望，不建立新部位。",
                "等待可驗證的財測、估值與法人資料後重新評估，不將觀察條件視為交易指令。",
            ],
            "recommendation": {
                "建議": "避免",
                "短期目標（3個月）": unavailable_target,
                "中期目標（6個月）": unavailable_target,
                "長期目標（12個月）": unavailable_target,
                "長期潛力（5年）": unavailable_target,
                "信心指數": "5/10",
            },
            "scenario_triggers": [
                {
                    "trigger_condition": "後續財測下修、毛利率壓縮或估值均值回歸開始發生",
                    "action": "重新評估空方假設，目前仍觀望，不開倉",
                    "direction": "bearish_downgrade",
                },
                {
                    "trigger_condition": "股價放量突破前高且基本面證據同步改善",
                    "action": "重新檢驗泡沫假設，目前不建立空方部位",
                    "direction": "neutral_review",
                },
            ],
            "short_setup": short_setup_fallback(),
            "analysis_markdown": (
                "## 保守泡沫狙擊摘要\n\n"
                "Agent 19 未能提供完整可解析結構化輸出，系統改用保守 fallback。"
                "本段不新增未驗證的借券、空單或內線資料；目前觀望，不建立新部位。\n\n"
                "## 做空觸發條件（Catalyst for crash）\n"
                "- 等待財測、毛利率與估值資料後重新評估，條件出現也不代表可直接開倉。\n"
                "- 法人資料、借券條件與交易風險尚需驗證，維持觀望。\n\n"
                "## 防軋空停損點（Stop-loss level）\n"
                "- 目前沒有可驗證的放空方案，回補停損不適用；不推定已持有空方部位。\n"
                "- 若後續財報或財測顯示基本面改善，須重新評估目前估值及原先的空方假設。"
            ),
        }
        structured_outputs[agent_num] = structured
        context["analyses"][agent_num] = structured_output_to_report_text(agent_num, structured, "")
        _clear_agent_blocking_issues(context, agent_num)
        return True, "已套用 deterministic 泡沫狙擊 fallback"

    if agent_num in {7, 16}:
        from recommendation_labels import CANONICAL_RECOMMENDATIONS, normalize_recommendation_label

        temp_context = dict(context)
        temp_context["pipeline_id"] = "v1" if agent_num == 7 else "v2"
        temp_context["structured_outputs"] = {}
        temp_context["analyses"] = {agent_num: previous_text or context.get("analyses", {}).get(agent_num, "")}
        temp_context["agent_sequence"] = [agent_num]
        parsed = parse_structured_data(temp_context)
        previous = structured_outputs.get(agent_num, structured_outputs.get(str(agent_num), {})) or {}
        previous_recommendation = previous.get("recommendation") if isinstance(previous, dict) else None
        candidates = (previous_recommendation, parsed.get("recommendation"))
        label = next((normalized for candidate in candidates if isinstance(candidate, dict)
                      if (normalized := normalize_recommendation_label(candidate.get("建議", candidate.get("recommendation"))))
                      in CANONICAL_RECOMMENDATIONS), "避免")
        unavailable_target = "N/A（未評估；缺少同期間可驗證目標）"
        recommendation = {
            "建議": label,
            "短期目標（3個月）": unavailable_target,
            "中期目標（6個月）": unavailable_target,
            "長期目標（12個月）": unavailable_target,
            "長期潛力（5年）": unavailable_target,
            "信心指數": "N/A（本次未重新評估）",
        }
        structured = {
            "reasoning_steps": [
                "原始結構化輸出不足，本次僅保留已有的研究分類，沒有新增估值結論。",
                "缺少可驗證同期間目標，目標價與信心均保留未評估，不從現價推算。",
                "目前不新增部位；等待可驗證來源與完整分析後重新評估。",
            ],
            "recommendation": recommendation,
            "analysis_markdown": (
                "## 研究資料限制\n\n"
                "可解析決策資料不足；若已有研究分類則保留，沒有可辨識分類時採避免、不新增部位。"
                "研究分類不代表個人持倉指令。缺少同期間可驗證目標與完整假設對照，尚未重算，亦未重新評估信心。"
                "等待可驗證財報、估值與風險資料後重新評估；不推定使用者實際持倉。"
            ),
        }
        if agent_num == 7:
            from research_assumption_contract import TOPICS, assess_reconciliation

            structured["assumption_reconciliation"] = {
                "status": "unassessed", "pending_recalculation": False,
                "checks": [{
                    "topic": topic, "status": "unassessed", "valuation_quote": "", "growth_quote": "",
                    "rationale": "本次 fallback 未完成此項假設對照；須取得可驗證的估值及成長分析後重新評估。",
                } for topic in TOPICS],
            }
            structured["assumption_reconciliation_assessment"] = assess_reconciliation(
                structured["assumption_reconciliation"], context)
        if agent_num == 16:
            from position_sizing_runtime import assess_position_plan

            structured["position_plan"] = position_plan_fallback(context)
            structured["position_sizing_assessment"] = assess_position_plan(
                structured["position_plan"], context, recommendation, structured["analysis_markdown"])
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
