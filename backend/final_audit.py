"""Deterministic cross-agent report audit rules."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from analysis_types import AnalysisContext, AuditResult
from agent_catalog import AGENT_NAMES
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


def _extract_confidence_score(value: str) -> Optional[float]:
    import re

    match = re.search(r"(\d+(?:\.\d+)?)", str(value or ""))
    if not match:
        return None
    score = float(match.group(1))
    if score <= 1:
        return score * 10
    return score


def _add_unique_issue(items: list[str], issue: str):
    if issue and issue not in items:
        items.append(issue)


def _append_final_audit_section(context: AnalysisContext, audit: AuditResult):
    """Expose non-blocking final audit notes in the final decision section."""
    if context.get("_final_audit_appended"):
        return
    final_agent = get_structured_agent_num("recommendation", context) or 7
    if final_agent not in context.get("analyses", {}):
        return

    critical = audit.get("critical", [])
    warnings = audit.get("warnings", [])
    corrections = audit.get("corrections", [])
    repair_log = context.get("audit_repair_log", [])
    if not critical and not warnings and not corrections and not repair_log:
        return

    lines = ["## 系統最終稽核"]
    if critical:
        lines.append("### 仍需注意的異常")
        lines.extend(f"- {item}" for item in critical[:8])
    if repair_log:
        lines.append("### AI 修復紀錄")
        lines.extend(f"- {item}" for item in repair_log[:8])
    if corrections:
        lines.append("### 已套用校正")
        lines.extend(f"- {item}" for item in corrections[:8])
    if warnings:
        lines.append("### 非阻斷提醒")
        lines.extend(f"- {item}" for item in warnings[:8])
    context["analyses"][final_agent] = f"{context['analyses'][final_agent].rstrip()}\n\n" + "\n".join(lines)
    context["_final_audit_appended"] = True


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
    moat_agent = get_structured_agent_num("moat", context) or 3
    valuation_agent = get_structured_agent_num("valuation", context) or 4
    recommendation_agent = get_structured_agent_num("recommendation", context) or 7

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

    for agent_num, label in [(moat_agent, "護城河評分"), (valuation_agent, "三情境目標價"), (recommendation_agent, "最終投資建議")]:
        if agent_num in completed_agents and agent_num not in structured_outputs:
            _add_unique_issue(critical, f"Agent {agent_num} {label} 未提供可解析 JSON 結構化輸出。")
            add_agent_repair_issue(agent_num, f"{label} 未提供可解析 JSON 結構化輸出。")

    price_targets = parsed.get("price_targets", {}) or {}
    required_targets = ["熊市情境", "基本情境", "牛市情境"]
    missing_targets = [key for key in required_targets if key not in price_targets]
    if missing_targets:
        _add_unique_issue(critical, f"Agent {valuation_agent} 缺少目標價情境：{', '.join(missing_targets)}")
        add_agent_repair_issue(valuation_agent, f"缺少目標價情境：{', '.join(missing_targets)}")

    current_price = data.get("current_price")
    numeric_targets = {
        key: value for key, value in price_targets.items()
        if isinstance(value, (int, float))
    }
    if isinstance(current_price, (int, float)) and current_price > 100:
        tiny_targets = [
            f"{key}=NT${value:g}"
            for key, value in numeric_targets.items()
            if value < current_price * 0.05
        ]
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
    if not required_moat.issubset(moat_scores.keys()):
        missing = sorted(required_moat - set(moat_scores.keys()))
        _add_unique_issue(critical, f"Agent {moat_agent} 護城河評分缺少欄位：{', '.join(missing)}")
        add_agent_repair_issue(moat_agent, f"護城河評分缺少欄位：{', '.join(missing)}")

    recommendation = parsed.get("recommendation", {}) or {}
    if not recommendation:
        _add_unique_issue(critical, f"Agent {recommendation_agent} 缺少最終投資建議結構化資料。")
        add_agent_repair_issue(recommendation_agent, "缺少最終投資建議結構化資料。")
    else:
        rec_text = _recommendation_value(recommendation, "建議")
        if not any(word in rec_text for word in ["買入", "持有", "避免"]):
            _add_unique_issue(critical, f"Agent {recommendation_agent} 投資建議不在允許值內：{rec_text or '空白'}")
            add_agent_repair_issue(recommendation_agent, f"投資建議不在允許值內：{rec_text or '空白'}")
        for label in ["3個月", "6個月", "12個月", "信心"]:
            if not _recommendation_value(recommendation, label):
                _add_unique_issue(critical, f"Agent {recommendation_agent} 缺少 {label} 欄位。")
                add_agent_repair_issue(recommendation_agent, f"缺少 {label} 欄位。")

        data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
        data_trust_status = data_trust.get("status", "unknown")
        confidence_score = _extract_confidence_score(_recommendation_value(recommendation, "信心"))
        if data_trust_status != "fresh" and confidence_score is not None and confidence_score >= 8:
            _add_unique_issue(
                warnings,
                f"Agent {recommendation_agent} 在 data_trust={data_trust_status} 時給出高信心，報告需明確揭露資料限制。"
            )

        target_12m = _extract_first_price(_recommendation_value(recommendation, "12個月"))
        if target_12m is not None and all(key in numeric_targets for key in required_targets):
            bear = numeric_targets["熊市情境"]
            bull = numeric_targets["牛市情境"]
            lower = bear * 0.7
            upper = bull * 1.3
            if not (lower <= target_12m <= upper):
                _add_unique_issue(
                    warnings,
                    f"Agent {recommendation_agent} 的 12 個月目標價 NT${target_12m:g} 與 Agent {valuation_agent} 三情境區間差距較大，需人工確認。"
                )

    data_notes = data.get("data_source_notes", []) or []
    if any("口徑互斥" in note for note in data_notes):
        _add_unique_issue(corrections, "資料源出現淨利/淨利率口徑互斥時，報告已採用 EPS/P/E 自洽的校準口徑。")
    if any("revenueGrowth" in note for note in data_notes):
        _add_unique_issue(corrections, "Yahoo revenueGrowth 已降級為近期/季度口徑，不得直接當年度或 TTM 年增率。")

    for warning in context.get("structured_quality_warnings", []) or []:
        _add_unique_issue(warnings, str(warning))

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
        "report_preserved": True,
    }

    if append_section and critical:
        _append_final_audit_section(context, audit)

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
