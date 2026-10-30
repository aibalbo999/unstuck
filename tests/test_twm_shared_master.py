"""Strict shared issuer master recovery through TWM's public transport, offline."""
from copy import deepcopy
from hashlib import sha256
import base64,gzip,json,time
import pytest
from search_provider_runtime import SourceResponseError
from data_fetch.market_sources import taiwanmobile_conference as source
from data_fetch.market_sources import taiwanmobile_conference_transport as transport
from data_fetch.market_sources import conference_issuer_master as identity
from data_fetch.market_sources.official_issuer_master_json import FIELDS

_REAL_REQUEST_MASTER=identity.request_master
NOW=1793275200.0

def raw_master():
    rows=[]
    for n in range(500):
        row=dict.fromkeys(FIELDS,'');row.update({'公司代號':str(1000+n),'出表日期':'1151029'})
        rows.append(row)
    rows[-1].update({'公司代號':'3045','公司名稱':source.LEGAL,'公司簡稱':'台灣大',
        '營利事業統一編號':source.UBN,'網址':'www.taiwanmobile.com','英文簡稱':'TWM'})
    return json.dumps(rows,ensure_ascii=False,separators=(',',':')).encode()

@pytest.fixture
def native(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import gce_conference_transport as downloader
    cache_store.set_cache_backend(InMemoryCache());clock=[NOW];calls=[];control={'failure':'timeout'}
    monkeypatch.setattr(time,'time',lambda:clock[0])
    raw=raw_master();wire=gzip.compress(raw)
    def download(self,url,diagnostic):
        calls.append(url);self.http_request_count+=1;diagnostic.update(http_request_sent=True)
        if url==source.MASTER_URL:raise SourceResponseError(control['failure'])
        assert url==identity.JSON_URL
        diagnostic['http_status']=200
        meta={'http_status':200,'effective_url':url,'num_redirects':0,'size_download':len(wire),
            'content_type':'application/json','content_length':None,'method':'GET','proxy_used':0,
            'cache_control':'','content_encoding':'gzip','age':None,'wire_bytes':len(wire),
            'wire_sha256':sha256(wire).hexdigest(),'decoded_bytes':len(raw),'decoded_sha256':sha256(raw).hexdigest()}
        return {'url':url,'body_b64':base64.b64encode(raw).decode(),'wire_b64':base64.b64encode(wire).decode(),
            'sha256':sha256(raw).hexdigest(),'request_method':'GET','request_body':None,'response_metadata':meta}
    monkeypatch.setattr(downloader.ConferenceHttp,'download_original',download)
    yield raw,calls,clock,control
    cache_store.reset_cache_store_for_tests()

def test_csv_timeout_recovers_native_json_without_changing_identity_or_expiry(native):
    raw,calls,clock,control=native;http=transport.ConferenceHttp(time.monotonic()+25)
    body,r=http.get_receipt(source.MASTER_URL)
    assert body==raw and r['source_url']==identity.JSON_URL
    assert calls==[source.MASTER_URL,identity.JSON_URL] and http.http_request_count==2
    assert http.components[0]['error_kind']=='timeout'
    assert source.parse_master(body,r['retrieved_at'],r['source_url']) is True
    assert transport.original_bytes(r,identity.JSON_URL,max_age=1800)==raw
    clock[0]+=10;warm=transport.ConferenceHttp(time.monotonic()+25)
    body,cached=warm.get_receipt(source.MASTER_URL)
    assert warm.http_request_count==0 and cached['retrieved_at']==r['retrieved_at']
    assert cached['fresh_until_epoch']==r['fresh_until_epoch'] and len(calls)==2
    clock[0]=r['fresh_until_epoch']+.01
    with pytest.raises(ValueError):transport.original_bytes(cached,identity.JSON_URL,max_age=86400)

@pytest.mark.parametrize('failure',['authentication','access_denied','rate_limited','parse_error','guard_storage_unavailable'])
def test_terminal_primary_errors_never_move_to_another_endpoint(native,failure):
    raw,calls,clock,control=native;control['failure']=failure
    with pytest.raises(SourceResponseError):transport.ConferenceHttp(time.monotonic()+25).get_receipt(source.MASTER_URL)
    assert calls==[source.MASTER_URL]

@pytest.mark.parametrize('field,value',[('公司名稱','中華電信股份有限公司'),('營利事業統一編號','00000000'),('網址','other.example'),('英文簡稱','CHT')])
def test_json_never_relaxes_exact_issuer_identity(field,value):
    rows=json.loads(raw_master());rows[-1][field]=value
    with pytest.raises(ValueError):source.parse_master(json.dumps(rows).encode(),NOW,identity.JSON_URL)

def test_legacy_cold_guard_blocks_both_endpoints(native):
    import cache_store
    raw,calls,clock,control=native
    cache_store.set_cache_json(transport.ConferenceHttp._admission_key(source.MASTER_URL),{'retry_at':NOW+120},ttl_seconds=120)
    with pytest.raises(SourceResponseError):transport.ConferenceHttp(time.monotonic()+25).get_receipt(source.MASTER_URL)
    assert calls==[]


from test_taiwanmobile_conference import acquisition as legacy_acquisition

def test_complete_transcript_retains_native_content_and_flags_with_shared_json(native,legacy_acquisition,monkeypatch):
    monkeypatch.setattr(identity,'request_master',_REAL_REQUEST_MASTER)
    diagnostic={};value=source.fetch_context('3045.TW',diagnostics=diagnostic)
    proof=value['taiwanmobile_conference_receipt']
    assert proof['policy']==source.POLICY and proof['identity']['source_url']==identity.JSON_URL
    assert diagnostic['http_request_count']==4
    assert len(value['documents'][0]['pages'])==12 and value['period']=='2026Q2'
    assert value['transcript_available'] is True and value['coverage_status']=='partial'
    assert value['documents'][0]['full_content_coverage_verified'] is False
    assert source.verify_context(value,'3045.TW')
    changed=deepcopy(value);changed['taiwanmobile_conference_receipt']['policy']=source.LEGACY_POLICY
    assert not source.verify_context(changed,'3045.TW')
    original_epoch=value['fetched_at_epoch'];warm={};again=source.fetch_context('3045.TW',diagnostics=warm)
    assert warm['http_request_count']==0 and again['fetched_at_epoch']==original_epoch
    assert len(native[1])==2 and len(legacy_acquisition[1])==2
