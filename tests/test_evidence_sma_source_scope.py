"""Real retained report claims must bind only to their dated SMA period."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from evidence_exit_gate import evaluate_report_evidence
from evidence_exit_gate_claims import extract_numeric_claims

ROWS=json.loads((Path(__file__).parent/'fixtures/sma_source_scope_20260922.json').read_text())

def claims(text, technical):
    return evaluate_report_evidence(text, {'data':{'technical_indicators':technical}}, sample_ratio=1, max_sample=100)['sampled_claims']

@pytest.mark.parametrize('index,value,field', [(0,127.0,'sma_20'),(0,124.05,'sma_60'),(1,40.58,'sma_10'),(1,46.97,'sma_5'),(2,38.98,'sma_10')])
def test_saved_same_date_sma_assignment_binds_exact_source(index,value,field):
    row=ROWS[index]
    claim=next(c for c in claims(row['lines'][0],row['technical_indicators']) if c['reported_value']==value)
    assert claim['status']=='verified'
    assert claim['matched_path']==f'data.technical_indicators.{field}'
    assert claim['candidate_count']==1

@pytest.mark.parametrize('text',[
    '收盤價147元（SMA20: 127.0元），2026-09-15',
    '收盤價147元（EMA20: 127.0元），2026-09-16',
    '成交量（SMA20: 127.0張），2026-09-16',
    '昨日收盤價147元（SMA20: 127.0元），2026-09-16',
    '預估（SMA20: 127.0元），2026-09-16',
    '成交量 SMA20: 127.0，2026-09-16',
    '收盤價147元（SMA20: 127.0，SMA20: 128.0），2026-09-16',
    '收盤價147元（SMA200: 127.0元），2026-09-16',
])
def test_other_date_basis_unit_duplicate_or_period_cannot_borrow_price_sma(text):
    assert all(c['status']!='verified' for c in claims(text,ROWS[0]['technical_indicators']))


def test_wrong_sma_value_does_not_borrow_equal_other_period_or_volume():
    technical={**ROWS[0]['technical_indicators'],'sma_20':80,'sma_200':127,'volume_sma_20':127}
    result=next(c for c in claims('收盤價147元（SMA20: 127.0元），2026-09-16',technical) if c['reported_value']==127)
    assert result['status']=='mismatch'
    assert result['matched_path']=='data.technical_indicators.sma_20'


def test_citation_counter_evidence_truncation_is_not_a_financial_claim():
    text=ROWS[3]['lines'][0]
    assert text.endswith('；反證：2')
    assert not any(c['reported_value']==2 for c in extract_numeric_claims(text))

@pytest.mark.parametrize('text', [
    '本益比：20；反證：EPS：2元',
    '本益比：20（來源：financials）；反證：毛利率：2%',
    '反證：EPS由3元降至2元；EPS：2元',
    '反證：2元',
])
def test_genuine_counter_evidence_financial_number_is_not_silenced(text):
    assert any(c['reported_value']==2 for c in extract_numeric_claims(text))
