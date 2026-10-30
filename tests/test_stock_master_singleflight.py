"""Normal identity and peer requests reuse valid master data without clearing it."""
from pathlib import Path
from copy import deepcopy
from datetime import date,datetime,timezone
import sys,json,time
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from data_fetch.market_sources import identity,peer_recovery
from data_fetch.market_sources import stock_identity_master as master


def reset_old_peer_cache():
    clear=getattr(peer_recovery._master_for_day,'cache_clear',None)
    if clear:clear()


def test_peer_lookup_does_not_erase_the_good_master_loaded_by_core(monkeypatch):
    reset_old_peer_cache();rows=[{'stock_id':'8926','stock_name':'台汽電','industry_category':'油電燃氣業','type':'twse','date':'2026-10-30'}]
    class Existing:
        def __init__(self):self.good=None;self.downloads=0;self.clears=0
        def __call__(self):
            if self.good is not None:return self.good
            self.downloads+=1
            if self.downloads>1:return []
            self.good=deepcopy(rows);return self.good
        def cache_clear(self):self.good=None;self.clears+=1
    source=Existing();monkeypatch.setattr(identity,'load_taiwan_stock_info_records',source)
    assert source()==rows
    assert peer_recovery._master_for_day(date(2026,10,30))==rows
    assert source.downloads==1 and source.clears==0


def test_peer_layer_cannot_pin_an_empty_provider_result_for_the_entire_day(monkeypatch):
    reset_old_peer_cache()
    class Source:
        def __init__(self):self.calls=0
        def __call__(self):
            self.calls+=1;return [] if self.calls==1 else [{'stock_id':'8926','date':'2026-10-30'}]
        def cache_clear(self):pass
    source=Source();monkeypatch.setattr(identity,'load_taiwan_stock_info_records',source)
    assert peer_recovery._master_for_day(date(2026,10,30))==[]
    assert peer_recovery._master_for_day(date(2026,10,30))==[{'stock_id':'8926','date':'2026-10-30'}]
    assert source.calls==2  # The provider, not a second cache, owns retry eligibility.


@pytest.fixture
def isolated_master(monkeypatch):
    import cache_store,shared_provider_cache
    from contextlib import contextmanager
    from official_response_evidence import archive_response
    clock=[datetime(2026,10,30,3,tzinfo=timezone.utc).timestamp()];saved={};downloads=[]
    monkeypatch.setattr(shared_provider_cache.time,'time',lambda:clock[0])
    monkeypatch.setattr(cache_store,'get_cache_json',lambda key:deepcopy(saved.get(key)))
    def store(key,value,**kwargs):saved[key]=deepcopy(value)
    monkeypatch.setattr(cache_store,'set_cache_json',store)
    @contextmanager
    def process_lock(*args,**kwargs):yield True
    monkeypatch.setattr(shared_provider_cache,'_process_lock',process_lock)
    def payload(day='2026-10-30'):
        raw=json.dumps({'status':200,'msg':'success','data':[{'stock_id':str(n),'stock_name':'測試公司'+str(n),
          'industry_category':'油電燃氣業','type':'twse','date':day}for n in range(1000,1800)]},ensure_ascii=False).encode()
        return {'schema':'finmind-stock-identity-master.v1','raw_receipt':archive_response(raw,source_url=master.URL,retrieved_at=clock[0],http_status=200)}
    def acquire():downloads.append(clock[0]);return payload()
    monkeypatch.setattr(master,'_download',acquire,raising=False)
    return clock,saved,downloads,payload


def test_two_identity_reads_share_one_fetch_and_preserve_source_time(isolated_master):
    clock,saved,downloads,payload=isolated_master
    first,meta1=master.read_master();clock[0]+=10;second,meta2=master.read_master()
    assert len(first)==len(second)==800 and first==second
    assert len(downloads)==1 and meta1['cache_hit']is False and meta2['cache_hit']is True
    assert meta2['fetched_at_epoch']==meta1['fetched_at_epoch']
    assert second[0]['date']=='2026-10-30'
    assert meta2['http_request_count']==0 and meta2['http_request_sent']is False
    assert list(saved.values())[0]['fresh_until_epoch']-meta1['fetched_at_epoch']==86400
    first[0]['stock_name']='changed locally'
    assert master.read_master()[0][0]['stock_name']!='changed locally'


def test_errors_get_a_bounded_cooldown_and_can_recover_after_eligibility(isolated_master,monkeypatch):
    clock,saved,downloads,payload=isolated_master
    def fail():downloads.append(clock[0]);raise RuntimeError('provider unavailable')
    monkeypatch.setattr(master,'_download',fail,raising=False)
    assert master.read_master()[0]==[]
    clock[0]+=599;assert master.read_master()[0]==[];assert len(downloads)==1
    monkeypatch.setattr(master,'_download',lambda:(downloads.append(clock[0]),payload())[1],raising=False)
    clock[0]+=2;rows,meta=master.read_master();assert len(rows)==800 and len(downloads)==2
    assert meta['cache_hit']is False


def test_old_document_dates_are_not_relabelled_as_current(isolated_master,monkeypatch):
    clock,saved,downloads,payload=isolated_master
    monkeypatch.setattr(master,'_download',lambda:payload('2020-01-01'),raising=False)
    rows,meta=master.read_master();assert len(rows)==800 and rows[0]['date']=='2020-01-01'
    candidates,audit=peer_recovery.resolve_legacy_peer_candidates('1000.TW',{},rows,today=date(2026,10,30))
    assert candidates==[] and audit['selection_status']=='target_stale_master_row'


def test_invalid_cached_receipt_does_not_trigger_force_refresh_or_fake_success(isolated_master):
    clock,saved,downloads,payload=isolated_master
    assert len(master.read_master()[0])==800
    entry=next(iter(saved.values()));entry['value']['raw_receipt']['raw_response_sha256']='0'*64
    rows,meta=master.read_master();assert rows==[] and meta['error_kind']=='cached_master_integrity_invalid'
    assert len(downloads)==1


def wire(raw,status=200,**changes):
    meta={'http_code':status,'url_effective':master.URL,'num_redirects':0,
          'ssl_verify_result':0,'proxy_used':0,'size_download':len(raw),**changes}
    return {'body':raw,'headers':f'HTTP/2 {status}\r\nContent-Type: application/json\r\n\r\n'.encode(),
            'metadata':json.dumps(meta).encode(),'process_started':True}


def test_verified_native_body_can_be_reparsed_and_does_not_claim_peer_metrics(isolated_master):
    clock,saved,downloads,payload=isolated_master
    from official_response_evidence import read_response
    p=payload();raw=read_response(p['raw_receipt'])
    received=master._consume_download(wire(raw),0,None)
    assert received['transport_summary']['http_request_count']==1
    assert received['transport_summary']['http_request_sent']is True
    assert master.parse_master(read_response(received['raw_receipt']))[0]['date']=='2026-10-30'


@pytest.mark.parametrize('status',[401,402,403,429,503,504])
def test_refusal_is_one_response_not_parsed_identity_or_sdk_retry(status,isolated_master):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError)as e:master._consume_download(wire(b'{}',status),0,None)
    assert e.value.status_code==status
    assert e.value.master_diagnostic['http_request_count']==1


@pytest.mark.parametrize('change',[{'url_effective':'https://evil.example/'},{'num_redirects':1},
    {'ssl_verify_result':1},{'proxy_used':1},{'size_download':-1}])
def test_wire_identity_tls_proxy_and_length_cannot_be_forged(change,isolated_master):
    from official_response_evidence import read_response
    raw=read_response(isolated_master[3]()['raw_receipt'])
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):master._consume_download(wire(raw,**change),0,None)


@pytest.mark.parametrize('payload',[{'status':200,'data':[]},{'status':True,'data':[]},
    {'status':403,'data':[]},{'status':429,'data':[]}])
def test_empty_or_refused_master_is_not_a_successful_cache_value(payload,isolated_master):
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):master._consume_download(wire(json.dumps(payload).encode()),0,None)


def test_source_identity_and_peer_paths_share_the_same_positive_cache(isolated_master):
    reset_old_peer_cache()
    first=identity.load_taiwan_stock_info_records()
    second=peer_recovery.load_peer_stock_master()
    assert len(first)==len(second)==800
    assert len(isolated_master[2])==1
    assert first.identity_master_metadata['cache_hit']is False
    assert second.identity_master_metadata['cache_hit']is True
