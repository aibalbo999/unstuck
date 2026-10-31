"""Captured original conference bodies through isolated public report refresh."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tests')]
D=ROOT/'docs/evidence/source-acquisition/20261014/conference-resilience/retention-implementation'
from report_refresh_service import refresh_report_data_snapshot
from report_persistence import report_bundle_keys_for_filename
from storage.report_storage import InMemoryStorage
from test_report_refresh_acquisition_audit import init_db,events

@pytest.fixture
def captures():
    from runtime_paths import current_runtime_paths
    dest=current_runtime_paths().cache_dir/'official-response-evidence'
    import os
    sandbox_cache=Path(os.environ['CACHE_DIR']).resolve()
    assert os.environ.get('STOCK_AGENT_TEST_NO_NETWORK') == '1'
    assert sandbox_cache.parent.name.startswith('prompt-boundary-tests-')
    assert sandbox_cache.parent == Path(os.environ['CACHE_DB_PATH']).resolve().parent
    assert dest.resolve().parent == sandbox_cache
    assert dest.resolve() != (ROOT/'backend/cache/official-response-evidence').resolve()
    dest.mkdir(parents=True,exist_ok=True)
    for p in (D/'fixtures/originals').glob('*.gz'):shutil.copyfile(p,dest/p.name)
    def relocate(v):
        if isinstance(v,dict):
            if 'raw_response_path'in v:v['raw_response_path']=str(dest/Path(v['raw_response_path']).name)
            for k,x in v.items():
                if k != 'analysis_evidence':relocate(x)
        elif isinstance(v,list):
            for x in v:relocate(x)
    def read(ticker,kind):
        v=json.loads((D/'fixtures'/f'{ticker}.{kind}.json').read_text());relocate(v);return v
    return read

def saved(old):
    name=old['refreshed_from_report'];keys=report_bundle_keys_for_filename(name);storage=InMemoryStorage()
    for key,body,ctype in [(keys.html_key,b'original HTML','text/html'),(keys.md_key,b'original Markdown','text/markdown'),(keys.data_key,json.dumps(old,ensure_ascii=False).encode(),'application/json')]:storage.save_report(key,body,content_type=ctype)
    return name,keys,storage

@pytest.mark.parametrize('ticker,pages',[('3324.TWO',15),('1623.TW',48),('2308.TW',13),('2367.TW',16)])
def test_original_conference_general_refresh_preserves_body_after_timeout(captures,tmp_path,ticker,pages):
    old=captures(ticker,'old');incoming=captures(ticker,'incoming')['data'];init_db();before=events();rawincoming=deepcopy(incoming)
    assert old['data']['earnings_call']['documents'][0]['page_count']==pages
    name,keys,storage=saved(old)
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=SimpleNamespace(),refreshed_data=incoming,return_refreshed_data=True))
    current=json.loads(storage.get_report(keys.data_key).content)
    assert current['data'].get('earnings_call')==old['data']['earnings_call']
    assert current['data']['source_freshness']['earnings_call']['stale'] is True
    assert current['data']['conference_retention']['new_acquisition'] is False
    assert result['refreshed_data']==rawincoming
    assert events()==before
    assert storage.get_report(keys.html_key).content==b'original HTML'
    assert storage.get_report(keys.md_key).content==b'original Markdown'
    for k in ('analysis_evidence','report_lint','evidence_exit_gate','content_credibility','report_conformance','final_audit'):
        assert current[k]==old[k]


def refresh(old, incoming, tmp_path):
    name, keys, storage = saved(old)
    result = asyncio.run(refresh_report_data_snapshot(name, output_dir=str(tmp_path), storage=storage,
        refresh_service=SimpleNamespace(), refreshed_data=incoming, return_refreshed_data=True))
    return json.loads(storage.get_report(keys.data_key).content), result, keys, storage


def replace_component_original(component, raw):
    from official_response_evidence import archive_response
    old = component['original_receipt']
    receipt = archive_response(raw, source_url=old['source_url'], retrieved_at=old['retrieved_at'])
    receipt.update({k: old[k] for k in ('http_status_observed', 'request_method', 'response_complete', 'cache_hit')})
    component['original_receipt'] = receipt


@pytest.mark.parametrize('change', ['new_event', 'different_pdf', 'wrong_master'])
def test_successful_new_index_or_master_conflict_before_pdf_timeout_refuses_retention(captures,tmp_path,change):
    from official_response_evidence import read_response
    from data_fetch.market_sources import auras_conference as source
    old = captures('3324.TWO','old'); incoming = captures('3324.TWO','incoming')['data']
    audit = next(a for a in incoming['source_audit'] if a.get('source') == 'earnings_call' and a.get('component_statuses'))
    c = next(c for c in audit['component_statuses'] if c['url'] == (source.MASTER if change == 'wrong_master' else source.INDEX))
    raw = read_response(c['original_receipt'])
    if change == 'wrong_master':
        assert b'16619628' in raw
        raw = raw.replace(b'16619628', b'16619629')
    else:
        body = json.loads(raw)
        for unit in (body['info'], body['infos'][0]):
            for lang in ['CN','ENG']:
                chosen = next(r for r in unit['unitAnnexFileList_'+lang] if r['groupNumber']==57)
                if change == 'new_event':
                    chosen['title'] = chosen['title'].replace('2026/09/04','2026/10/01')
                    chosen['createDate'] = '2026-10-01T15:00:00'
                elif lang == 'CN':
                    chosen['filePath'] = chosen['filePath'].replace('7835f665','7835f666')
        raw = json.dumps(body,ensure_ascii=False).encode()
        selected = source.select_presentation(raw,c['fetched_at_epoch'],as_of_epoch=c['fetched_at_epoch'])
        assert selected != old['data']['earnings_call']['auras_conference_receipt']['selected']
    replace_component_original(c,raw)
    current, _, _, _ = refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call'] == {}
    assert 'conference_retention' not in current['data']


@pytest.mark.parametrize('ticker',['3324.TWO','1623.TW','2308.TW','2367.TW'])
def test_repeated_report_local_reuse_keeps_original_epochs_failures_and_no_acquisition(captures,tmp_path,ticker):
    from provider_acquisition import project_acquisition_events
    from report_source_refresh import _timestamp
    import time
    old=captures(ticker,'old'); incoming=captures(ticker,'incoming')['data']
    raw=deepcopy(incoming); first, response, _, _=refresh(old,incoming,tmp_path)
    second, _, _, _=refresh(first,incoming,tmp_path)
    marker=first['data']['conference_retention']
    assert second['data']['conference_retention']==marker
    assert second['data']['earnings_call']==first['data']['earnings_call']==old['data']['earnings_call']
    assert incoming==raw and response['refreshed_data']==raw
    epoch=min(_timestamp(x['source_freshness']['earnings_call']) for x in (old,old['data']))
    assert marker['original_fetched_at_epoch']==epoch
    for row in (first,second):
        data=row['data'];f=data['source_freshness']['earnings_call']
        assert f['fetched_at_epoch']==epoch and f['stale'] and not f['is_fresh']
        assert data['source_audit'][1:]==incoming['source_audit']
        assert data['conference_retention']['failed_refresh_audits']==[a for a in incoming['source_audit'] if a.get('source')=='earnings_call']
        for k in ('current_price','revenue_ttm','eps_ttm','years','revenue_history','price_history','financials_source','company_identity'):
            assert data.get(k)==incoming.get(k)
        assert {k:v for k,v in data['source_freshness'].items() if k!='earnings_call'}=={k:v for k,v in incoming['source_freshness'].items() if k!='earnings_call'}
    now=time.time(); reuse=second['data']['source_audit'][0]
    p=project_acquisition_events([{**reuse,'created_at':now,'details_json':json.dumps(reuse)}],window='last_24h',now=now)['sources'][0]
    assert p['fetch_attempts']==p['fetched_count']==0 and p['stale_cache_count']==1
    # The shared provider result cannot inject this report's archive into another report.
    other=deepcopy(old);other['data']['earnings_call']={}
    third,_,_,_=refresh(other,response['refreshed_data'],tmp_path)
    assert third['data']['earnings_call']=={} and 'conference_retention' not in third['data']


@pytest.mark.parametrize('change',['text','omission','translation','wrong_identity','wrong_type','wrong_stock_id',
    'missing_archive','bad_hash','bool_count','bool_finality','retimed_audit','bad_freshness','receipt_expired_at_origin','wrong_policy'])
def test_unqualified_old_publication_is_not_retained(captures,tmp_path,change):
    old=captures('2308.TW','old');incoming=captures('2308.TW','incoming')['data'];value=old['data']['earnings_call']
    proof=value['delta_transcript_receipt']
    if change=='text':value['documents'][0]['pages'][0]['text']+=' fabricated assertion'
    elif change=='omission':value['coverage_status']='complete'
    elif change=='translation':value['documents'][0]['translation_accuracy_verified']=True
    elif change=='wrong_identity':old['data']['company_name']='聯電'
    elif change=='wrong_type':old['data']['company_identity']['quote_type']='ETF'
    elif change=='wrong_stock_id':old['data']['company_identity']['stock_id']='2303'
    elif change=='missing_archive':Path(proof['transcript']['raw_response_path']).unlink()
    elif change=='bad_hash':proof['transcript']['raw_response_sha256']='0'*64
    elif change=='bool_count':
        for p in (old,old['data']):
            next(a for a in p['source_audit'] if a.get('source')=='earnings_call')['record_count']=True
    elif change=='bool_finality':proof['transcript']['finality_guaranteed']=0
    elif change=='retimed_audit':
        for p in (old,old['data']):
            next(a for a in p['source_audit'] if a.get('source')=='earnings_call')['fetched_at_epoch']+=100
    elif change=='bad_freshness':old['source_freshness']['earnings_call']['fetched_at_epoch']=True
    elif change=='receipt_expired_at_origin':proof['identity']['retrieved_at']-=1801
    else:proof['policy']='delta-original-translated-transcript-v2'
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']=={} and 'conference_retention' not in current['data']


@pytest.mark.parametrize('change',['403','429','parse_error','malformed','positive_records','different_provider',
    'new_metadata','bad_type','wrong_identity','wrong_stock_id','missing_component_original','wrong_component_epoch'])
def test_incoming_conflict_is_never_hidden_by_old_body(captures,tmp_path,change):
    old=captures('3324.TWO','old');incoming=captures('3324.TWO','incoming')['data']
    rows=[a for a in incoming['source_audit'] if a.get('source')=='earnings_call'];row=rows[0]
    if change in ('403','429'):row['component_statuses'][-1]['http_status']=int(change)
    elif change=='parse_error':row['component_statuses'][-1]['error_kind']='parse_error'
    elif change=='malformed':incoming['earnings_call']=[]
    elif change=='positive_records':row['record_count']=1
    elif change=='different_provider':row['provider']='MOPS'
    elif change=='new_metadata':incoming['earnings_call']={'date':'2026-10-14','documents':[]}
    elif change=='bad_type':incoming['company_identity']['quote_type']='ETF'
    elif change=='wrong_identity':incoming['company_name']='合庫金'
    elif change=='wrong_stock_id':incoming['company_identity']['stock_id']='3325'
    elif change=='missing_component_original':row['component_statuses'][1].pop('original_receipt')
    else:row['component_statuses'][1]['fetched_at_epoch']+=1
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']==incoming['earnings_call']
    assert 'conference_retention' not in current['data']


def test_historical_auras_date_validation_has_no_clock_patch_and_default_stays_current(captures):
    from data_fetch.market_sources import auras_conference as source
    from official_response_evidence import read_response
    from datetime import datetime,timedelta
    from zoneinfo import ZoneInfo
    import time
    proof=captures('3324.TWO','old')['data']['earnings_call']['auras_conference_receipt']
    at=proof['pdf']['retrieved_at'];raw=read_response(proof['identity'])
    historical_date=datetime.fromtimestamp(at,ZoneInfo('Asia/Taipei')).date()
    assert source.parse_master(raw,proof['identity']['retrieved_at'],as_of_epoch=at)['as_of']=='2026-10-13'
    with pytest.raises(ValueError):source._master_anchor(raw,today=historical_date+timedelta(days=30))
    # Explicit reference cannot exceed now or precede original observation.
    for bad in (True,float('inf'),float('nan'),10**500,at-1800,time.time()+86400):
        with pytest.raises(ValueError):source.parse_master(raw,at,as_of_epoch=bad)
    assert source._master_anchor(raw)==source._master_anchor(raw,today=source._today())


def test_historical_replay_deadline_fails_closed_after_native_reader(captures,tmp_path,monkeypatch):
    import time
    from data_fetch.market_sources import auras_conference as source
    old=captures('3324.TWO','old');incoming=captures('3324.TWO','incoming')['data']
    real=source.native_presentation; clock=time.monotonic();elapsed=[0]
    monkeypatch.setattr(time,'monotonic',lambda:clock+elapsed[0])
    def late(*a,**kw):
        value=real(*a,**kw);elapsed[0]=11;return value
    monkeypatch.setattr(source,'native_presentation',late)
    current,_,_,_=refresh(old,incoming,tmp_path)
    assert current['data']['earnings_call']=={}


def test_public_service_fetch_keeps_failure_while_saved_report_retains_body(captures,tmp_path):
    old=captures('3324.TWO','old');incoming=captures('3324.TWO','incoming')['data'];calls=[]
    class Service:
        async def fetch_async(self,request):
            calls.append(request)
            return SimpleNamespace(data=deepcopy(incoming))
    init_db();before=events();name,keys,storage=saved(old)
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
        refresh_service=Service(),return_refreshed_data=True))
    current=json.loads(storage.get_report(keys.data_key).content)
    assert len(calls)==1 and calls[0].options.force_refresh and calls[0].options.record_provider_sla
    assert current['data']['earnings_call']==old['data']['earnings_call']
    assert result['refreshed_data']==incoming and events()==before


def test_new_verified_source_only_retires_reuse_provenance_without_touching_other_sources(captures,tmp_path,monkeypatch):
    import base64,time
    from hashlib import sha256
    from data_fetch.market_sources import auras_conference as source
    from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from official_response_evidence import read_response
    old=captures('3324.TWO','old');incoming=captures('3324.TWO','incoming')['data']
    retained,_,_,_=refresh(old,incoming,tmp_path)
    marker=deepcopy(retained['data']['conference_retention']);name,keys,storage=saved(retained)
    proof=old['data']['earnings_call']['auras_conference_receipt']
    bodies={r['source_url']:read_response(r) for k,r in proof.items() if k in ('identity','index','pdf')}
    calls=[]
    def download(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
        raw=bodies[url]
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                'http_status':200,'response_complete':True,'request_method':'GET','http_status_observed':True,
                'fetched_at_epoch':time.time()}
    # Simulated new native acquisition at the actual current clock; never make
    # the old historical receipt fresh by replacing the process clock.
    monkeypatch.setattr(AurasConferenceHttp,'_download',download)
    service=StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    init_db();before=events()
    asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,
                refresh_service=service,source='earnings_call'))
    current=json.loads(storage.get_report(keys.data_key).content);data=current['data']
    assert calls==[source.MASTER,source.INDEX,proof['pdf']['source_url']]
    assert 'conference_retention' not in data and data['conference_retention_archive'][-1]==marker
    assert all(not s.startswith('法說原件沿用此報告歷史證據：') for s in data['data_source_notes'])
    assert data['earnings_call']['fetched_at_epoch']>marker['original_fetched_at_epoch']
    assert not data['source_freshness']['earnings_call']['stale']
    assert len(events())==len(before)+1 and events()[-1]['status']=='success'
    for k in ('current_price','eps_ttm','years','revenue_history','company_identity'):
        assert data.get(k)==retained['data'].get(k)
    for k in ('analysis_evidence','report_lint','evidence_exit_gate','content_credibility','report_conformance','final_audit'):
        assert current[k]==retained[k]


from test_annual_shared_issuer_master import native_master
from test_shared_provider_cache import memory_cache
import time as _time
_REAL_TIME = _time.time


@pytest.mark.parametrize('name',['tewc','delta','unitech'])
def test_v2_shared_json_context_replays_archives_without_current_cache(native_master,monkeypatch,name):
    import cache_store
    from test_conference_shared_issuer_master import packet_transport,source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from conference_historical_evidence import replay_historical_conference,profile
    monkeypatch.setattr(_time,'time',_REAL_TIME)
    _,calls=packet_transport(name,monkeypatch);s=source(name)
    from provider_correlation import correlation_scope
    with correlation_scope(replace=True,ticker=s.TICKER):
        result=EarningsCallProvider().fetch(FetchRequest.from_ticker(s.TICKER))
    assert result.status=='success',result.audit
    oldcalls=list(calls);mastercalls=list(native_master[0]);_,marker,_=profile(s.TICKER)
    assert result.value[marker]['policy']==s.POLICY
    assert result.value[marker]['identity']['source_url']==s.master_identity.JSON_URL
    def no_cache(*a,**kw):raise AssertionError('historical replay cannot read current shared cache')
    monkeypatch.setattr(cache_store,'get_cache_json',no_cache)
    proof=replay_historical_conference(result.value,s.TICKER,result.audit)
    assert proof['current_acquisition'] is False and proof['original_observation_epoch']==result.value['fetched_at_epoch']
    assert calls==oldcalls and native_master[0]==mastercalls
    bad=deepcopy(result.value);bad[marker]['policy']=s.LEGACY_POLICY
    with pytest.raises(ValueError):replay_historical_conference(bad,s.TICKER,result.audit)
