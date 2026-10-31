"""Real production transport routing; only anonymous native process I/O is offline."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import asyncio,base64,json,time
import pytest
from test_annual_shared_issuer_master import native_master,RAW,WIRE,CSV,JSON,NOW
from test_shared_provider_cache import memory_cache

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tests/run_prompt_boundary_tests.py').exists())
STAGE=ROOT/'docs/evidence/source-acquisition/20261016/remaining-source-expansion/csc-master-diagnosis/staged'
E=ROOT/'docs/evidence/source-acquisition/20261014/free-gap-followup/industrial-research'
INDEX='https://www.csc.com.tw/csc_e/ss/pst/pst_index.html'
PDF='https://www.csc.com.tw/csc_e/ss/pst/pdf/2026Sep23.pdf'
MASTER_BYTES=(ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body').read_bytes()

@pytest.fixture
def packet(native_master,monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as old
    from data_fetch.market_sources import twse_iih_conference_notice as iih_source
    master_process=old.collect_capped_process
    bodies={INDEX:(E/'csc-conference-index.body').read_bytes(),PDF:(E/'csc-presentation.body').read_bytes()}
    mops_fixture=ROOT/'tests/fixtures/source_acquisition/csc_mops_month_202609'
    iih_raw=(mops_fixture/'iih.json').read_bytes()
    month_raw=(mops_fixture/'month.html').read_bytes()
    iih_url='https://wwwc.twse.com.tw/rwd/en/IIH/company/events'
    month_url=('https://emops.twse.com.tw/server-java/t100sb07_1_e?TYPEK=all&step=show&code=2002'
               '&LPSHOW_DATE_YY=2026&LPSHOW_DATE_MM=09')
    class ReplayResponse:
        status_code=200
        def __init__(self,content,url):self.content,self.url=content,url
        def json(self):return json.loads(iih_raw)
    class ReplayHistoryHttp:
        def __init__(self,deadline,**kwargs):self.deadline=deadline;self.http_request_count=0;self.request_observations=[]
        def get(self,url,*,params=None,**kwargs):
            self.http_request_count+=1
            if url==iih_url and params=={'code':'2002'}:return ReplayResponse(iih_raw,url)
            if url==month_url and params is None:return ReplayResponse(month_raw,url)
            raise AssertionError(f'unexpected official IIH/MOPS route: {url} {params}')
    monkeypatch.setattr(iih_source,'BoundedHistoryHttp',ReplayHistoryHttp)
    body_calls=[]
    def process(args,deadline,**options):
        url=args[-1]
        if url in (CSV,JSON):return master_process(args,deadline,**options)
        assert url in bodies,'unexpected endpoint';body_calls.append(url);raw=bodies[url]
        ctype='application/pdf'if url==PDF else'text/html'
        return {'process_started':True,'body':raw,'headers':f'HTTP/2 200\r\nContent-Type: {ctype}\r\nContent-Length: {len(raw)}\r\n\r\n'.encode(),
            'metadata':json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,'size_download':len(raw),'content_type':ctype,'method':'GET','proxy_used':0}).encode()},0,None
    monkeypatch.setattr(old,'collect_capped_process',process)
    return native_master[0],native_master[1],bodies,body_calls


def context():
    return {'ticker':'2002.TW','quote_type':'EQUITY','company_name':'中鋼 / China Steel Corporation',
        'company_identity':{'ticker':'2002.TW','stock_id':'2002','official_name':'中鋼','instrument_type':'EQUITY'}}


def normal():
    from data_fetch import StockDataService,FetchRequest
    return asyncio.run(StockDataService().fetch_source_async(FetchRequest.from_ticker('2002.TW'),'earnings_call',context={'data':context()}))


def assert_only_independent_official_notice(result,packet):
    notice=result.data.get('earnings_call')
    assert notice
    assert notice['source']=='TWSE IIH/MOPS monthly conference index'
    assert notice['transcript_available'] is False and notice['transcript_excerpt']==''
    assert notice['coverage_status'] in {'official_monthly_event_metadata','official_monthly_event_metadata_with_material_links'}
    assert not packet[3]


def test_normal_default_service_csv_timeout_recovers_complete_json_and_qualified_body(packet):
    result=normal()
    assert result.data.get('earnings_call',{}).get('documents'), 'CSV timeout must reach qualified CSC body through the shared complete JSON roster'
    doc=result.data['earnings_call']['documents'][0];audit=result.source_audit[0]
    assert doc['page_count']==35 and doc['coverage_status']=='partial'
    assert audit['http_request_count']==4 and audit['status']=='success' and audit['record_count']==1
    assert [c[0]for c in packet[0]]==[CSV,JSON] and packet[3]==[INDEX,PDF]
    assert audit['component_statuses'][0]['error_kind']=='timeout'
    identity=result.data['earnings_call']['csc_conference_receipt']['identity']
    assert identity['source_url']==JSON and identity['raw_response_sha256']==sha256(RAW).hexdigest()
    assert identity['wire_original']['raw_response_sha256']==sha256(WIRE).hexdigest()
    for url,args,deadline,_ in packet[0]:
        if url==CSV:
            assert float(args[args.index('--max-time')+1])==8
            assert float(args[args.index('--connect-timeout')+1])==3
        else:
            assert float(args[args.index('--max-time')+1])<=5
            assert float(args[args.index('--connect-timeout')+1])<=2
        assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'


@pytest.mark.parametrize('kind,state',[
    ('admission',{}),('admission',{'retry_at':True}),('admission',{'retry_at':float('nan')}),
    ('admission',{'retry_at':NOW+60}),('raw',{'error_kind':'timeout'}),('raw',{'error_kind':False}),
    ('raw',{'error_kind':'SourceResponseError','retry_after_epoch':NOW+60}),
    ('raw',{'error_kind':'HTTPStatusError','http_status':403,'retry_after_epoch':NOW+60}),
])
def test_preserves_legacy_cold_guard_before_either_endpoint(native_master,kind,state):
    from test_conference_shared_issuer_master import test_old_source_namespace_blocks_cold_both_endpoints
    test_old_source_namespace_blocks_cold_both_endpoints(native_master,'csc',kind,state)


@pytest.mark.parametrize('status',[401,403,429])
def test_refused_csv_never_starts_json(native_master,status):
    from test_conference_shared_issuer_master import test_denied_csv_never_calls_json
    test_denied_csv_never_calls_json(native_master,'csc',status)


def test_legacy_guard_unavailable_no_network(native_master,monkeypatch):
    from test_conference_shared_issuer_master import test_old_guard_storage_failure_does_not_allow_network
    test_old_guard_storage_failure_does_not_allow_network(native_master,monkeypatch,'csc')


def test_malformed_csv_never_falls_back(native_master):
    from test_conference_shared_issuer_master import test_malformed_successful_csv_does_not_authorize_fallback
    test_malformed_successful_csv_does_not_authorize_fallback(native_master,'csc')


def test_no_direct_json_or_expired_deadline(native_master):
    from test_conference_shared_issuer_master import test_deadline_and_direct_json_cannot_create_hidden_request
    test_deadline_and_direct_json_cannot_create_hidden_request(native_master,'csc')


def test_two_timeouts_stop_with_actual_two_requests(packet):
    packet[1]['json_rc']=28
    result=normal();assert not result.data.get('earnings_call')
    assert result.source_audit[0]['http_request_count']==2 and result.source_audit[0]['status']=='error'
    assert [x[0]for x in packet[0]]==[CSV,JSON] and not packet[3]


def test_wrong_csv_identity_does_not_authorize_json(packet):
    packet[1].update(csv_rc=0,csv_body=MASTER_BYTES.replace(b'30414175',b'30414176'))
    result=normal();assert_only_independent_official_notice(result,packet)
    assert [x[0]for x in packet[0]]==[CSV]


@pytest.mark.parametrize('field,value',[('公司名稱','中國鋼鐵結構股份有限公司'),('營利事業統一編號','30414176'),('網址','http://evil.example'),('英文簡稱','CSC Group'),('出表日期','1151030')])
def test_json_identity_and_future_date_not_relaxed(packet,field,value):
    import gzip
    rows=json.loads(RAW)
    if field=='出表日期':
        for row in rows:row[field]=value
    else:next(r for r in rows if r['公司代號']=='2002')[field]=value
    packet[1]['wire']=gzip.compress(json.dumps(rows,ensure_ascii=False).encode())
    result=normal();assert_only_independent_official_notice(result,packet)
    # Existing generic metadata fallback retains the issuer failure under its component.
    failed=result.source_audit[0]['component_statuses']['CSC_presentation']
    assert failed['csc_originals_verified'] is False and failed['http_request_count']==2
    assert [x[0]for x in packet[0]]==[CSV,JSON]


def test_cross_issuer_warm_original_before_csc_guard_never_renews_epoch(packet,monkeypatch):
    from data_fetch.market_sources import unitech_conference_transport as other,csc_conference_transport as t
    import cache_store
    packet[1]['policy']='max-age=300'
    first=other.ConferenceHttp(time.monotonic()+25).get_receipt(CSV)[1]
    packet[0].clear();monkeypatch.setattr(time,'time',lambda:NOW+30)
    cache_store.set_cache_json(t.ConferenceHttp._admission_key(CSV),{'retry_at':NOW+100},ttl_seconds=100)
    from data_fetch.market_sources import csc_conference as s
    details={};value=s.fetch_csc_context('2002.TW',force_refresh=True,use_cache=False,diagnostics=details)
    receipt=value['csc_conference_receipt']['identity']
    assert receipt['cache_hit'] is True and receipt['retrieved_at']==first['retrieved_at']==NOW
    assert receipt['fresh_until_epoch']==first['fresh_until_epoch']==NOW+300
    assert not packet[0] and packet[3]==[INDEX,PDF]
    assert details['cache_hit'] is False and details['http_request_count']==2
    assert value['documents'][0]['retrieved_at_epoch']==NOW+30


def test_full_packet_warm_body_is_cache_count_not_new_success(packet,monkeypatch):
    from provider_acquisition import observation_kind
    first=normal();packet[0].clear();packet[3].clear();monkeypatch.setattr(time,'time',lambda:NOW+20)
    again=normal();a=again.source_audit[0]
    assert a['status']=='skipped_fresh_cache' and a['http_request_count']==0 and a['cache_hit'] is True
    assert again.data['earnings_call']['documents']==first.data['earnings_call']['documents']
    assert a['fetched_at_epoch']==NOW and not packet[0] and not packet[3]
    assert observation_kind({'provider':a['provider'],'status':a['status'],'record_count':a['record_count'],'message':'','details':a})=='fresh_cache_count'


@pytest.mark.parametrize('change',['v2_to_v1','missing_marker','all_markers','wrong_url','epoch','expiry'])
def test_v2_master_cannot_downgrade_or_relabel(packet,change):
    from data_fetch.market_sources import csc_conference as s,csc_conference_transport as t
    value=normal().data['earnings_call'];p=value['csc_conference_receipt'];r=p['identity']
    assert p['policy']==s.POLICY and s.POLICY!=s.LEGACY_POLICY
    if change=='v2_to_v1':p['policy']=s.LEGACY_POLICY
    elif change=='missing_marker':r.pop('retrieval_policy')
    elif change=='all_markers':
        for key in set(r)-t.RECEIPT_FIELDS:r.pop(key)
    elif change=='wrong_url':r['source_url']=CSV
    elif change=='epoch':r['retrieved_at']+=1
    else:r['fresh_until_epoch']+=1
    assert not s.verify_context(value,'2002.TW')


def legacy_source():
    import importlib.util,sys
    from unittest.mock import patch
    prefix='data_fetch.market_sources.'
    def load(name,file):
        spec=importlib.util.spec_from_file_location(prefix+name,STAGE/'before/backend/data_fetch/market_sources'/file)
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    transport=load('_csc_legacy_transport','csc_conference_transport.py')
    with patch.dict(sys.modules,{prefix+'csc_conference_transport':transport}):
        return load('_csc_legacy_source','csc_conference.py')


def test_exact_before_v1_full_packet_replays_without_rewriting_policy_or_receipt(packet):
    from data_fetch.market_sources import csc_conference as current
    packet[1].update(csv_rc=0,csv_body=MASTER_BYTES)
    old=legacy_source().fetch_csc_context('2002.TW');before=deepcopy(old)
    assert old['csc_conference_receipt']['policy']=='csc-original-presentation-v1'
    assert current.verify_context(old,'2002.TW') and old==before
    old['csc_conference_receipt']['policy']=current.POLICY
    assert not current.verify_context(old,'2002.TW')
    old=deepcopy(before);old['csc_conference_receipt']['identity']['retrieval_policy']='fake shared'
    assert not current.verify_context(old,'2002.TW')
    old=deepcopy(before);old['csc_conference_receipt']['identity']['source_url']=JSON
    assert not current.verify_context(old,'2002.TW')


@pytest.mark.parametrize('stage',['reader','diagnostic'])
def test_short_shared_master_expiry_checked_after_final_work(packet,monkeypatch,stage):
    from data_fetch.market_sources import csc_conference as s
    from search_provider_runtime import SourceResponseError
    packet[1]['policy']='max-age=5';wall=[NOW];monkeypatch.setattr(time,'time',lambda:wall[0])
    if stage=='reader':
        old=s.extract_csc_presentation_pages
        def delayed(*a,**k):v=old(*a,**k);wall[0]=NOW+5.1;return v
        monkeypatch.setattr(s,'extract_csc_presentation_pages',delayed)
        details={}
    else:
        class Details(dict):
            def update(self,*a,**k):
                super().update(*a,**k)
                if self.get('csc_originals_verified') is True:wall[0]=NOW+5.1
        details=Details()
    with pytest.raises(SourceResponseError):s.fetch_csc_context('2002.TW',diagnostics=details)
    assert details['csc_originals_verified'] is False and 'cache_hit'not in details
    assert details['http_request_count']==4


def test_json_source_only_refresh_preserves_report_and_partial_semantics(packet,monkeypatch,tmp_path):
    from data_fetch import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_refresh_acquisition_audit import init_db
    from test_unitech_tcfhc_source_integration import saved_target,assert_preserved
    init_db();storage=InMemoryStorage();name,keys,before=saved_target(storage,'2002.TW','中鋼')
    before['data'].update(context());storage.save_report(keys.data_key,json.dumps(before).encode(),content_type='application/json')
    result=asyncio.run(refresh_report_data_snapshot(name,output_dir=str(tmp_path),storage=storage,refresh_service=StockDataService(),source='earnings_call',return_refreshed_data=True))
    after=json.loads(storage.get_report(keys.data_key).content);doc=after['data']['earnings_call']['documents'][0]
    assert doc['page_count']==35 and doc['coverage_status']=='partial' and doc['q_and_a_transcript_available'] is False
    assert '*preliminary results' in doc['pages'][10]['text'] and doc['published_at'] is None
    assert doc['financial_scope_caution'] and doc['subsidiary_scope_caution'] and doc['period_scope_caution']
    assert_preserved(storage,keys,before,after)
    assert result['analysis_text_stale'] is True
