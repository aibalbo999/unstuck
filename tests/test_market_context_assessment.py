"""Assessments cannot self-authorize sources or turn unknown into no impact."""

import copy
import importlib
import importlib.util

import pytest

from test_market_context_manifest import manifest_module, source_data


def assessment_module():
    assert importlib.util.find_spec("market_context_assessment") is not None, "Structured market coverage validator is required"
    return importlib.import_module("market_context_assessment")


def assessment_context(*, agent=7, data=None, compact=False, omitted=False):
    module = manifest_module()
    data = source_data() if data is None else data
    blocks = module.build_source_blocks(data, agent_num=agent, compact=compact)
    prompt = "" if omitted else "\n".join(block["text"] for block in blocks)
    manifest = module.build_market_context_manifest(data, prompt, blocks, agent_num=agent)
    assessment = {source: {"impact": "no_material_impact", "reason": "供應與利率變化尚不足以改變本次等待決策。",
                           "source_refs": values["visible_refs"][:1]}
                  for source, values in manifest["sources"].items()}
    return {"pipeline_id": {7: "v1", 16: "v2", 19: "v3"}[agent], "data": data,
            "market_context_contract_version": "market_context.v1", "market_context_manifests": {agent: manifest},
            "structured_outputs": {agent: {"market_context_assessment": assessment}}}


@pytest.mark.parametrize("agent", [7, 16, 19])
@pytest.mark.parametrize("impact", ["affects_conclusion", "no_material_impact"])
def test_valid_grounded_assessment_is_accepted(agent, impact):
    module = assessment_module()
    context = assessment_context(agent=agent)
    for value in context["structured_outputs"][agent]["market_context_assessment"].values():
        value["impact"] = impact
    result = module.assess_final_market_context(context)
    assert result["status"] == "passed"
    assert not result["critical"] and not result["coverage_repair_agent_issues"]


@pytest.mark.parametrize("omitted", [False, True])
def test_unavailable_or_wholly_omitted_sources_warn_without_retry(omitted):
    module = assessment_module()
    context = assessment_context(data=source_data() if omitted else {"ticker": "TEST"}, omitted=omitted)
    context["structured_outputs"][7] = {}
    result = module.assess_final_market_context(context)
    assert result["status"] == "warning"
    assert not result["repair_agent_issues"] and not result["coverage_repair_agent_issues"]
    assert all(item["impact"] == "not_assessed" for item in result["assessment"].values())
    assert {item["reason_code"] for item in result["checks"]} == {"prompt_omitted" if omitted else "source_unavailable"}


@pytest.mark.parametrize("value", [None, {"impact": "no_material_impact", "reason": "", "source_refs": []},
                                  {"impact": "no_material_impact", "reason": "global_market_context", "source_refs": []}])
def test_missing_or_empty_assessment_is_only_a_bounded_coverage_repair(value):
    module = assessment_module()
    context = assessment_context()
    context["structured_outputs"][7]["market_context_assessment"] = value
    result = module.assess_final_market_context(context)
    assert result["coverage_repair_agent_issues"].get(7)
    assert not result["critical"]
    assert all(item["impact"] == "not_assessed" for item in result["assessment"].values())


@pytest.mark.parametrize("kind", ["fabricated", "other_snapshot", "unseen", "modified_item", "wrong_agent"])
def test_untrusted_or_stale_source_claim_is_critical(kind):
    module = assessment_module()
    context = assessment_context(compact=True)
    assessment = context["structured_outputs"][7]["market_context_assessment"]
    if kind == "fabricated":
        assessment["international_news_context"]["source_refs"] = ["https://model-invented.invalid/news"]
    elif kind == "other_snapshot":
        context["data"]["ticker"] = "OTHER"
    elif kind == "unseen":
        all_blocks = manifest_module().build_source_blocks(context["data"], agent_num=7)
        assessment["international_news_context"]["source_refs"] = [all_blocks[-1]["ref"]]
    elif kind == "modified_item":
        context["data"]["international_news_context"]["topics"][0]["headline"] = "Revised source"
    else:
        context["market_context_manifests"][7]["agent_num"] = 19
    result = module.assess_final_market_context(context)
    assert result["critical"] and result["repair_agent_issues"].get(7)


def test_legacy_missing_assessment_is_not_recorded_and_d_is_not_applicable():
    module = assessment_module()
    assert module.assess_final_market_context({"pipeline_id": "v1"})["status"] == "not_recorded"
    assert module.assess_final_market_context({"pipeline_id": "v4", "market_context_contract_version": "market_context.v1"})["status"] == "not_applicable"


def test_missing_sources_without_manifest_do_not_request_a_model_retry():
    result = assessment_module().assess_final_market_context({
        "pipeline_id": "v1", "market_context_contract_version": "market_context.v1", "data": {"ticker": "TEST"}})
    assert result["status"] == "warning"
    assert result["coverage_repair_agent_issues"] == {}
    assert {check["reason_code"] for check in result["checks"]} == {"source_unavailable"}


@pytest.mark.parametrize("kind", ["error_placeholder", "declared_unavailable"])
def test_failed_source_context_does_not_issue_refs_or_schedule_coverage_retry(kind):
    data = source_data()
    if kind == "error_placeholder":
        data["international_news_context"]["topics"] = [{"error": "failed"}]
        data["global_market_context"]["items"] = [{"symbol": "QQQ", "error": "failed"}]
    else:
        for source in ("global_market_context", "international_news_context"):
            data[source]["availability"] = "unavailable"
    context = assessment_context(data=data)
    context["structured_outputs"][7] = {}
    assert not context["market_context_manifests"][7]["items"]
    result = assessment_module().assess_final_market_context(context)
    assert not result["coverage_repair_agent_issues"]
    assert {check["reason_code"] for check in result["checks"]} == {"source_unavailable"}


def test_current_structured_output_does_not_borrow_stale_parsed_assessment():
    context = assessment_context()
    context["parsed"] = {"market_context_assessment": context["structured_outputs"][7]["market_context_assessment"]}
    context["structured_outputs"][7] = {"analysis_markdown": "New result has not assessed the sources"}
    result = assessment_module().assess_final_market_context(context)
    assert result["status"] == "warning"
    assert result["coverage_repair_agent_issues"].get(7)


@pytest.mark.parametrize("impact", [[], {}, False, None])
def test_malformed_model_impact_is_unassessed_instead_of_crashing(impact):
    context = assessment_context()
    context["structured_outputs"][7]["market_context_assessment"]["global_market_context"]["impact"] = impact
    result = assessment_module().assess_final_market_context(context)
    assert result["assessment"]["global_market_context"]["impact"] == "not_assessed"
    assert result["coverage_repair_agent_issues"].get(7)


@pytest.mark.parametrize("field,value", [("reason", []), ("source_refs", "made-up"), ("source_refs", {"fake": True}), ("impact", {})])
def test_malformed_assessment_fields_fail_closed_in_validation_and_text(field, value):
    context = assessment_context()
    assessment = context["structured_outputs"][7]["market_context_assessment"]
    assessment["global_market_context"][field] = value
    result = assessment_module().assess_final_market_context(context)
    assert result["status"] in {"warning", "critical"}
    assert isinstance(assessment_module().market_assessment_text(assessment), str)


@pytest.mark.parametrize("agent_value", [True, "v1", [], {}])
def test_malformed_manifest_agent_never_authorizes_claims(agent_value):
    context = assessment_context()
    context["market_context_manifests"][7]["agent_num"] = agent_value
    assert assessment_module().assess_final_market_context(context)["critical"]


@pytest.mark.parametrize("agent", [7, 16, 19])
def test_schema_normalizer_parser_snapshot_and_report_text_keep_the_same_assessment(agent):
    from structured_output_models import get_structured_response_schema
    from structured_output_normalizer import normalize_structured_output, structured_output_to_report_text
    from structured_output_parser import parse_structured_data
    from data_trust_snapshot import build_data_snapshot
    from test_structured_output_models import _recommendation_payload

    context = assessment_context(agent=agent)
    assessment = context["structured_outputs"][agent]["market_context_assessment"]
    payload = _recommendation_payload()
    payload["market_context_assessment"] = assessment
    if agent == 16:
        payload["position_plan"] = {"action": "等待"}
    if agent == 19:
        payload["short_setup"] = {}
    schema = get_structured_response_schema(agent)
    assert schema.model_validate(payload).model_dump()["market_context_assessment"] == assessment
    normalized = normalize_structured_output(agent, payload)
    assert normalized["market_context_assessment"] == assessment
    context["structured_outputs"] = {agent: normalized}
    context["parsed"] = parse_structured_data(context)
    assert context["parsed"]["market_context_assessment"] == assessment
    snapshot = build_data_snapshot(context, max_bytes=400)
    assert snapshot["market_context_contract_version"] == "market_context.v1"
    assert snapshot["market_context_manifests"][str(agent)] == context["market_context_manifests"][agent]
    assert snapshot["market_context_assessment"] == assessment
    text = structured_output_to_report_text(agent, normalized)
    assert "市場與新聞評估" in text and "未實質改變結論" in text
    assert assessment["international_news_context"]["reason"] in text


def test_normalizer_keeps_invalid_source_claim_for_the_validator_instead_of_dropping_it():
    from structured_output_normalizer import normalize_structured_output
    from test_structured_output_models import _recommendation_payload

    context = assessment_context()
    assessment = context["structured_outputs"][7]["market_context_assessment"]
    assessment["international_news_context"]["source_refs"] = "made-up-ref"
    payload = {**_recommendation_payload(), "market_context_assessment": assessment}
    context["structured_outputs"][7] = normalize_structured_output(7, payload)
    assert context["structured_outputs"][7]["market_context_assessment"] == assessment
    assert assessment_module().assess_final_market_context(context)["critical"]


@pytest.mark.parametrize("agent", [7, 16, 19])
@pytest.mark.parametrize("html", [False, True])
def test_final_report_sections_render_validated_limitations_without_rewriting_raw_assertions(agent, html):
    from reporting.sections import build_agent_sections
    from structured_output_normalizer import normalize_structured_output
    from test_structured_output_models import _recommendation_payload

    context = assessment_context(agent=agent)
    assessment = context["structured_outputs"][agent]["market_context_assessment"]
    assessment["international_news_context"]["source_refs"] = ["MODEL_INVENTED_REFERENCE"]
    payload = {**_recommendation_payload(), "market_context_assessment": assessment}
    if agent == 16:
        payload["position_plan"] = {"action": "等待"}
    if agent == 19:
        payload["short_setup"] = {}
    context["structured_outputs"][agent] = normalize_structured_output(agent, payload)
    context["analyses"] = {agent: "Final report content"}
    context["agent_sequence"] = [agent]
    before = copy.deepcopy(context)
    section = build_agent_sections(context, html=html)[0]["body"]
    assert "來源引用無法綁定" in section
    assert "MODEL_INVENTED_REFERENCE" not in section
    assert context == before
