"""Fundamental rechecks preserve evidence without certifying a trading plan."""

import copy
import json

import pytest

from test_short_observation_fidelity import _research_setup


LIVE_ENTRY = "本研究情境不建立空方部位，等待單月營收未能突破 55 億元且毛利率未能回升之條件達成後再重新評估"
LIVE_STOP = "本研究情境不建立空方部位，回補停損不適用"
LIVE_ACTION = "執行防軋空停損控管，立即暫停所有下行風險觀察部位"


def _decode(setup, *, action="重新評估空方研究論點", label="避險觀察"):
    from structured_output_runtime import process_agent_response
    from test_google_recommendation_decode import _payload

    payload = _payload(label)
    for key in payload["recommendation"]:
        if "目標" in key or "潛力" in key:
            payload["recommendation"][key] = "N/A／未評估"
    payload["short_setup"] = copy.deepcopy(setup)
    payload["scenario_triggers"][0]["action"] = action
    payload["analysis_markdown"] = (
        "本次研究結論為避免，等待財務證據後再評估。研究政策不代表使用者實際持倉為零。\n"
        "## 做空觸發條件（Catalyst for crash）\n" + setup["entry_trigger"] + "\n"
        "## 防軋空停損點（Stop-loss level）\n" + setup["cover_stop"]
    )
    context = {"pipeline_id": "v3", "agent_sequence": [19], "data": {"current_price": 948.0}}
    rendered = process_agent_response(19, json.dumps(payload, ensure_ascii=False), context, model_id="gemini-test")
    output = context["structured_outputs"][19]
    context["parsed"] = {key: copy.deepcopy(output[key]) for key in ("recommendation", "short_setup", "scenario_triggers")}
    context["analyses"] = {19: rendered}
    return payload, output, context


def _alignment(context):
    from reporting.content_credibility import evaluate_content_credibility

    result = evaluate_content_credibility(context)
    check = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    return result, check


@pytest.mark.parametrize("entry", [
    LIVE_ENTRY,
    "本研究情境不建立空方部位；等待單月營收低於 55 億元後重新評估。",
    "本研究情境不建立空方部位，等待季度營收低於 5,500 百萬元且毛利率低於 24%後再重新評估。",
    "本研究情境不建立空方部位，等待營益率低於 10.5%之條件達成後再重新評估。",
    "本研究情境不建立空方部位，等待淨利率高於 8%後重新評估。",
])
def test_fundamental_numeric_recheck_survives_decode_and_actual_audits(entry):
    from final_audit import run_final_report_audit
    from trade_execution_contract import explicit_short_no_position

    setup = _research_setup()
    setup.update(entry_trigger=entry, cover_stop=LIVE_STOP)
    payload, output, context = _decode(setup)
    assert output["recommendation"]["建議"] == "避免"  # Existing provider wire decode.
    assert output["short_setup"]["entry_trigger"] == entry
    assert output["short_setup"]["cover_stop"] == LIVE_STOP
    assert output["analysis_markdown"] == payload["analysis_markdown"]
    assert explicit_short_no_position(output["short_setup"])
    context["final_audit"] = run_final_report_audit(context, append_section=False)
    assert context["final_audit"]["critical"] == []
    _, alignment = _alignment(context)
    assert alignment["status"] == "not_applicable"
    assert alignment["details"]["contract_verified"] is True
    assert alignment["details"]["analysis_completeness"] == "not_evaluated"


@pytest.mark.parametrize(("field", "value"), [
    ("entry_trigger", "本研究情境不建立空方部位，等待股價低於 900 元後重新評估。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待單月營收低於 55 後重新評估。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待單月營收低於 55 張後重新評估。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待借券餘額高於 55 億元後重新評估。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待單月營收低於 55 億元且股價跌破 900 元後重新評估。"),
    ("entry_trigger", LIVE_ENTRY + "；條件達成後建立空單。"),
    ("entry_trigger", LIVE_ENTRY + "；已有空單未平倉。"),
    ("entry_trigger", "假設財報未確認，" + LIVE_ENTRY),
    ("entry_trigger", "財報未公布則，" + LIVE_ENTRY),
    ("entry_trigger", LIVE_ENTRY + "；目前持倉為 0%。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待營收 55 億元價格進場後重新評估。"),
    ("entry_trigger", "本研究情境不建立空方部位，等待 900 元重新評估。"),
    ("cover_stop", LIVE_STOP + "，900 元。"),
    ("cover_stop", "N/A"),
    ("downside_target", "900"),
])
def test_numeric_recheck_does_not_exempt_prices_holdings_orders_or_missing_claims(field, value):
    from trade_execution_contract import explicit_short_no_position

    setup = _research_setup()
    setup.update(entry_trigger=LIVE_ENTRY, cover_stop=LIVE_STOP)
    setup[field] = value
    assert not explicit_short_no_position(setup)
    _, _, context = _decode(setup)
    _, alignment = _alignment(context)
    assert alignment["status"] == "warning"
    assert alignment["details"].get("contract_verified") is not True


@pytest.mark.parametrize("action", [
    LIVE_ACTION,
    "已有空單未平倉，立即回補。",
    "條件達成後建立空單。",
    "維持現有空方部位。",
    "全部回補。",
    "停損出場。",
    "不得不立即回補所有空單。",
    "等待回補空單後重新評估是否放空。",
    "Do not short. Cover existing short position.",
    "條件達成後回補。",
    "若營收改善則減碼。",
])
def test_scenario_decision_cannot_override_no_position_research_policy(action):
    from final_audit_mode_contracts import v3_recommendation_contract_issues

    _, output, context = _decode(_research_setup(), action=action)
    assert output["scenario_triggers"][0]["action"] == action
    _, alignment = _alignment(context)
    assert alignment["status"] == "warning"
    assert alignment["details"].get("contract_verified") is not True
    issues = v3_recommendation_contract_issues(context["analyses"], context["structured_outputs"], 19, {19})
    assert any("scenario_triggers[0].action" in issue and action in issue for issue in issues)


@pytest.mark.parametrize("action", [
    "重新評估研究論點；不得建立空單。",
    "暫停下行風險研究，等待新財報後重新評估。",
    "不代表使用者實際持倉為零；重新評估財務證據。",
    "重新評估是否放空；不得立即回補。",
    "重新評估回補風險與停損策略。",
    "不維持現有空單，無需退出任何部位。",
    "重新評估是否持有空方部位；不建立空單。",
    "不得全部回補；禁止停損出場。",
    "等待財報確認毛利率後再重新評估是否放空。",
    "Do not short.",
])
def test_non_trading_scenario_actions_do_not_block_research_policy(action):
    _, _, context = _decode(_research_setup(), action=action)
    _, alignment = _alignment(context)
    assert alignment["status"] == "not_applicable"


def test_live_numeric_condition_with_exit_action_reaches_bounded_audit_repair():
    from final_audit import run_final_report_audit

    setup = _research_setup()
    setup.update(entry_trigger=LIVE_ENTRY, cover_stop=LIVE_STOP)
    _, output, context = _decode(setup, action=LIVE_ACTION)
    assert output["short_setup"]["entry_trigger"] == LIVE_ENTRY
    assert output["short_setup"]["cover_stop"] == LIVE_STOP
    audit = run_final_report_audit(context, append_section=False)
    assert any(LIVE_ACTION in issue and "scenario_triggers[0].action" in issue for issue in audit["critical"])
    assert any(LIVE_ACTION in issue for issue in audit["repair_agent_issues"][19])
    context["final_audit"] = audit
    result, alignment = _alignment(context)
    assert result["status"] in {"blocked", "warning"}
    assert alignment["status"] == "warning"
    assert "short_observation_action_conflict" in {row["id"] for row in result["warnings"]}


def test_provider_schema_and_prompt_preserve_fundamental_thresholds_and_action_consistency():
    from structured_output_recommendation_outputs import BubbleSniperStructuredOutput, ShortSetup
    from test_four_mode_role_instructions import request

    _, prompt = request(19, "v3")
    schema = ShortSetup.model_json_schema()["properties"]["entry_trigger"]["description"]
    for text in (schema, prompt):
        assert "55 億元" in text
        assert "毛利率" in text
        assert "不是本次證據" in text
    scenarios = BubbleSniperStructuredOutput.model_json_schema()["properties"]["scenario_triggers"]["description"]
    assert "退出觀察部位" in scenarios
    assert "scenario_triggers.action" in prompt


@pytest.mark.parametrize("source", ["parsed", "structured", "string_key_structured"])
def test_scenario_conflict_in_either_decision_representation_retains_warning(source):
    _, _, context = _decode(_research_setup(), action=LIVE_ACTION)
    if source == "parsed":
        context["structured_outputs"] = {}
    else:
        context["parsed"].pop("scenario_triggers")
        if source == "string_key_structured":
            context["structured_outputs"]["19"] = context["structured_outputs"].pop(19)
    _, alignment = _alignment(context)
    assert alignment["status"] == "warning"


def test_scenario_source_quotes_and_risk_descriptions_are_not_execution_actions():
    _, output, context = _decode(_research_setup())
    output["confidence_basis"] = {"evidence_items": ["引文：立即回補所有空單。", "來源二", "來源三"]}
    output["short_setup"]["squeeze_risk"] = "財報若改善，可能迫使市場空方回補既有空單。"
    context["parsed"]["short_setup"] = copy.deepcopy(output["short_setup"])
    _, alignment = _alignment(context)
    assert alignment["status"] == "not_applicable"


def test_snapshot_decision_conflict_is_not_hidden_by_partial_context_outputs():
    from reporting.content_credibility import evaluate_content_credibility

    _, output, context = _decode(_research_setup(), action=LIVE_ACTION)
    snapshot = {"structured_outputs": {"19": copy.deepcopy(output)}}
    context["parsed"].pop("scenario_triggers")
    context["structured_outputs"] = {18: {"analysis_markdown": "財務風險分析"}}
    result = evaluate_content_credibility(context, snapshot=snapshot)
    alignment = next(row for row in result["checks"] if row["id"] == "recommendation_target_alignment")
    assert alignment["status"] == "warning"
