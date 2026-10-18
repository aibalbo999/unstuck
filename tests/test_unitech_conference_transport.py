import time
from test_shared_provider_cache import memory_cache
from test_tcfhc_conference_transport import network,response
from data_fetch.market_sources.unitech_conference_transport import ConferenceHttp,PDF_URL


def test_unitech_native_transport_has_published_route_and_warm_original_epoch(network,monkeypatch):
    _,base=network; calls=[]
    def native(argv,*a,**kw):calls.append(argv);return response(argv)
    monkeypatch.setattr(base,'collect_capped_process',native)
    first=ConferenceHttp(time.monotonic()+25);raw,a=first.get_receipt(PDF_URL)
    second=ConferenceHttp(time.monotonic()+25);same,b=second.get_receipt(PDF_URL)
    assert raw==same and not a['cache_hit'] and b['cache_hit']
    assert a['retrieved_at']==b['retrieved_at'] and len(calls)==1
    assert first.http_request_count==1 and second.http_request_count==0

import pytest
from copy import deepcopy
from hashlib import sha256
from data_fetch.market_sources.unitech_conference_transport import MASTER_URL,INDEX_URL,PROVIDER,original_bytes
from search_provider_runtime import SourceResponseError


@pytest.mark.parametrize('url',[PDF_URL+'?x=1',PDF_URL+'#page=2',PDF_URL.replace('https:','http:'),
    PDF_URL.replace('www.pcbut.com.tw','www.pcbut.com.tw.evil.example'),PDF_URL.replace('2026.pdf','2025.pdf'),
    INDEX_URL.replace('IN5_3','M5'),MASTER_URL+'?x=1'])
def test_unpublished_routes_are_rejected_before_process(network,monkeypatch,url):
    _,base=network
    monkeypatch.setattr(base,'collect_capped_process',lambda *a,**kw:pytest.fail('must not start HTTP'))
    with pytest.raises(SourceResponseError):ConferenceHttp(time.monotonic()+25).get_receipt(url)


@pytest.mark.parametrize('status',[403,429,503])
def test_native_failure_cooldown_cannot_be_bypassed_by_force_or_uncached(network,monkeypatch,status):
    _,base=network;calls=[]
    monkeypatch.setattr(base,'remember_failure',lambda *a:{})
    def native(argv,*a,**kw):calls.append(argv);return response(argv,status)
    monkeypatch.setattr(base,'collect_capped_process',native)
    for options in ({},{'force_refresh':True},{'use_cache':False}):
        with pytest.raises(SourceResponseError):ConferenceHttp(time.monotonic()+25,**options).get_receipt(PDF_URL)
    assert len(calls)==1


def test_storage_unavailable_never_starts_download(network,monkeypatch):
    _,base=network
    import cache_store
    def unavailable(*a,**kw):raise OSError('storage unavailable')
    monkeypatch.setattr(cache_store,'get_cache_json',unavailable)
    monkeypatch.setattr(base,'collect_capped_process',lambda *a,**kw:pytest.fail('must not start HTTP'))
    with pytest.raises(SourceResponseError) as exc:ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    assert exc.value.error_kind=='guard_storage_unavailable'


def test_transport_preserves_five_second_single_call_and_credentials_policy(network,monkeypatch):
    _,base=network;calls=[]
    def native(argv,*a,**kw):calls.append(argv);return response(argv)
    monkeypatch.setattr(base,'collect_capped_process',native)
    ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    a=calls[0]
    assert float(a[a.index('--max-time')+1])==5. and a[a.index('--retry')+1]=='0'
    assert a[a.index('--max-redirs')+1]=='0' and float(a[a.index('--connect-timeout')+1])==2
    assert not any('cookie' in s.lower() or 'authorization' in s.lower() for s in a)


def test_original_expiring_during_readback_is_rejected(network,monkeypatch):
    _,base=network
    from data_fetch.market_sources import tcfhc_conference_transport as shared
    monkeypatch.setattr(base,'collect_capped_process',lambda argv,*a,**kw:response(argv))
    raw,receipt=ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    original=shared.read_response;clock=[receipt['retrieved_at']+1799]
    monkeypatch.setattr(time,'time',lambda:clock[0])
    def delayed(value):
        result=original(value);clock[0]+=1;return result
    monkeypatch.setattr(shared,'read_response',delayed)
    with pytest.raises(ValueError):original_bytes(receipt,PDF_URL,max_age=1800)


@pytest.mark.parametrize('field,value',[('http_status_observed',False),('http_status',None),('finality_guaranteed',True),
    ('raw_response_sha256','0'*64),('cache_source','shared-roster'),('response_complete',False)])
def test_mutated_original_receipts_fail_closed(network,monkeypatch,field,value):
    _,base=network
    monkeypatch.setattr(base,'collect_capped_process',lambda argv,*a,**kw:response(argv))
    raw,receipt=ConferenceHttp(time.monotonic()+25).get_receipt(PDF_URL)
    receipt[field]=value
    with pytest.raises((ValueError,SourceResponseError)):original_bytes(receipt,PDF_URL)
