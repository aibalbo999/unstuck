"""Whole-master sharing through public GCE and Allis transports; no HTTP."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import time
import pytest
from search_provider_runtime import SourceResponseError

from data_fetch.market_sources import gce_conference_transport as gce
from data_fetch.market_sources import allis_conference_transport as allis

ROOT = Path(__file__).parents[1]
MASTER = ROOT/'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791955321.0


@pytest.fixture
def native_master(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    cache_store.set_cache_backend(InMemoryCache())
    clock = [NOW]
    monkeypatch.setattr(time, 'time', lambda: clock[0])
    calls = []; controls = {'cache_control': 'private'}
    raw = MASTER.read_bytes()
    def download(self, url, diagnostic):
        assert url == gce.MASTER_URL
        calls.append(url); self.http_request_count += 1
        diagnostic.update(http_request_sent=True, http_status=200)
        value = controls.get('body', raw)
        meta = {'http_status':200, 'effective_url':url, 'num_redirects':0,
                'size_download':len(value), 'content_length':len(value),
                'content_type':'text/csv', 'method':'GET', 'proxy_used':0,
                'cache_control':controls['cache_control']}
        # The new adapter keeps these native-only facts for masters. The old
        # transport sees the old valid metadata, so the RED is duplicated HTTP.
        if hasattr(gce, 'official_issuer_master'):
            meta = gce.official_issuer_master.master_metadata(meta, value, {'age':controls.get('age')})
        meta.update(controls.get('metadata', {}))
        return {'url':url,'body_b64':base64.b64encode(value).decode(),
                'sha256':sha256(value).hexdigest(),'request_method':'GET',
                'request_body':None,'response_metadata':meta}
    monkeypatch.setattr(gce.ConferenceHttp, 'download_original', download)
    monkeypatch.setattr(allis.ConferenceHttp, 'download_original', download)
    yield raw, calls, clock, controls
    cache_store.reset_cache_store_for_tests()


def test_two_publishers_share_one_original_master_without_retiming(native_master):
    raw, calls, clock, _ = native_master
    a = gce.ConferenceHttp(time.monotonic()+25)
    first, receipt = a.get_receipt(gce.MASTER_URL)
    clock[0] += 10
    b = allis.ConferenceHttp(time.monotonic()+25, force_refresh=True)
    second, warm = b.get_receipt(allis.MASTER_URL)
    assert first == second == raw
    assert len(calls) == 1
    assert a.http_request_count == 1 and b.http_request_count == 0
    assert receipt['cache_hit'] is False and warm['cache_hit'] is True
    assert warm['retrieved_at'] == receipt['retrieved_at'] == NOW
    assert warm['fresh_until_epoch'] == receipt['fresh_until_epoch']
    assert b.components[0]['http_request_sent'] is False
    assert allis.original_bytes(warm, allis.MASTER_URL, max_age=1800) == raw


@pytest.mark.parametrize('policy',['no-cache','no-store','private, no-cache','private, max-age=0'])
def test_nonreusable_master_is_new_http_but_current_original_is_usable(native_master,policy):
    from data_fetch.market_sources import official_issuer_master as master
    import cache_store
    raw,calls,clock,controls=native_master;controls['cache_control']=policy
    for cls in (gce.ConferenceHttp,allis.ConferenceHttp):
        clock[0]+=1
        got,r=cls(time.monotonic()+25).get_receipt(gce.MASTER_URL)
        assert got==raw and r['cache_hit'] is False and r['reusable'] is False
        assert master.original_bytes(r,max_age=1800)==raw
    assert len(calls)==2 and cache_store.get_cache_json(master.CACHE_KEY) is None


def test_short_cache_control_deadline_and_age_do_not_renew(native_master):
    raw,calls,clock,controls=native_master
    controls.update(cache_control='private, max-age=30',age='10')
    _,first=gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert first['fresh_until_epoch']==NOW+20
    clock[0]=NOW+19.5
    _,warm=allis.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert warm['retrieved_at']==NOW and warm['fresh_until_epoch']==NOW+20 and len(calls)==1
    clock[0]=NOW+20.1
    with pytest.raises(ValueError):allis.original_bytes(warm,gce.MASTER_URL,max_age=1800)
    _,new=gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert len(calls)==2 and new['retrieved_at']==NOW+20.1


@pytest.mark.parametrize('change',['epoch','expiry','cache_hit','sha','metadata','extra','manifest'])
def test_master_receipt_cannot_self_retime_or_mutate(native_master,change):
    from data_fetch.market_sources import official_issuer_master as master
    _,r=gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    if change=='epoch':r['retrieved_at']+=1;r['fresh_until_epoch']+=1
    elif change=='expiry':r['fresh_until_epoch']-=1
    elif change=='cache_hit':r['cache_hit']=True
    elif change=='sha':r['raw_response_sha256']='0'*64
    elif change=='metadata':r['response_metadata']['wire_bytes']-=1
    elif change=='extra':r['unexpected']=True
    else:r['acquisition_manifest']['retrieved_at']+=1
    with pytest.raises(ValueError):master.original_bytes(r,max_age=1800)


@pytest.mark.parametrize('change',['remove','new_epoch','new_body','shorten'])
def test_warm_original_rechecks_independent_row_but_historical_replay_does_not(native_master,change):
    import cache_store
    from data_fetch.market_sources import official_issuer_master as master
    raw,calls,clock,_=native_master
    gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    _,warm=allis.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    backend=cache_store.get_cache_backend();row=cache_store.get_cache_json(master.CACHE_KEY)
    if change=='remove':backend.delete(master.CACHE_KEY)
    elif change=='new_epoch':row['fetched_at_epoch']+=1;backend.set_json(master.CACHE_KEY,row,ttl_seconds=1800)
    elif change=='new_body':row['receipt']['raw_response_sha256']='0'*64;backend.set_json(master.CACHE_KEY,row,ttl_seconds=1800)
    else:
        value,_=backend._entries[master.CACHE_KEY];backend._entries[master.CACHE_KEY]=(value,NOW+1);clock[0]+=2
    with pytest.raises(ValueError):master.original_bytes(warm,max_age=1800)
    assert master.original_bytes(warm,max_age=86400)==raw and len(calls)==1


@pytest.mark.parametrize('change',['bad_shape','duplicate_code','truncated_row','future_date','bad_bytes','bad_metadata'])
def test_incomplete_or_malformed_master_never_enters_success_cache(native_master,change):
    import cache_store
    from data_fetch.market_sources import official_issuer_master as master
    raw,calls,_,c=native_master
    if change=='bad_shape':c['body']=b'code,name\n2368,GCE\n'
    elif change=='duplicate_code':c['body']=raw.replace(b'\n1102,',b'\n1101,') if b'\n1102,' in raw else raw+raw.splitlines(keepends=True)[1]
    elif change=='truncated_row':c['body']=raw+b'1151013,2368\n'
    elif change=='future_date':c['body']=raw.replace(b'1151013',b'1151015')
    elif change=='bad_bytes':c['body']=b'captcha'
    else:c['metadata']={'size_download':1}
    with pytest.raises(SourceResponseError):gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert cache_store.get_cache_json(master.CACHE_KEY) is None
    with pytest.raises(SourceResponseError):allis.ConferenceHttp(time.monotonic()+25,force_refresh=True).get_receipt(gce.MASTER_URL)
    assert len(calls)==1


def test_legacy_publisher_error_guard_cannot_be_bypassed_by_other_publisher(native_master):
    import cache_store
    _,calls,_,_=native_master
    key=gce.ConferenceHttp._admission_key(gce.MASTER_URL)
    marker={'retry_at':NOW+120,'token':'before-deploy-failed-request'}
    cache_store.set_cache_json(key,marker,ttl_seconds=120)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        from data_fetch.market_sources import official_issuer_master as master
        http=allis.ConferenceHttp(time.monotonic()+25,**options)
        # This guard protects CSV; the public transport may now separately use
        # the authorized exact JSON host after a CSV cooldown.
        with pytest.raises(SourceResponseError) as e:
            master.get_receipt(deadline=http.deadline,download=http.download_original,diagnostic={})
        assert e.value.error_kind=='cooldown'
    assert calls==[] and cache_store.get_cache_json(key)==marker


@pytest.mark.parametrize('which',['admission','success'])
def test_guard_write_failure_blocks_but_optional_success_write_failure_keeps_cold(native_master,monkeypatch,which):
    import cache_store
    from data_fetch.market_sources import official_issuer_master as master
    raw,calls,_,_=native_master;real=master.set_cache_json
    def fail(key,value,**kw):
        if key==(master.ADMISSION_KEY if which=='admission' else master.CACHE_KEY):raise OSError('isolated write unavailable')
        return real(key,value,**kw)
    monkeypatch.setattr(master,'set_cache_json',fail)
    if which=='admission':
        with pytest.raises(SourceResponseError):gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
        assert not calls
    else:
        value,r=gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
        assert value==raw and r['reusable'] is False and r['cache_hit'] is False
        assert cache_store.get_cache_json(master.CACHE_KEY) is None
        assert master.original_bytes(r,max_age=1800)==raw


def test_success_readback_mismatch_does_not_become_optional_cache_outage(native_master,monkeypatch):
    from data_fetch.market_sources import official_issuer_master as master
    real=master._stored;n=[0]
    def changed():
        row,expiry=real();n[0]+=1
        if row:row['fetched_at_epoch']+=20
        return row,expiry
    monkeypatch.setattr(master,'_stored',changed)
    with pytest.raises(SourceResponseError):gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)


def test_completed_cold_original_survives_success_readback_storage_outage(native_master,monkeypatch):
    from data_fetch.market_sources import official_issuer_master as master
    raw,calls,_,_=native_master;real=master._stored
    def outage(*args):
        if calls:raise OSError('optional success readback outage')
        return real(*args)
    monkeypatch.setattr(master,'_stored',outage)
    got,r=gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert got==raw and r['reusable'] is False and r['cache_hit'] is False
    assert master.original_bytes(r,max_age=1800)==raw


def test_corrupt_stored_row_is_not_mistaken_for_storage_outage(native_master,monkeypatch):
    from data_fetch.market_sources import official_issuer_master as master
    _,calls,_,_=native_master
    def corrupt():raise ValueError('stored row cannot be decoded or has invalid physical TTL')
    monkeypatch.setattr(master,'_stored',corrupt)
    with pytest.raises(SourceResponseError):gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert not calls


def test_warm_short_physical_expiry_crossed_during_archive_is_rejected(native_master,monkeypatch):
    import cache_store
    from data_fetch.market_sources import official_issuer_master as master
    _,calls,clock,_=native_master
    gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    backend=cache_store.get_cache_backend();row,_=backend._entries[master.CACHE_KEY]
    backend._entries[master.CACHE_KEY]=(row,NOW+0.5)
    real=master._seal
    def late(receipt):
        result=real(receipt);clock[0]+=1;return result
    monkeypatch.setattr(master,'_seal',late)
    with pytest.raises(SourceResponseError):allis.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL)
    assert len(calls)==1


def test_cleanup_and_late_storage_error_use_total_timeout(native_master,monkeypatch):
    from data_fetch.market_sources import official_issuer_master as master
    from types import SimpleNamespace
    _,calls,_,_=native_master;mono=[100.]
    monkeypatch.setattr(master,'time',SimpleNamespace(monotonic=lambda:mono[0],time=lambda:NOW))
    def late():mono[0]=126.;raise OSError('late cache read')
    monkeypatch.setattr(master,'_stored',late)
    with pytest.raises(SourceResponseError) as e:gce.ConferenceHttp(125.).get_receipt(gce.MASTER_URL)
    assert e.value.error_kind=='timeout' and not calls


def test_concurrent_publishers_share_single_flight(native_master,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    raw,calls,_,_=native_master
    original=gce.ConferenceHttp.download_original;entered=Event();release=Event()
    def held(self,url,d):
        entered.set();assert release.wait(2);return original(self,url,d)
    monkeypatch.setattr(gce.ConferenceHttp,'download_original',held)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(lambda:gce.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL))
        assert entered.wait(2)
        b=pool.submit(lambda:allis.ConferenceHttp(time.monotonic()+25).get_receipt(gce.MASTER_URL))
        release.set();aa=a.result();bb=b.result()
    assert aa[0]==bb[0]==raw and len(calls)==1
    assert aa[1]['cache_hit'] is False and bb[1]['cache_hit'] is True
