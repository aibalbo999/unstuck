"""The existing negative-FCF policy must survive model and draft boundaries."""
import copy
import json

import pytest

from agent_runtime.quality_structured_outputs import try_parse_structured_output
from structured_output_runtime import process_agent_response
from test_trade_source_completion import setup_payload


WARNING = "注意：自由現金流為負，短線財務壓力升高"


def context(value):
    return {"pipeline_id": "v4", "data": {"free_cash_flow_raw": value},
            "_trade_source_manifest": {"version": "trade-sources:v1", "visible": True,
                "fingerprint": "fixture", "catalog": {"short_term_market_context": {
                    "technical_indicators": {"availability": "available", "source": "fixture",
                        "as_of": "2026-09-24", "sma_20": 95, "sma_5": 110}}}}}


@pytest.mark.parametrize("value", [-1_000_000_000, -1, "-1000000000"])
def test_negative_fcf_escalates_risk_without_changing_price_or_source_evidence(value):
    ctx = context(value)
    payload = {**setup_payload(), "risk_level": "Low"}
    text = process_agent_response(24, json.dumps(payload), ctx)
    actual = ctx["structured_outputs"][24]
    assert actual["risk_level"] == "High"
    assert WARNING not in actual["core_catalyst"] and WARNING in actual["financial_risk_flags"] and WARNING in text
    assert "TTM" not in actual["core_catalyst"]
    for field in ("trade_direction", "entry_zone", "target_price", "stop_loss",
                  "support_source_refs", "resistance_source_refs", "catalyst_source_refs"):
        assert actual[field] == payload[field]
    assert actual["source_assessment"]["status"] == "source_bound"


@pytest.mark.parametrize("value", [0, 1_000_000_000, None, "N/A", float("nan"),
                                   float("-inf"), True, False, [], {}])
def test_nonnegative_or_unusable_fcf_does_not_invent_financial_warning(value):
    ctx = context(value)
    process_agent_response(24, json.dumps({**setup_payload(), "risk_level": "Low"}), ctx)
    actual = ctx["structured_outputs"][24]
    assert actual["risk_level"] == "Low"
    assert WARNING not in actual["core_catalyst"]


@pytest.mark.parametrize("agent_key", [24, "24"])
def test_restored_structured_draft_is_rechecked_and_rendered_without_mutating_saved_payload(agent_key):
    ctx = context(-1_000_000_000)
    saved = {**setup_payload(), "risk_level": "Low", "source_assessment": {"status": "degraded"}}
    before = copy.deepcopy(saved)
    ctx["structured_outputs"] = {agent_key: saved}
    ok, text = try_parse_structured_output(24, "old low-risk draft", ctx)
    assert ok and WARNING in text and "風險：High" in text
    assert ctx["structured_outputs"][24]["risk_level"] == "High"
    assert ctx["structured_outputs"][24]["source_assessment"] == before["source_assessment"]
    assert saved == before
    ok, second = try_parse_structured_output(24, text, ctx)
    assert second == text and second.count(WARNING) == 1


def test_financial_guard_does_not_authorize_fake_sources_or_incomplete_generation():
    ctx = context(-1_000_000_000)
    payload = {**setup_payload(), "risk_level": "Low", "catalyst_source_refs": ["invented"]}
    process_agent_response(24, json.dumps(payload), ctx)
    actual = ctx["structured_outputs"][24]
    assert actual["trade_direction"] == "Neutral"
    assert actual["source_assessment"]["status"] == "degraded"
    assert actual["risk_level"] == "High" and WARNING in actual["financial_risk_flags"]
    process_agent_response(24, json.dumps(payload), ctx,
                           completion_diagnostics={"finish_reasons": ["MAX_TOKENS"]})
    assert not ctx["structured_outputs"].get(24)
