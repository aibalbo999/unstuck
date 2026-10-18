"""Recover genuine optional job gaps without refreshing analysis or core prices."""
import asyncio
from copy import deepcopy
import json
import time

import pytest
from fastapi import HTTPException
from test_kgi_official_careers import provider_setup, NOW
from test_shared_provider_cache import memory_cache
from test_report_source_refresh import saved_report
from test_report_refresh_acquisition_audit import init_db, events


@pytest.fixture
def job_setup(provider_setup, monkeypatch):
    from data_fetch.market_sources.kgi_careers_transport import KgiCareersHttp
    original = KgiCareersHttp.get_receipt
    def observed(self, path=None):
        receipt = original(self, path)
        self.http_request_count += 1
        self.components.append({'url':receipt['url'], 'cache_hit':False, 'http_request_sent':True,
                                'http_status':200, 'fetched_at_epoch':receipt['fetched_at_epoch']})
        return receipt
    monkeypatch.setattr(KgiCareersHttp, 'get_receipt', observed)
    return provider_setup


def old_report(storage, data):
    from report_persistence import report_bundle_keys_for_filename
    filename, keys, old = saved_report(storage)
    filename = filename.replace('6214', '2883')
    new_keys = report_bundle_keys_for_filename(filename)
    old = json.loads(json.dumps(old, ensure_ascii=False).replace('6214', '2883').replace('精誠', '凱基金'))
    old['data'].update({k: deepcopy(data[k]) for k in ('ticker','company_name','quote_type','instrument_type','company_identity')})
    old['data']['alternative_data'] = {'status': 'unavailable', 'prior_diagnostic': 'exact employer unavailable'}
    old['source_audit'].append({'source':'alternative_data','provider':'original jobs','status':'degraded_enrichment',
                              'record_count':0,'fetched_at_epoch':NOW-86400,'fetch_id':'original-fetch'})
    old['data']['source_audit'] = deepcopy(old['source_audit'])
    for source, target in ((keys.html_key,new_keys.html_key),(keys.md_key,new_keys.md_key)):
        storage.save_report(target, storage.get_report(source).content, content_type='text/html' if source.endswith('.html') else 'text/markdown')
    storage.save_report(new_keys.data_key, json.dumps(old).encode(), content_type='application/json')
    return filename, new_keys, old


def run_refresh(tmp_path, storage, filename, service):
    from report_refresh_service import refresh_report_data_snapshot
    return asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                      refresh_service=service, source='alternative_data', return_refreshed_data=True))


def test_existing_report_gets_verified_jobs_without_reacquiring_core(job_setup,memory_cache,tmp_path,monkeypatch):
    from storage.report_storage import InMemoryStorage
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    data,calls,_=job_setup;init_db();storage=InMemoryStorage();filename,keys,old=old_report(storage,data)
    provider=AlternativeJobOpeningsProvider();original=provider.fetch;requests=[]
    def fetch(request,context=None):
        requests.append(request);return original(request,context)
    monkeypatch.setattr(provider,'fetch',fetch)
    service=StockDataService(registry=ProviderRegistry([provider]))
    response=run_refresh(tmp_path,storage,filename,service)
    after=json.loads(storage.get_report(keys.data_key).content)
    assert after['data']['alternative_data']['current_open_job_count_official']==2
    assert len(calls)==3 and len(requests)==1 and requests[0].options.force_refresh is False
    assert response['analysis_text_stale'] is True
    for name in ('current_price','revenue_history','years','peer_discovery_results','company_identity'):
        assert after['data'][name]==old['data'][name]
    for name in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
        assert after[name]==old[name]
    assert [a for a in after['source_audit']if a['source']!='alternative_data']==old['source_audit'][:-1]
    assert storage.get_report(keys.html_key).content==b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content==b'original conclusions'
    assert any(r.get('record')==old['data']['alternative_data']for r in after['data']['source_record_archive'])
    assert any(r.get('audit')==old['source_audit'][-1]for r in after['data']['source_record_archive'])
    assert len(events())==1 and events()[0]['source']=='alternative_data' and events()[0]['record_count']==2


@pytest.mark.parametrize('mutation',[
    lambda d:d.update(quote_type='ETF'), lambda d:d['company_identity'].update(ticker='2882.TW'),
    lambda d:d['company_identity'].update(stock_id='2882'),lambda d:d.update(alternative_data=[]),
])
def test_invalid_context_rejected_before_acquisition(job_setup,memory_cache,tmp_path,mutation):
    from storage.report_storage import InMemoryStorage
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    data,calls,_=job_setup;init_db();storage=InMemoryStorage();filename,keys,old=old_report(storage,data)
    mutation(old['data']);storage.save_report(keys.data_key,json.dumps(old).encode(),content_type='application/json');before=storage.get_report(keys.data_key).content
    with pytest.raises(HTTPException)as exc:run_refresh(tmp_path,storage,filename,StockDataService(registry=ProviderRegistry([AlternativeJobOpeningsProvider()])))
    assert exc.value.status_code==400 and not calls and not events()
    assert storage.get_report(keys.data_key).content==before


@pytest.mark.parametrize('change',['description','employer','raw_hash','published','count','bool_count','future','renewed','empty','huge_epoch','huge_component','huge_duration','text_duration'])
def test_unverified_acquisition_is_recorded_as_failure_and_preserves_report(job_setup,memory_cache,tmp_path,change):
    from storage.report_storage import InMemoryStorage
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    data,_,_=job_setup;init_db();storage=InMemoryStorage();filename,keys,old=old_report(storage,data)
    originals={key:storage.get_report(key).content for key in (keys.html_key,keys.md_key,keys.data_key)}
    def acquire(request,context):
        result=AlternativeJobOpeningsProvider().fetch(request,context)
        official=result.value['job_openings_official']
        if change=='description':official['job_postings'][0]['description']='invented'
        elif change=='employer':official['job_postings'][0]['employer']='subsidiary'
        elif change=='raw_hash':official['source_record_archive']['listing_receipt']['sha256']='0'*64
        elif change=='published':official['job_postings'][0]['published_date']='2026-09-21'
        elif change=='count':result.audit['record_count']=11
        elif change=='bool_count':result.audit['record_count']=True
        elif change=='future':result.audit['fetched_at_epoch']=NOW+1
        elif change=='renewed':result.audit['fetched_at_epoch']=NOW-1
        elif change=='huge_epoch':result.audit['fetched_at_epoch']=10**500
        elif change=='huge_component':
            result.audit['record_count']=11
            result.audit['component_statuses']['official_careers']['fetched_at_epoch']=10**500
        elif change=='huge_duration':
            result.audit['record_count']=11
            result.audit['duration_ms']=10**500
        elif change=='text_duration':
            result.audit['record_count']=11
            result.audit['duration_ms']='invalid elapsed time'
        else:result.value={'status':'qualitative_only','recent_recruitment_news':[]}
        return result
    service=StockDataService(registry=ProviderRegistry([CallableProvider('alternative_data','104 & 1111 job openings',acquire)]))
    with pytest.raises(HTTPException)as exc:run_refresh(tmp_path,storage,filename,service)
    assert exc.value.status_code==502
    assert {key:storage.get_report(key).content for key in originals}==originals
    observed=events();assert len(observed)==1 and observed[0]['record_count']==0 and observed[0]['status']=='unavailable'


def test_warm_source_read_keeps_original_epoch_and_is_not_another_acquisition(job_setup,memory_cache,monkeypatch):
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    data,calls,_=job_setup;init_db();service=StockDataService(registry=ProviderRegistry([AlternativeJobOpeningsProvider()]))
    request=FetchRequest.from_ticker('2883.TW')
    cold=asyncio.run(service.fetch_source_async(request,'alternative_data',context={'data':data}))
    monkeypatch.setattr(time,'time',lambda:NOW+20)
    warm=asyncio.run(service.fetch_source_async(request,'alternative_data',context={'data':data}))
    assert len(calls)==3
    assert cold.source_audit[0]['record_count']==warm.source_audit[0]['record_count']==2
    assert cold.source_audit[0]['fetched_at_epoch']==warm.source_audit[0]['fetched_at_epoch']==NOW
    assert warm.source_audit[0]['cache_hit']is True and warm.source_audit[0]['http_request_sent']is False
    projected=project_acquisition_events(events(),window='last_24h',now=NOW+20)['sources']
    row=next(r for r in projected if r['source']=='alternative_data')
    assert row['fetch_attempts']==row['fetched_count']==1 and row['fresh_cache_count']==1


def test_non_free_provider_is_never_called(job_setup,memory_cache,tmp_path):
    from storage.report_storage import InMemoryStorage
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    data,calls,_=job_setup;init_db();storage=InMemoryStorage();filename,_,_=old_report(storage,data)
    provider=AlternativeJobOpeningsProvider();provider.cost_tier='paid'
    with pytest.raises(HTTPException)as exc:run_refresh(tmp_path,storage,filename,StockDataService(registry=ProviderRegistry([provider])))
    assert exc.value.status_code==502 and calls==[] and events()==[]


@pytest.mark.parametrize('failure',['error','unavailable','degraded_enrichment'])
def test_failed_provider_wrapper_cannot_be_overridden_by_success_audit(job_setup,memory_cache,tmp_path,failure):
    from storage.report_storage import InMemoryStorage
    from data_fetch.agent_context_providers import AlternativeJobOpeningsProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    data,_,_=job_setup;init_db();storage=InMemoryStorage();filename,keys,_=old_report(storage,data)
    originals={key:storage.get_report(key).content for key in (keys.html_key,keys.md_key,keys.data_key)}
    def acquire(request,context):
        result=AlternativeJobOpeningsProvider().fetch(request,context);result.status=failure;return result
    service=StockDataService(registry=ProviderRegistry([CallableProvider('alternative_data','104 & 1111 job openings',acquire)]))
    with pytest.raises(HTTPException)as exc:run_refresh(tmp_path,storage,filename,service)
    assert exc.value.status_code==502
    assert {key:storage.get_report(key).content for key in originals}==originals
    assert len(events())==1 and events()[0]['status']==failure and events()[0]['record_count']==0
