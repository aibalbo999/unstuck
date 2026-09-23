"""Independent, offline review reproductions; no production writes."""
from datetime import datetime, timezone
from pathlib import Path
import sys, json



def test_failed_news_refresh_does_not_renew_retained_news(monkeypatch):
    import data_fetch.enrichment_merge as merge
    epoch=datetime(2026,9,23,5,tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(merge.time_module,'time',lambda:epoch)
    data={'ticker':'2305.TW','recent_catalysts':[{'title':'still within news window', 'date':'2026-09-20', 'link':'https://example.test/a'}],
          'source_freshness':{'recent_catalysts':{'fetched_at_epoch':epoch-86400}},
          'source_audit':[{'source':'recent_catalysts','provider':'Alternative Search','status':'error',
                           'error_kind':'HTTPStatusError','record_count':0,'stale':True,'fetched_at_epoch':epoch}]}
    result=merge._merge_optional_http_bundle(data,{'free_news':[], 'search_catalysts':[], 'yahoo_news':[], 'fmp_news':[]},
                                             refreshed_sources=('recent_catalysts',))
    latest=result['source_audit'][-1]
    assert latest['status']=='degraded_enrichment',latest
    assert latest['stale'] is True,latest
    assert result['source_freshness']['recent_catalysts']['fetched_at_epoch']==epoch-86400


def test_institutional_stale_payload_cannot_become_fresh_by_recent_observation():
    from data_freshness import build_source_freshness_entry
    epoch=datetime(2026,9,23,5,tzinfo=timezone.utc).timestamp()
    result=build_source_freshness_entry('institutional_trading','2330.TW',epoch,True,now_epoch=epoch,
            source_data={'latest_date':'2026-09-22','status':'stale','stale':True})
    assert result['stale'] is True and result['is_fresh'] is False,result


def test_incomplete_calendar_file_does_not_claim_annual_coverage(tmp_path):
    from market_calendar_store import load_market_calendar
    (tmp_path/'tw_2027.json').write_text(json.dumps({'market':'tw','year':2027}))
    result=load_market_calendar('tw',2027,calendar_dir=str(tmp_path))
    assert result['coverage_status']=='unknown',result


def test_explicit_cache_observation_is_not_mislabeled_as_local_block():
    from provider_acquisition import observation_kind
    row={'provider':'FRED DGS10','status':'success','record_count':1,'message':'cached observation',
         'details':{'cache_hit':True,'stale':False,'http_request_sent':False}}
    assert observation_kind(row)=='fresh_cache_count'


def test_supported_plain_taiwan_symbol_keeps_successful_radar_source():
    import asyncio
    from data_fetch import CallableProvider, ProviderRegistry, ProviderResult, StockDataService, FetchRequest
    def fetch(request, context):
        return ProviderResult(source='institutional_trading',provider='FinMind',status='success',
            value={'latest_date':'2026-09-22','foreign_net_buy':100},
            audit={'source':'institutional_trading','provider':'FinMind','status':'success','record_count':1})
    registry=ProviderRegistry([CallableProvider('institutional_trading','FinMind',fetch,markets={'tw'})])
    result=asyncio.run(StockDataService(registry=registry).fetch_radar_async(
        FetchRequest.from_ticker('2330',record_provider_sla=False),('institutional_trading',)))
    assert result.source_audit[0]['status']=='success',result.source_audit
