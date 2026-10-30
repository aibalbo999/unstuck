"""Each stated FCF amount retains its own period and numeric denominator."""
from copy import deepcopy
import pytest
from test_official_financial_claim_binding import projected


def data():
    value=projected()
    value.update(years=['2024','2025'],fcf_history=[0.08,-0.23])
    return value


def result(text, value=None):
    from evidence_exit_gate import evaluate_report_evidence
    return evaluate_report_evidence(text, {'data':data() if value is None else value})


def annual(text):
    return next(c for c in result(text)['sampled_claims'] if c.get('reported_value') in (-0.23,-2.3))


@pytest.mark.parametrize('text', [
    '主因為 2025 年度 FCF 為 -0.23 億元，且最新官方 TTM FCF（至 2026-06-30）為 0.0885 億元。',
    '- **內在價值計算限制**：根據 `quant_metrics.v2`，DCF 狀態為 **unavailable**。主因為 2025 年度 FCF 為 -0.23 億元，且最新官方 TTM FCF（至 2026-06-30）為 0.0885 億元。',
    'TTM FCF為0.0885億元，且主因為2025年度FCF為-0.23億元。',
    '2024年度FCF為0.8億元；主因為2025年度FCF為-0.23億元，且TTM FCF為0.0885億元。',
])
def test_annual_tenfold_error_is_not_hidden_by_other_ttm_amount(text):
    from financial_money_claims import financial_money_claim_issues
    assert financial_money_claim_issues(text, data())
    claim=annual(text)
    assert claim['status']=='mismatch',claim
    assert claim['matched_path']=='data.fcf_history[1]'
    assert claim['financial_period']=='2025'
    assert claim['expected_value_raw_twd']==-230000000
    assert claim['independent_primary_source_verified'] is False
    fixed=annual(text.replace('-0.23','-2.3'))
    assert fixed['status']=='verified',fixed


@pytest.mark.parametrize('text', [
    '本公司TTM FCF（至2026-06-30）為0.0885億元。',
    '主因為2025年度FCF為-2.3億元，且最新官方TTM FCF（至2026-06-30）為0.0885億元。',
])
def test_date_between_metric_and_amount_keeps_ttm_in_denominator(text):
    r=result(text)
    assert r['coverage_complete']
    c=next(c for c in r['sampled_claims'] if c.get('reported_value')==0.0885)
    assert c['financial_amount']
    assert c['raw_text']==text
    assert c['status']!='mismatch'


@pytest.mark.parametrize('prefix', ['同業華通','華通','美元','本集團合併','預估','若未來'])
def test_causal_intro_does_not_remove_foreign_owner_currency_or_condition(prefix):
    claim=annual('主因為'+prefix+'2025年度FCF為-0.23億元，且本公司TTM FCF為0.0885億元。')
    assert claim['status']=='unverifiable',claim


def test_unknown_year_and_input_immutable():
    value=data();before=deepcopy(value)
    r=result('主因為年度FCF為-0.23億元，且TTM FCF為0.0885億元。',value)
    assert next(c for c in r['sampled_claims'] if c.get('reported_value')==-0.23)['status']=='unverifiable'
    assert value==before


@pytest.mark.parametrize('prefix', ['華通，','同業華通：','美元資料，','某分部，'])
def test_ambiguous_preamble_is_not_erased_by_causal_intro(prefix):
    claim=annual(prefix+'主因為2025年度FCF為-0.23億元，且TTM FCF為0.0885億元。')
    assert claim['status']=='unverifiable',claim


@pytest.mark.parametrize('qualifier',['（同業大亞）','（合併報表口徑）','（歐元）','（預期數值）','（2024年度）'])
def test_causal_annual_postfix_keeps_unknown_owner_scope_and_period(qualifier):
    claim=annual('主因為2025年度FCF為-2.3億元'+qualifier+'，且最新官方TTM FCF（至2026-06-30）為0.0885億元。')
    assert claim['status']=='unverifiable',claim


def test_causal_annual_direction_is_not_discarded():
    assert annual('主因為2025年度FCF為-2.3億元（淨流入），且TTM FCF為0.0885億元。')['status']=='mismatch'
    assert annual('主因為2025年度FCF為-2.3億元（淨流出），且TTM FCF為0.0885億元。')['status']=='verified'


@pytest.mark.parametrize('qualifier',['此為同業大亞的資料','此為合併報表口徑'])
def test_causal_annual_cannot_search_past_comma_qualifier_for_later_ttm(qualifier):
    claim=annual('主因為2025年度FCF為-2.3億元，'+qualifier+'，且最新官方TTM FCF（至2026-06-30）為0.0885億元。')
    assert claim['status']=='unverifiable',claim
