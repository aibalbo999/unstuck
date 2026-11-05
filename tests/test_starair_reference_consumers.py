from copy import deepcopy
import pytest
from test_starair_reference_evidence import individual_environment,DAY


def row_with_individual_proof():
    from data_fetch.market_sources.peers import PEER_METRIC_FIELDS
    from data_fetch.market_sources.starair_reference_evidence import collect_reference_income
    row={key:1.0 for key in PEER_METRIC_FIELDS}
    row.update(ticker='2646.TW',name='星宇航空',pe_ttm=None,
        pe_applicability_evidence=collect_reference_income('2646.TW','2026-11-03',today=DAY),
        metric_applicability={key:'applicable'for key in PEER_METRIC_FIELDS},
        metric_sources={key:{'provider':'fixture source','observed_at':'2026-06-30','basis':'annual_revenue / same_date_year_end_assets'if key=='asset_turnover'else'fixture'}for key in PEER_METRIC_FIELDS if key!='pe_ttm'},
        missing_metrics=['pe_ttm'],metrics_status='partial')
    return row


def test_individual_field_reason_requires_all_originals_for_complete_status(individual_environment):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from data_trust import source_record_count
    from thermal_peer_source_refresh import _usable_metrics
    row=row_with_individual_proof();reassess_reference_applicability(row,today=DAY)
    assert row['pe_ttm']is None and row['metrics_status']=='complete'and row['missing_metrics']==[]
    assert row['pe_applicability_evidence']['scope']=='individual_issuer_income'
    assert _usable_metrics(row,DAY)is True
    assert source_record_count('dynamic_peer_metrics',{'dynamic_peer_metrics':[row]})==1


@pytest.mark.parametrize('damage',['owner','public_scope','typed_issuer','amount'])
def test_invalid_individual_reason_cannot_promote_undefined_PE(individual_environment,damage):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from data_trust import source_record_count
    row=row_with_individual_proof();proof=row['pe_applicability_evidence'];reassess_reference_applicability(row,today=DAY)
    if damage=='owner':individual_environment[1].clear()
    elif damage=='public_scope':proof['scope']='consolidated_parent_income'
    elif damage=='typed_issuer':row['ticker']='6230.TW'
    else:proof['source_record_archive']['derived']['net_income_twd']-=1
    assert source_record_count('dynamic_peer_metrics',{'dynamic_peer_metrics':[row]})==0
    reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='partial'and row['missing_metrics']==['pe_ttm']


def test_another_missing_metric_is_not_hidden_by_individual_income_reason(individual_environment):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    row=row_with_individual_proof();row['gross_margin_pct']=None;row['metric_sources'].pop('gross_margin_pct')
    reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='partial'and row['missing_metrics']==['gross_margin_pct']


def test_existing_numeric_path_cannot_be_overridden_by_individual_fallback(monkeypatch):
    from data_fetch.market_sources import starair_reference_evidence as e
    from data_fetch.market_sources.peer_recovery import _attach_reference_income
    monkeypatch.setattr(e,'collect_reference_income',lambda *a,**k:pytest.fail('numeric P/E must stay on existing path'))
    row={'metrics':{'pe_ttm':20.0}}
    assert _attach_reference_income(row,{'official_company_name':'星宇航空','observed_at':'2026-11-03'},'2646.TW',DAY)==row


def test_fallback_dispatch_is_exact_starair_only_and_keeps_unknown_failures(monkeypatch):
    from data_fetch.market_sources import starair_reference_evidence as e
    from data_fetch.market_sources.peer_recovery import _attach_reference_income
    calls=[]
    def collect(*args,**kwargs):calls.append(args);raise ValueError('individual period not verified')
    monkeypatch.setattr(e,'collect_reference_income',collect)
    result=_attach_reference_income({'metrics':{'pe_ttm':None}},{'official_company_name':'星宇航空','observed_at':'2026-11-03'},'2646.TW',DAY)
    assert calls==[('2646.TW','2026-11-03')]
    assert result['attempts'][-1]['status']=='unavailable'and 'pe_applicability_evidence'not in result
    before=len(calls)
    _attach_reference_income({'metrics':{'pe_ttm':None}},{'official_company_name':'other','observed_at':'2026-11-03'},'2646.TW',DAY)
    _attach_reference_income({'metrics':{'pe_ttm':None}},{'official_company_name':'星宇航空','observed_at':'2026-11-03'},'6558.TW',DAY)
    assert len(calls)==before


def test_normal_fallback_preserves_valid_numeric_cache_and_never_refetches_auxiliary_proof(individual_environment,monkeypatch):
    from data_fetch.market_sources import peer_recovery,official_peer_valuation,taiwan
    e,store,calls,master=individual_environment
    monkeypatch.setattr(taiwan,'DataLoader',None)
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',lambda *a,**k:{'metrics':{'pb':1.92},'status':'success','source':official_peer_valuation.PROVIDER,'official_company_name':'星宇航空','observed_at':'2026-11-03'})
    result=peer_recovery.fetch_peer_valuation_fallback('2646.TW',today=DAY)
    assert result['metrics']=={'pb':1.92}and result['pe_applicability_evidence']['scope']=='individual_issuer_income'
    before=deepcopy(store);count=len(calls)
    warm=peer_recovery.fetch_peer_valuation_fallback('2646.TW',today=DAY)
    assert warm['cache_hit']is True and len(calls)==count and store==before
    key=next(key for key in store if key.startswith('shared_provider:'))
    store.pop(key);before=deepcopy(store)
    stale=peer_recovery.fetch_peer_valuation_fallback('2646.TW',today=DAY)
    assert stale['metrics']=={'pb':1.92}and 'pe_applicability_evidence'not in stale
    assert store==before and len(calls)==count
