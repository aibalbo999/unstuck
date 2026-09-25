"""Keep observations, future events, rechecks and policy risk in distinct fields."""
import copy
import json
from pathlib import Path

import pytest

from structured_output_runtime import process_agent_response
from trade_financial_risk import NEGATIVE_FCF_WARNING
from trade_source_contract import bind_trade_payload


def real_case():
    fixture = json.loads((Path(__file__).parent / "fixtures/trade_catalyst_6488_20260925.json").read_text())
    return copy.deepcopy(fixture["payload"]), copy.deepcopy(fixture["context"])


def separated_case():
    payload, context = real_case()
    payload.update(
        core_catalyst="等待法人賣壓衰竭並帶量突破1015元後再重新評估",
        observed_signal="截至2026-09-24，外資近30個交易日淨賣超23,840.33千股，且技術面日RSI為49.43呈現中性",
        observed_source_refs=payload["catalyst_source_refs"],
        recheck_condition="等待法人賣壓衰竭並帶量突破1015元後再重新評估",
        event_catalyst=None,
        financial_risk_flags=[],
    )
    return payload, context


def test_real_6488_full_binding_separates_exact_legacy_policy_suffix():
    payload, context = real_case()
    rendered = process_agent_response(24, json.dumps(payload), context)
    actual = context["structured_outputs"][24]
    assert actual["source_assessment"]["status"] == "observation"
    assert actual["catalyst_source_refs"] == payload["catalyst_source_refs"]
    assert NEGATIVE_FCF_WARNING not in actual["core_catalyst"]
    assert actual["financial_risk_flags"] == [NEGATIVE_FCF_WARNING]
    assert actual["risk_level"] == "High"
    assert rendered.count(NEGATIVE_FCF_WARNING) == 1


@pytest.mark.parametrize("suffix", [
    "；注意：自由現金流為負，短線財務壓力升高且法人已連續買超",
    "；注意：自由現金流為負，短線財務壓力升高；外資已買超9999千股",
    "；等待法人近5日買超9999千股後再評估；" + NEGATIVE_FCF_WARNING,
])
def test_policy_migration_never_hides_other_actual_or_ambiguous_assertions(suffix):
    payload, context = real_case()
    payload["core_catalyst"] = payload["core_catalyst"].split("；注意：")[0] + suffix
    assert bind_trade_payload(payload, context)[1]["status"] == "degraded"


def test_distinct_fields_survive_model_runtime_and_render_without_event_invention():
    payload, context = separated_case()
    rendered = process_agent_response(24, json.dumps(payload), context)
    actual = context["structured_outputs"][24]
    for field in ("observed_signal", "observed_source_refs", "recheck_condition", "event_catalyst"):
        assert actual[field] == payload[field]
    assert actual["source_assessment"]["status"] == "observation"
    assert payload["observed_signal"] in rendered and payload["recheck_condition"] in rendered
    assert "事件日期未確認" in rendered


@pytest.mark.parametrize("field, value", [
    ("observed_signal", {"hidden": "外資已買超"}),
    ("observed_source_refs", "short_term_market_context.institutional_evidence.records[5]"),
    ("recheck_condition", ["外資已買超"]),
    ("financial_risk_flags", {"hidden": "外資已買超"}),
    ("event_catalyst", "明天法說"),
])
def test_malformed_new_fields_degrade_before_default_normalization(field, value):
    payload, context = separated_case()
    payload[field] = value
    process_agent_response(24, json.dumps(payload), context)
    assert context["structured_outputs"][24]["source_assessment"]["status"] == "degraded"


@pytest.mark.parametrize("field, value", [
    ("observed_signal", "外資近5日買超9999千股"),
    ("recheck_condition", "等待量能回升，但外資已連續買超後再評估"),
    ("financial_risk_flags", ["法人已連續買超，不構成風險"]),
])
def test_new_fields_cannot_bypass_claim_checks(field, value):
    payload, context = separated_case()
    payload[field] = value
    assert bind_trade_payload(payload, context)[1]["status"] == "degraded"


def test_observation_cannot_borrow_legacy_refs_or_move_facts_into_recheck():
    payload, context = separated_case()
    payload["observed_source_refs"] = []
    assert bind_trade_payload(payload, context)[1]["status"] == "degraded"


def test_valid_observed_field_never_hides_an_unsupported_legacy_summary():
    payload, context = separated_case()
    payload["core_catalyst"] = "外資近5日已買超9999千股；等待量能回升後再重新評估"
    _, assessment = bind_trade_payload(payload, context)
    assert assessment["status"] == "degraded"
    assert "core_catalyst_semantic_mismatch" in assessment["reason_codes"]
    assert "catalyst_evidence_scope_mismatch" in assessment["reason_codes"]


def test_legacy_exact_policy_suffix_requires_corroborated_raw_negative_fcf():
    payload, context = real_case()
    context["data"] = {"free_cash_flow_raw": 0}
    _, assessment = bind_trade_payload(payload, context)
    assert assessment["status"] == "degraded"
    assert "unverified_financial_policy_warning" in assessment["reason_codes"]


def event_case():
    payload, context = separated_case()
    context["_trade_source_manifest"]["catalog"]["short_term_market_context"]["event_calendar"] = {
        "availability": "available", "as_of": "2026-09-25", "window_end": "2026-10-09",
        "events": [{"date": "2026-09-30", "label": "法人說明會", "date_status": "scheduled", "source": "company"}],
    }
    payload["event_catalyst"] = {"description": "法人說明會", "date": "2026-09-30", "timezone": None,
                                "status": "scheduled", "source_refs": ["short_term_market_context.event_calendar.events[0]"]}
    return payload, context


def test_event_requires_own_exact_schedule_and_does_not_invent_timezone():
    payload, context = event_case()
    assert bind_trade_payload(payload, context)[1]["status"] == "observation"
    process_agent_response(24, json.dumps(payload), context)
    assert context["structured_outputs"][24]["event_catalyst"]["timezone"] is None


@pytest.mark.parametrize("changes", [
    {"date": "N/A"}, {"date": None}, {"date": "2026-09-31"},
    {"date": "2026-10-01"}, {"status": "confirmed"}, {"timezone": "Asia/Taipei"},
    {"description": "外資買超將推動上漲"},
    {"source_refs": ["short_term_market_context.technical_indicators.rsi_14"]},
    {"status": []}, {"source_refs": [False]}, {"timezone": {}},
])
def test_scheduled_event_rejects_unknown_or_fabricated_dates_status_timezone_and_claims(changes):
    payload, context = event_case()
    payload["event_catalyst"].update(changes)
    assert bind_trade_payload(payload, context)[1]["status"] == "degraded"


def test_unknown_event_has_no_date_or_refs_and_does_not_count_as_scheduled_evidence():
    payload, context = separated_case()
    payload["event_catalyst"] = {"description": None, "date": "N/A", "timezone": "N/A", "status": "unknown", "source_refs": []}
    process_agent_response(24, json.dumps(payload), context)
    actual = context["structured_outputs"][24]
    assert actual["event_catalyst"]["date"] is None
    assert actual["event_catalyst"]["timezone"] is None
    assert actual["source_assessment"]["status"] == "observation"


def test_changing_separate_fields_invalidates_diagnostic_candidate_fingerprint():
    from trade_source_diagnostics import candidate_fingerprint
    payload, _ = separated_case()
    for field, changed in (("observed_signal", "different"), ("recheck_condition", "different"),
                           ("financial_risk_flags", [NEGATIVE_FCF_WARNING]), ("event_catalyst", {"date": "2026-09-30"})):
        candidate = {**payload, field: changed}
        assert candidate_fingerprint(candidate) != candidate_fingerprint(payload)


def test_negative_fcf_source_repair_receipt_matches_the_separated_output():
    from trade_source_diagnostics import source_repair_feedback
    payload, context = separated_case()
    payload["observed_signal"] = "外資近5日買超9999千股"
    process_agent_response(24, json.dumps(payload), context)
    actual = context["structured_outputs"][24]
    feedback = source_repair_feedback(actual["source_assessment"], context["_trade_source_manifest"], actual)
    assert "原候選來源退件診斷" in feedback


@pytest.mark.parametrize("field", ["observed_signal", "observed_source_refs", "event_catalyst", "recheck_condition", "financial_risk_flags"])
def test_new_source_manifest_requires_raw_semantic_fields_before_normalization(field):
    from trade_source_contract import CONTRACT_VERSION, missing_trade_fields
    payload, context = separated_case()
    context["_trade_source_manifest"]["version"] = CONTRACT_VERSION
    payload.pop(field)
    assert field in missing_trade_fields(payload, context=context)
    process_agent_response(24, json.dumps(payload), context)
    assert not context.get("structured_outputs", {}).get(24)
    assert field in context["_trade_incomplete_fields"]


@pytest.mark.parametrize("version", ["trade-sources:v1", "trade-sources:v2"])
def test_legacy_manifest_reads_old_shapes_without_inventing_new_fields(version):
    payload, context = real_case()
    context["_trade_source_manifest"]["version"] = version
    process_agent_response(24, json.dumps(payload), context)
    assert context["structured_outputs"][24]["source_assessment"]["status"] == "observation"
