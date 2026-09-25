"""Mode C's declared research no-position contract survives real decoding."""

import copy
import json

import pytest


def _research_setup():
    return {
        "entry_trigger": "本研究情境不建立空方部位，等待下次財報確認毛利率後重新評估。",
        "downside_target": "N/A",
        "cover_stop": "本研究情境不建立空方部位，回補停損不適用。",
        "squeeze_risk": "借券資料不足，需確認法人籌碼與軋空風險。",
        "thesis_invalidation": "若後續財報毛利率回升，重新評估空方論點。",
    }


def _decode(setup, label="避免"):
    from structured_output_runtime import process_agent_response
    from test_google_recommendation_decode import _payload

    payload = _payload(label)
    for key in payload["recommendation"]:
        if "目標" in key or "潛力" in key:
            payload["recommendation"][key] = "N/A／未評估（缺少可驗證的同期間估值）"
    payload["short_setup"] = setup
    payload["analysis_markdown"] = (
        "本次研究結論為避免，等待可驗證的財務證據後再評估，不建立新部位。\n"
        "## 做空觸發條件（Catalyst for crash）\n" + setup.get("entry_trigger", "資料不足") + "\n"
        "## 防軋空停損點（Stop-loss level）\n" + setup.get("cover_stop", "資料不足")
    )
    context = {"pipeline_id": "v3", "agent_sequence": [19], "data": {"current_price": 948.0}}
    text = process_agent_response(19, json.dumps(payload, ensure_ascii=False), context, model_id="gemini-test")
    output = context["structured_outputs"][19]
    context["parsed"] = {key: copy.deepcopy(output[key]) for key in ("recommendation", "short_setup")}
    context["analyses"] = {19: text}
    return payload, output, context


@pytest.mark.parametrize("stop", [
    "本研究情境不建立空方部位，回補停損不適用。",
    "回補停損不適用，本研究情境目前不建立空方部位。",
    "不適用，本研究情境不建立空方部位。",
])
def test_research_no_position_survives_raw_normalization_audit_and_credibility(stop):
    from final_audit_mode_contracts import mode_execution_contract_issues, v3_recommendation_contract_issues
    from reporting.content_credibility import evaluate_content_credibility
    from trade_execution_contract import explicit_short_no_position
    from trade_price_inputs import execution_value_missing

    setup = _research_setup()
    setup["cover_stop"] = stop
    payload, output, context = _decode(setup)

    for field, original in setup.items():
        if field != "downside_target":
            assert output["short_setup"][field] == original
    assert execution_value_missing(output["short_setup"]["downside_target"])
    assert output["analysis_markdown"] == payload["analysis_markdown"]
    assert explicit_short_no_position(output["short_setup"])
    assert mode_execution_contract_issues(context["parsed"], position_plan_agent=None,
                                         short_setup_agent=19, trade_setup_agent=None) == []
    assert v3_recommendation_contract_issues(context["analyses"], context["structured_outputs"], 19, {19}) == []
    context["final_audit"] = {"status": "warning", "warnings": ["法說逐字稿尚未取得"], "critical": []}
    result = evaluate_content_credibility(context)
    alignment = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "not_applicable"
    assert alignment["details"]["contract_verified"] is True
    assert alignment["details"]["analysis_completeness"] == "not_evaluated"
    assert result["status"] == "warning"
    assert "final_audit_warning" in {row["id"] for row in result["warnings"]}


@pytest.mark.parametrize(("field", "value"), [
    ("entry_trigger", "本研究情境不建立空方部位；跌破支撐後放空。"),
    ("entry_trigger", "若財報未確認，本研究情境不建立空方部位。"),
    ("entry_trigger", "假設財報未確認，本研究情境不建立空方部位。"),
    ("entry_trigger", "假定財報未確認，本研究情境不建立空方部位。"),
    ("entry_trigger", "財報不佳時，本研究情境不建立空方部位。"),
    ("entry_trigger", "財報未公布則，本研究情境不建立空方部位。"),
    ("entry_trigger", "本研究情境不建立空方部位；現有空單繼續持有。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待財報後重新評估。已有空單未平倉。"),
    ("entry_trigger", "本研究情境不建立空方部位；等待 900 元重新評估。"),
    ("cover_stop", "本研究情境不建立空方部位；回補停損不適用，立即回補。"),
    ("cover_stop", "本研究情境不建立空方部位；回補停損不適用時仍須回補。"),
    ("cover_stop", "本研究情境不建立空方部位；不是回補停損不適用。"),
    ("cover_stop", "本研究情境不建立空方部位；回補停損不適用；既有持倉續抱。"),
    ("cover_stop", "本研究情境不建立空方部位，回補停損不適用。已有空單未平倉。"),
    ("cover_stop", "本研究情境不建立空方部位；回補停損不適用；1,100 元回補。"),
    ("cover_stop", "回補停損不適用。"),
    ("cover_stop", "N/A"),
    ("downside_target", "900"),
    ("squeeze_risk", "N/A"),
    ("thesis_invalidation", "N/A"),
])
def test_research_wording_cannot_exempt_missing_evidence_or_real_positions(field, value):
    from reporting.content_credibility import evaluate_content_credibility
    from trade_execution_contract import explicit_short_no_position

    setup = _research_setup()
    setup[field] = value
    assert not explicit_short_no_position(setup)
    _, output, context = _decode(setup)
    assert not explicit_short_no_position(output["short_setup"])
    result = evaluate_content_credibility(context)
    assert "missing_price_alignment_inputs" in {row["id"] for row in result["warnings"]}


@pytest.mark.parametrize("label", ["持有", "買入", "放空", "賣出", "減碼", "持有，但避免追高"])
def test_research_no_position_exemption_stays_limited_to_exact_avoid(label):
    from reporting.content_credibility import evaluate_content_credibility

    _, _, context = _decode(_research_setup(), label)
    result = evaluate_content_credibility(context)
    alignment = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "warning"


@pytest.mark.parametrize("field", ["entry_trigger", "cover_stop"])
def test_actual_decoder_cannot_certify_an_existing_unclosed_short(field):
    from reporting.content_credibility import evaluate_content_credibility

    setup = _research_setup()
    setup[field] += "已有空單未平倉。"
    _, _, context = _decode(setup)
    result = evaluate_content_credibility(context)
    alignment = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "warning"
    assert alignment["details"].get("contract_verified") is not True


def test_provider_schema_and_delivered_prompt_describe_the_same_no_position_statement():
    from structured_output_recommendation_outputs import ShortSetup
    from test_four_mode_role_instructions import request

    canonical = "本研究情境不建立空方部位，回補停損不適用"
    _, prompt = request(19, "v3")
    assert canonical in prompt
    assert canonical in ShortSetup.model_json_schema()["properties"]["cover_stop"]["description"]


def test_full_final_audit_accepts_the_preserved_research_setup():
    from final_audit import run_final_report_audit
    from reporting.content_credibility import evaluate_content_credibility

    _, _, context = _decode(_research_setup())
    audit = run_final_report_audit(context, append_section=False)
    context["final_audit"] = audit
    assert audit["critical"] == []
    assert audit["status"] == "passed"
    result = evaluate_content_credibility(context)
    alignment = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "not_applicable"
    assert alignment["details"]["target_price"] is None
    assert "missing_price_alignment_inputs" not in {row["id"] for row in result["warnings"]}
