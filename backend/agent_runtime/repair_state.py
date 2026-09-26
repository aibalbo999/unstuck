"""Publish only accepted repair versions to the typed State blackboard."""

from context_dependencies import invalidate_repair_digests
from final_audit_mode_contracts import v3_short_setup_contract_issues
from final_audit_helpers import extract_first_price, recommendation_value
from forward_consistency_checker import run_forward_consistency_checks
from pipeline_modes import get_structured_agent_num
from structured_output_parser import parse_structured_data

from .state_report_adapter import record_agent_state_report
from .structured_repair_contracts import structured_output_missing


def research_repair_feedback(context: dict) -> list[str]:
    """Explain existing A7 failures using validated fields, never alter a claim."""
    from research_assumption_contract import AssumptionReconciliation, TOPICS, assess_reconciliation

    outputs = context.get("structured_outputs") or {}
    output = outputs.get(7, outputs.get("7")) if isinstance(outputs, dict) else None
    if not isinstance(output, dict):
        return []
    value = output.get("assumption_reconciliation")
    assessment = assess_reconciliation(value, context)
    if not assessment["issues"]:
        return []
    try:
        checked = AssumptionReconciliation.model_validate(value)
    except (ValueError, TypeError):
        return ["假設對照結構缺漏或格式錯誤；依既有 schema 重寫完整五項對照，不可補造證據。"]
    if "incomplete_assumption_topics" in assessment["issues"]:
        return ["假設對照五項 topic 必須各出現一次：" + "、".join(TOPICS) + "；不可用重複項目代替缺項。"]
    rows = {row.topic: row for row in checked.checks}
    feedback = []
    for item in assessment["quote_issues"]:
        row = rows[item["topic"]]
        reason = ("引文為空，不能支持目前 aligned/conflict 判定。"
                  if not getattr(row, item["field"]).strip()
                  else "引文不是對應來源中的連續逐字片段。")
        feedback.append(f"假設對照 {row.topic}.{item['field']}（來源 Agent {item['source_agent']}；"
                        f"目前 status={row.status}）：{reason}")
    if "missing_reconciliation_rationale" in assessment["issues"]:
        fields = "、".join(f"{row.topic}.rationale" for row in checked.checks if not row.rationale.strip())
        feedback.append(f"假設對照 {fields} 為空白；須逐項說明依據或資料缺口。")
    if "inconsistent_reconciliation_status" in assessment["issues"]:
        feedback.append(f"assumption_reconciliation.status={checked.status} 與各列不一致；"
                        f"依目前五列應為 {assessment['status']}。修正各列後重新聚合："
                        "conflict 優先，其次 unassessed，全部 aligned 才能標 aligned。")
    if "conflict_requires_recalculation" in assessment["issues"]:
        feedback.append("assumption_reconciliation.pending_recalculation=false；保留 conflict 時必須為 true，"
                        "既有價格不代表已完成重算。修正各列後依最終狀態核對。")
    if feedback:
        feedback.append("只可引用對應 Agent 的連續原文，不可省略、拼接或補造；無對應證據時引文留空、"
                        "本列標 unassessed 並說明缺口。重寫完整候選，同步核對正文、推薦與市場評估，"
                        "不得只改標籤以通過檢查。")
    return feedback


def repair_contract_issues(agent_num: int, context: dict) -> list[str]:
    """Use existing per-agent contracts; the complete report audit still follows."""
    issues = []
    if agent_num == 24:
        from .trade_audit_source_contract import audit_source_issues
        issues.extend(audit_source_issues(context))
    if structured_output_missing(context, agent_num):
        issues.append(f"Agent {agent_num} 結構化輸出未通過本模式契約檢查。")
        if agent_num == 7:
            issues.extend(research_repair_feedback(context))
        if get_structured_agent_num("short_setup", context) == agent_num:
            outputs = context.get("structured_outputs") or {}
            output = outputs.get(agent_num, outputs.get(str(agent_num)))
            if isinstance(output, dict):
                short_setup = output.get("short_setup")
                if isinstance(short_setup, dict):
                    issues.extend(v3_short_setup_contract_issues(
                        short_setup, recommendation=output.get("recommendation"),
                    ))
    if get_structured_agent_num("recommendation", context) == agent_num:
        recommendation = parse_structured_data(context).get("recommendation") or {}
        checks = run_forward_consistency_checks(
            recommendation=recommendation_value(recommendation, "建議"),
            current_price=(context.get("data") or {}).get("current_price"),
            target_3m=extract_first_price(recommendation_value(recommendation, "3個月")),
            target_6m=extract_first_price(recommendation_value(recommendation, "6個月")),
            target_12m=extract_first_price(recommendation_value(recommendation, "12個月")),
        )
        issues.extend(checks["critical"])
    return issues


def adopt_repair_result(agent_num: int, context: dict, result: tuple[bool, str]) -> tuple[bool, str]:
    if result[0]:
        issues = repair_contract_issues(agent_num, context)
        if issues:
            return False, "修復候選未通過契約檢查：" + "；".join(issues)
        analyses = context.get("analyses") or {}
        structured = context.get("structured_outputs") or {}
        record_agent_state_report(
            context.get("agent_state"), agent_num,
            analyses.get(agent_num, analyses.get(str(agent_num), "")),
            structured.get(agent_num, structured.get(str(agent_num))),
        )
        invalidate_repair_digests(context, agent_num)
    return result
