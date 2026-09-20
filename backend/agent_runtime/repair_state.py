"""Publish only accepted repair versions to the typed State blackboard."""

from context_dependencies import invalidate_repair_digests
from final_audit_mode_contracts import v3_short_setup_contract_issues
from final_audit_helpers import extract_first_price, recommendation_value
from forward_consistency_checker import run_forward_consistency_checks
from pipeline_modes import get_structured_agent_num
from structured_output_parser import parse_structured_data

from .state_report_adapter import record_agent_state_report
from .structured_repair_contracts import structured_output_missing


def repair_contract_issues(agent_num: int, context: dict) -> list[str]:
    """Use existing per-agent contracts; the complete report audit still follows."""
    issues = []
    if structured_output_missing(context, agent_num):
        issues.append(f"Agent {agent_num} 結構化輸出未通過本模式契約檢查。")
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
