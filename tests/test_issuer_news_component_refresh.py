"""A new issuer-news component fills a real gap without reacquiring other sources."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
import time

import pytest
from fastapi import HTTPException

from data_fetch.provider_base import CallableProvider
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.service import StockDataService
from data_fetch.types import ProviderResult
from report_analysis_evidence import capture_analysis_evidence
from report_persistence import report_bundle_keys_for_filename
from report_refresh_service import refresh_report_data_snapshot
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import events, init_db
from test_report_source_refresh import saved_report
from test_ventec_issuer_republication import get, DATA, ORIGINAL, NOW


def saved(storage):
    _filename, oldkeys, snapshot = saved_report(storage)
    filename = '6672_TW_v4_report_20261010_100000.html'
    keys = report_bundle_keys_for_filename(filename)
    snapshot['ticker'] = snapshot['data']['ticker'] = '6672.TW'
    snapshot['data']['company_identity'] = deepcopy(DATA['company_identity'])
    snapshot['data']['company_name'] = '騰輝電子-KY'
    snapshot['data']['social_sentiment'] = {'original_sample': 'must remain byte-for-byte'}
    snapshot['data']['recent_catalysts'] = [{'title': '騰輝電子-KY原有新聞', 'date': '2026-10-08',
        'text': '騰輝電子-KY原有新聞事實', 'link': 'https://example.com/other-original', 'source': 'other publisher'}]
    snapshot['source_audit'].append({'source': 'recent_catalysts', 'provider': 'other original news',
        'status': 'success', 'record_count': 1, 'fetched_at_epoch': time.time()-86400, 'fetch_id': 'old-other-news'})
    snapshot['data']['source_audit'] = deepcopy(snapshot['source_audit'])
    snapshot['analysis_evidence'] = capture_analysis_evidence({'data':snapshot['data']},generated_at=snapshot['generated_at'])
    for oldkey, newkey in [(oldkeys.html_key,keys.html_key),(oldkeys.md_key,keys.md_key)]:
        storage.save_report(newkey,storage.get_report(oldkey).content,content_type='text/plain')
    storage.save_report(keys.data_key,json.dumps(snapshot).encode(),content_type='application/json')
    return filename, keys, snapshot


def service(calls, *, invalid=False, status='success'):
    def acquire(request,context):
        calls.append('issuer_news')
        rows,_audit = get()
        if invalid:
            rows[0]['publisher'] = 'forged publisher'
        audit = {'source':'recent_catalysts','provider':'Verified issuer news','status':status,
                 'record_count':len(rows) if status=='success' else 0,'event_kind':'http_request',
                 'http_request_sent':True,'fetched_at_epoch':time.time(),'coverage_status':'partial'}
        return ProviderResult('recent_catalysts','Verified issuer news',status,value=rows if status=='success' else [],audit=audit)
    def forbidden(*args):
        pytest.fail('a component refresh reacquired another provider')
    return StockDataService(registry=ProviderRegistry([
        CallableProvider('recent_catalysts','other original news',forbidden),
        CallableProvider('recent_catalysts','Verified issuer news',acquire),
        CallableProvider('market_data','forbidden core',forbidden),
    ]))


def test_one_component_refresh_preserves_existing_news_core_social_and_quality(tmp_path,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage);calls=[]
    response=asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                       refresh_service=service(calls),source='issuer_news',return_refreshed_data=True))
    after=json.loads(storage.get_report(keys.data_key).content)
    assert calls==['issuer_news'] and response['analysis_text_stale'] is True
    assert response['refresh_sources']==['recent_catalysts']
    assert len(after['data']['recent_catalysts'])==2
    assert any(r['link']=='https://example.com/other-original' for r in after['data']['recent_catalysts'])
    assert any(r['link']==ORIGINAL and len(r['text'])>4900 for r in after['data']['recent_catalysts'])
    for field in ['current_price','revenue_history','years','peer_discovery_results','social_sentiment','company_identity','earnings_call']:
        assert after['data'][field]==before['data'][field]
    assert all(a in after['source_audit'] for a in before['source_audit'])
    assert after['analysis_evidence']==before['analysis_evidence']
    for gate in ['report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance']:
        assert after[gate]==before[gate]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert after['data_trust']['status']!='fresh' and 'market_data' in after['data_trust']['stale_sources']
    observed=events();assert len(observed)==1 and observed[0]['source']=='recent_catalysts'


@pytest.mark.parametrize('invalid,status',[(True,'success'),(False,'error')])
def test_component_failure_preserves_snapshot_and_original_news(tmp_path,invalid,status):
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage);calls=[]
    raw=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as caught:
        asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                    refresh_service=service(calls,invalid=invalid,status=status),source='issuer_news'))
    assert caught.value.status_code==502 and calls==['issuer_news']
    assert storage.get_report(keys.data_key).content==raw
    observed=events();assert len(observed)==1


def test_existing_original_copy_is_deduplicated_without_discarding_its_saved_evidence(tmp_path,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage)
    old={'title':'騰輝電子-KY original publisher headline','date':'2026-09-17','link':ORIGINAL,
         'source':'DigiTimes','summary':'騰輝電子-KY older saved snippet'}
    before['data']['recent_catalysts'].append(old)
    storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
    asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                refresh_service=service([]),source='issuer_news'))
    after=json.loads(storage.get_report(keys.data_key).content)['data']
    assert sum(v['link']==ORIGINAL for v in after['recent_catalysts'])==1
    assert any(a.get('record')==old and a.get('reason')=='duplicate_issuer_republication' for a in after['source_record_archive'])


@pytest.mark.parametrize('field,bad',[('recent_catalysts',{'not':'list'}),('source_record_archive','not list'),('additional_recent_catalysts',[False])])
def test_invalid_saved_news_format_is_rejected_before_provider_work(tmp_path,field,bad):
    storage=InMemoryStorage();filename,keys,before=saved(storage);before['data'][field]=bad
    raw=json.dumps(before).encode();storage.save_report(keys.data_key,raw,content_type='application/json');calls=[]
    with pytest.raises(HTTPException)as caught:
        asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                    refresh_service=service(calls),source='issuer_news'))
    assert caught.value.status_code==400 and calls==[] and storage.get_report(keys.data_key).content==raw


def test_public_component_query_retains_mutation_authorization(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.reports import ReportRouteDeps,create_reports_router
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage);calls=[];raw=storage.get_report(keys.data_key).content
    def authorize(request):
        if request.headers.get('X-Test-Mutation')!='approved':
            raise HTTPException(status_code=403,detail='mutation authorization required')
    app=FastAPI();app.include_router(create_reports_router(ReportRouteDeps(
        get_output_dir=lambda:str(tmp_path),get_report_storage=lambda:storage,get_refresh_service=lambda:service(calls),
        get_pipeline_runner=lambda:None,get_report_renderer=lambda:None,get_task_queue=lambda:None,
        run_report_rerun_job=lambda *_:'',create_job=lambda *_:'job',get_job=lambda *_:{},get_events_since=lambda *_:[],
        update_job=lambda *a,**k:None,append_event=lambda *a:None,request_job_cancel=lambda *_:False,
        print_streamed_event=lambda *_:None,require_mutation_authorized=authorize)))
    client=TestClient(app);url='/api/report/'+filename+'/refresh/data?source=issuer_news'
    assert client.post(url).status_code==403 and calls==[] and storage.get_report(keys.data_key).content==raw
    response=client.post(url,headers={'X-Test-Mutation':'approved'})
    assert response.status_code==200 and calls==['issuer_news']
    assert response.json()['refresh_sources']==['recent_catalysts'] and response.json()['refresh_component']=='Verified issuer news'


def cached_service(*,changes=None):
    def acquire(request,context):
        rows,_=get();stamp=time.time()-300
        audit={'source':'recent_catalysts','provider':'Verified issuer news','status':'skipped_fresh_cache',
               'record_count':len(rows),'cache_hit':True,'stale':False,'http_request_sent':False,
               'http_request_count':0,'event_kind':'cache_hit','fetched_at_epoch':stamp}
        audit.update(changes or {})
        return ProviderResult('recent_catalysts','Verified issuer news','skipped_fresh_cache',value=rows,audit=audit)
    return StockDataService(registry=ProviderRegistry([CallableProvider('recent_catalysts','Verified issuer news',acquire)]))


def test_valid_cached_original_can_fill_report_gap_without_new_fetch_or_restamp(tmp_path,monkeypatch):
    monkeypatch.setattr(time,'time',lambda:NOW.timestamp())
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage)
    asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                refresh_service=cached_service(),source='issuer_news'))
    after=json.loads(storage.get_report(keys.data_key).content)
    audit=next(a for a in after['source_audit']if a['provider']=='Verified issuer news')
    assert audit['status']=='skipped_fresh_cache' and audit['fetched_at_epoch']==NOW.timestamp()-300
    assert audit['cache_hit'] is True and audit['http_request_sent'] is False
    from provider_acquisition import get_provider_acquisition_summary
    row=next(r for r in get_provider_acquisition_summary('last_24h')['sources']if r['source']=='recent_catalysts')
    assert row['fresh_cache_count']==1 and row['fetch_attempts']==0


@pytest.mark.parametrize('changes',[{'http_request_sent':True},{'cache_hit':False},{'stale':True},
                                   {'http_request_count':1},{'record_count':2},{'fetched_at_epoch':None}])
def test_invalid_cache_receipt_cannot_replace_saved_report(tmp_path,changes):
    init_db();storage=InMemoryStorage();filename,keys,before=saved(storage);raw=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as caught:
        asyncio.run(refresh_report_data_snapshot(filename,output_dir=str(tmp_path),storage=storage,
                    refresh_service=cached_service(changes=changes),source='issuer_news'))
    assert caught.value.status_code==502 and storage.get_report(keys.data_key).content==raw
