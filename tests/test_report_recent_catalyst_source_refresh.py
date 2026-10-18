"""Only new qualified recent evidence may repair a saved report news gap."""
import asyncio
from copy import deepcopy
from datetime import datetime,timezone,timedelta
import json,time
from contextlib import asynccontextmanager

import pytest
from fastapi import HTTPException
from data_fetch.provider_base import CallableProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import init_db,events


def rows(count=8):
    return [{'title':f'精誠營收展望新聞 {i}','summary':'精誠公布最新營運展望與營收資訊。',
        'date':(datetime.now(timezone.utc)-timedelta(hours=2)).isoformat(),
        'link':f'https://publisher{i%3}.example/news/{i}','source':f'publisher{i%3}',
        'source_type':'google_news_rss_search'}for i in range(count)]


def setup(monkeypatch,*,change=None):
    init_db();storage=InMemoryStorage();name,keys,old=saved_report(storage)
    old['data'].update(quote_type='EQUITY',company_identity={'official_name':'精誠','allowed_aliases':['精誠']},
        financial_currency='TWD',currency='TWD',revenue_ttm_raw=123456789,_cache_hit=True,
        social_sentiment={'social_samples':[{'original':True}]},recent_catalysts=[],data_source_notes=['original note'])
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');calls=[]
    def acquire(request,context):
        calls.append(deepcopy(context));value=rows();stamp=time.time();audit={'source':'recent_catalysts','provider':'Alternative Search',
            'status':'success','record_count':len(value),'quality_status':'sufficient_candidates','selection_policy':'company-time-v1',
            'fetched_at_epoch':stamp,'fetched_at':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
            'selection_cutoff':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),'cache_hit':False,'stale':False}
        if change:change(value,audit)
        return ProviderResult('recent_catalysts','Alternative Search',audit['status'],value=value,audit=audit)
    service=StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts','Alternative Search',acquire),
        CallableProvider('market_data','forbidden',lambda *a:pytest.fail('news-only refresh fetched market'))]))
    return storage,name,keys,old,service,calls


def run(tmp_path,storage,name,service):
    return asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
        refresh_service=service,source='recent_catalysts',return_refreshed_data=True))


def test_public_recent_refresh_uses_only_free_search_and_preserves_core_other_sources_and_analysis(tmp_path,monkeypatch):
    storage,name,keys,old,service,calls=setup(monkeypatch);response=run(tmp_path,storage,name,service)
    saved=json.loads(storage.get_report(keys.data_key).content)
    assert len(calls)==1 and calls[0]['free_sources_only']is True and calls[0]['data']['_cache_hit']is False
    assert old['data']['_cache_hit']is True  # Existing snapshot builder strips transient cache debug markers.
    assert len(saved['data']['recent_catalysts'])==8 and saved['data']['news_selection']['publisher_count']==3
    for key in ['current_price','revenue_ttm_raw','revenue_history','years','peer_discovery_results','earnings_call','social_sentiment']:
        assert saved['data'][key]==old['data'][key]
    for gate in ['analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:
        assert saved[gate]==old[gate]
    assert [a for a in saved['source_audit']if a['source']!='recent_catalysts']==old['source_audit']
    assert 'market_data'in saved['data_trust']['stale_sources']and response['analysis_text_stale']is True
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert response['refresh_sources']==['recent_catalysts']and len(events())==1
    assert events()[0]['source']=='recent_catalysts'and events()[0]['status']=='success'and events()[0]['record_count']==8


@pytest.mark.parametrize('bad',['too_few','one_publisher','wrong_issuer','future_article','old_article','duplicate','bool_count','future_epoch','mismatched_epoch','quality_missing','cache','stale','duplicate_title','publisher_override','old_epoch','contradictory_http'])
def test_invalid_recent_success_is_not_saved_or_counted_as_success(tmp_path,monkeypatch,bad):
    def damage(value,audit):
        if bad=='too_few':value.pop();audit['record_count']=len(value)
        elif bad=='one_publisher':
            for r in value:r['source']='one';r['link']='https://one.example/'+r['link'].rsplit('/',1)[-1]
        elif bad=='wrong_issuer':value[0].update(title='聯發科消息',summary='聯發科營運資訊')
        elif bad=='future_article':value[0]['date']=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        elif bad=='old_article':value[0]['date']=(datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
        elif bad=='duplicate':value[0]=deepcopy(value[1])
        elif bad=='duplicate_title':value[0]['title']=value[1]['title']
        elif bad=='publisher_override':
            for r in value:r['publisher']='one'
        elif bad=='old_epoch':
            audit['fetched_at_epoch']-=3600;audit['selection_cutoff']=audit['fetched_at']=datetime.fromtimestamp(audit['fetched_at_epoch'],timezone.utc).isoformat()
        elif bad=='contradictory_http':audit['http_status']=403
        elif bad=='bool_count':audit['record_count']=True
        elif bad=='future_epoch':audit['fetched_at_epoch']=time.time()+60;audit['fetched_at']=datetime.fromtimestamp(audit['fetched_at_epoch'],timezone.utc).isoformat()
        elif bad=='mismatched_epoch':audit['fetched_at_epoch']-=3600
        elif bad=='quality_missing':audit.pop('quality_status')
        elif bad=='cache':audit['cache_hit']=True
        elif bad=='stale':audit['stale']=True
    storage,name,keys,_old,service,calls=setup(monkeypatch,change=damage);before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as raised:run(tmp_path,storage,name,service)
    assert raised.value.status_code==502 and len(calls)==1 and storage.get_report(keys.data_key).content==before
    assert len(events())==1 and events()[0]['status']!='success'


@pytest.mark.parametrize('change',[{'quote_type':'ETF'},{'quote_type':'unknown'},{'ticker':'2330.TW'},{'company_name':'','company_identity':{}}])
def test_invalid_saved_context_is_rejected_before_news_provider(tmp_path,monkeypatch,change):
    storage,name,keys,old,service,calls=setup(monkeypatch);old['data'].update(change)
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as raised:run(tmp_path,storage,name,service)
    assert raised.value.status_code==400 and calls==[]and storage.get_report(keys.data_key).content==before and events()==[]


def test_free_search_allowlist_keeps_disabled_order_and_excludes_key_providers(monkeypatch):
    import external_search_providers as source
    from external_search_types import SearchResult
    calls=[]
    @asynccontextmanager
    async def client():yield object()
    async def fetch(client,provider,query,**kwargs):
        calls.append(provider)
        return [SearchResult(r['title'],r['summary'],r['link'],r['source'],r['date'])for r in rows()]
    monkeypatch.setattr(source,'async_client',client)
    monkeypatch.setattr(source,'_provider_order',lambda:['tavily','google_news_rss','brave'])
    monkeypatch.setattr(source,'_provider_configured',lambda name:True)
    monkeypatch.setattr(source,'_fetch_provider_results',fetch)
    result=asyncio.run(source.fetch_web_search_results_async('精誠',max_results=8,require_recent=True,
        company_context={'ticker':'6214.TW','company_name':'精誠'},provider_allowlist={'google_news_rss','bing_news_rss','duckduckgo_news','gdelt','yahoo_rss'}))
    assert len(result)==8 and calls==['google_news_rss']


def test_same_receipt_epoch_and_iso_microsecond_rounding_is_accepted(tmp_path,monkeypatch):
    def damage(value,audit):
        stamp=int(time.time())-1+0.1234567
        audit.update(fetched_at_epoch=stamp,fetched_at=datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
            selection_cutoff=datetime.fromtimestamp(stamp,timezone.utc).isoformat())
    storage,name,keys,_old,service,_calls=setup(monkeypatch,change=damage)
    response=run(tmp_path,storage,name,service)
    assert response['success']is True and len(json.loads(storage.get_report(keys.data_key).content)['data']['recent_catalysts'])==8


def test_service_threads_anonymous_allowlist_into_existing_search_provider(monkeypatch):
    import external_search_providers
    from data_fetch.enrichment_search_providers import AlternativeSearchProvider
    from data_fetch.types import FetchRequest
    observed=[]
    async def acquire(ticker,company_name,identity,**kwargs):
        observed.append(kwargs['provider_allowlist']);stamp=time.time()
        kwargs['diagnostics'].update(selection_policy='company-time-v1',quality_status='sufficient_candidates',
            selection_cutoff=datetime.fromtimestamp(stamp,timezone.utc).isoformat())
        return rows()
    monkeypatch.setattr(external_search_providers,'fetch_alternative_search_catalysts_async',acquire)
    data={'ticker':'6214.TW','quote_type':'EQUITY','company_name':'精誠','company_identity':{'official_name':'精誠'},'_cache_hit':True}
    service=StockDataService(registry=ProviderRegistry([AlternativeSearchProvider()]))
    result=asyncio.run(service.fetch_source_async(FetchRequest.from_ticker('6214.TW',record_provider_sla=False),
        'recent_catalysts',context={'data':data,'free_sources_only':False}))
    assert observed==[{'google_news_rss','bing_news_rss','duckduckgo_news','gdelt','yahoo_rss'}]
    assert result.source_audit[0]['status']=='success'and result.source_audit[0]['cache_hit']is False
    assert data['_cache_hit']is True


def test_recent_refresh_archives_superseded_search_and_keeps_other_provider_observations(tmp_path,monkeypatch):
    storage,name,keys,old,service,_calls=setup(monkeypatch)
    previous={'source':'recent_catalysts','provider':'Alternative Search','status':'degraded_enrichment','record_count':2,
        'fetched_at_epoch':time.time()-3600,'fetch_id':'old-search','message':'original incomplete search'}
    other={**deepcopy(previous),'provider':'TWSE company announcement history','fetch_id':'old-official'}
    old['source_audit'].extend([previous,other]);old['data']['source_audit']=deepcopy(old['source_audit'])
    old['data']['source_record_archive']=[{'source':'financial_statements','reason':'original archive'}]
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    run(tmp_path,storage,name,service);saved=json.loads(storage.get_report(keys.data_key).content)
    assert other in saved['source_audit']and previous not in saved['source_audit']
    archive=saved['data']['source_record_archive']
    assert old['data']['source_record_archive'][0]in archive
    assert any(r.get('audit')==previous and r['reason']=='superseded_recent_search_audit'for r in archive)
    assert len(events())==1


@pytest.mark.parametrize('field',['allowed_aliases','english_names','forbidden_aliases'])
def test_malformed_saved_alias_vectors_are_rejected_without_provider_or_exception(tmp_path,monkeypatch,field):
    storage,name,keys,old,service,calls=setup(monkeypatch);old['data']['company_identity'][field]=True
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    with pytest.raises(HTTPException)as raised:run(tmp_path,storage,name,service)
    assert raised.value.status_code==400 and calls==[]and events()==[]


@pytest.mark.parametrize('bad',['wrong_ticker','old_correlation','zero_http','nonbool_http'])
def test_explicit_observation_contradictions_do_not_save_or_count_success(tmp_path,monkeypatch,bad):
    def change(value,audit):
        if bad=='wrong_ticker':audit['ticker']='2330.TW'
        elif bad=='old_correlation':audit.update(fetch_id='previous-fetch',operation_id='previous-operation')
        elif bad=='zero_http':audit.update(http_request_sent=True,http_request_count=0,event_kind='http_request')
        else:audit['http_request_sent']=0
    storage,name,keys,_old,service,calls=setup(monkeypatch,change=change)
    before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as error:run(tmp_path,storage,name,service)
    assert error.value.status_code==502 and len(calls)==1 and storage.get_report(keys.data_key).content==before
    assert len(events())==1 and events()[0]['status']!='success'
    details=json.loads(events()[0]['details_json'])
    assert details['ticker']=='6214.TW'and details['fetch_id']!='previous-fetch'
    if bad=='old_correlation':
        assert 'operation_id'not in details


@pytest.mark.parametrize('field,bad,label',[('official_name',True,'True'),('legal_name',False,'False'),('display_name',123,'123')])
def test_nonstring_identity_name_cannot_create_an_unrelated_issuer_alias(tmp_path,monkeypatch,field,bad,label):
    def unrelated(value,audit):
        for i,row in enumerate(value):row.update(title=f'{label} stock revenue news {i}',summary=f'{label} earnings outlook')
    storage,name,keys,old,service,calls=setup(monkeypatch,change=unrelated)
    old['data']['company_identity'][field]=bad
    storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json')
    before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as error:run(tmp_path,storage,name,service)
    assert error.value.status_code==400 and calls==[]and events()==[]
    assert storage.get_report(keys.data_key).content==before


@pytest.mark.parametrize('legacy_missing_fetch',[True,False])
def test_current_receipt_preserves_provider_owned_operation_and_allows_real_http(tmp_path,monkeypatch,legacy_missing_fetch):
    from provider_correlation import current_correlation
    def change(value,audit):
        audit.update(operation_id='nested-source-operation',http_request_sent=True,http_request_count=2,event_kind='http_request')
        if not legacy_missing_fetch:audit.update(current_correlation(),operation_id='nested-source-operation')
    storage,name,keys,_old,service,_calls=setup(monkeypatch,change=change)
    assert run(tmp_path,storage,name,service)['success']is True
    audit=[a for a in json.loads(storage.get_report(keys.data_key).content)['source_audit']if a['source']=='recent_catalysts'][0]
    assert audit['operation_id']=='nested-source-operation'and audit['ticker']=='6214.TW'
    assert audit['fetch_id']and json.loads(events()[0]['details_json'])['fetch_id']==audit['fetch_id']


def test_standalone_refresh_rejects_old_analysis_job_attribution(tmp_path,monkeypatch):
    def change(value,audit):audit['job_id']='previous-analysis-job'
    storage,name,keys,_old,service,_calls=setup(monkeypatch,change=change)
    before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as error:run(tmp_path,storage,name,service)
    assert error.value.status_code==502 and storage.get_report(keys.data_key).content==before
    assert len(events())==1 and events()[0]['status']!='success'
    details=json.loads(events()[0]['details_json'])
    assert details['ticker']=='6214.TW'and details['fetch_id']and 'job_id'not in details


def test_source_refresh_retains_actual_active_job_attribution(tmp_path,monkeypatch):
    from provider_correlation import correlation_scope,current_correlation
    def change(value,audit):audit.update(current_correlation(),operation_id='nested-current-operation')
    storage,name,keys,_old,service,_calls=setup(monkeypatch,change=change)
    with correlation_scope(replace=True,job_id='active-analysis-job'):
        assert run(tmp_path,storage,name,service)['success']is True
    audit=[a for a in json.loads(storage.get_report(keys.data_key).content)['source_audit']if a['source']=='recent_catalysts'][0]
    assert audit['job_id']=='active-analysis-job'and audit['operation_id']=='nested-current-operation'
    assert json.loads(events()[0]['details_json'])['job_id']=='active-analysis-job'
