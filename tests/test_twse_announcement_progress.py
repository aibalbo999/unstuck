"""Native-process boundary replay only; generated 37-row HTML is synthetic, not evidence to adopt."""
from datetime import datetime
from html import escape
import hashlib
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import pytest

from data_fetch.market_sources import twse_company_history as source
from data_fetch.market_sources import twse_history_transport as transport

NOW = datetime(2026, 10, 13, 12, tzinfo=ZoneInfo('Asia/Taipei'))


class Replay:
    def __init__(self, monkeypatch, count=37, detail_cost=.7):
        import cache_store, cache_backends
        self.mono = 100.; self.epoch = NOW.timestamp(); self.calls = []
        self.detail_cost = detail_cost; self.failures = {}; self.after_transfer = None
        self.clock = SimpleNamespace(monotonic=lambda: self.mono, time=lambda: self.epoch)
        monkeypatch.setattr(source, 'time', self.clock)
        monkeypatch.setattr(transport, 'time', self.clock)
        from data_fetch.market_sources import twse_json_history
        monkeypatch.setattr(twse_json_history, 'time', self.clock)
        monkeypatch.setattr(cache_backends, 'time', self.clock)
        try:
            from data_fetch.market_sources import twse_announcement_progress as progress
            monkeypatch.setattr(progress, 'time', self.clock)
            import official_announcement_source_refresh as originals
            monkeypatch.setattr(originals, 'time', self.clock)
        except ImportError:
            pass
        self.cache = cache_backends.InMemoryCache()
        monkeypatch.setattr(cache_store, '_backend', self.cache)
        monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
        for key in transport.PROXY_ENV:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setattr(transport, 'proxy_url_for_request', lambda *a: None)
        monkeypatch.setattr(transport, 'cooldown_state', lambda *a: {})
        self.remembered = []
        monkeypatch.setattr(transport, 'remember_failure', lambda key, exc: self.remembered.append(exc.error_kind))
        monkeypatch.setattr(transport, 'observe_http_response', lambda response: None)
        monkeypatch.setattr(transport, 'collect_capped_process', self.collect)
        self.items = []
        for n in range(1, count + 1):
            link = ('https://mopsov.twse.com.tw/mops/web/ajax_t05sr01_1?firstin=true&stp=1&step=1'
                    f'&SEQ_NO={n}&SPOKE_TIME=141538&SPOKE_DATE=20261006&COMPANY_ID=2891')
            self.items.append({'link':link, 'title':f'公告本公司第{n}項董事會決議', 'company':'中信金'})
        self.by_url = {i['link']: i for i in self.items}

    def advance(self, seconds):
        self.mono += seconds; self.epoch += seconds

    def detail(self, item):
        return (f"<table class='noBorder'><tr class='compName'><td>本資料由 (上市公司) 2891 {item['company']} 公司提供</td></tr></table>"
                "<table class='hasBorder'><tr><th>發言日期</th><td>115/10/06</td><th>發言時間</th><td>14:15:38</td></tr>"
                f"<tr><th>主旨</th><td>{escape(item['title'])}</td></tr><tr><th>說明</th><td>本公司董事會決議辦理公開公告事項，此原文內容僅供隔離測試核對，不是正式來源資料。</td></tr></table>").encode()

    def collect(self, argv, end, **kwargs):
        url = argv[2] if argv[1].endswith('mops_monthly_http_child.py') else argv[-1]
        self.calls.append(url)
        if url.startswith(transport.IIH_URL):
            payload = {'info':{'status':'success','data':{'code':'2891'}},'news':[
                {'companyId':'2891','companyName':i['company'],'subject':i['title'],'date':'115/10/06','time':'14:15','link':i['link']}
                for i in self.items[:10]]}
            body = json.dumps(payload).encode(); mime = 'application/json'; cost = .1
        elif url == transport.EZ_URL:
            payload = {'status':'success','data':[
                {'COMPANY_ID':'2891','COMPANY_NAME':i['company'],'TYPEK':'上市','CDATE':'115/10/06','CTIME':'14:15:38',
                 'AN_CODE':'M99','SUBJECT':i['title'],'HYPERLINK':i['link']} for i in self.items]}
            body = json.dumps(payload).encode(); mime = 'application/json'; cost = .1
        elif url == transport.JSON_URL:
            from data_fetch.market_sources.twse_json_history import TITLES
            form = json.loads(argv[3]); selected = self.items if form['month'] == '10' else []
            payload = {'code':200,'message':'查詢成功','result':{'marketName':'上市公司','companyId':'2891',
                'companyAbbreviation':'中信金','titles':[{'main':s} for s in TITLES], 'data':[
                  ['2891',i['company'],'115/10/06','14:15:38',i['title'],{'apiName':'t05st01_detail','parameters':
                   {'companyId':'2891','marketKind':'sii','enterDate':'1151006','serialNumber':parse_qs(urlsplit(i['link']).query)['SEQ_NO'][0]}}] for i in selected]}}
            body = json.dumps(payload).encode(); mime = 'application/json'; cost = .1
        else:
            body = self.detail(self.by_url[url]); mime = 'text/html; charset=utf-8'; cost = self.detail_cost
        kind, status = self.failures.get(url, (None, 200))
        if cost > end - self.mono:
            cost = max(0., end-self.mono); kind = 'timeout'; body = body[:25]
        self.advance(cost)
        if kind == 'unexpected_content_type': mime = 'image/png'; kind = None
        p = {'body':body, 'headers':f'HTTP/2 {status}\r\nContent-Type: {mime}\r\n\r\n'.encode(),
             'metadata':json.dumps({'http_code':status,'url_effective':url,'num_redirects':0}).encode(), 'process_started':True}
        if self.after_transfer: self.after_transfer(url, p)
        return p, 28 if kind == 'timeout' else 1 if kind else 0, kind

    def fetch(self):
        return source.fetch_recent_company_announcements('2891.TW', now=NOW)


def test_second_gap_request_revalidates_indexes_and_fetches_only_missing_bodies(monkeypatch):
    r = Replay(monkeypatch)
    first, audit = r.fetch()
    assert 0 < len(first) < 37 and audit['coverage_status'] == 'partial'
    assert audit['monthly_index']['candidate_count'] == 37 and audit['detail_limit'] == 64
    assert r.mono == pytest.approx(120.)
    assert audit['progress_missing_count'] == 37-len(first)
    first_urls = {x['link'] for x in first}; first_count = len(r.calls)
    r.advance(60)
    second, again = r.fetch()
    new_details = [url for url in r.calls[first_count:] if url in r.by_url]
    assert not first_urls.intersection(new_details), 'already qualified bodies were re-downloaded'
    assert len(second) == 37 and again['coverage_status'] == 'window_complete'
    assert any(url.startswith(transport.IIH_URL) for url in r.calls[first_count:])
    assert r.calls[first_count:].count(transport.JSON_URL) == 2
    assert audit['progress_resume_possible'] is True
    assert again['detail_new_body_count'] == 37-len(first)
    assert again['detail_cache_hit_count'] == len(first)


def test_distinct_native_failure_kinds_and_request_identity_are_retained(monkeypatch):
    r = Replay(monkeypatch, count=3, detail_cost=.1)
    urls = [i['link'] for i in r.items]
    r.failures[urls[0]] = ('timeout',200)
    r.failures[urls[1]] = ('unexpected_content_type',200)
    rows,audit = r.fetch()
    assert len(rows) == 1
    errors = {o['url']:o for o in audit.get('request_observations',[]) if o.get('error_kind')}
    assert errors[urls[0]]['error_kind'] == 'timeout'
    assert errors[urls[1]]['error_kind'] == 'unexpected_content_type'
    assert all(o['http_request_count'] == 1 and o['http_status'] == 200 for o in errors.values())
    assert all(o['elapsed_seconds'] >= 0 and o['remaining_seconds'] >= 0 for o in errors.values())


def test_warm_bodies_preserve_original_bytes_epochs_and_shorter_physical_expiry(monkeypatch):
    r = Replay(monkeypatch, count=2, detail_cost=.1)
    first, a = r.fetch(); assert len(first) == 2
    for key, (value, _) in list(r.cache._entries.items()):
        r.cache._entries[key] = (value, r.epoch+80)
    first_count = len(r.calls); r.advance(60)
    second,b = r.fetch()
    assert second == first and r.calls[first_count:] == [transport.IIH_URL+'?code=2891']
    assert b['body_cache_hit'] is True and b['detail_new_body_count'] == 0
    assert b['http_request_count'] == 1
    assert b['progress_fresh_until_epoch'] == pytest.approx(r.epoch-.1+20)
    assert [o['receipt'] for o in b['source_record_archive'] if 'receipt' in o] == [
        o['receipt'] for o in a['source_record_archive'] if 'receipt' in o]
    assert b['body_fetched_at_epoch'] == a['body_fetched_at_epoch']
    r.advance(21); count = len(r.calls)
    third,c = r.fetch()
    assert third == first and len(r.calls[count:]) == 3 and c['detail_new_body_count'] == 2


def test_original_1800_second_expiry_requires_new_bodies(monkeypatch):
    r = Replay(monkeypatch, count=1, detail_cost=.1)
    _,a = r.fetch(); r.advance(1801); count=len(r.calls)
    _,b = r.fetch()
    assert len(r.calls[count:]) == 2 and b['detail_cache_hit_count'] == 0
    assert b['body_fetched_at_epoch'] > a['body_fetched_at_epoch']


@pytest.mark.parametrize('tamper', ['method','url','digest','bytes','http_status','cache_only','expiry','future_stamp'])
def test_invalid_saved_original_is_not_used_as_successful_progress(monkeypatch, tamper):
    r=Replay(monkeypatch,count=1,detail_cost=.1);r.fetch()
    key,(row,until)=next(iter(r.cache._entries.items()))
    if tamper=='method': row['method']='POST'
    elif tamper=='url': row['url']=row['url'].replace('2891','2881')
    elif tamper=='digest': row['receipt']['raw_response_sha256']='0'*64
    elif tamper=='bytes': row['receipt']['raw_response_bytes']+=1
    elif tamper=='http_status': row['receipt']['http_status']=None
    elif tamper=='cache_only': row['receipt']['http_status_observed']=False
    elif tamper=='expiry': row['fresh_until_epoch']=row['receipt']['retrieved_at']+1801
    elif tamper=='future_stamp': row['receipt']['retrieved_at']=r.epoch+100
    r.cache._entries[key]=(row,until); count=len(r.calls)
    rows,a=r.fetch()
    assert len(rows)==1 and len(r.calls[count:])==2
    assert a['detail_cache_hit_count']==0 and a['detail_new_body_count']==1


def test_changed_fresh_index_title_revalidates_cached_body_and_does_not_relabel_it(monkeypatch):
    r=Replay(monkeypatch,count=2,detail_cost=.1); r.fetch()
    r.items[0]['title']='完全不同的新主旨'; count=len(r.calls)
    rows,a=r.fetch()
    assert len(rows)==1 and a['coverage_status']=='partial'
    assert a['rejected_reason_counts']=={'detail_mismatch':1}
    assert a['progress_resume_possible'] is False
    assert len(r.calls[count:])==1  # no automatic replacement/refusal bypass


def test_semantically_invalid_200_never_becomes_resumable_raw(monkeypatch):
    r=Replay(monkeypatch,count=2,detail_cost=.1)
    original=r.detail
    r.detail=lambda item: b'<html>security challenge</html>' if item==r.items[0] else original(item)
    rows,a=r.fetch(); count=len(r.calls)
    assert len(rows)==1 and a['progress_resume_possible'] is False and len(r.cache._entries)==1
    error = next(o for o in a['detail_observations'] if o['error_kind'])
    assert error['error_kind']=='detail_mismatch' and error['http_status']==200
    assert not any('security challenge' in str(o) for o in a['request_observations'])
    again,b=r.fetch()
    assert len(again)==1 and r.items[0]['link'] in r.calls[count:]
    assert r.items[1]['link'] not in r.calls[count:]


@pytest.mark.parametrize('status',[403,429,503])
def test_actual_refusal_stops_without_scheduling_quick_resume(monkeypatch,status):
    r=Replay(monkeypatch,count=3,detail_cost=.1)
    # The collector sorts sequence-linked titles newest first: 3,2,1.
    r.failures[r.items[1]['link']]=(None,status)
    rows,a=r.fetch()
    assert len(rows)==1 and r.items[0]['link'] not in r.calls
    assert a['progress_resume_possible'] is False and r.remembered
    assert a['detail_observations'][-1]['http_status']==status
    assert a['detail_observations'][-1]['http_request_count']==1


@pytest.mark.parametrize('status',[403,429,503])
def test_primary_index_refusal_never_falls_through_to_other_host(monkeypatch,status):
    r=Replay(monkeypatch,count=3,detail_cost=.1)
    r.failures[transport.IIH_URL+'?code=2891']=(None,status)
    rows,a=r.fetch()
    assert not rows and len(r.calls)==1 and a['status']=='error'
    assert a['http_request_count']==1 and a['progress_resume_possible'] is False


def test_final_handoff_cannot_keep_originals_that_expire_during_copy(monkeypatch):
    r=Replay(monkeypatch,count=2,detail_cost=.1); r.fetch()
    for key,(row,_) in list(r.cache._entries.items()):
        r.cache._entries[key]=(row,r.epoch+5)
    copy=source.deepcopy; used=[]
    def slow_copy(value):
        answer=copy(value)
        if not used:
            used.append(True);r.advance(6)
        return answer
    monkeypatch.setattr(source,'deepcopy',slow_copy)
    rows,a=r.fetch()
    assert not rows and a['status']!='success'
    assert not a['source_record_archive'] and a['progress_resume_possible'] is False


def test_reader_deadline_is_terminal_without_new_body_request(monkeypatch):
    from data_fetch.market_sources import twse_announcement_progress as p
    r=Replay(monkeypatch,count=1,detail_cost=.1);r.fetch(); count=len(r.calls)
    original=p.read_response
    def delayed(*args,**kwargs):
        answer=original(*args,**kwargs);r.advance(21);return answer
    monkeypatch.setattr(p,'read_response',delayed)
    rows,a=r.fetch()
    assert not rows and len(r.calls[count:])==1
    assert a['detail_observations'][0]['error_kind']=='timeout'
    assert a['coverage_status']=='partial'


def test_injected_plain_http_200_is_never_seeded_as_native_progress(monkeypatch):
    import httpx
    r=Replay(monkeypatch,count=1,detail_cost=.1)
    def get(url,**kwargs):
        if url==transport.IIH_URL:
            i=r.items[0]
            return httpx.Response(200,request=httpx.Request('GET',url),json={'info':{'status':'success','data':{'code':'2891'}},'news':[
                {'companyId':'2891','companyName':'中信金','subject':i['title'],'date':'115/10/06','time':'14:15','link':i['link']}]})
        return httpx.Response(200,request=httpx.Request('GET',url),content=r.detail(r.by_url[url]))
    rows,a=source.fetch_recent_company_announcements('2891.TW',now=NOW,get=get)
    assert len(rows)==1 and not r.cache._entries
    assert 'progress_resume_possible' not in a


def test_request_key_separates_method_payload_and_exact_query_identity():
    from data_fetch.market_sources.twse_announcement_progress import request_fingerprint as fp
    url=transport.JSON_URL
    keys=[fp('POST',url,payload={'companyId':'2891','month':'9'}),
          fp('POST',url,payload={'companyId':'2891','month':'10'}),
          fp('GET',url,payload={'companyId':'2891','month':'9'}),
          fp('POST',url+'?a=1',payload={'companyId':'2891','month':'9'}),
          fp('POST',url,data={'companyId':'2891','month':'9'})]
    assert len(set(keys))==5


def test_cold_valid_original_survives_optional_sqlite_cache_outage(monkeypatch, tmp_path):
    import sqlite3,cache_store
    from cache_backends import SqliteCacheBackend
    r=Replay(monkeypatch,count=1,detail_cost=.1)
    broken=SqliteCacheBackend(tmp_path/'outage.sqlite3')
    def unavailable(): raise sqlite3.OperationalError('database unavailable')
    monkeypatch.setattr(broken,'_connection',unavailable)
    monkeypatch.setattr(cache_store,'_backend',broken)
    rows,a=r.fetch()
    assert len(rows)==1 and a['coverage_status']=='window_complete'
    assert a['source_record_archive'][0]['reusable'] is False
    assert a['progress_resume_possible'] is False and a['http_request_count']==2


def test_warm_original_is_not_delivered_if_cache_fails_at_final_handoff(monkeypatch, tmp_path):
    import sqlite3,cache_store
    from cache_backends import SqliteCacheBackend
    r=Replay(monkeypatch,count=1,detail_cost=.1);r.fetch();count=len(r.calls)
    broken=SqliteCacheBackend(tmp_path/'outage.sqlite3')
    def unavailable(): raise sqlite3.OperationalError('database unavailable')
    monkeypatch.setattr(broken,'_connection',unavailable)
    original=source._detail_fields
    def parse_then_outage(text):
        value=original(text);monkeypatch.setattr(cache_store,'_backend',broken);return value
    monkeypatch.setattr(source,'_detail_fields',parse_then_outage)
    rows,a=r.fetch()
    assert not rows and a['coverage_status']=='partial' and len(r.calls[count:])==1
    assert not a['source_record_archive'] and a['progress_resume_possible'] is False


def test_huge_nonfinite_time_in_cache_is_a_miss_not_an_uncaught_overflow(monkeypatch):
    r=Replay(monkeypatch,count=1,detail_cost=.1);r.fetch();count=len(r.calls)
    key,(row,expiry)=next(iter(r.cache._entries.items()))
    row['fresh_until_epoch']=10**1000;r.cache._entries[key]=(row,expiry)
    rows,a=r.fetch()
    assert len(rows)==1 and len(r.calls[count:])==2 and a['detail_cache_hit_count']==0
