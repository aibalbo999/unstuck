"""Synthetic contracts and native-boundary replay; no live HTTP acquisition."""
from copy import deepcopy
from types import SimpleNamespace
import sys,time
import pytest

from test_shared_provider_cache import memory_cache


def test_observed_empty_legacy_result_selects_master_bound_route(monkeypatch,memory_cache):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import twse_company_history as legacy
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    from data_fetch.market_sources import mops_master_bound_announcements as dynamic
    init_db()
    record_source_audit_entries([{'source':'recent_catalysts','provider':'TWSE company announcement history',
        'ticker':'3653.TW','status':'unavailable','record_count':0,'http_request_sent':True,'http_request_count':1}])
    calls=[]
    monkeypatch.setattr(legacy,'fetch_recent_company_announcements',lambda ticker:([],{'status':'unavailable','record_count':0}))
    def acquire(ticker):
        calls.append(ticker)
        return [],{'status':'unavailable','record_count':0,'http_request_sent':False,'http_request_count':0}
    monkeypatch.setattr(dynamic,'fetch_master_bound_announcements',acquire)
    provider=TwseCompanyHistoryProvider()
    result=provider.fetch(FetchRequest.from_ticker('3653.TW'),{'data':{'ticker':'3653.TW'}})
    assert calls==['3653.TW']
    assert result.status=='unavailable'


CONTEXT = {'ticker':'3653.TW','stock_id':'3653','instrument_type':'EQUITY',
    'company_identity':{'ticker':'3653.TW','stock_id':'3653','official_name':'健策',
        'legal_name':'健策精密工業股份有限公司','instrument_type':'EQUITY'}}


@pytest.fixture
def wire(monkeypatch,memory_cache):
    import base64,csv,io,json
    from datetime import datetime
    from hashlib import sha256
    from zoneinfo import ZoneInfo
    from data_fetch.market_sources import official_issuer_master as master,twse_history_transport as transport
    from data_fetch.market_sources.official_issuer_master_transport import IssuerMasterHttp
    from test_ta_tung_mops_originals import FIXTURE
    controls={'master_short':'健策','index_company':None,'damage_body':False,'master_rows':501}
    calls=[]
    def download(self,url,diagnostic):
        assert url==master.MASTER_URL
        now=datetime.now(ZoneInfo('Asia/Taipei'));day=f'{now.year-1911:03d}{now.month:02d}{now.day:02d}'
        out=io.StringIO();fields=['公司代號','公司名稱','公司簡稱','營利事業統一編號','英文簡稱','網址','出表日期']
        writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
        rows=[{'公司代號':str(1000+n),'公司名稱':'合成公司'+str(n),'公司簡稱':'合成'+str(n),
            '營利事業統一編號':'10000000','英文簡稱':'Synthetic','網址':'https://example.com','出表日期':day}for n in range(500)]
        rows.append({'公司代號':'3653','公司名稱':CONTEXT['company_identity']['legal_name'],'公司簡稱':controls['master_short'],
            '營利事業統一編號':'10000001','英文簡稱':'SyntheticIssuer','網址':'https://example.com','出表日期':day})
        writer.writerows(rows[:controls['master_rows']]);raw=out.getvalue().encode()
        metadata=master.master_metadata({'http_status':200,'effective_url':url,'num_redirects':0,
            'size_download':len(raw),'content_type':'text/csv','content_length':len(raw),'method':'GET','proxy_used':0,'cache_control':'max-age=1800'},raw,{})
        self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
        calls.append(('master',url))
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
            'request_method':'GET','request_body':None,'response_metadata':metadata}
    monkeypatch.setattr(IssuerMasterHttp,'download_original',download)
    fixture=json.loads(FIXTURE.read_text());raws=[]
    for original in fixture['wire_originals']:
        value=deepcopy(original)
        value['parameters']=json.loads(json.dumps(value['parameters']).replace('1623','3653'))
        value['raw_body_utf8']=value['raw_body_utf8'].replace('1623','3653').replace('大東電','健策')
        raws.append(value)
    def collect(argv,end,**kwargs):
        url,params=argv[2],__import__('json').loads(argv[3]);calls.append(('json',url,params))
        original=next(x for x in raws if x['url']==url and (x['parameters'].get('month')==params.get('month')if url==transport.JSON_URL else x['parameters']==params))
        body=original['raw_body_utf8']
        if controls['index_company'] and url==transport.JSON_URL:
            body=body.replace('健策',controls['index_company'])
        if controls['damage_body'] and url==transport.ORDINARY_DETAIL_URL:
            body=body.replace('健策','其他公司')
        raw=body.encode()
        return {'body':raw,'headers':b'HTTP/2 200\r\nContent-Type: application/json\r\n\r\n',
            'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0}).encode(),'process_started':True},0,None
    monkeypatch.setattr(transport,'collect_capped_process',collect)
    for name in transport.PROXY_ENV:monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    monkeypatch.setattr(transport,'proxy_url_for_request',lambda *a:None)
    monkeypatch.setattr(transport,'cooldown_state',lambda *a:{})
    return master,transport,controls,calls


def test_native_bound_route_replays_master_index_body_and_indexes_pathlessly(wire,tmp_path,monkeypatch):
    from data_fetch.market_sources.mops_master_bound_announcements import fetch_master_bound_announcements
    from data_fetch.market_sources.mops_json_company_history import verified_json_record
    from mops_document_bridge import index_records
    import source_document_index as index
    monkeypatch.setattr(index,'_database_path',lambda:tmp_path/'documents.sqlite3')
    rows,audit=fetch_master_bound_announcements('3653.TW')
    assert audit['status']=='success' and len(rows)==2
    assert all(verified_json_record(row,CONTEXT)=='健策'for row in rows)
    assert audit['http_request_count']==5 and len(audit['request_observations'])==4
    docs,receipt=index_records(rows,CONTEXT)
    assert len(docs)==receipt['accepted']==2 and receipt['new_source_successes']==0
    import json
    assert 'raw_response_path'not in json.dumps(docs)and'/Volumes/'not in json.dumps(docs)
    assert len(index.search_source_documents('3653.TW'))==2


@pytest.mark.parametrize('damage',['master_name','index_company','body_company','incomplete_master'])
def test_dynamic_route_cannot_skip_issuer_or_complete_original_guards(wire,damage):
    from data_fetch.market_sources.mops_master_bound_announcements import fetch_master_bound_announcements
    _,_,control,calls=wire
    if damage=='master_name':control['master_short']='另一公司'
    elif damage=='index_company':control['index_company']='另一公司'
    elif damage=='body_company':control['damage_body']=True
    else:control['master_rows']=2
    rows,audit=fetch_master_bound_announcements('3653.TW')
    assert rows==[] and audit['status']!='success'
    if damage in {'master_name','index_company','incomplete_master'}:
        assert not any(x[0]=='json'and x[1].endswith('_detail')for x in calls)


def test_forged_or_unpublished_action_never_reaches_transport(wire):
    import httpx,json
    from data_fetch.market_sources.official_issuer_master_transport import IssuerMasterHttp
    from search_provider_runtime import SourceResponseError
    master,t,_,calls=wire
    http=t.BoundedHistoryHttp(time.monotonic()+20)
    action={'companyId':'3653','marketKind':'sii','enterDate':'1151027','serialNumber':'1'}
    with pytest.raises(SourceResponseError):http.post(t.ORDINARY_DETAIL_URL,json=action)
    assert not calls
    _,receipt=IssuerMasterHttp(http.deadline).get_receipt(master.MASTER_URL)
    query={'companyId':'3653','year':'115','month':'10','firstDay':'1','lastDay':'31'}
    response=http.post(t.JSON_URL,json=query)
    forged=httpx.Response(200,content=response.content,request=httpx.Request('POST',t.JSON_URL),extensions=dict(response.extensions))
    with pytest.raises(ValueError):http.register_published_json_index(forged,query,receipt)
    http.register_published_json_index(response,query,receipt)
    count=len(calls)
    for field,value in [('companyId','2330'),('serialNumber','99999'),('enterDate','1150101')]:
        with pytest.raises(SourceResponseError):http.post(t.ORDINARY_DETAIL_URL,json={**action,field:value})
    assert len(calls)==count


def test_existing_valid_legacy_cache_remains_first_even_after_observed_failure(monkeypatch,memory_cache):
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import mops_master_bound_announcements as dynamic
    from shared_provider_cache import shared_fetch
    from cache_store import get_cache_json
    from hashlib import sha256
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    init_db()
    record_source_audit_entries([{'source':'recent_catalysts','provider':'TWSE company announcement history',
        'ticker':'3653.TW','status':'unavailable','record_count':0,'http_request_sent':True}])
    records=[{'title':'保留既有舊流程資料'}]
    key='twse-company-announcements:v3:3653.TW'
    shared_fetch(key,lambda:(records,{'status':'success','record_count':1,'http_request_count':4}),freshness_seconds=1800)
    cache_key='shared_provider:v1:'+sha256(key.encode()).hexdigest();before=deepcopy(get_cache_json(cache_key))
    monkeypatch.setattr(dynamic,'fetch_master_bound_announcements',lambda *_:pytest.fail('Valid legacy cache cannot be bypassed'))
    result=TwseCompanyHistoryProvider().fetch(FetchRequest.from_ticker('3653.TW'),{'data':CONTEXT})
    assert result.value==records and result.status=='skipped_fresh_cache'
    assert result.audit['http_request_sent']is False and result.audit['http_request_count']==0
    assert get_cache_json(cache_key)==before


@pytest.mark.parametrize('damage',['missing_master','body_hash','legal_name','instrument','unknown_policy','master_path'])
def test_saved_generic_original_cannot_downgrade_or_rebind_identity(wire,damage):
    from data_fetch.market_sources.mops_master_bound_announcements import fetch_master_bound_announcements
    from data_fetch.market_sources.mops_json_company_history import verified_json_record
    rows,_=fetch_master_bound_announcements('3653.TW');assert rows
    row=deepcopy(rows[0]);data=deepcopy(CONTEXT)
    if damage=='missing_master':row['mops_json_receipt'].pop('issuer_master')
    elif damage=='body_hash':row['mops_json_receipt']['detail_receipt']['raw_response_sha256']='0'*64
    elif damage=='legal_name':data['company_identity']['legal_name']='另一公司股份有限公司'
    elif damage=='instrument':data['company_identity']['quoteType']='ETF'
    elif damage=='unknown_policy':row['mops_json_receipt']['policy']='unsupported-master-policy'
    else:row['mops_json_receipt']['issuer_master']['raw_response_path']='/tmp/untrusted'
    assert verified_json_record(row,data)is None


def test_expired_live_master_can_only_support_historical_document_content(wire,monkeypatch,tmp_path):
    from data_fetch.market_sources.mops_master_bound_announcements import fetch_master_bound_announcements
    from data_fetch.market_sources.mops_json_company_history import verified_json_record,guard_json_result,PROVIDER
    from data_fetch.types import ProviderResult
    from mops_document_bridge import index_records
    import source_document_index as index
    rows,audit=fetch_master_bound_announcements('3653.TW');assert len(rows)==2
    expiry=rows[0]['mops_json_receipt']['issuer_master']['fresh_until_epoch']
    monkeypatch.setattr(time,'time',lambda:expiry+1)
    assert verified_json_record(rows[0],CONTEXT)=='健策'
    current={**audit,'source':'recent_catalysts','provider':PROVIDER,'status':'success','fetched_at_epoch':expiry-100}
    guarded=guard_json_result(ProviderResult('recent_catalysts',PROVIDER,'success',value=rows,audit=current),CONTEXT)
    assert guarded.status=='error'and guarded.value==[]
    monkeypatch.setattr(index,'_database_path',lambda:tmp_path/'documents.sqlite3')
    docs,result=index_records(rows,CONTEXT)
    assert len(docs)==2 and result['new_source_successes']==0
    assert docs[0]['retrieved_at_epoch']<expiry


@pytest.mark.parametrize('error,status,expected',[('rate_limited',429,False),('access_denied',403,False),
    ('authentication',401,False),('original_unverified',None,False),('context_unverified',None,False),
    ('timeout',None,True),('server_error',503,True)])
def test_recovery_routing_never_bypasses_identity_or_access_refusals(memory_cache,error,status,expected):
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import record_source_audit_entries
    from data_fetch.market_sources.mops_master_bound_announcements import prefer_master_bound_route
    init_db()
    record_source_audit_entries([{'source':'recent_catalysts','provider':'TWSE company announcement history',
        'ticker':'3653.TW','status':'error','record_count':0,'http_request_sent':True,
        'error_kind':error,'http_status':status}])
    assert prefer_master_bound_route('3653.TW')is expected


def test_normal_service_preserves_old_failure_and_counts_warm_reuse_as_zero_HTTP(wire,monkeypatch,tmp_path):
    import asyncio,json
    from test_report_refresh_acquisition_audit import init_db,events
    from provider_sla import record_source_audit_entries
    from data_fetch.enrichment_providers import TwseCompanyHistoryProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from data_fetch.types import FetchRequest
    import source_document_index as index
    from provider_acquisition import get_provider_acquisition_summary
    init_db();monkeypatch.setattr(index,'_database_path',lambda:tmp_path/'documents.sqlite3')
    record_source_audit_entries([{'source':'recent_catalysts','provider':'TWSE company announcement history',
        'ticker':'3653.TW','status':'unavailable','record_count':0,'http_request_sent':True,'http_request_count':1}])
    original=events()[0]
    service=StockDataService(ProviderRegistry([TwseCompanyHistoryProvider()]))
    request=FetchRequest.from_ticker('3653.TW',force_refresh=False)
    first=asyncio.run(service.fetch_source_async(request,'official_announcements',context={'data':CONTEXT}))
    assert len(first.data['recent_catalysts'])==2 and first.source_audit[0]['status']=='success'
    from source_content_selection import select_company_records
    from datetime import datetime
    from zoneinfo import ZoneInfo
    selected,_=select_company_records(first.data['recent_catalysts'],CONTEXT,cutoff=datetime.now(ZoneInfo('Asia/Taipei')))
    assert len(selected)==2
    before_calls=len(wire[-1])
    second=asyncio.run(service.fetch_source_async(request,'official_announcements',context={'data':CONTEXT}))
    assert len(wire[-1])==before_calls
    assert second.source_audit[0]['status']=='skipped_fresh_cache'and second.source_audit[0]['http_request_count']==0
    assert second.source_audit[0]['request_observations']==[]
    assert len(index.search_source_documents('3653.TW'))==2
    assert events()[0]==original
    summary=next(r for r in get_provider_acquisition_summary()['sources']if r['source']=='recent_catalysts')
    assert summary['fetched_count']==1 and summary['fetch_attempts']==2
