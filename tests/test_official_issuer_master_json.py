"""Captured official JSON fallback through both public issuer collectors."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import json
import time
import pytest
from search_provider_runtime import SourceResponseError
from test_gce_conference import harness
from data_fetch.market_sources.gce_conference_transport import ConferenceHttp
_NATIVE_DOWNLOAD=ConferenceHttp.download_original

ROOT=Path(__file__).parents[1]
D=ROOT/'docs/evidence/source-acquisition/20261014/issuer-master-reliability/compression-research'
JSON_URL='https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
RAW=(D/'json.decoded').read_bytes();WIRE=(D/'json.wire').read_bytes()


def json_value(raw=RAW,wire=WIRE,encoding='gzip',policy=''):
    meta={'http_status':200,'effective_url':JSON_URL,'num_redirects':0,'size_download':len(wire),
          'content_type':'application/json','content_length':None,'method':'GET','proxy_used':0,
          'cache_control':policy,'content_encoding':encoding,'age':None,'wire_bytes':len(wire),
          'wire_sha256':sha256(wire).hexdigest(),'decoded_bytes':len(raw),'decoded_sha256':sha256(raw).hexdigest()}
    return {'url':JSON_URL,'body_b64':base64.b64encode(raw).decode(),'wire_b64':base64.b64encode(wire).decode(),
            'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':meta}


@pytest.fixture
def fallback(harness,monkeypatch):
    from data_fetch.market_sources import gce_conference_transport as t
    old=t.ConferenceHttp.download_original;calls=[];control={'failure':'timeout','value':json_value()}
    def download(self,url,diagnostic):
        calls.append(url)
        if url==t.MASTER_URL:
            self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
            raise SourceResponseError(control['failure'],status_code=200)
        if url==JSON_URL:
            self.http_request_count+=1;diagnostic.update(http_request_sent=True,http_status=200)
            return deepcopy(control['value'])
        return old(self,url,diagnostic)
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    return t,calls,control


def test_public_cold_csv_timeout_recovers_full_json_and_retains_first_attempt(fallback):
    from data_fetch.market_sources import gce_conference as source
    t,calls,c=fallback;d={}
    value=source.fetch_gce_context('2368.TW',diagnostics=d)
    assert len(value['documents'][0]['pages'])==11 and d['http_request_count']==4
    assert calls==[t.MASTER_URL,JSON_URL,t.INDEX_URL,t.PDF_URL]
    identity=value['gce_conference_receipt']['identity']
    assert identity['source_url']==JSON_URL and identity['raw_response_sha256']==sha256(RAW).hexdigest()
    assert d['component_statuses'][0]['error_kind']=='timeout'
    assert d['component_statuses'][0]['http_request_sent'] is True
    assert source.verify_context(value,'2368.TW',max_age=1800)


@pytest.mark.parametrize('failure',['timeout','transport_error','server_error'])
def test_only_typed_recoverable_failures_attempt_json(fallback,failure):
    t,calls,control=fallback;control['failure']=failure
    http=t.ConferenceHttp(time.monotonic()+25)
    raw,r=http.get_receipt(t.MASTER_URL)
    assert raw==RAW and calls==[t.MASTER_URL,JSON_URL]
    assert http.components[0]['error_kind']==failure and http.http_request_count==2


@pytest.mark.parametrize('failure',['authentication','access_denied','rate_limited','guard_storage_unavailable','lease_lost',
                                    'single_flight_busy','request_pacing','original_unverified','cache_receipt_invalid','parse_error'])
def test_terminal_primary_errors_never_attempt_another_host(fallback,failure):
    t,calls,control=fallback;control['failure']=failure
    with pytest.raises(SourceResponseError) as exc:t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    assert exc.value.error_kind==failure and calls==[t.MASTER_URL]


def test_expired_whole_deadline_never_falls_back(fallback,monkeypatch):
    from types import SimpleNamespace
    from data_fetch.market_sources import official_issuer_master as m
    t,calls,_=fallback;clock=[100.];http=t.ConferenceHttp(101.)
    old=http.download_original
    def late(url,diag):
        clock[0]=102
        return old(url,diag)
    http.download_original=late;monkeypatch.setattr(m,'time',SimpleNamespace(time=time.time,monotonic=lambda:clock[0]))
    with pytest.raises(SourceResponseError) as exc:http.get_receipt(t.MASTER_URL)
    assert exc.value.error_kind=='timeout' and calls==[t.MASTER_URL]


def test_json_warm_original_and_csv_cooldown_preserve_epochs_and_body_http(fallback,monkeypatch):
    from data_fetch.market_sources import gce_conference as source
    t,calls,_=fallback;d={};first=source.fetch_gce_context('2368.TW',diagnostics=d)
    old=first['gce_conference_receipt']['identity'];clock=time.time()+10
    monkeypatch.setattr(time,'time',lambda:clock)
    second=source.fetch_gce_context('2368.TW',force_refresh=True,diagnostics=d)
    new=second['gce_conference_receipt']['identity']
    assert new['cache_hit'] is True and new['retrieved_at']==old['retrieved_at']
    assert new['fresh_until_epoch']==old['fresh_until_epoch']
    assert [c['http_request_sent'] for c in d['component_statuses']]==[False,False,True,True]
    assert d['component_statuses'][0]['error_kind']=='cooldown'
    assert d['http_request_count']==2 and d['cache_hit'] is False
    assert new['wire_original']==old['wire_original']


@pytest.mark.parametrize('which',['truncated','crc','trailing','members','oversize','encoding'])
def test_gzip_failure_is_closed_without_success_cache(fallback,which):
    import gzip
    from data_fetch.market_sources import official_issuer_master as m
    import cache_store
    t,calls,c=fallback
    if which=='truncated':wire=WIRE[:-5]
    elif which=='crc':wire=WIRE[:-8]+bytes([WIRE[-8]^1])+WIRE[-7:]
    elif which=='trailing':wire=WIRE+b'x'
    elif which=='members':wire=WIRE+WIRE
    elif which=='oversize':wire=gzip.compress(b' '*2_500_001)
    else:wire=WIRE
    c['value']=json_value(wire=wire,encoding='br' if which=='encoding' else 'gzip')
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    assert cache_store.get_cache_json(m._parameters(JSON_URL)[2]) is None
    # Both reserved original attempts remain cooled; no second native request.
    with pytest.raises(SourceResponseError):t.ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(t.MASTER_URL)
    assert calls==[t.MASTER_URL,JSON_URL]


@pytest.mark.parametrize('change',['duplicate_key','missing_field','nonstring','duplicate_code','partial_population','mixed_dates','future','wrong_ubn'])
def test_complete_json_schema_and_exact_issuer_identity_are_required(fallback,change):
    from data_fetch.market_sources import gce_conference as source
    t,calls,c=fallback;rows=json.loads(RAW)
    if change=='duplicate_key':raw=RAW.replace('"公司代號"'.encode(),'"公司代號":"0000","公司代號"'.encode(),1)
    else:
        if change=='missing_field':del rows[-1]['營利事業統一編號']
        elif change=='nonstring':rows[-1]['營利事業統一編號']=True
        elif change=='duplicate_code':rows[-1]['公司代號']=rows[0]['公司代號']
        elif change=='partial_population':rows=rows[:10]
        elif change=='mixed_dates':rows[-1]['出表日期']='1151012'
        elif change=='future':
            for row in rows:row['出表日期']='1151015'
        else:next(r for r in rows if r['公司代號']=='2368')['營利事業統一編號']='00000000'
        raw=json.dumps(rows,ensure_ascii=False).encode()
    c['value']=json_value(raw=raw,wire=raw,encoding='identity')
    with pytest.raises(SourceResponseError):source.fetch_gce_context('2368.TW')
    assert calls==[t.MASTER_URL,JSON_URL]


@pytest.mark.parametrize('change',['epoch','wire_hash','wire_url','wire_kind','wire_time','format','content_length','cache_flag'])
def test_json_saved_receipt_rejects_cross_original_or_retiming(fallback,change):
    from data_fetch.market_sources import official_issuer_master as m
    t,_,_=fallback;raw,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    if change=='epoch':r['retrieved_at']+=1
    elif change=='wire_hash':r['wire_original']['raw_response_sha256']='0'*64
    elif change=='wire_url':r['wire_original']['source_url']=t.MASTER_URL
    elif change=='wire_kind':r['wire_original']['evidence_kind']='private_acquisition_manifest'
    elif change=='wire_time':r['wire_original']['retrieved_at']+=1
    elif change=='format':r['retrieval_policy']=m.POLICY
    elif change=='content_length':r['response_metadata']['content_length']=len(raw)
    else:r['cache_hit']=True
    with pytest.raises(ValueError):t.original_bytes(r,JSON_URL,max_age=1800)


def test_json_identity_encoding_is_truthful_and_shorter_expiry_survives_warm(fallback,monkeypatch):
    t,calls,c=fallback;c['value']=json_value(raw=RAW,wire=RAW,encoding='identity',policy='private, max-age=20')
    _,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL);stamp=r['retrieved_at']
    assert r['response_metadata']['wire_sha256']==r['response_metadata']['decoded_sha256']
    assert r['fresh_until_epoch']==stamp+20
    monkeypatch.setattr(time,'time',lambda:stamp+19)
    _,warm=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    assert warm['cache_hit'] and warm['fresh_until_epoch']==stamp+20
    monkeypatch.setattr(time,'time',lambda:stamp+20.1)
    with pytest.raises(ValueError):t.original_bytes(warm,JSON_URL,max_age=1800)
    assert t.original_bytes(warm,JSON_URL,max_age=86400)==RAW


@pytest.mark.parametrize('policy',['no-cache','no-store'])
def test_json_response_policy_forbids_reuse(fallback,policy):
    t,calls,c=fallback;c['value']['response_metadata']['cache_control']=policy
    for _ in range(2):
        _,r=t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
        assert r['reusable'] is False and r['cache_hit'] is False
    assert calls==[t.MASTER_URL,JSON_URL,JSON_URL]


def test_wrong_csv_issuer_never_uses_json_to_override_identity(harness):
    from data_fetch.market_sources import gce_conference as source
    from data_fetch.market_sources import gce_conference_transport as t
    raw=harness[0][t.MASTER_URL];assert b'30955404' in raw
    harness[0][t.MASTER_URL]=raw.replace(b'30955404',b'00000000')
    with pytest.raises(SourceResponseError):source.fetch_gce_context('2368.TW')
    assert harness[1]==[t.MASTER_URL]


def test_cached_csv_original_cannot_be_served_from_json_cache_key(harness,monkeypatch):
    import cache_store
    from data_fetch.market_sources import official_issuer_master as m, gce_conference_transport as t
    old=t.ConferenceHttp.download_original
    def private(self,url,diag):
        value=old(self,url,diag);value['response_metadata']['cache_control']='private';return value
    monkeypatch.setattr(t.ConferenceHttp,'download_original',private)
    t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    csvrow=cache_store.get_cache_json(m.CACHE_KEY)
    cache_store.set_cache_json(m._parameters(JSON_URL)[2],csvrow,ttl_seconds=1800)
    http=t.ConferenceHttp(time.monotonic()+25)
    with pytest.raises(SourceResponseError):m.get_receipt(deadline=http.deadline,download=http.download_original,diagnostic={},url=JSON_URL)


from test_allis_conference import harness as allis_harness


def test_allis_public_json_recovery_keeps_all_29_pages_and_issuer_identity(allis_harness,monkeypatch):
    from data_fetch.market_sources import allis_conference as source, allis_conference_transport as t
    old=t.ConferenceHttp.download_original
    def download(self,url,diag):
        if url==t.MASTER_URL:
            self.http_request_count+=1;diag['http_request_sent']=True;raise SourceResponseError('transport_error')
        if url==JSON_URL:
            self.http_request_count+=1;diag.update(http_request_sent=True,http_status=200);return json_value()
        return old(self,url,diag)
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    diag={};value=source.fetch_allis_context('1514.TW',diagnostics=diag)
    assert len(value['documents'][0]['pages'])==29 and diag['http_request_count']==4
    r=value['allis_conference_receipt']['identity']
    assert source.parse_master(RAW,r['retrieved_at'],JSON_URL)['official_ubn']=='03213392'
    assert source.verify_context(value,'1514.TW',max_age=1800)


@pytest.fixture
def native_json(harness,monkeypatch):
    from data_fetch.market_sources import gce_conference_transport as t,official_issuer_master_json as j
    control={};calls=[]
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK',raising=False)
    for k in j.PROXY_ENV:monkeypatch.delenv(k,raising=False)
    monkeypatch.setattr(j,'proxy_url_for_request',lambda *a:None)
    def download(self,url,diag):
        if url==t.MASTER_URL:
            self.http_request_count+=1;diag['http_request_sent']=True;raise SourceResponseError('timeout')
        return _NATIVE_DOWNLOAD(self,url,diag)
    monkeypatch.setattr(t.ConferenceHttp,'download_original',download)
    def process(args,deadline,**options):
        calls.append((args,deadline,options));status=control.get('status',200)
        wire=control.get('wire',WIRE)
        headers=(f'HTTP/2 {status}\r\nContent-Type: application/json\r\nContent-Encoding: gzip\r\n'+control.get('extra','')+'\r\n').encode()
        meta={'http_code':status,'url_effective':JSON_URL,'num_redirects':0,'size_download':len(wire),'content_type':'application/json','method':'GET','proxy_used':0}
        meta.update(control.get('meta',{}))
        return {'process_started':True,'body':wire,'headers':headers,'metadata':json.dumps(meta).encode()},control.get('rc',0),None
    monkeypatch.setattr(j,'collect_capped_process',process)
    return t,j,control,calls


def test_native_gzip_arguments_wire_receipts_and_metadata(native_json):
    t,j,control,calls=native_json;http=t.ConferenceHttp(time.monotonic()+25)
    raw,r=http.get_receipt(t.MASTER_URL)
    assert raw==RAW and r['evidence_kind']=='decoded_http_response_bytes'
    assert r['wire_original']['evidence_kind']=='raw_http_response_bytes'
    args,deadline,options=calls[0]
    assert 'Accept-Encoding: gzip' in args and '--compressed' not in args
    assert all(x not in args for x in ('--location','--insecure','--cookie','--proxy'))
    assert args[args.index('--retry')+1]=='0' and args[args.index('--max-redirs')+1]=='0'
    assert float(args[args.index('--max-time')+1])<=5 and float(args[args.index('--connect-timeout')+1])<=2
    assert deadline<=http.deadline and options['body_limit']==2_500_000
    assert r['response_metadata']['content_length'] is None
    assert r['response_metadata']['wire_bytes']==302549 and r['response_metadata']['decoded_bytes']==1327577
    assert http.http_request_count==2 and len(calls)==1


@pytest.mark.parametrize('change',['duplicate_header','length_is_decoded','redirect','wrong_method','proxy','wrong_url','partial','403','429','crc'])
def test_native_json_rejection_and_error_cooldown_preserve_http_truth(native_json,change):
    t,j,c,calls=native_json
    if change=='duplicate_header':c['extra']='Content-Encoding: gzip\r\n'
    elif change=='length_is_decoded':c['extra']=f'Content-Length: {len(RAW)}\r\n'
    elif change=='partial':c['rc']=28;c['wire']=WIRE[:100]
    elif change in {'403','429'}:c['status']=int(change)
    elif change=='crc':c['wire']=WIRE[:-8]+bytes([WIRE[-8]^1])+WIRE[-7:]
    else:c['meta']={ {'redirect':'num_redirects','wrong_method':'method','proxy':'proxy_used','wrong_url':'url_effective'}[change]:{'redirect':1,'wrong_method':'POST','proxy':1,'wrong_url':'https://example.com/'}[change]}
    for opts in ({},{'force_refresh':True},{'use_cache':False}):
        http=t.ConferenceHttp(time.monotonic()+25,**opts)
        with pytest.raises(SourceResponseError):http.get_receipt(t.MASTER_URL)
        assert sum(v['http_request_sent'] for v in http.components)==http.http_request_count
    assert len(calls)==1


def test_decompression_completion_is_in_original_request_and_total_budget(native_json,monkeypatch):
    from types import SimpleNamespace
    t,j,c,calls=native_json;clock=[100.];old=j.decode_wire
    def slow(wire,encoding):
        value=old(wire,encoding);clock[0]+=6;return value
    monkeypatch.setattr(j,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr(j,'decode_wire',slow)
    with pytest.raises(SourceResponseError) as e:t.ConferenceHttp(time.monotonic()+25).get_receipt(t.MASTER_URL)
    assert e.value.error_kind=='timeout' and len(calls)==1
