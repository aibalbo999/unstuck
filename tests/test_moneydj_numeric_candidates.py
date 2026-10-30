"""Offline public checks; original-data replay remains in the local private corpus."""
"""Published candidates may gain numbers without becoming valuation comparables."""

from datetime import date

import pytest

TODAY = date(2026, 10, 9)

MASTER = [{"stock_id":code,"stock_name":name,"type":market,"date":TODAY.isoformat()}
          for code,name,market in [("5314","世紀*","tpex"),("1294","漢田生技","tpex"),
                                   ("1295","生合","tpex"),("1707","葡萄王","twse")]]

def metric_plan(monkeypatch, *, missing=False, wrong_identity=False, mixed_period_assets=False,
                annual_missing=False, cohort_audit=None):
    from data_fetch.market_sources import peers
    candidates=[{"ticker":r["stock_id"]+(".TW" if r["type"]=="twse" else ".TWO"),
                 "name":r["stock_name"],"comparison_status":"published_segment_candidate",
                 "business_comparability_verified_current":False,
                 "comparison_scope":"publisher_food_biotech_candidates"} for r in MASTER[1:]]
    monkeypatch.setattr(peers,"load_peer_stock_master",lambda:MASTER)
    monkeypatch.setattr(peers,"resolve_legacy_peer_candidates",lambda *a,**k:([],{"selection_status":"broad_industry_only"}))
    monkeypatch.setattr(peers,"documented_peer_candidates",lambda *a,**k:[])
    monkeypatch.setattr(peers,"get_published_food_biotech_candidates",lambda *a,**k:{"candidates":candidates,"status":"success","source_audit":cohort_audit},raising=False)
    class Stock:
        def __init__(self,symbol):self.symbol=symbol
        @property
        def info(self):
            return {"symbol":"2330.TW" if wrong_identity else self.symbol,"quoteType":"EQUITY",
                    "industry":"Biotechnology","trailingPE":18.,"priceToBook":1.2,
                    "priceToSalesTrailing12Months":None if missing else 1.1,
                    "grossMargins":.15,"operatingMargins":.08,"profitMargins":.07,"returnOnEquity":.12,
                    "totalRevenue":1000 if mixed_period_assets else None,
                    "totalAssets":10000 if mixed_period_assets else None}
    monkeypatch.setattr(peers.yf,"Ticker",Stock)
    monkeypatch.setattr(peers,"_annual_asset_turnover",lambda *a,**k:None if annual_missing else {"value":.8,"observed_at":"2025-12-31"})
    return peers.fetch_dynamic_peer_metrics_with_diagnostics("5314.TWO","世紀*","Technology","Semiconductors",{})

def test_current_published_candidates_acquire_all_eight_metrics_but_remain_out_of_valuation(monkeypatch):
    from prompt_peer_projection import comparable_peer_rows
    from stock_snapshot.peers_valuation import _peer_comparison
    result=metric_plan(monkeypatch)
    assert len(result["peers"])==3
    assert all(r["metrics_status"]=="complete" and not r["missing_metrics"] for r in result["peers"])
    assert result["audit"]["coverage_status"]=="success"
    assert result["audit"]["candidate_attempt_count"]<=10
    assert comparable_peer_rows(result["peers"])==[]
    assert _peer_comparison({"ticker":"5314.TWO","dynamic_peer_metrics":result["peers"]})["summary"]["peer_count"]==0

def test_missing_published_candidate_metric_is_not_filled_with_zero(monkeypatch):
    result=metric_plan(monkeypatch,missing=True)
    assert result["peers"] and result["audit"]["coverage_status"]=="partial"
    assert all(r["ps_ttm"] is None and "ps_ttm" in r["missing_metrics"] for r in result["peers"])

def test_wrong_live_quote_identity_cannot_supply_published_candidate_numbers(monkeypatch):
    result=metric_plan(monkeypatch,wrong_identity=True)
    assert not result["peers"] and result["audit"]["usable_count"]==0

def test_published_asset_turnover_uses_same_annual_date_over_undated_quote_fields(monkeypatch):
    result=metric_plan(monkeypatch,mixed_period_assets=True)
    assert all(r['asset_turnover']==.8 and r['metric_sources']['asset_turnover']['observed_at']=='2025-12-31'
               for r in result['peers'])

def test_published_asset_turnover_without_common_annual_date_stays_missing(monkeypatch):
    result=metric_plan(monkeypatch,mixed_period_assets=True,annual_missing=True)
    assert all(r['asset_turnover'] is None and 'asset_turnover' in r['missing_metrics'] for r in result['peers'])

def test_numeric_collector_retains_actual_cohort_related_audit(monkeypatch):
    audit={'source':'peer_discovery','provider':'MoneyDJ published food-biotech cohort','status':'success',
           'record_count':3,'http_request_sent':True,'cache_hit':False,'event_kind':'http_request'}
    result=metric_plan(monkeypatch,cohort_audit=audit)
    assert result['audit']['related_entries']==[audit]

@pytest.mark.parametrize('status,count',[('success',3),('error',0)])
def test_legacy_sync_core_keeps_one_actual_cohort_event_before_optional_cache_read(monkeypatch,status,count):
    from data_fetch import yfinance_sync_enrichment as sync
    from data_fetch.enrichment_providers import DynamicPeerMetricsProvider
    from data_fetch.types import ProviderResult
    import source_applicability
    child={'source':'peer_discovery','provider':'MoneyDJ published food-biotech cohort','status':status,
           'record_count':count,'http_request_sent':True,'cache_hit':False,'event_kind':'http_request'}
    parent={'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':status,
            'record_count':count,'related_entries':[child]}
    monkeypatch.setattr(DynamicPeerMetricsProvider,'fetch',lambda *a,**k:ProviderResult(
        'dynamic_peer_metrics','FinMind/yfinance',status,value=[{'ticker':'1707.TW'}] if count else [],audit=parent))
    monkeypatch.setattr(source_applicability,'source_is_applicable',lambda source,*a:source=='dynamic_peer_metrics')
    def scheduled(fetchers,**kwargs):
        assert 'dynamic_peer_metrics' not in fetchers, 'typed source must own one resilience admission'
        return {'values':{},'audit':[]}
    monkeypatch.setattr(sync,'_run_named_fetches',scheduled)
    result=sync.fetch_sync_enrichment_bundle(ticker='5314.TWO',stock=None,company_name='世紀*',
        sector='',industry='',company_identity={},years=[],net_income_history=[],shares_outstanding=None,
        skip_optional_http=True)
    assert result['audit'].count(child)==1

def test_missing_core_typed_workflow_flattens_related_cohort_audit(monkeypatch):
    import asyncio
    from data_fetch import workflow
    from data_fetch.types import FetchRequest,ProviderResult
    child={'source':'peer_discovery','provider':'MoneyDJ published food-biotech cohort','status':'success',
           'record_count':3,'http_request_sent':True,'cache_hit':False,'event_kind':'http_request'}
    parent={'source':'dynamic_peer_metrics','provider':'FinMind/yfinance','status':'success','record_count':3,'related_entries':[child]}
    class Registry:
        def for_request(self,*a,**k):return [object()]
    async def fetched(*a,**k):
        return [ProviderResult('dynamic_peer_metrics','FinMind/yfinance','success',value=[{'ticker':'1707.TW'}],audit=parent)]
    monkeypatch.setattr(workflow,'source_is_applicable',lambda source,*a:source=='dynamic_peer_metrics')
    monkeypatch.setattr(workflow,'fetch_provider_results',fetched)
    monkeypatch.setattr(workflow,'_mark_sources_fetched',lambda *a,**k:None)
    monkeypatch.setattr(workflow,'finalize_data_trust',lambda *a:None)
    result=asyncio.run(workflow._run_missing_core_provider_plan(FetchRequest.from_ticker('5314.TWO'),Registry(),{'ticker':'5314.TWO','source_audit':[]}))
    assert result['source_audit'].count(child)==1

def test_removed_stock_old_master_row_cannot_supply_a_current_identity():
    from data_fetch.market_sources.moneydj_peer_cohort import _current_identity
    rows=[{**r,"date":"2026-10-08"} if r["stock_id"]=="1294" else r for r in MASTER]
    assert _current_identity("1294",rows,TODAY) is None

def acquire(monkeypatch, *, epoch=None, change=None, removed=False):
    from data_fetch.market_sources import moneydj_peer_cohort as source
    from data_fetch.market_sources.moneydj_numeric_candidates import get_published_food_biotech_candidates
    import shared_provider_cache
    import time
    from copy import deepcopy
    body=''.join(f'<tr><td><a href="javascript:Link2Stk(\'AS{r["stock_id"]}\');">{r["stock_id"]}{r["stock_name"]}</a></td><td>2026/10/08</td></tr>' for r in MASTER)
    raw=(f'<html><title>{source.TITLE}</title><table id="oMainTable">{body}</table></html>').encode('big5')
    value=source.parse_cohort_page(raw,'5314.TWO',MASTER,today=TODAY)
    if change=='hash':value['response_sha256']='f'*64
    elif change=='url':value['source_url']='https://wrong.example/peer'
    elif change=='bytes':value['raw_html_base64']='A'*266672
    elif change=='parsed_peer':value['records'][0]['counterparty']['ticker']='2330.TW'
    elif change=='future_date':
        import base64,hashlib
        changed=raw.replace(b'2026/10/08',b'2026/10/10')
        value['raw_html_base64']=base64.b64encode(changed).decode()
        value['response_sha256']=hashlib.sha256(changed).hexdigest()
    meta={'cache_hit':True,'stale':change=='stale','fetched_at_epoch':time.time() if epoch is None else epoch}
    monkeypatch.setattr(shared_provider_cache,'shared_fetch',lambda *a,**k:(deepcopy(value),deepcopy(meta)))
    master=([{**r,'date':'2026-10-08'} if r['stock_id']=='1294' else r for r in MASTER]
            if removed else MASTER)
    return get_published_food_biotech_candidates('5314.TWO',master,today=TODAY)

def test_current_byte_receipt_and_master_supply_only_unverified_numeric_leads(monkeypatch):
    result=acquire(monkeypatch)
    assert len(result['candidates'])==3
    assert all(r['business_comparability_verified_current'] is False
               and r['comparison_scope']=='publisher_food_biotech_candidates' for r in result['candidates'])

@pytest.mark.parametrize('epoch',[0,True,float('nan'),float('inf'),10**400])
def test_invalid_receipt_time_cannot_supply_numeric_candidates(monkeypatch,epoch):
    assert acquire(monkeypatch,epoch=epoch)['candidates']==[]

@pytest.mark.parametrize('change',['hash','url','bytes','stale','future_date'])
def test_bad_original_receipt_cannot_supply_numeric_candidates(monkeypatch,change):
    assert acquire(monkeypatch,change=change)['candidates']==[]

@pytest.mark.parametrize('offset',[3600,-14401])
def test_future_or_expired_receipt_time_cannot_supply_numeric_candidates(monkeypatch,offset):
    import time
    assert acquire(monkeypatch,epoch=time.time()+offset)['candidates']==[]

def test_parsed_cache_edit_is_reconstructed_from_original_bytes(monkeypatch):
    result=acquire(monkeypatch,change='parsed_peer')
    assert result['candidates'][0]['ticker']=='1294.TWO'
    assert '2330.TW' not in [r['ticker'] for r in result['candidates']]

def test_removed_old_peer_is_rejected_without_erasing_independent_receipts(monkeypatch):
    result=acquire(monkeypatch,removed=True)
    assert [r['ticker'] for r in result['candidates']]==['1295.TWO','1707.TW']

def test_other_issuer_does_not_acquire_published_food_biotech_candidates(monkeypatch):
    from data_fetch.market_sources import moneydj_numeric_candidates as source
    monkeypatch.setattr(source,'acquire_published_cohort',lambda *a,**k:pytest.fail('unrelated issuer must not acquire this source'))
    assert source.get_published_food_biotech_candidates('2330.TW',MASTER,today=TODAY)['status']=='not_applicable'

def test_persistent_cohort_cooldown_is_zero_http_and_zero_api_units(monkeypatch):
    import time
    import search_provider_runtime as runtime
    from data_fetch.market_sources import peer_recovery, moneydj_cohort_transport
    from data_fetch.enrichment_search_providers import MoneyDjPublishedPeerCohortProvider
    from data_fetch.types import FetchRequest
    from api_usage_recorders import _provider_usage_units
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    monkeypatch.setattr(peer_recovery,'load_peer_stock_master',lambda:MASTER)
    monkeypatch.setattr(runtime,'cooldown_state',lambda *a:{'retry_at':time.time()+300})
    monkeypatch.setattr(moneydj_cohort_transport,'download_html',lambda **k:pytest.fail('provider cooldown must start no request'))
    result=MoneyDjPublishedPeerCohortProvider().fetch(FetchRequest.from_ticker('5314.TWO'))
    assert result.audit['http_request_sent'] is False and result.audit['record_count']==0
    assert _provider_usage_units(result.audit,result.status)==0
