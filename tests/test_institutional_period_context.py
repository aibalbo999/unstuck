"""Canary-shaped as-of and complete-population phrases must retain their scope."""
import pytest
from institutional_evidence import institutional_evidence_issues
from test_institutional_evidence import data


@pytest.mark.parametrize('claim', [
    '近30個交易日（截至2026-09-21）三大法人合計淨買超1599.24千股（其中外資淨買超1528.58千股、投信淨買超0千股、自營商淨買超70.67千股）。',
    '外資、投信與自營商在近30個交易日合計呈現淨買超1599.24千股，但近5個交易日合計買超1576.69千股。',
    '自營商與投信、外資近30個交易日合計淨買超1599.24千股。',
])
def test_valid_as_of_period_and_all_three_population_total(data, claim):
    assert institutional_evidence_issues(claim, data) == []


@pytest.mark.parametrize('claim', [
    '近30個交易日（截至2026-09-20）三大法人合計淨買超1599.24千股。',
    '近30個交易日（截至2026-09-21）三大法人合計淨買超1599.24千張。',
    '近30個交易日（截至2026-09-21）三大法人合計淨買超1576.69千股。',
    '近30個交易日2026-09-21單日法人合計淨買超1599.24千股。',
    '近30個交易日（截至2026-09-21）2026-09-18單日法人買超21.74千股。',
    '近30個交易日（截至2026-09-21）三大法人合計買超1599.24千股（其中外資近5日買超1528.58千股）。',
    '外資、投信近30日合計淨買超1599.24千股。',
    '外資與自營商近30日合計淨買超70.67千股。',
    '外資、投信與自營商近30日淨買超1599.24千股。',
    '外資、外資與自營商近30日合計淨買超1599.24千股。',
])
def test_wrong_date_unit_period_or_incomplete_population_remains_rejected(data, claim):
    assert institutional_evidence_issues(claim, data)


@pytest.mark.parametrize('index', [1, 2])
def test_real_3324_corrected_candidates_keep_the_verified_institutional_scope(index):
    import json
    from pathlib import Path
    fixture=json.loads((Path(__file__).parent/'fixtures/institutional_3324_canary.json').read_text())
    original=fixture['original_responses'][index]
    parsed=json.loads(original)
    assert institutional_evidence_issues(original, fixture['data']) == []
    assert institutional_evidence_issues(parsed['analysis_markdown'], fixture['data']) == []
    for item in parsed['evidence_items']:
        assert institutional_evidence_issues(item['finding'], fixture['data']) == []
