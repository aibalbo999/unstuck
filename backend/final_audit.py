"""Deterministic cross-agent report audit rules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from analysis_types import AnalysisContext, AuditResult
from agent_catalog import AGENT_NAMES
from confidence_calibration import build_confidence_calibration
from final_audit_context_coverage import missing_final_context_labels
from final_audit_dcf import dcf_conflict_warnings
from final_audit_sections import append_final_audit_section
from final_audit_v3 import v3_recommendation_contract_issues
from final_audit_v4 import v4_trade_setup_contract_issues
from forward_consistency_checker import run_forward_consistency_checks
from pipeline_modes import get_pipeline_definition, get_structured_agent_num
from runtime_events import emit_log
from validators import (
    _extract_price_numbers,
    strip_generated_audit_sections,
    validate_analysis_output,
    validate_company_identity,
    validate_prompt_leakage,
)


def _is_agent_execution_failure(text: str) -> bool:
    return bool(text and text.startswith("[Agent ") and "執行失敗" in text)


def _recommendation_value(recommendation: dict, key_fragment: str) -> str:
    for key, value in (recommendation or {}).items():
        if key_fragment in str(key):
            return str(value)
    return ""


def _extract_first_price(value: str) -> Optional[float]:
    try:
        prices = _extract_price_numbers(value or "")
    except Exception:
        return None
    return prices[0] if prices else None


def _add_unique_issue(items: list[str], issue: str):
    if issue and issue not in items:
        items.append(issue)


def run_final_report_audit(context: AnalysisContext, append_section: bool = True) -> AuditResult:
    """
    Cross-agent final audit before report rendering.

    The audit is deterministic. It classifies serious issues, asks the pipeline
    to repair them in a separate pass, and always leaves enough information for
    the renderer to preserve a report with visible abnormality notes.
    """
    data = context.get("data", {}) or {}
    analyses = context.get("analyses", {}) or {}
    parsed = context.get("parsed", {}) or {}
    structured_outputs = context.get("structured_outputs", {}) or {}
    pipeline_def = get_pipeline_definition(context.get("pipeline_id", "v1"))
    required_agents = tuple(context.get("agent_sequence") or pipeline_def["agents"])
    moat_agent = get_structured_agent_num("moat", context)
    valuation_agent = get_structured_agent_num("valuation", context)
    recommendation_agent = get_structured_agent_num("recommendation", context)
    trade_setup_agent = get_structured_agent_num("trade_setup", context)

    critical: list[str] = []
    warnings: list[str] = []
    corrections: list[str] = []
    repair_agent_issues: dict[int, list[str]] = {}

    def add_agent_repair_issue(agent_num: int, issue: str):
        repair_agent_issues.setdefault(agent_num, [])
        _add_unique_issue(repair_agent_issues[agent_num], issue)

    completed_agents = set(analyses.keys())
    missing_agents = [num for num in required_agents if num not in completed_agents or not str(analyses.get(num, "")).strip()]
    if missing_agents:
        _add_unique_issue(critical, f"缺少 Agent 輸出：{', '.join(str(num) for num in missing_agents)}")
        for agent_num in missing_agents:
            add_agent_repair_issue(agent_num, "缺少 Agent 輸出，請補跑本 Agent 並產生完整正式段落。")

    for agent_num, text in analyses.items():
        agent_name = AGENT_NAMES.get(agent_num, f"Agent {agent_num}")
        audited_text = strip_generated_audit_sections(str(text))
        if _is_agent_execution_failure(str(text)):
            _add_unique_issue(critical, f"{agent_name} 輸出為失敗訊息，不能產生正式報告。")
            add_agent_repair_issue(agent_num, "前次輸出為失敗訊息，請重新執行本 Agent。")
        if "分析進行中" in audited_text:
            _add_unique_issue(critical, f"{agent_name} 仍含佔位文字「分析進行中」。")
            add_agent_repair_issue(agent_num, "前次輸出仍是佔位文字，請補齊正式分析。")

        for issue in validate_prompt_leakage(audited_text):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)
        for issue in validate_company_identity(audited_text, data):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)

        for issue in validate_analysis_output(agent_num, audited_text, data):
            _add_unique_issue(critical, f"{agent_name}: {issue}")
            add_agent_repair_issue(agent_num, issue)

    if pipeline_def["id"] == "v3":
        for issue in v3_recommendation_contract_issues(
            analyses, structured_outputs, recommendation_agent, completed_agents
        ):
            _add_unique_issue(critical, f"Agent {recommendation_agent} {issue}")
            add_agent_repair_issue(recommendation_agent, issue)

    for agent_num, label in [
        (moat_agent, "護城河評分"),
        (valuation_agent, "三情境目標價"),
        (recommendation_agent, "最終投資建議"),
        (trade_setup_agent, "極短線交易計畫"),
    ]:
        if agent_num is None:
            continue
        if agent_num in completed_agents and agent_num not in structured_outputs:
            _add_unique_issue(critical, f"Agent {agent_num} {label} 未提供可解析 JSON 結構化輸出。")
            add_agent_repair_issue(agent_num, f"{label} 未提供可解析 JSON 結構化輸出。")

    price_targets = parsed.get("price_targets", {}) or {}
    required_targets = ["熊市情境", "基本情境", "牛市情境"]
    missing_targets = [key for key in required_targets if key not in price_targets] if valuation_agent is not None else []
    if valuation_agent is not None and missing_targets:
        _add_unique_issue(critical, f"Agent {valuation_agent} 缺少目標價情境：{', '.join(missing_targets)}")
        add_agent_repair_issue(valuation_agent, f"缺少目標價情境：{', '.join(missing_targets)}")

    current_price = data.get("current_price")
    numeric_targets = {key: value for key, value in price_targets.items() if isinstance(value, (int, float))}
    if isinstance(current_price, (int, float)) and current_price > 100:
        tiny_targets = [f"{key}=NT${value:g}" for key, value in numeric_targets.items() if value < current_price * 0.05]
        if tiny_targets:
            _add_unique_issue(critical, f"目標價疑似單位縮小錯誤：{', '.join(tiny_targets)}")
            add_agent_repair_issue(valuation_agent, f"目標價疑似單位縮小錯誤：{', '.join(tiny_targets)}")

    if all(key in numeric_targets for key in required_targets):
        bear = numeric_targets["熊市情境"]
        base = numeric_targets["基本情境"]
        bull = numeric_targets["牛市情境"]
        if not (bear <= base <= bull):
            _add_unique_issue(critical, f"三情境目標價順序不合理：熊市 {bear:g}、基本 {base:g}、牛市 {bull:g}。")
            add_agent_repair_issue(valuation_agent, f"三情境目標價順序不合理：熊市 {bear:g}、基本 {base:g}、牛市 {bull:g}。")

    moat_scores = parsed.get("moat_scores", {}) or {}
    required_moat = {"品牌影響力", "網路效應", "轉換成本", "成本優勢", "專利技術", "整體護城河"}
    if moat_agent is not None and not required_moat.issubset(moat_scores.keys()):
        missing = sorted(required_moat - set(moat_scores.keys()))
        _add_unique_issue(critical, f"Agent {moat_agent} 護城河評分缺少欄位：{', '.join(missing)}")
        add_agent_repair_issue(moat_agent, f"護城河評分缺少欄位：{', '.join(missing)}")

    recommendation = parsed.get("recommendation", {}) or {}
    trade_setup = parsed.get("trade_setup", {}) or {}
    if trade_setup_agent is not None:
        for issue in v4_trade_setup_contract_issues(trade_setup):
            _add_unique_issue(critical, f"Agent {trade_setup_agent} {issue}")
            add_agent_repair_issue(trade_setup_agent, issue)
    elif recommendation_agent is None:
        _add_unique_issue(critical, "此 pipeline 未宣告最終投資建議 Agent。")
    elif not recommendation:
        _add_unique_issue(critical, f"Agent {recommendation_agent} 缺少最終投資建議結構化資料。")
        add_agent_repair_issue(recommendation_agent, "缺少最終投資建議結構化資料。")
    else:
        rec_text = _recommendation_value(recommendation, "建議")
        allowed_recommendations = ["強烈放空", "避免", "持有", "買進"] if pipeline_def["id"] == "v3" else ["買入", "持有", "避免"]
        if not any(word in rec_text for word in allowed_recommendations):
            _add_unique_issue(critical, f"Agent {recommendation_agent} 投資建議不在允許值內：{rec_text or '空白'}")
            add_agent_repair_issue(recommendation_agent, f"投資建議不在允許值內：{rec_text or '空白'}")
        for label in ["3個月", "6個月", "12個月", "信心"]:
            if not _recommendation_value(recommendation, label):
                _add_unique_issue(critical, f"Agent {recommendation_agent} 缺少 {label} 欄位。")
                add_agent_repair_issue(recommendation_agent, f"缺少 {label} 欄位。")

        missing_context_labels = missing_final_context_labels(data, str(analyses.get(recommendation_agent, "")))
        if missing_context_labels:
            _add_unique_issue(warnings, f"Agent {recommendation_agent} 最終建議未說明可用的{'、'.join(missing_context_labels)}是否影響結論。")

        data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
        confidence_calibration = build_confidence_calibration(recommendation, data_trust)
        if confidence_calibration.get("status") == "needs_downgrade":
            data_trust_status = confidence_calibration.get("data_trust_status", "unknown")
            raw_confidence = confidence_calibration.get("raw_confidence", "N/A")
            cap = confidence_calibration.get("max_recommended_confidence")
            _add_unique_issue(warnings, f"Agent {recommendation_agent} 在 data_trust={data_trust_status} 時給出高信心（{raw_confidence}），建議信心上限 {cap}/10，報告需明確揭露資料限制。")

        target_12m = _extract_first_price(_recommendation_value(recommendation, "12個月"))
        if valuation_agent is not None and target_12m is not None and all(key in numeric_targets for key in required_targets):
            bear = numeric_targets["熊市情境"]
            bull = numeric_targets["牛市情境"]
            lower = bear * 0.7
            upper = bull * 1.3
            if not (lower <= target_12m <= upper):
                _add_unique_issue(
                    warnings,
                    f"Agent {recommendation_agent} 的 12 個月目標價 NT${target_12m:g} 與 Agent {valuation_agent} 三情境區間差距較大，需人工確認。"
                )

        # Forward consistency checks
        target_3m = _extract_first_price(_recommendation_value(recommendation, "3個月"))
        target_6m = _extract_first_price(_recommendation_value(recommendation, "6個月"))
        rec_text = _recommendation_value(recommendation, "建議")
        
        forward_checks = run_forward_consistency_checks(
            recommendation=rec_text,
            current_price=current_price,
            target_3m=target_3m,
            target_6m=target_6m,
            target_12m=target_12m,
        )
        for issue in forward_checks.get("critical", []):
            _add_unique_issue(critical, issue)
            add_agent_repair_issue(recommendation_agent, issue)
        for issue in forward_checks.get("warnings", []):
            _add_unique_issue(warnings, issue)

    confidence_calibration = build_confidence_calibration(recommendation, data.get("data_trust", {}))
    data_notes = data.get("data_source_notes", []) or []
    if any("口徑互斥" in note for note in data_notes):
        _add_unique_issue(corrections, "資料源出現淨利/淨利率口徑互斥時，報告已採用 EPS/P/E 自洽的校準口徑。")
    if any("revenueGrowth" in note for note in data_notes):
        _add_unique_issue(corrections, "Yahoo revenueGrowth 已降級為近期/季度口徑，不得直接當年度或 TTM 年增率。")

    for warning in context.get("structured_quality_warnings", []) or []:
        _add_unique_issue(warnings, str(warning))

    for warning in dcf_conflict_warnings(analyses, data):
        _add_unique_issue(warnings, warning)

    price_history = data.get("price_history", {}) or {}
    if isinstance(price_history, dict):
        future_dates = []
        today = date.today()
        for raw_date in price_history.keys():
            try:
                parsed_date = datetime.fromisoformat(str(raw_date)[:10]).date()
            except ValueError:
                continue
            if parsed_date > today:
                future_dates.append(str(raw_date)[:10])
        if future_dates:
            _add_unique_issue(
                corrections,
                f"歷史股價含未來日期，報告圖表會忽略：{', '.join(sorted(future_dates)[:5])}。"
            )

    status = "needs_attention" if critical else "passed"
    audit = {
        "status": status,
        "critical": critical,
        "warnings": warnings,
        "corrections": corrections,
        "repair_agent_issues": repair_agent_issues,
        "confidence_calibration": confidence_calibration,
        "report_preserved": True,
    }

    if append_section and critical:
        append_final_audit_section(context, audit)

    if critical:
        if append_section:
            emit_log("  ⚠️  最終跨 Agent 稽核仍有異常；報告會保留，並在報告內標示異常提醒。")
        else:
            emit_log("  ⚠️  最終跨 Agent 稽核發現異常，準備嘗試 AI 自動修復。")
        for issue in critical[:8]:
            emit_log(f"     - {issue}")
    elif warnings or corrections:
        emit_log("  ✅ 最終跨 Agent 稽核通過，已附加非阻斷稽核註記。")
    else:
        emit_log("  ✅ 最終跨 Agent 稽核通過。")

    return audit
