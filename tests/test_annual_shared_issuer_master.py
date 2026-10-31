"""Captured complete master fallback through actual annual acquisition interfaces."""
from copy import deepcopy
from hashlib import sha256
import json
import time
from pathlib import Path

import pytest
from test_shared_provider_cache import memory_cache
from test_cal_annual_bridge import Http as CalBodies, DATA as CAL_DATA
from test_tcfhc_annual_financial import Http as HoldingBodies, DATA as HOLDING_DATA

ROOT=Path(__file__).parents[1]
E=ROOT/'docs/evidence/source-acquisition/20261014/issuer-master-reliability/compression-research'
RAW=(E/'json.decoded').read_bytes(); WIRE=(E/'json.wire').read_bytes()
CSV='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
JSON='https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
NOW=1791936000.


@pytest.fixture
def native_master(monkeypatch,memory_cache):
    from provider_resilience import clear_provider_circuits, clear_provider_throttles
    from data_fetch.market_sources.cal_annual_bridge import PROVIDER as CAL
    from data_fetch.market_sources.tcfhc_annual_financial import PROVIDER as HOLDING
    for provider in (CAL,HOLDING):
        clear_provider_circuits(provider);clear_provider_throttles(provider)
    from data_fetch.market_sources import issuer_news_transport as old, gce_conference_transport as native, official_issuer_master_json as compressed
    monkeypatch.setattr(time,'time',lambda:NOW)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for key in old.PROXY_ENV:monkeypatch.delenv(key,raising=False)
    calls=[];control={'csv_status':200,'csv_rc':28,'wire':WIRE,'json_status':200,'json_rc':0,'policy':''}
    def process(args,deadline,**options):
        url=args[-1];calls.append((url,args,deadline,options))
        assert url in {CSV,JSON},'only offline master process seam allowed'
        is_csv=url==CSV;status=control['csv_status'] if is_csv else control['json_status']
        body=control.get('csv_body',b'partial CSV') if is_csv else control['wire'];mime='text/csv' if is_csv else 'application/json'
        headers=f'HTTP/2 {status}\r\nContent-Type: {mime}\r\n'
        if not is_csv:headers+='Content-Encoding: gzip\r\nCache-Control: '+control['policy']+'\r\n'
        meta={'http_code':status,'url_effective':url,'num_redirects':0,'size_download':len(body),'content_type':mime,'method':'GET','proxy_used':0}
        return {'body':body,'headers':(headers+'\r\n').encode(),'metadata':json.dumps(meta).encode(),'process_started':True},control['csv_rc'] if is_csv else control['json_rc'],None
    for module in (old,native,compressed):
        monkeypatch.setattr(module,'collect_capped_process',process)
        monkeypatch.setattr(module,'proxy_url_for_request',lambda *a:None)
        monkeypatch.setattr(module,'observe_http_response',lambda *a:None)
    yield calls,control
    for provider in (CAL,HOLDING):
        clear_provider_circuits(provider);clear_provider_throttles(provider)


def transport(ticker,*,cached_bodies=False):
    if ticker=='2610.TW':
        from data_fetch.market_sources.cal_annual_transport import BridgeHttp
        class Mixed(CalBodies):
            def __init__(self):super().__init__();self.master=BridgeHttp();self.master.deadline=self.deadline
            def request(self,url,**kwargs):
                if url in {CSV,JSON}:
                    start=len(self.master.components)
                    try:return self.master.request(url,**kwargs)
                    finally:self.components.extend(deepcopy(self.master.components[start:]));self.calls.append(url)
                return super().request(url,**kwargs)
    else:
        from data_fetch.market_sources.tcfhc_annual_transport import AnnualHttp
        class Mixed(HoldingBodies):
            def __init__(self):super().__init__(cached=cached_bodies);self.master=AnnualHttp(self.deadline)
            def request(self,url):
                if url in {CSV,JSON}:
                    start=len(self.master.components)
                    try:return self.master.request(url)
                    finally:self.components.extend(deepcopy(self.master.components[start:]));self.calls.append(url)
                return super().request(url)
    return Mixed()


def result(ticker,http):
    if ticker=='2610.TW':
        from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_result
        return fetch_bridge_result(ticker,transport=http)
    from data_fetch.market_sources.tcfhc_annual_financial import fetch_annual_result
    return fetch_annual_result(ticker,transport=http)


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
def test_public_annual_csv_timeout_recovers_complete_gzip_json(native_master,ticker):
    calls,_=native_master;http=transport(ticker);out=result(ticker,http)
    assert out['value'] is not None, out['audit']
    assert out['value']['years']==['2021','2022','2023','2024','2025']
    mr=out['value']['issuer_master_receipt']
    assert mr['source_url']==JSON and mr['raw_response_sha256']==sha256(RAW).hexdigest()
    assert mr['evidence_kind']=='decoded_http_response_bytes' and mr['wire_original']['raw_response_sha256']==sha256(WIRE).hexdigest()
    assert [c[0] for c in calls]==[CSV,JSON]
    assert out['audit']['http_request_count']==(25 if ticker=='2610.TW' else 8)
    assert out['audit']['component_statuses']['0']['error_kind']=='timeout'
    assert out['audit']['component_statuses']['0']['http_request_sent'] is True
    for url,args,deadline,_ in calls:
        if url==CSV:
            assert float(args[args.index('--max-time')+1])==8
            assert float(args[args.index('--connect-timeout')+1])==3
        else:
            assert float(args[args.index('--max-time')+1])<=5
            assert float(args[args.index('--connect-timeout')+1])<=2
        assert deadline<=http.deadline
        assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'
    assert 'Accept-Encoding: gzip' in calls[1][1]


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
def test_two_master_failures_do_not_trigger_a_third_request(native_master,ticker):
    calls,c=native_master;c['json_rc']=28
    out=result(ticker,transport(ticker))
    assert out['value'] is None and out['audit']['record_count']==0
    assert [x[0] for x in calls]==[CSV,JSON]
    assert out['audit']['http_request_count']==2


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
@pytest.mark.parametrize('status',[401,403,429])
def test_denied_csv_never_changes_endpoint(native_master,ticker,status):
    calls,c=native_master;c.update(csv_status=status,csv_rc=0)
    h=transport(ticker);out=result(ticker,h)
    assert out['value'] is None and [x[0] for x in calls]==[CSV]
    assert out['audit']['component_statuses']['0']['http_status']==status
    assert len(h.calls)==1


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
def test_whole_deadline_exhaustion_sends_no_master(native_master,ticker):
    calls,_=native_master;h=transport(ticker);h.master.deadline=time.monotonic()-1
    out=result(ticker,h)
    assert out['value'] is None and not calls and out['audit']['http_request_count']==0


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
def test_warm_identity_and_new_financial_bodies_are_new_canonical_source_success(native_master,monkeypatch,ticker):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from provider_correlation import correlation_scope
    calls,_=native_master
    cold=result(ticker,transport(ticker));assert cold['value'] is not None
    first=cold['value']['issuer_master_receipt'];calls.clear()
    monkeypatch.setattr(time,'time',lambda:NOW+60)
    h=transport(ticker)
    if ticker=='2610.TW':
        from data_fetch.market_sources import cal_annual_bridge as source
        monkeypatch.setattr(source,'BridgeHttp',lambda **kw:h);data=CAL_DATA
    else:
        from data_fetch.market_sources import tcfhc_annual_transport as t
        monkeypatch.setattr(t,'AnnualHttp',lambda **kw:h);data=HOLDING_DATA
    with correlation_scope(replace=True,ticker=ticker,fetch_id='annual-master-warm-new-body'):
        out=AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker(ticker),{'data':deepcopy(data)})
    assert out.value is not None and out.audit['status']=='success',out.audit
    assert out.audit['cache_hit'] is False and out.audit['http_request_count']==(23 if ticker=='2610.TW' else 6)
    new=out.audit['issuer_master_receipt']
    assert new['cache_hit'] is True and new['retrieved_at']==first['retrieved_at']==NOW
    assert new['fresh_until_epoch']==first['fresh_until_epoch']
    assert out.audit['fetched_at_epoch']==NOW+60 and not calls


def test_new_index_with_old_pdf_bodies_is_not_new_source_success(native_master,monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from data_fetch.market_sources import tcfhc_annual_transport as t
    from official_response_evidence import archive_response
    from provider_acquisition import observation_kind
    calls,_=native_master
    assert result('5880.TW',transport('5880.TW'))['value'] is not None
    calls.clear();monkeypatch.setattr(time,'time',lambda:NOW+60)
    h=transport('5880.TW',cached_bodies=True);old=h.request
    def mixed(url):
        raw,r=old(url)
        if url==t.IR_URL:
            r=archive_response(raw,source_url=url,retrieved_at=NOW+60)
            r.update(http_status_observed=True,request_method='GET',response_complete=True,cache_hit=False)
            h.components[-1].update(http_request_sent=True,cache_hit=False)
        return raw,r
    h.request=mixed
    out=result('5880.TW',h);assert out['value'] is not None
    audit=out['audit']
    assert audit['cache_hit'] is True and audit['http_request_count']==1
    assert audit['fetched_at_epoch']==NOW-40 and audit['event_kind']=='cache_hit'
    assert observation_kind({**audit,'details':audit})=='fresh_cache_count'
    monkeypatch.setattr(t,'AnnualHttp',lambda **kw:h)
    out=AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW'),{'data':deepcopy(HOLDING_DATA)})
    assert out.value is None and out.audit['status']!='success' and not calls


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
@pytest.mark.parametrize('stage',['parse','last_readback','batch_cleanup'])
def test_short_master_expiry_rechecked_at_actual_handoff(native_master,monkeypatch,ticker,stage):
    from contextlib import contextmanager
    calls,c=native_master;c['policy']='max-age=5';clock=[NOW]
    monkeypatch.setattr(time,'time',lambda:clock[0]);h=transport(ticker)
    if ticker=='2610.TW':
        from data_fetch.market_sources import cal_annual_bridge as s
    else:
        from data_fetch.market_sources import tcfhc_annual_financial as s
    if stage=='last_readback':
        old=s.read_master;count=[0]
        def read(*a,**kw):
            value=old(*a,**kw);count[0]+=1
            if count[0]==2:clock[0]=NOW+5.1
            return value
        monkeypatch.setattr(s,'read_master',read)
    elif stage=='parse':
        old=s._book
        def book(raw,year,*a,**kw):
            value=old(raw,year,*a,**kw)
            if year==2025:clock[0]=NOW+5.1
            return value
        monkeypatch.setattr(s,'_book',book)
    else:
        @contextmanager
        def batch():
            yield h
            clock[0]=NOW+5.1
        h.batch=batch
    out=result(ticker,h)
    assert out['value'] is None and out['audit']['record_count']==0
    assert out['audit']['http_request_count']==(25 if ticker=='2610.TW' else 8)
    assert [x[0] for x in calls]==[CSV,JSON]


@pytest.mark.parametrize('key,state',[
    ('raw',{'error_kind':'SourceResponseError','retry_after_epoch':NOW+60}),
    ('raw',{'error_kind':'timeout','retry_after_epoch':NOW+60}),
    ('raw',{'error_kind':'access_denied','http_status':403,'retry_after_epoch':NOW+60}),
    ('raw',{'error_kind':'timeout'}),('raw',[]),
    ('admission',{'retry_at':NOW+60}),('admission',{}),('admission',[]),
    ('admission',{'retry_at':True}),('admission',{'retry_at':float('nan')}),
    ('admission',{'retry_at':0,'next_request_at':NOW+60}),
])
def test_legacy_holding_cold_guards_cannot_be_bypassed(native_master,key,state):
    import cache_store
    from data_fetch.market_sources import annual_issuer_master as m
    calls,_=native_master
    k=m.LEGACY_RAW_KEY if key=='raw' else m.LEGACY_ADMISSION_KEY
    cache_store.set_cache_json(k,state,ttl_seconds=120)
    saved=deepcopy(cache_store.get_cache_json(k))
    out=result('5880.TW',transport('5880.TW'))
    assert out['value'] is None and not calls and out['audit']['http_request_count']==0
    assert json.dumps(cache_store.get_cache_json(k),sort_keys=True)==json.dumps(saved,sort_keys=True)


@pytest.mark.parametrize('endpoint',['csv','json'])
def test_valid_shared_warm_identity_precedes_legacy_cold_guard(native_master,monkeypatch,endpoint):
    import cache_store
    from data_fetch.market_sources import annual_issuer_master as m
    from test_cal_annual_bridge import raw
    calls,c=native_master
    if endpoint=='csv':c.update(csv_rc=0,csv_body=raw('master'))
    first=result('5880.TW',transport('5880.TW'));assert first['value'] is not None
    saved=deepcopy(cache_store.get_cache_backend()._entries)
    cache_store.set_cache_json(m.LEGACY_ADMISSION_KEY,{'retry_at':NOW+120},ttl_seconds=120)
    calls.clear();monkeypatch.setattr(time,'time',lambda:NOW+1)
    second=result('5880.TW',transport('5880.TW'))
    assert second['value'] is not None and not calls
    assert second['value']['issuer_master_receipt']['cache_hit'] is True
    for k,(v,expiry) in saved.items():
        if isinstance(v,dict) and 'receipt' in v:assert cache_store.get_cache_backend()._entries[k]==(v,expiry)


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
def test_shared_saved_original_replay_does_not_require_a_current_cache(native_master,monkeypatch,ticker):
    from data_fetch.market_sources import official_issuer_master as shared
    out=result(ticker,transport(ticker));assert out['value'] is not None
    v=deepcopy(out['value']);monkeypatch.setattr(time,'time',lambda:NOW+86400*10)
    monkeypatch.setattr(shared,'_stored',lambda *a:pytest.fail('historical replay must not query live master cache'))
    if ticker=='2610.TW':
        from data_fetch.market_sources.cal_annual_bridge import project_bridge_history as project
    else:
        from data_fetch.market_sources.tcfhc_annual_financial import project_annual_statement as project
    assert project(v,ticker)==v


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
@pytest.mark.parametrize('change',['policy','removed_policy','wire_hash','url','cache_flag','body_hash','manifest'])
def test_shared_master_tampering_cannot_downgrade_to_legacy(native_master,ticker,change):
    out=result(ticker,transport(ticker));assert out['value'] is not None
    v=deepcopy(out['value']);r=v['issuer_master_receipt']
    if change=='policy':r['retrieval_policy']='unknown'
    elif change=='removed_policy':del r['retrieval_policy']
    elif change=='wire_hash':r['wire_original']['raw_response_sha256']='0'*64
    elif change=='url':r['source_url']=CSV
    elif change=='cache_flag':r['cache_hit']=1
    elif change=='body_hash':r['raw_response_sha256']='0'*64
    else:r['acquisition_manifest']['raw_response_sha256']='0'*64
    if ticker=='2610.TW':
        from data_fetch.market_sources.cal_annual_bridge import project_bridge_history as project
    else:
        from data_fetch.market_sources.tcfhc_annual_financial import project_annual_statement as project
    assert project(v,ticker) is None


@pytest.mark.parametrize('state',[{'error_kind':False},{'fallback_eligible':0},{'http_status':True}])
def test_malformed_legacy_raw_metadata_cannot_authorize_http(native_master,state):
    import cache_store
    from data_fetch.market_sources import annual_issuer_master as m
    calls,_=native_master
    cache_store.set_cache_json(m.LEGACY_RAW_KEY,state,ttl_seconds=120)
    out=result('5880.TW',transport('5880.TW'))
    assert out['value'] is None and not calls


def test_cal_local_archive_failure_does_not_restart_batch(native_master):
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_result
    class Broken(CalBodies):
        def request(self,url,**kwargs):
            self.calls.append(url)
            raise OSError('isolated unavailable original archive')
    h=Broken();out=fetch_bridge_result('2610.TW',transport=h)
    assert out['value'] is None and len(h.calls)==1 and out['audit']['http_request_count']==0


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
@pytest.mark.parametrize('change',['issuer','seven_day_window'])
def test_complete_master_does_not_weaken_each_issuer_identity_or_date_window(native_master,ticker,change):
    import gzip
    calls,c=native_master;rows=json.loads(RAW)
    if change=='issuer':next(r for r in rows if r['公司代號']==ticker.split('.')[0])['營利事業統一編號']='00000000'
    else:
        for row in rows:row['出表日期']='1151004'
    c['wire']=gzip.compress(json.dumps(rows,ensure_ascii=False).encode())
    h=transport(ticker);out=result(ticker,h)
    assert out['value'] is None and out['audit']['record_count']==0 and len(h.calls)==1
    assert [x[0] for x in calls]==[CSV,JSON]


@pytest.mark.parametrize('ticker',['2610.TW','5880.TW'])
@pytest.mark.parametrize('policy',['no-store','no-cache'])
def test_master_policy_does_not_reuse_unreusable_success(native_master,ticker,policy):
    calls,c=native_master;c['policy']=policy
    for _ in range(2):
        out=result(ticker,transport(ticker));assert out['value'] is not None
        r=out['value']['issuer_master_receipt']
        assert r['reusable'] is False and r['cache_hit'] is False
    assert [x[0] for x in calls]==[CSV,JSON,JSON]


def test_holding_legacy_guard_storage_failure_prevents_both_endpoints(native_master,monkeypatch):
    import cache_store
    from data_fetch.market_sources import annual_issuer_master as m
    old=cache_store.get_cache_json;calls,_=native_master
    def read(key):
        if key==m.LEGACY_RAW_KEY:raise OSError('isolated guard unavailable')
        return old(key)
    monkeypatch.setattr(cache_store,'get_cache_json',read)
    out=result('5880.TW',transport('5880.TW'))
    assert out['value'] is None and out['audit']['error_kind']=='guard_storage_unavailable' and not calls
