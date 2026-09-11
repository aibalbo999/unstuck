"""Merge source-credibility findings without conflating optional coverage and blockers."""

from final_audit_dcf import dcf_audit_findings
from final_audit_helpers import add_unique_issue
from market_context_assessment import assess_final_market_context


def merge_credibility_findings(context, valuation_agent, critical, warnings, add_agent_repair_issue):
    if valuation_agent is not None:
        findings = dcf_audit_findings(context.get("analyses") or {}, context.get("data") or {},
                                     context.get("structured_outputs") or {}, valuation_agent=valuation_agent)
        for finding in findings:
            message = finding["message"]
            add_unique_issue(critical if finding["severity"] == "critical" else warnings, message)
            if finding["severity"] == "critical":
                add_agent_repair_issue(finding["agent"], message)
    market = assess_final_market_context(context)
    for issue in market["critical"]:
        add_unique_issue(critical, issue)
    for issue in market["warnings"]:
        add_unique_issue(warnings, issue)
    for agent_num, issues in market["repair_agent_issues"].items():
        for issue in issues:
            add_agent_repair_issue(agent_num, issue)
    return market
