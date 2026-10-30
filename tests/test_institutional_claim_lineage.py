import copy
from institutional_claim_lineage import institutional_claim_lineage
from reporting.content_credibility_trade_basis import evaluate_trade_basis
from trade_source_contract import source_catalog,resolve_reference,reference_is_evidence,allowed_source_refs

import pytest

@pytest.fixture(autouse=True)
def replay_observation_date(monkeypatch):
    import trade_source_contract as contract
    original = contract.build_short_term_market_context
    # source_catalog now supplies an explicit Taipei evaluation date. This
    # historical lineage fixture owns its replay date and replaces that keyword
    # once; it must not pass two as_of arguments before the assertions can run.
    monkeypatch.setattr(contract, 'build_short_term_market_context',
        lambda data, **kwargs: original(data, **{**kwargs, 'as_of': '2026-10-02'}))


def fixture():
    rows=[{'date':'2026-10-02','category':category,'net_buy_shares':value,'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell','unit':'shares'} for category,value in [('foreign',1234),('investment_trust',0),('dealer',-34)]]
    return {'ticker':'1301.TW','institutional_trading':{'source':'FinMind TaiwanStockInstitutionalInvestorsBuySell','latest_date':'2026-10-02','lookback_trading_days':1,'daily_category_observations':rows,'net_buy_thousand_shares_by_category':{'foreign':1.23},'fetched_at_epoch':1790935241}}


def record():return {'population':'foreign','window':{'kind':'trailing_trading_days','trading_days':1},'observed_at':'2026-10-02','value':1.23,'unit':'thousand_shares','provider':'FinMind TaiwanStockInstitutionalInvestorsBuySell'}


def test_recompute_rounding_does_not_claim_primary_verification():
    r=institutional_claim_lineage(fixture(),record());assert r['status']=='recomputed' and r['recomputed_shares']==1234
    assert not r['independent_primary_source_verified'] and r['normalized_observations_sha256']


def test_changed_input_duplicate_missing_units_and_dates_fail_closed():
    data=fixture();data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']=2000
    assert institutional_claim_lineage(data,record())['status']=='mismatch'
    data=fixture();data['institutional_trading']['daily_category_observations']*=2
    assert institutional_claim_lineage(data,record())['reason']=='missing_or_duplicate_category_observations'
    data=fixture();data['institutional_trading']['daily_category_observations'][0]['unit']='lots'
    assert institutional_claim_lineage(data,record())['status']=='unavailable'
    data=fixture();r=record();r['window']['trading_days']=2
    assert institutional_claim_lineage(data,r)['reason']=='exchange_session_window_incomplete'


def test_report_direction_blocked_by_contradictory_underlying_rows():
    data=fixture();catalog=source_catalog(data);refs=['short_term_market_context.institutional_evidence.records[0]']
    setup={'core_catalyst':'截至2026-10-02，外資近1個交易日淨買超1.23千股。','catalyst_source_refs':refs}
    context={'parsed':{'trade_setup':setup}}
    assert not evaluate_trade_basis(context,data,'v4')['blocking_issues']
    data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']=2000
    assert any(r['id']=='v4_institutional_lineage_mismatch' for r in evaluate_trade_basis(context,data,'v4')['blocking_issues'])


def test_mismatched_institutional_record_is_not_offered_as_a_citable_source():
    data=fixture();ref='short_term_market_context.institutional_evidence.records[0]'
    assert reference_is_evidence(source_catalog(data),ref,'catalyst_source_refs')
    data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']=2000
    catalog=source_catalog(data)
    assert catalog['short_term_market_context']['institutional_evidence']['records'][0]['lineage_status']=='mismatch'
    assert not reference_is_evidence(catalog,ref,'catalyst_source_refs')
    assert ref not in allowed_source_refs(catalog)['catalyst_source_refs']
    assert data['institutional_trading']['daily_category_observations'][0]['net_buy_shares']==2000


def test_actual_institutional_assertion_without_refs_is_blocked_but_wait_is_not():
    context={'parsed':{'trade_setup':{'core_catalyst':'外資持續買超，籌碼集中'}}}
    assert any(issue['id']=='v4_trade_reason_source_missing' for issue in evaluate_trade_basis(context,fixture(),'v4')['blocking_issues'])
    context['parsed']['trade_setup']['core_catalyst']='等待技術及法人確認'
    assert not evaluate_trade_basis(context,fixture(),'v4')['blocking_issues']


def test_provider_receipt_cannot_be_relabelled():
    data=fixture();data['institutional_trading']['daily_category_observations'][0]['source']='unknown provider'
    assert institutional_claim_lineage(data,record())['reason']=='provider_dataset_mismatch'


def test_malformed_legacy_shapes_return_unknown_without_exception():
    data=fixture();data['institutional_trading']=[]
    assert institutional_claim_lineage(data,record())['status']=='unavailable'
    data=fixture();r=record();r['window']=['bad']
    assert institutional_claim_lineage(data,r)['reason']=='window_unknown'
    data['institutional_trading']['daily_category_observations'][0]['source']={'bad':'value'}
    assert institutional_claim_lineage(data,record())['reason']=='invalid_observation_value_unit_or_source'
