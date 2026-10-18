"""A rejected indexed metric must not return from a saved news bucket."""
import asyncio,json
from copy import deepcopy
import pytest
from test_bound_brand_fallback_query import DATA,NEW,NOW,install

def static_metric():
    from external_search_payloads import parse_news_rss_payload
    r=next(x for x in parse_news_rss_payload(NEW.decode(),provider='google_news_rss',fallback_source='Google News RSS')if x.source=='TradingView')
    return {'title':r.title,'summary':r.snippet,'date':r.published_at,'source':r.source,'link':r.link}

@pytest.mark.parametrize('bucket',['recent_catalysts','additional_recent_catalysts','historical_catalysts','unverified_catalysts','identity_rejected_catalysts'])
def test_public_news_only_merge_preserves_legacy_metric_as_unverified_and_eight_real_records(monkeypatch,bucket):
    from data_fetch.service import StockDataService
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from report_source_refresh import fetch_report_source_data
    from recent_catalyst_source_refresh import valid_recent_receipt
    calls,_=install(monkeypatch);data=deepcopy(DATA);data.update(instrument_type='EQUITY',current_price=123.,revenue_ttm_raw=456000000,financial_currency='TWD',years=['2021','2022','2023','2024','2025']);data[bucket]=[static_metric()]
    audits=[{'source':'market_data','provider':'original','status':'success','record_count':1,'fetched_at_epoch':NOW.timestamp()-600}]
    snap={'ticker':DATA['ticker'],'data':data,'source_audit':audits};before=deepcopy(snap)
    merged=asyncio.run(fetch_report_source_data(snap,'recent_catalysts',StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]))))
    assert len(merged['recent_catalysts'])==8 and len(calls)==2
    assert not any('股東人數'in r['title']for key in ('recent_catalysts','additional_recent_catalysts')for r in merged[key])
    held=[r for r in merged['unverified_catalysts']if '股東人數'in r['title']]
    assert len(held)==1 and held[0]['source_role_status']=='indexed_non_article_unverified'
    assert merged['news_selection']['source_role_unverified_count']==1
    assert valid_recent_receipt(merged['recent_catalysts'],merged['source_audit'][-1],merged)
    assert snap==before and merged['source_audit'][:1]==audits
    for k in ('current_price','revenue_ttm_raw','financial_currency','years','company_identity'):assert merged[k]==data[k]

def test_repeated_saved_projection_does_not_promote_rejected_role_or_renew_acquisition_time():
    from news_freshness_policy import apply_news_freshness
    stamp=NOW.timestamp()-600;data=deepcopy(DATA);data.update(recent_catalysts=[static_metric()],source_audit=[{'source':'recent_catalysts','fetched_at_epoch':stamp}])
    apply_news_freshness(data,cutoff=NOW);first=deepcopy(data);apply_news_freshness(data,cutoff=NOW)
    assert data==first and data['recent_catalysts']==[]and len(data['unverified_catalysts'])==1
    assert data['source_audit'][0]['fetched_at_epoch']==stamp

def test_existing_saved_data_refresh_persists_role_correction_without_any_provider(tmp_path,monkeypatch):
    from news_freshness_policy import apply_news_only_freshness
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db,events
    init_db();storage=InMemoryStorage();name,keys,old=saved_report(storage)
    old['ticker']=DATA['ticker'];old['data'].update(deepcopy(DATA));old['data']['recent_catalysts']=[static_metric()]
    old['data']['social_sentiment']=[{'text':'original saved social input'}]
    old['data']['sentiment_context']={'original_saved_social_context':True}
    old['data']['source_audit']=deepcopy(old['source_audit']);storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    data=deepcopy(old['data']);apply_news_only_freshness(data,cutoff=NOW)
    class NoProvider:
        async def fetch_async(self,*a,**k):pytest.fail('saved-data projection must not fetch')
        async def fetch_source_async(self,*a,**k):pytest.fail('saved-data projection must not fetch source')
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=NoProvider(),refreshed_data=data))
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert saved['data']['recent_catalysts']==[]and saved['data']['unverified_catalysts'][0]['source_role_status']=='indexed_non_article_unverified'
    assert saved['source_audit']==old['source_audit']and events()==[]
    for k in ('social_sentiment','sentiment_context'):assert saved['data'][k]==old['data'][k]
    for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):assert saved[k]==old[k]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'and storage.get_report(keys.md_key).content==b'original conclusions'

def test_news_only_projection_preserves_every_non_news_field_and_original_record():
    from news_freshness_policy import apply_news_only_freshness
    data=deepcopy(DATA);data.update(recent_catalysts=[static_metric()],social_sentiment=[{'text':'original'}],sentiment_context={'original':True},source_audit=[{'fetched_at_epoch':1.}],current_price=123.,revenue_ttm_raw=456000000)
    before=deepcopy(data);apply_news_only_freshness(data,cutoff=NOW)
    for k in before:
        if k!='recent_catalysts':assert data[k]==before[k]
    assert data['recent_catalysts']==[]and data['unverified_catalysts'][0]['source_role_status']=='indexed_non_article_unverified'
    once=deepcopy(data);apply_news_only_freshness(data,cutoff=NOW);assert data==once
