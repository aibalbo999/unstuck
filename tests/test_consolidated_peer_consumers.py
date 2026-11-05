"""New issuer reasons remain nonnumeric and revalidate on normal cache delivery."""
from copy import deepcopy
import pytest
from test_consolidated_peer_evidence import environment6558, normal_frame
from test_peer_reference_evidence import evidence_environment, DAY


def proof_row():
    from data_fetch.market_sources.peers import PEER_METRIC_FIELDS
    from data_fetch.market_sources.peer_reference_evidence import collect_reference_income
    with normal_frame(): reason=collect_reference_income('6558.TW',DAY.isoformat(),today=DAY)
    row={k:1.0 for k in PEER_METRIC_FIELDS}
    row.update(ticker='6558.TW',name='興能高',pe_ttm=None,pe_applicability_evidence=reason,
        metric_sources={k:{'provider':'fixture','observed_at':'2026-06-30','basis':'annual_revenue / same_date_year_end_assets'if k=='asset_turnover'else'fixture'}for k in PEER_METRIC_FIELDS if k!='pe_ttm'},
        missing_metrics=['pe_ttm'],metrics_status='partial')
    return row


def test_normal_counter_accepts_verified_reason_only_while_every_other_field_is_available(environment6558):
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    from data_trust_audit import source_record_count
    from thermal_peer_source_refresh import _usable_metrics
    row=proof_row();reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='complete'and row['pe_ttm']is None
    assert source_record_count('dynamic_peer_metrics',{'dynamic_peer_metrics':[row]})==1
    assert _usable_metrics(row,DAY)
    row['pb']=None;reassess_reference_applicability(row,today=DAY)
    assert row['metrics_status']=='partial'and row['missing_metrics']==['pb']


def test_original_owner_loss_restores_missing_PE_and_never_leaks_private_money_or_paths(environment6558):
    import json
    from prompt_evidence import prompt_evidence_copy
    from data_fetch.market_sources.peer_reference_applicability import reassess_reference_applicability
    row=proof_row();before=deepcopy(row);public=json.dumps(prompt_evidence_copy(row))
    assert 'raw_response_path'not in public and 'net_income_twd'not in public and row==before
    environment6558[0].clear();reassess_reference_applicability(row,today=DAY)
    assert row['missing_metrics']==['pe_ttm']and row['metric_applicability']['pe_ttm']=='applicable'


def test_normal_fallback_uses_original_numeric_key_and_keeps_valid_cache_epochs(environment6558,monkeypatch):
    from data_fetch.market_sources import peer_recovery,official_peer_valuation,taiwan
    monkeypatch.setattr(taiwan,'DataLoader',None)
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',lambda *args,**kwargs:{'metrics':{'pb':1.25},'status':'success','source':official_peer_valuation.PROVIDER,'official_company_name':'興能高','observed_at':DAY.isoformat()})
    with normal_frame():result=peer_recovery.fetch_peer_valuation_fallback('6558.TW',today=DAY)
    assert result['metrics']=={'pb':1.25}and'pe_applicability_evidence'in result
    store,calls,_=environment6558;before=deepcopy(store);count=len(calls)
    warm=peer_recovery.fetch_peer_valuation_fallback('6558.TW',today=DAY)
    assert warm['cache_hit']is True and store==before and len(calls)==count
    store.pop(next(k for k in store if k.startswith('shared_provider:')));before=deepcopy(store)
    stale=peer_recovery.fetch_peer_valuation_fallback('6558.TW',today=DAY)
    assert stale['metrics']=={'pb':1.25}and'pe_applicability_evidence'not in stale
    assert store==before and len(calls)==count


def test_positive_numeric_PE_does_not_launch_reference_source(environment6558,monkeypatch):
    from data_fetch.market_sources import peer_recovery,official_peer_valuation,taiwan
    monkeypatch.setattr(taiwan,'DataLoader',None)
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',lambda *a,**kw:{'metrics':{'pe_ttm':12,'pb':1.25},'status':'success','source':official_peer_valuation.PROVIDER,'official_company_name':'興能高','observed_at':DAY.isoformat()})
    with normal_frame():value=peer_recovery.fetch_peer_valuation_fallback('6558.TW',today=DAY)
    assert value['metrics']['pe_ttm']==12 and not environment6558[1]


@pytest.mark.parametrize('sdk_pe', [None,-20,0])
def test_normal_peer_loop_delivers_verified6558_reason_under_the_original_quality_gate(environment6558,monkeypatch,sdk_pe):
    from data_fetch.market_sources import peers,official_peer_valuation,taiwan
    monkeypatch.setattr(peers,'_today',lambda:DAY)
    monkeypatch.setattr(taiwan,'DataLoader',None)
    monkeypatch.setattr(peers,'load_peer_stock_master',lambda:[])
    monkeypatch.setattr(peers,'resolve_legacy_peer_candidates',lambda *a,**kw:([
        {'ticker':'6558.TW','name':'興能高','identity_status':'master_verified',
         'comparison_status':'industry_candidate_only','industry_categories':['其他電子業']}],
        {'selection_status':'selected','selection_rejected_reason_counts':{}}))
    monkeypatch.setattr(peers.yf,'Ticker',lambda symbol:type('Quote',(),{'info':{
        'symbol':symbol,'quoteType':'EQUITY','industry':'Electrical Equipment & Parts','trailingPE':sdk_pe,
        'grossMargins':.2,'operatingMargins':.1,'profitMargins':.05,'returnOnEquity':.1,
        'totalRevenue':100,'totalAssets':200,'priceToSalesTrailing12Months':3}})())
    monkeypatch.setattr(official_peer_valuation,'fetch_official_peer_valuation',lambda *a,**kw:{
        'metrics':{'pb':1.25},'status':'success','source':official_peer_valuation.PROVIDER,
        'official_company_name':'興能高','observed_at':DAY.isoformat()})
    with normal_frame():
        result=peers.fetch_dynamic_peer_metrics_with_diagnostics('6409.TW','fixture target',
            'Industrials','Electrical Equipment & Parts',{})
    assert len(result['peers'])==1
    row=result['peers'][0]
    assert row['ticker']=='6558.TW'and row['pe_ttm']is None and row['metrics_status']=='complete'
    assert result['audit']['coverage_status']=='success'
