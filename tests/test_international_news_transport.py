import asyncio
from contextlib import contextmanager
import json

import httpx
import pytest
import external_data_gdelt as gdelt
import provider_sla
from provider_correlation import correlation_scope, source_operation
from search_response_validation import observed_json_get

REAL_RECORD=provider_sla.record_source_audit_entries

class Client:
    def __init__(self,response,change=None,error=None):self.response=response;self.calls=[];self.change=change;self.error=error
    async def get(self,*args,**kwargs):
        self.calls.append((args,kwargs))
        if self.change:self.change()
        if self.error:raise self.error
        return self.response
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass

@pytest.fixture
def events(monkeypatch):
    rows=[];monkeypatch.setattr(provider_sla,'record_source_audit_entries',lambda entries:rows.extend(entries));return rows

@contextmanager
def owner(source='international_news_context',provider='GDELT / Google News RSS',ticker='2356.TW'):
    with correlation_scope(replace=True,job_id='native-news-test',ticker=ticker):
        with source_operation(source,provider):yield

def response(kind='rss',status=200,url=None,method='GET'):
    return httpx.Response(status,content=b'{"articles":[]}' if kind=='gdelt' else b'<rss><channel/></rss>',request=httpx.Request(method,url or (gdelt.GDELT_DOC_URL if kind=='gdelt' else gdelt.GOOGLE_NEWS_RSS_URL)))

def call(client,kind,monkeypatch):
    if kind=='gdelt':return asyncio.run(observed_json_get(client,gdelt.GDELT_DOC_URL,{'query':'private query must not be logged'}))
    monkeypatch.setattr(gdelt,'parse_google_news_rss_payload',lambda text,tag:[{'headline':'unchanged result','topic':tag}])
    return asyncio.run(gdelt._fetch_google_news_rss_fallback(client,'macro','private query must not be logged'))

@pytest.mark.parametrize('kind',['gdelt','rss'])
def test_actual_get_receipt_preserves_value_and_never_claims_parsed_records(events,monkeypatch,kind):
    r=response(kind);c=Client(r)
    with owner():value=call(c,kind,monkeypatch)
    assert value==({'articles':[]} if kind=='gdelt' else [{'headline':'unchanged result','topic':'macro'}])
    assert len(c.calls)==len(events)==1
    receipt=events[0]
    assert receipt['source']=='international_news_context' and receipt['http_status']==200
    assert receipt['record_count']==0 and receipt['http_request_sent'] is True
    assert receipt['event_kind']=='http_transport_receipt' and receipt['selection_policy']=='transport-receipt-only:v1'
    assert receipt['response_bytes']==len(r.content) and receipt['response_sha256']
    assert 'private query' not in json.dumps(receipt)

@pytest.mark.parametrize('source,provider,ticker',[
    ('recent_catalysts','GDELT / Google News RSS','2356.TW'),
    ('international_news_context','other provider','2356.TW'),
    ('international_news_context','GDELT / Google News RSS','')])
def test_unbound_or_wrong_owner_cannot_borrow_receipt(events,monkeypatch,source,provider,ticker):
    with owner(source,provider,ticker):call(Client(response()),'rss',monkeypatch)
    assert not events

@pytest.mark.parametrize('change',['foreign_host','http','wrong_path','post','cache','changed_owner'])
def test_transport_scope_is_exact(events,monkeypatch,change):
    r=response()
    if change=='foreign_host':r=response(url='https://other.example/rss/search')
    elif change=='http':r=response(url='http://news.google.com/rss/search')
    elif change=='wrong_path':r=response(url='https://news.google.com/not-rss')
    elif change=='post':r=response(method='POST')
    elif change=='cache':r.from_cache=True
    def mutate():monkeypatch.setattr('provider_correlation.current_source_identity',lambda:('other','other'))
    with owner():call(Client(r,change=mutate if change=='changed_owner' else None),'rss',monkeypatch)
    assert not events

@pytest.mark.parametrize('kind',['gdelt','rss'])
def test_http_failure_receipt_does_not_turn_failure_into_content(events,monkeypatch,kind):
    c=Client(response(kind,status=429))
    with owner():
        if kind=='gdelt':
            with pytest.raises(httpx.HTTPStatusError):call(c,kind,monkeypatch)
        else:assert call(c,kind,monkeypatch)==[]
    assert len(events)==1 and events[0]['status']=='error' and events[0]['record_count']==0

@pytest.mark.parametrize('kind',['gdelt','rss'])
def test_no_response_never_fabricates_http_success(events,monkeypatch,kind):
    c=Client(None,error=TimeoutError('ordinary timeout'))
    with owner():
        if kind=='gdelt':
            with pytest.raises(TimeoutError):call(c,kind,monkeypatch)
        else:assert call(c,kind,monkeypatch)==[]
    assert len(c.calls)==1 and not events

def test_audit_write_failure_does_not_discard_content(events,monkeypatch):
    def fail(*args):raise RuntimeError('audit sink unavailable')
    monkeypatch.setattr(provider_sla,'record_source_audit_entries',fail)
    with owner():assert call(Client(response()),'rss',monkeypatch)

def test_cached_topics_do_not_create_http_receipts(events,monkeypatch):
    c=Client(None,error=AssertionError('cache must not request HTTP'))
    monkeypatch.setattr(gdelt,'async_client',lambda:c)
    monkeypatch.setattr(gdelt,'_cached_gdelt_topics',lambda key:[{'headline':'cached','url':'https://example.test/a'}])
    with owner():value=asyncio.run(gdelt.fetch_gdelt_international_news_context())
    assert value['topics'] and not c.calls and not events

def test_receipts_preserve_failed_denominator_and_acquisition_rate(events,monkeypatch,tmp_path):
    from provider_acquisition import get_provider_acquisition_summary
    monkeypatch.setattr(provider_sla,'TASK_DB_PATH',str(tmp_path/'audit.sqlite3'))
    REAL_RECORD([{'source':'international_news_context','provider':'GDELT / Google News RSS','status':status,'record_count':count} for status,count in [('success',2),('error',0)]])
    before,=get_provider_acquisition_summary()['sources']
    with owner():call(Client(response()),'rss',monkeypatch)
    REAL_RECORD(events);after,=get_provider_acquisition_summary()['sources']
    for field in ['fetched_count','failed_count','fetch_attempts','nonempty_rate']:assert after[field]==before[field]
    assert before['failed_count']==1 and before['nonempty_rate']==.5
    assert after['http_attempt_count']==before['http_attempt_count']+1


def test_new_operation_cannot_reuse_an_old_binding(events):
    from international_news_transport import begin,record
    with owner():
        binding=begin(gdelt.GOOGLE_NEWS_RSS_URL)
        with source_operation('international_news_context','GDELT / Google News RSS'):
            record(binding,response())
    assert not events


def test_changed_ticker_cannot_borrow_binding(events,monkeypatch):
    from provider_correlation import current_correlation
    def change():
        context=current_correlation();context['ticker']='other.TW'
        monkeypatch.setattr('provider_correlation.current_correlation',lambda:context)
    with owner():call(Client(response(),change=change),'rss',monkeypatch)
    assert not events


def test_malformed_json_remains_parse_failure_despite_transport_receipt(events,monkeypatch):
    from search_provider_runtime import SourceResponseError
    r=httpx.Response(200,content=b'not JSON',request=httpx.Request('GET',gdelt.GDELT_DOC_URL))
    with owner():
        with pytest.raises(SourceResponseError):call(Client(r),'gdelt',monkeypatch)
    assert len(events)==1 and events[0]['record_count']==0


def test_stream_is_not_consumed_to_create_receipt(events):
    from international_news_transport import begin,record
    class Stream(httpx.SyncByteStream):
        def __iter__(self):raise AssertionError('telemetry must not read stream')
    r=httpx.Response(200,stream=Stream(),request=httpx.Request('GET',gdelt.GOOGLE_NEWS_RSS_URL))
    with owner():record(begin(gdelt.GOOGLE_NEWS_RSS_URL),r)
    assert not events and not r.is_stream_consumed


def test_extension_cache_marker_excludes_receipt(events,monkeypatch):
    r=response();r.extensions['from_cache']=True
    with owner():assert call(Client(r),'rss',monkeypatch)
    assert not events
