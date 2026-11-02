from agent_runtime.generation_config import build_generation_config,google_safe_agent_system_instruction
from research_assumption_contract import AssumptionReconciliation,TOPICS


def test_provider_schema_requests_fingerprint_before_short_reference_rows():
    schema=build_generation_config(7).response_schema
    node=schema["$defs"]["AssumptionReconciliation"]
    assert "upstream_fingerprint" in node["required"]
    assert node["propertyOrdering"][0]=="upstream_fingerprint"
    assert "upstream_fingerprint" in google_safe_agent_system_instruction(7,"gemini-3.8-flash")


def test_legacy_literal_unassessed_reports_do_not_require_provider_metadata():
    value={"status":"unassessed","pending_recalculation":False,
        "checks":[{"topic":topic,"status":"unassessed","valuation_quote":"",
                   "growth_quote":"","rationale":"缺少同期間原件"}for topic in TOPICS]}
    assert AssumptionReconciliation.model_validate(value).upstream_fingerprint is None
