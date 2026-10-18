"""Saved 1229 single-day values must bind separately, never to their sum."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics

CASE = json.loads((Path(__file__).parent / "fixtures/source_acquisition/institutional_1229_daily_pair_20261009.json").read_text())


def test_saved_correct_two_daily_values_are_not_compared_to_two_day_sum():
    assert institutional_evidence_issues(CASE["text"], CASE["data"]) == []


@pytest.mark.parametrize("old,new", [("523.37", "999"), ("846.27", "999"), ("千股", "千張"),
                                   ("10/07", "10/06"), ("法人合計", "外資"), ("淨買超", "淨賣超")])
def test_wrong_value_unit_date_population_and_direction_remain_blocked(old, new):
    assert institutional_evidence_issues(CASE["text"].replace(old, new), CASE["data"])


def test_each_daily_source_must_be_present_and_visible():
    data = deepcopy(CASE["data"])
    data["institutional_trading"]["daily_total_net_buy_last_10"].pop()
    assert institutional_evidence_issues(CASE["text"], data)
    paths = ["institutional_trading.daily_total_net_buy_last_10[8].net_buy_thousand_shares"]
    assert institutional_evidence_issues(CASE["text"], CASE["data"], allowed_paths=paths)


def test_bad_second_value_is_diagnosed_against_second_day():
    bad = CASE["text"].replace("846.27", "999")
    diagnostics = institutional_evidence_diagnostics(bad, CASE["data"])
    assert len(diagnostics) == 1
    assert diagnostics[0]["window"] == {"kind": "day", "date": "2026-10-08"}


def test_a_third_value_or_conflicting_period_is_not_silently_discarded():
    text = CASE["text"].rstrip("。")
    for tail in ("與999千股。", "（近5日）。", "（2025-10-08）。"):
        assert institutional_evidence_issues(text + tail, CASE["data"])


def test_actual_two_day_sum_and_a_single_day_cannot_be_substituted():
    assert institutional_evidence_issues("10/07與10/08法人合計淨買超1369.64千股。", CASE["data"]) == []
    assert institutional_evidence_issues("10/07與10/08法人合計淨買超523.37千股。", CASE["data"])


@pytest.mark.parametrize("prefix,tail", [
    ("10/06 至 ", ""), ("10/06與", ""), ("", "（外資）"),
    ("", "（投信）"), ("", "（自營商）"),
    ("110/07與", ""), ("114/10/07與", ""),
])
def test_new_pair_grammar_cannot_ignore_another_date_or_population(prefix, tail):
    text = prefix + CASE["text"].rstrip("。") + tail + "。"
    assert institutional_evidence_issues(text, CASE["data"])


@pytest.mark.parametrize("date", ["110/07", "114/10/07", "114年10月07日"])
def test_invalid_or_roc_date_prefix_is_not_discarded(date):
    assert institutional_evidence_issues(CASE["text"].replace("10/07", date), CASE["data"])
