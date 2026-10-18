from copy import deepcopy
import pytest
from evidence_exit_gate import evaluate_report_evidence
from report_source_admission import report_source_admission


def snapshot(setup=None, ticker='1514.TW'):
    value={'data':{'ticker':ticker,'quote_type':'EQUITY','current_price':100.0,
                   'daily_market_data':{'as_of':'2026-10-02'},
                   'institutional_trading':{'latest_date':'2026-10-02'}}}
    if setup is not None:value['rerun_context']={'parsed':{'trade_setup':setup}}
    return value


@pytest.mark.parametrize('setup',[None,{}, {'trade_direction':'Neutral'}])
def test_matched_numbers_do_not_approve_missing_raw_sources_without_an_order(setup):
    value=snapshot(setup);before=deepcopy(value)
    gate=evaluate_report_evidence('- 股價: NT$100.00',value)
    assert gate['verified_count']>0
    assert gate['verdict']=='caution'
    admission=gate['source_admission']
    assert admission['source_eligible'] is False and admission['eligible'] is False
    assert admission['source_warnings'] and not admission['blockers']
    assert not admission['order_gate_applicable'] and not admission['actionable']
    assert value==before


def test_malformed_oos_context_cannot_skip_source_disclosure():
    value=snapshot();value['oos_evaluation_inputs']=b'invalid mapping'
    gate=evaluate_report_evidence('- 股價: NT$100.00',value)
    assert gate['verdict']=='caution' and gate['source_admission']['source_eligible'] is False


@pytest.mark.parametrize('direction',['Long','Short'])
def test_active_orders_still_fail_closed_with_missing_raw_sources(direction):
    value=snapshot({'trade_direction':direction,'entry_zone':'10','target_price':'12','stop_loss':'9'})
    gate=evaluate_report_evidence('- 股價: NT$100.00',value)
    assert gate['verdict']=='rejected' and gate['source_admission']['blockers']


def test_unknown_instrument_type_is_not_inferred_for_a_non_order_report():
    value=snapshot();value['data']['ticker']='6715.TW';value['data'].pop('quote_type')
    result=report_source_admission(value['data'],{})
    assert result['price_grid']['status']=='unverified'
    assert result['price_grid']['instrument_type'] is None
    assert result['order_review_proposal']['status']=='unavailable'
    assert not result['eligible'] and not result['actionable']


def test_other_market_numeric_gate_is_not_changed():
    gate=evaluate_report_evidence('- 股價: NT$100.00',snapshot(ticker='EXAMPLE.US'))
    assert gate['verdict']=='approved' and gate['source_admission'] is None


def test_verified_source_seam_preserves_numeric_approval_without_an_order(monkeypatch):
    import report_source_admission as source
    monkeypatch.setattr(source,'institutional_admission',lambda *a:{'eligible':True,'reason':'isolated verified source fixture'})
    monkeypatch.setattr(source,'price_admission',lambda *a:{'eligible':True,'reason':'isolated verified source fixture'})
    gate=evaluate_report_evidence('- 股價: NT$100.00',snapshot())
    assert gate['verdict']=='approved' and gate['source_admission']['source_eligible'] is True
    assert not gate['source_admission']['actionable']
