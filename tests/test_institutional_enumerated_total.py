"""Narrow same-sentence same-window aggregate for the actual round2 canary."""
import json
from pathlib import Path
import pytest
from institutional_evidence import institutional_evidence_issues


@pytest.fixture
def fixture():
    return json.loads((Path(__file__).parent/'fixtures/institutional_2033_round2.json').read_text())


def test_actual_last_candidate_same_period_three_component_aggregate(fixture):
    raw = fixture['original_responses'][3]
    assert institutional_evidence_issues(raw, fixture['data']) == []
    parsed=json.loads(raw)
    assert institutional_evidence_issues(parsed['analysis_markdown'], fixture['data']) == []


@pytest.mark.parametrize('index', [0, 1, 2])
def test_original_wrong_population_and_switched_period_remain_blocked(fixture,index):
    assert institutional_evidence_issues(fixture['original_responses'][index], fixture['data'])


BASE = '近30日，外資買超1528.58千股，自營商買超70.67千股，投信無佈局（0千股），合計總買超1599.24千股。'


def test_flow_prose_does_not_take_following_credit_balance_as_its_amount(fixture):
    assert institutional_evidence_issues('法人買賣超呈現拉鋸，且融資餘額處於2,537張。', fixture['data']) == []


@pytest.mark.parametrize('text', [
    '外資近5日呈現集中買超，累計達1576.69千股。',
    '法人近5日買超1,576.69千張。',
])
def test_explicit_cumulative_flow_still_checks_population_and_unit(fixture, text):
    assert institutional_evidence_issues(text, fixture['data'])


@pytest.mark.parametrize('text', [
    BASE.replace('，投信無佈局（0千股）', ''),
    BASE.replace('投信無佈局（0千股）', '外資買超1528.58千股'),
    BASE.replace('，合計總', '，最近5日合計總'),
    BASE.replace('，合計總', '，2026-09-21合計總'),
    BASE.replace('，合計總', '，總'),
    BASE.replace('投信無佈局（0千股）', '投信未知'),
    BASE.replace('合計總買超1599.24', '合計總買超1576.69'),
    BASE.replace('1599.24千股', '1599.24千張'),
])
def test_incomplete_ambiguous_or_wrong_aggregate_remains_blocked(fixture,text):
    assert institutional_evidence_issues(text, fixture['data'])
