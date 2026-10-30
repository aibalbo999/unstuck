"""Each final-assessment field cites only evidence issued for that source."""

import copy
import json

import pytest

from market_context_manifest import build_source_blocks, market_assessment_workplan
from structured_output_models import get_structured_response_schema
from test_market_context_assessment import assessment_context, assessment_module
from test_market_context_manifest import source_data


@pytest.mark.parametrize("agent", [7, 16, 19])
def test_workplan_binds_each_output_field_to_its_own_visible_source_paths(agent):
    data = source_data()
    blocks = build_source_blocks(data, agent_num=agent)
    # A reduced prompt must not advertise refs from omitted source blocks.
    blocks = blocks[:2]
    workplan = market_assessment_workplan(data, blocks)
    plan = json.loads(workplan.split("\n", 1)[1])
    for source, field in (("global_market_context", "items"), ("international_news_context", "topics")):
        item = plan[source]
        assert item["output_field"] == f"market_context_assessment.{source}.source_refs"
        assert item["source_path_prefix"] == f"data.{source}.{field}"
        assert item["visible_source_refs"] == [b["ref"] for b in blocks if b["source"] == source]
    assert "不得跨欄混用" in workplan
    assert "利率或全球景氣的新聞仍屬 international_news_context" in workplan


@pytest.mark.parametrize("agent", [7, 16, 19])
def test_provider_schema_explains_source_ownership_on_each_assessment_field(agent):
    schema = get_structured_response_schema(agent).model_json_schema()
    fields = schema["$defs"]["MarketContextAssessment"]["properties"]
    for source, field in (("global_market_context", "items"), ("international_news_context", "topics")):
        assert f"data.{source}.{field}" in fields[source]["description"]
        assert "不得跨欄混用" in fields[source]["description"]


@pytest.mark.parametrize("agent", [7, 16, 19])
def test_real_news_ref_under_global_field_remains_critical_and_unmodified(agent):
    context = assessment_context(agent=agent)
    raw = context["structured_outputs"][agent]["market_context_assessment"]
    wrong = raw["international_news_context"]["source_refs"][0]
    raw["global_market_context"]["source_refs"].append(wrong)
    original = copy.deepcopy(raw)
    result = assessment_module().assess_final_market_context(context)
    assert result["critical"]
    assert result["checks"][0]["reason_code"] == "source_reference_invalid"
    assert raw == original
    hint = result["repair_agent_issues"][agent][0]
    assert "market_context_assessment.global_market_context.source_refs" in hint
    assert wrong not in hint
    assert "不得只替換引用碼" in hint
