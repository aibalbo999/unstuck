"""Saved production claims bind only to their own dated technical scalar."""
import json
from copy import deepcopy
from pathlib import Path
import pytest
from evidence_exit_gate import evaluate_report_evidence

FIXTURES = json.loads((Path(__file__).parent / 'fixtures/technical_claims_20260922.json').read_text())


def check(text, technical):
    return evaluate_report_evidence(text, {'data': {'technical_indicators': technical,
        'current_price': 2.867, 'quant_metrics': {'atr': 2.867, 'rsi': 2.867}}},
        sample_ratio=1, max_sample=100)['sampled_claims']


@pytest.mark.parametrize('index,value,path,label', [
    (0,4.63,'macd_signal','Signal'), (2,-18.29,'macd_signal','Signal'),
    (1,2.867,'atr_14','ATR'),
])
def test_saved_production_assignments_have_exact_semantic_identity(index,value,path,label):
    row=FIXTURES[index]
    result=next(r for r in check(row['lines'][0], row['technical_indicators']) if r['reported_value']==value)
    assert result['label']==label
    assert result['status']=='verified'
    assert result['matched_path']==f'data.technical_indicators.{path}'
    assert result['candidate_count']==1
    assert label in result['raw_text']


@pytest.mark.parametrize('index,field,value', [(0,'macd_signal',4.63),(1,'atr_14',2.867)])
def test_other_equal_technical_numbers_cannot_replace_claimed_scalar(index,field,value):
    row=FIXTURES[index];technical={**row['technical_indicators'],field:42,'rsi_14':value,'macd':value}
    result=next(r for r in check(row['lines'][0],technical) if r['reported_value']==value)
    assert result['status']=='mismatch'
    assert result['candidate_count']==1


@pytest.mark.parametrize('text', [
    'Signal: 4.63', 'RSI: 88.45, Signal: 4.63',
    'MACD: 7.32。交易 Signal: 4.63', '新聞 MACD: 7.32, Signal: 4.63',
    '昨日 MACD: 7.32, Signal: 4.63', '2026-09-21 MACD: 7.32, Signal: 4.63',
    'MACD: 7.32, Signal: 4.63%', 'MACD: 7.32, Signal: 4.63張',
    'MACD: 7.32, Signal: 4.63, Signal: 9.0',
    'ATR: 2.867%', 'ATR: 2.867張', '昨日 ATR: 2.867', '2026-09-21 ATR: 2.867',
    'ATR_7: 2.867', 'ATR: 2.867, ATR: 42',
])
def test_ambiguous_or_other_date_units_never_verify(text):
    assert all(r['status']!='verified' for r in check(text,FIXTURES[1]['technical_indicators'])
               if r['reported_value'] in {4.63,2.867})


@pytest.mark.parametrize('change', [
    {'source':None}, {'source':'unknown'}, {'as_of':None}, {'as_of':'2026-02-30'},
    {'availability':'unavailable'}, {'atr_14':None}, {'atr_14':True},
    {'atr_14':float('nan')}, {'missing_indicators':['atr_14']}, {'calculation_policy':{}},
])
def test_atr_needs_its_source_date_scalar_and_explicit_period_policy(change):
    row=FIXTURES[1]
    results=check(row['lines'][0],{**row['technical_indicators'],**change})
    assert next(r for r in results if r['reported_value']==2.867)['status']=='unverifiable'


def test_explicit_atr_period_does_not_require_inferred_policy():
    technical={**FIXTURES[1]['technical_indicators'],'calculation_policy':{}}
    assert check('ATR_14: 2.867',technical)[0]['status']=='verified'


@pytest.mark.parametrize('text', [
    'MACD: 7.32, Signal: 4.63, macd_signal: 9.0',
    'ATR: 2.867, ATR_14: 42',
    'MACD: 7.32, Trading Signal: 4.63',
    'MACD: 7.32, 成交量 Signal: 4.63',
])
def test_alias_collision_or_explicit_other_signal_subject_cannot_verify(text):
    result=check(text,FIXTURES[0 if 'Signal' in text else 1]['technical_indicators'])
    assert result
    assert all(r['status']!='verified' for r in result if r['reported_value'] in {4.63,2.867})


def test_true_zero_atr_remains_a_numeric_observation():
    assert check('ATR_14: 0',{**FIXTURES[1]['technical_indicators'],'atr_14':0})[0]['status']=='verified'
