"""Precision and local financial semantics; private replay is opt-in and read-only."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3

import pytest

from audit_rule_engine import evaluate_configured_audit_rules
from institutional_evidence import institutional_evidence_issues


@pytest.fixture(autouse=True)
def no_database_access(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError("Financial gate checks must not access a database")
    monkeypatch.setattr(sqlite3, "connect", reject)


def flow_data(value=-21488.43):
    return {"ticker": "TEST.TW", "institutional_trading": {
        "source": "TWSE T86", "latest_date": "2026-10-16",
        "lookback_trading_days": 30,
        "net_buy_thousand_shares_by_category": {"foreign": value},
    }}


@pytest.mark.parametrize("alias", ["約2.1萬張", "約21,488張", "約-2.1萬張", "約21488.4千股"])
def test_explicit_approximate_alias_preserves_precise_main_value(alias):
    text = f"外資近30個交易日賣超21,488.43千股（{alias}）。"
    data = flow_data()
    original = deepcopy(data)
    assert institutional_evidence_issues(text, data) == []
    assert data == original


@pytest.mark.parametrize("value,alias,accepted", [
    (-21500, "約2.2萬張", True),
    (-21500, "約2.1萬張", False),
    (-21499.99, "約2.1萬張", True),
    (-21499.99, "約2.2萬張", False),
    (21500, "約2.2萬張", True),
    (-21488.43, "約2.10萬張", False),
    (-21488.43, "約2.15萬張", True),
    (-21488.43, "約21千張", True),
])
def test_alias_uses_declared_decimal_places_and_half_up(value, alias, accepted):
    verb = "賣超" if value < 0 else "買超"
    text = f"外資近30個交易日{verb}{abs(value)}千股（{alias}）。"
    assert bool(institutional_evidence_issues(text, flow_data(value))) is not accepted


@pytest.mark.parametrize("text", [
    "外資近30個交易日賣超21,488.43千股（2.1萬張）。",
    "外資近30個交易日賣超21,488.43千股（即2.1萬張）。",
    "外資近30個交易日賣超21,488.43千股（約2.1千張）。",
    "外資近30個交易日賣超21,488.43千股（約21,488.43千張）。",
    "外資近30個交易日賣超21,488.43千股（約+2.1萬張）。",
    "外資近30個交易日賣超+21,488.43千股（約2.1萬張）。",
    "外資近30個交易日賣超21,488.43千股（約2,1萬張）。",
    "外資近30個交易日賣超21,000千股（約2.1萬張）。",
    "外資近30個交易日賣超約2.1萬張。",
    "投信近30個交易日賣超21,488.43千股（約2.1萬張）。",
    "截至2026年10月15日，外資近30個交易日賣超21,488.43千股（約2.1萬張）。",
    "外資近5個交易日賣超21,488.43千股（約2.1萬張）。",
])
def test_alias_does_not_relax_main_value_sign_unit_or_scope(text):
    assert institutional_evidence_issues(text, flow_data())


def test_alias_requires_verified_market_and_cited_evidence():
    text = "外資近30個交易日賣超21,488.43千股（約2.1萬張）。"
    assert institutional_evidence_issues(text, {**flow_data(), "ticker": "TEST"})
    assert institutional_evidence_issues(text, flow_data(), allowed_paths=[])


def pb_issues(text):
    normalized = re.sub(r"[^\S\n]+", "", text)
    return [issue for issue in evaluate_configured_audit_rules(
        4, normalized, has_data_quality_caveat=False) if "負淨值股紅線" in issue]


@pytest.mark.parametrize("text", [
    "股價淨值比（P/B）為1.62x，反映實體資產支撐。不可用固定折讓補造目標價。",
    "股價淨值比（P/B）為1.62x，估值具有吸引力。",
    "股價淨值比（P/B）為0.3x，股東權益為100億元，價格便宜。",
    "股價淨值比（P/B）為0.3x，沒有負淨值，價格便宜。",
    "股價淨值比（P/B）為0.3x，淨利為-5億元，估值便宜。",
    "股價淨值比（P/B）為-0.3x，不可因此推論低估。",
    "股東權益為負，P/B為0.3x，不能認為便宜。",
    "若股東權益為負，P/B不可用於判斷低估。",
    "同業甲公司股東權益為負。乙公司股價淨值比（P/B）為0.8x，估值便宜。",
    "甲公司P/B為-0.3x，不具可比性；乙公司股價淨值比（P/B）為0.8x，估值便宜。",
    "去年股東權益為負。今年股價淨值比（P/B）為0.8x，估值便宜。",
    "股東權益變動為-5億元，股價淨值比（P/B）為0.8x，估值便宜。",
    "股價淨值比（P/B）為-0.3x，已失去意義。營運前景具吸引力。",
    "甲公司股東權益為負，乙公司股價淨值比（P/B）為0.8x，估值便宜。",
    "去年股東權益為負，今年股價淨值比（P/B）為0.8x，估值便宜。",
    "甲公司P/B為0.3x且股東權益為負，乙公司P/B為0.8x，估值便宜。",
    "股價淨值比（P/B）為0.8x，負淨值已消除，估值便宜。",
    "P/B為-0.3x，因此並非便宜，也不應因折讓買入。",
])
def test_pb_rule_requires_bound_negative_evidence_and_actual_endorsement(text):
    assert pb_issues(text) == []


@pytest.mark.parametrize("text", [
    "股價淨值比（P/B）為-0.3x，因此股價便宜。",
    "P/B為-0.3x，因此股價低估。",
    "股價淨值比為-0.3倍，因此股價低估。",
    "公司股東權益為負，股價淨值比（P/B）為0.3x，因此低估。",
    "公司負淨值，P/B為0.3倍，因此便宜。",
    "每股淨值為-5元，P/B為0.3倍，因此便宜。",
    "股東權益為-5億元，P/B為0.3倍，因此便宜。",
    "淨值極低，P/B為0.3倍，因此便宜。",
    "公司股東權益為負。其P/B為0.3倍，因此便宜。",
    "股價淨值比（P/B）為-0.3x，因此股價低估。另有匯率警示。",
    "公司負淨值，P/B為0.3倍，不可認為便宜，但仍然低估。",
    "若股東權益為負，P/B很低就代表便宜，可以買入。",
    "股價便宜，因為P/B為-0.3x。",
    "P/B為-0.3x。因此該P/B代表股價低估。",
    "股東權益為-0.5億元，P/B很低，因此有折讓買入價值。",
])
def test_pb_rule_still_blocks_negative_equity_bargain_logic(text):
    assert pb_issues(text)


@pytest.mark.parametrize('separator', ['。', '。\n', '；\n', '。\r\n'])
def test_parser_scope_pb_explicit_continuation_survives_line_break(separator):
    from financial_output_validator import validate_analysis_output
    text = 'P/B（股價淨值比）為-0.3x' + separator + '因此該P/B代表股價低估。'
    assert pb_issues(text)
    assert any('負淨值股紅線' in issue for issue in validate_analysis_output(4, text, {}))


@pytest.mark.parametrize('separator', ['。\n\n', '；\n\n'])
def test_parser_scope_pb_does_not_inherit_across_a_blank_paragraph(separator):
    text = 'P/B為-0.3x' + separator + '因此該P/B代表股價低估。'
    assert not pb_issues(text)


@pytest.mark.parametrize('local_equity,blocked', [('', False), ('且股東權益為負', True)])
def test_parser_scope_second_pb_uses_its_own_equity(local_equity, blocked):
    from financial_output_validator import validate_analysis_output
    text = ('同業P/B為0.3x且股東權益為負，2330.TW的P/B為0.8x'
            + local_equity + '，估值便宜。')
    assert bool(pb_issues(text)) is blocked
    assert any('負淨值股紅線' in issue for issue in validate_analysis_output(4, text, {})) is blocked


@pytest.mark.parametrize('alias', [
    '（約2.1千張）',
    '（約2.1千張／21,488.43張）',
    '（21,488.43張／約2.1千張）',
    '（21,488.43張）（約2.1千張）',
    '／21,488.43張／約2.1千張',
])
def test_parser_scope_every_adjacent_alias_is_checked(alias):
    from financial_output_validator import validate_analysis_output
    text = '外資近30個交易日賣超21,488.43千股' + alias + '。'
    assert institutional_evidence_issues(text, flow_data())
    assert any('法人' in issue for issue in validate_analysis_output(19, text, flow_data()))


@pytest.mark.parametrize('alias', [
    '（約2.1萬張／21,488.43張）',
    '（21,488.43張／約2.1萬張）',
    '（21,488.43張）（約2.1萬張）',
    '／21,488.43張／約2.1萬張',
])
def test_parser_scope_equivalent_adjacent_aliases_remain_valid(alias):
    text = '外資近30個交易日賣超21,488.43千股' + alias + '。'
    assert institutional_evidence_issues(text, flow_data()) == []


@pytest.mark.skipif(not os.environ.get("FINANCIAL_GATE_REPLAY_STATE"), reason="Private state is opt-in")
def test_private_original_final_audit_replay(monkeypatch):
    from final_audit import run_final_report_audit
    from output_sanitizer import strip_generated_audit_sections
    from structured_output_parser import parse_structured_data

    path = Path(os.environ["FINANCIAL_GATE_REPLAY_STATE"])
    original = path.read_bytes()
    state = json.loads(original)
    context = deepcopy(state)
    context["data"] = context["raw_financial_data"]["input"]
    for key in ("analyses", "structured_outputs"):
        context[key] = {int(k) if k.isdecimal() else k: v for k, v in context[key].items()}
    # Graph snapshots may not persist this derived projection; use the normal parser.
    context["parsed"] = parse_structured_data(context)
    untouched = deepcopy(context)
    per_agent = {}
    for num, raw in context["analyses"].items():
        text = strip_generated_audit_sections(raw)
        per_agent[num] = {"institutional": institutional_evidence_issues(text, context["data"]),
                          "negative_equity_pb": pb_issues(text)}
    audit = run_final_report_audit(context, append_section=False)
    baseline = None
    baseline_dir = os.environ.get("FINANCIAL_GATE_BASELINE_DIR")
    if baseline_dir:
        import financial_output_validator as financial
        import short_term_output_validator as short_term

        def old_module(name):
            spec = importlib.util.spec_from_file_location("baseline_" + name, Path(baseline_dir) / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        old_flow = old_module("institutional_evidence")
        old_rules = old_module("audit_rule_engine")
        old_rules.RULES_FILE = Path(baseline_dir) / "audit_rules.json"
        with monkeypatch.context() as patch:
            patch.setattr(financial, "evaluate_configured_audit_rules", old_rules.evaluate_configured_audit_rules)
            patch.setattr(financial, "institutional_evidence_diagnostics", old_flow.institutional_evidence_diagnostics)
            patch.setattr(short_term, "institutional_evidence_issues", old_flow.institutional_evidence_issues)
            baseline = run_final_report_audit(context, append_section=False)
    print("PRIVATE_REPLAY=" + json.dumps({
        "sha256": hashlib.sha256(original).hexdigest(),
        "saved_critical": state["final_audit"]["critical"],
        "per_agent": per_agent,
        "replayed_status": audit["status"], "replayed_critical": audit["critical"],
        "baseline_critical": baseline["critical"] if baseline else None,
        "removed_critical": [item for item in baseline["critical"] if item not in audit["critical"]] if baseline else None,
        "state_unchanged": context == untouched and path.read_bytes() == original,
    }, ensure_ascii=False))
    assert path.read_bytes() == original
    assert context == untouched
    assert any("約2.1萬張" in item for item in state["final_audit"]["critical"])
    assert any("負淨值股紅線" in item for item in state["final_audit"]["critical"])
    assert not any(per_agent[num]["institutional"] or per_agent[num]["negative_equity_pb"] for num in (11, 4, 21))
    assert not any("括號／並列單位" in item or "負淨值股紅線" in item for item in audit["critical"])
    if baseline:
        removed = [item for item in baseline["critical"] if item not in audit["critical"]]
        assert len(removed) == 4
        assert all("約2.1萬張" in item or "負淨值股紅線" in item for item in removed)
        assert [item for item in baseline["critical"] if item not in removed] == audit["critical"]
