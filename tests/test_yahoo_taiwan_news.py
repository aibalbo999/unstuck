from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from data_fetch.enrichment_providers import YahooProvider
from data_fetch.types import FetchRequest

FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/yahoo_tw_5314_news_20260927.html'
CUTOFF = datetime(2026, 9, 27, 10, 34, 59, tzinfo=timezone.utc)


def context(ticker='5314.TWO'):
    return {'stock': SimpleNamespace(news=[]), 'data': {'ticker': ticker, 'quote_type': 'EQUITY',
        'exchange': 'TWO' if ticker.endswith('.TWO') else 'TAI',
        'company_name': '世紀* / Myson Century, Inc.',
        'company_identity': {'ticker': ticker, 'stock_id': ticker.split('.')[0],
                             'official_name': '世紀*', 'instrument_type': 'EQUITY'}}}


@pytest.fixture(autouse=True)
def isolation(monkeypatch):
    import news_freshness_policy
    import provider_resilience
    import provider_throttle
    provider_resilience.clear_provider_circuits()
    provider_throttle.clear_provider_throttles()
    monkeypatch.setattr(news_freshness_policy, 'news_cutoff', lambda value=None: value or CUTOFF)
    monkeypatch.setenv('PROVIDER_RETRY_BACKOFF_SECONDS', '0')
    monkeypatch.setenv('PROVIDER_RETRY_JITTER_SECONDS', '0')
    yield
    provider_resilience.clear_provider_circuits()
    provider_throttle.clear_provider_throttles()


def fake_http(monkeypatch, body=None, status=200, headers=None):
    calls=[]
    @contextmanager
    def stream(method, url, **kwargs):
        calls.append({'method':method, 'url':url, **kwargs})
        response=httpx.Response(status, content=FIXTURE.read_bytes() if body is None else body,
                                headers=headers or {'Content-Type':'text/html; charset=utf-8'},
                                request=httpx.Request(method,url))
        try:
            yield response
        finally:
            response.close()
    from data_fetch.market_sources import yahoo_taiwan_news as regional
    monkeypatch.setattr(regional, 'curl_stream', stream)
    return calls


def test_optional_tw_provider_recovers_three_with_original_partial_archive(monkeypatch):
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert len(result.value)==3
    assert result.status=='degraded_enrichment'
    assert result.provider=='Yahoo Finance news'
    assert result.audit['transport']=='yahoo_taiwan_quote_news_html'
    assert result.audit['source_url']=='https://tw.stock.yahoo.com/quote/5314/news'
    assert result.audit['raw_count']==10 and result.audit['usable_count']==3
    assert result.audit['rejected_reason_counts']=={'historical':7}
    assert result.audit['coverage_status']=='partial'
    assert len(result.audit['source_record_archive'])>=7
    assert [row['date'][:10] for row in result.value]==['2026-09-18','2026-09-10','2026-09-04']
    assert all(row['source']=='中央社財經' for row in result.value)
    assert all(row['source_type']=='yahoo_taiwan_news' for row in result.value)
    assert len(calls)==1 and calls[0]['method']=='GET' and calls[0]['follow_redirects'] is False


def changed_fixture(change):
    from data_fetch.market_sources.yahoo_taiwan_news import _decode_assignment
    import json
    value,_=_decode_assignment(FIXTURE.read_bytes())
    change(value['context']['dispatcher']['stores'])
    return ('<script>root.App.main = '+json.dumps(value,ensure_ascii=False)+';</script>').encode()


def slots(stores):
    return stores['StreamStore']['streams']['CUSTOM:NEWS.mega']['data']['stream_items']


def test_raw_invalid_rows_consume_budget_and_survive_prompt_boundary(monkeypatch):
    def change(stores):
        articles=[r for r in slots(stores) if r.get('type')=='article']
        for index,row in enumerate(articles[:10]):
            row['title'] = 'RAW_REJECTED_SENTINEL '+str(index)
            row['is_eligible'] = False
        stores['StreamStore']['streams']['CUSTOM:NEWS.mega']['data']['stream_items']=articles
    calls=fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.value==[] and result.status=='degraded_enrichment'
    assert result.audit['raw_count']==10 and result.audit['rejected_count']==10
    assert result.audit['rejected_reason_counts']=={'article_unavailable':10}
    assert result.audit['capacity_excluded_count']==10 and len(calls)==1
    from prompt_evidence import prompt_evidence_copy
    from data_trust_snapshot import build_data_snapshot
    data={'ticker':'5314.TWO','source_audit':[result.audit]}
    assert 'RAW_REJECTED_SENTINEL' in str(build_data_snapshot({'data':data},max_bytes=300000))
    assert 'RAW_REJECTED_SENTINEL' not in str(prompt_evidence_copy(data))
    assert not any(key.startswith('_') for key in result.audit)


def test_unknown_dates_are_not_replaced_with_fetch_time(monkeypatch):
    def change(stores):
        articles=[r for r in slots(stores) if r.get('type')=='article'][:1]
        articles[0]['pubtime']=None
        stores['StreamStore']['streams']['CUSTOM:NEWS.mega']['data']['stream_items']=articles
    fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.value==[] and result.status=='degraded_enrichment'
    assert result.audit['rejected_reason_counts']=={'unknown_date':1}
    assert result.audit['source_record_archive'][0]['record']['pubtime'] is None
    assert result.audit['source_record_archive'][0]['normalized_record']['date']==''


def test_invalid_title_or_url_rejections_merge_with_historical_gate(monkeypatch):
    def change(stores):
        slots(stores)[0]['title']={'untrusted':'title'}
        slots(stores)[2]['url']=slots(stores)[2]['link']='https://evil.test/story'
    fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert len(result.value)==1 and result.status=='degraded_enrichment'
    assert result.audit['raw_count']==10 and result.audit['rejected_count']==9
    assert result.audit['rejected_reason_counts']=={'historical':7,'invalid_title':1,'invalid_link':1}


def test_bare_request_keeps_verified_resolved_ticker(monkeypatch):
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314'),context())
    assert len(result.value)==3 and len(calls)==1
    assert result.audit['page_ticker']=='5314.TWO'
    assert all(row['page_ticker']=='5314.TWO' for row in result.value)


@pytest.mark.parametrize('mutation',[
    lambda d:d.pop('quote_type'), lambda d:d.update(quote_type='ETF'),
    lambda d:d.pop('exchange'),lambda d:d.update(exchange='TAI'),
    lambda d:d.update(ticker='5314'),
    lambda d:d['company_identity'].update(ticker='2330.TW'),
])
def test_unresolved_instrument_or_market_preserves_legacy(monkeypatch,mutation):
    import data_fetch.market_sources.http_enrichment as legacy
    data=context();mutation(data['data']);seen=[]
    monkeypatch.setattr(legacy,'fetch_yfinance_news_catalysts',lambda stock:seen.append(stock) or [])
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),data)
    assert len(seen)==1 and calls==[]
    assert 'transport' not in result.audit


def test_us_provider_and_legacy_sync_path_unchanged(monkeypatch):
    import data_fetch.market_sources.http_enrichment as legacy
    stock=SimpleNamespace(news=[{'content':{'title':'Apple launches product','pubDate':'2026-09-25T12:00:00Z',
        'summary':'Apple report','provider':{'displayName':'Publisher'},'clickThroughUrl':{'url':'https://publisher.test/aapl'}}}])
    direct=legacy.fetch_yfinance_news_catalysts(stock)
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('AAPL'),{'stock':stock,'data':{'ticker':'AAPL','company_name':'Apple'}})
    assert result.status=='success' and result.value[0]['title']==direct[0]['title']
    assert result.value[0]['source_type']=='yfinance_news' and calls==[]
    assert 'transport' not in result.audit


@pytest.mark.parametrize('mutation',[
    lambda s:s['QuoteFundamental']['currentSymbolInfo'].update(symbol='2330.TW'),
    lambda s:s['QuoteFundamental']['currentSymbolInfo'].update(exchange='TAI'),
    lambda s:s['QuoteFundamental']['currentSymbolInfo'].update(holdingType='ETF'),
    lambda s:s['PageStore'].update(currentPageName='stockIndex'),
    lambda s:s['PageStore']['pageData'].update(url='https://tw.stock.yahoo.com/quote/5314.TW/news'),
    lambda s:s['PageStore']['compositeConfig']['main-3-QuoteNews']['components'][0]['config']['ncpParams']['query'].update(s=['2330.TW']),
    lambda s:s['StreamStore']['streams']['CUSTOM:NEWS.mega']['data'].pop('stream_items'),
])
def test_page_schema_or_identity_mismatch_fails_once(monkeypatch,mutation):
    calls=fake_http(monkeypatch,changed_fixture(mutation))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.value==[] and len(calls)==1
    assert result.audit['error_kind']=='parse_error'
    assert result.audit['response_complete'] is True


def test_exact_bound_empty_stream_is_unknown_not_error_or_success(monkeypatch):
    body=changed_fixture(lambda s:s['StreamStore']['streams']['CUSTOM:NEWS.mega']['data'].update(stream_items=[]))
    calls=fake_http(monkeypatch,body)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='degraded_enrichment' and result.value==[]
    assert result.audit['raw_count']==0 and result.audit['retrieval_status']=='no_records'
    assert len(calls)==1


@pytest.mark.parametrize('status,kind',[(302,'http_error'),(401,'authentication'),(403,'access_denied'),(429,'rate_limited'),(503,'server_error')])
def test_http_errors_are_single_attempt_and_not_empty_success(monkeypatch,status,kind):
    calls=fake_http(monkeypatch,status=status)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']==kind
    assert result.audit['http_status']==status and result.value==[] and len(calls)==1
    assert result.audit['http_request_sent'] is True


def test_existing_yahoo_outer_guard_prevents_regional_call(monkeypatch):
    import provider_resilience
    monkeypatch.setattr(provider_resilience,'_check_provider_state',lambda provider:(_ for _ in ()).throw(provider_resilience.ProviderCircuitOpenError('blocked')))
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='unavailable' and calls==[]
    assert result.audit['http_request_sent'] is False


def test_regional_retry_after_persists_and_local_block_has_no_new_http(monkeypatch):
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    from search_provider_runtime import cooldown_state, scope_key
    import provider_throttle
    calls=fake_http(monkeypatch,status=429,headers={'Retry-After':'1200'})
    first=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    state=cooldown_state(scope_key('Yahoo Finance news', endpoint='yahoo_tw_quote_news'))
    assert state.get('retry_at',0)-regional.time.time()>=1199
    assert first.audit['http_status']==429
    # Isolated test only: simulate a different process with no local throttle,
    # retaining the persistent endpoint guard written by the actual first call.
    provider_throttle.clear_provider_throttles()
    second=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert second.value==[] and second.status!='success' and len(calls)==1
    assert second.audit['http_request_sent'] is False
    assert second.audit['error_kind']=='cooldown'
    assert second.audit.get('http_status') is None
    assert second.audit['prior_http_status']==429
    assert second.audit['retry_at']==state['retry_at']


def test_decoder_no_execution_preserves_strings_and_rejects_unbounded_shapes():
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    value,diag=regional._decode_assignment(b'root.App.main = {"s":"undefined \\\" text", "x":undefined};')
    assert value=={'s':'undefined " text','x':None} and diag['undefined_value_count']==1
    for body in [b'root.App.main = {"x":(()=>1)()};',b'root.App.main = {"x":undefined+1};',
                 b'root.App.main = {"x":1,"x":2};',b'root.App.main = {"x":NaN};',
                 b'root.App.main = {"x":'+b'['*70+b'0'+b']'*70+b'};']:
        with pytest.raises(ValueError):regional._decode_assignment(body)


def test_only_selected_quote_stream_counts_not_duplicate_or_other_streams(monkeypatch):
    from copy import deepcopy
    def change(stores):
        other=deepcopy(stores['StreamStore']['streams']['CUSTOM:NEWS.mega'])
        other['data']['stream_items'][0]['title']='世紀 UNRELATED_STREAM_SENTINEL'
        stores['StreamStore']['streams']['other.mega']=other
        stores['ApacStreamStore']={'streams':{'CUSTOM:NEWS.mega':other}}
    calls=fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert len(result.value)==3 and result.audit['raw_count']==10 and len(calls)==1
    assert 'UNRELATED_STREAM_SENTINEL' not in str(result.value)+str(result.audit)


def test_earlier_unknown_type_slot_cannot_be_replaced_by_later_valid_article(monkeypatch):
    def change(stores):
        articles=[r for r in slots(stores) if r.get('type')=='article']
        for row in articles[:10]:row['type']='unexpected'
        articles[10]=dict(articles[-1],pubtime=1789713761000,type='article')
        stores['StreamStore']['streams']['CUSTOM:NEWS.mega']['data']['stream_items']=articles
    fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.value==[] and result.audit['raw_count']==10
    assert result.audit['rejected_reason_counts']=={'invalid_article_schema':10}
    assert result.audit['capacity_excluded_count']==10


def test_future_and_unrelated_articles_remain_rejected(monkeypatch):
    def change(stores):
        first=slots(stores)[0]
        first['pubtime']=int(CUTOFF.timestamp()*1000)+60000
        second=slots(stores)[2]
        second['title']='別家公司產品上市';second['summary']='別家公司新聞'
    fake_http(monkeypatch,changed_fixture(change))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert len(result.value)==1 and result.audit['rejected_reason_counts']=={'future':1,'issuer_unverified':1,'historical':7}


def test_connection_failure_is_not_a_received_http_response(monkeypatch):
    calls=[]
    def broken(*args,**kwargs):
        calls.append(args)
        raise httpx.ConnectError('connection failure')
    monkeypatch.setattr(__import__('data_fetch.market_sources.yahoo_taiwan_news',fromlist=['curl_stream']),'curl_stream',broken)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']=='transport_error'
    assert result.audit.get('http_status') is None
    assert result.audit['response_bytes']==0 and result.audit['response_complete'] is False
    assert result.audit['response_hash_scope']=='not_read' and 'response_sha256' not in result.audit
    assert len(calls)==1


def test_bounded_body_hash_is_labelled_prefix_not_full_response(monkeypatch):
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    import hashlib
    monkeypatch.setattr(regional,'MAX_BODY_BYTES',100)
    calls=[]
    @contextmanager
    def oversized(method,url,**kwargs):
        calls.append(url)
        class Response:
            status_code=200;headers={}
            def iter_bytes(self,chunk_size):
                yield b'a'*60
                yield b'b'*60
        yield Response()
    monkeypatch.setattr(__import__('data_fetch.market_sources.yahoo_taiwan_news',fromlist=['curl_stream']),'curl_stream',oversized)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']=='response_too_large'
    assert result.audit['response_bytes']==100 and result.audit['response_bytes_read']==120
    assert result.audit['response_complete'] is False
    assert result.audit['response_hash_scope']=='captured_prefix'
    assert result.audit['captured_prefix_sha256']==hashlib.sha256(b'a'*60+b'b'*40).hexdigest()
    assert 'response_sha256' not in result.audit
    assert len(calls)==1


def test_declared_oversized_body_is_not_read(monkeypatch):
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    calls=fake_http(monkeypatch,headers={'Content-Length':str(regional.MAX_BODY_BYTES+1)})
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']=='response_too_large'
    assert result.audit['response_bytes']==0 and result.audit['response_hash_scope']=='not_read'
    assert len(calls)==1


def test_timeout_during_body_does_not_adopt_or_retry(monkeypatch):
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    clock=SimpleNamespace(value=0)
    monkeypatch.setattr(regional,'time',SimpleNamespace(monotonic=lambda:clock.value,time=lambda:1790505299))
    @contextmanager
    def owns(*args,**kwargs):yield lambda:True
    monkeypatch.setattr(regional,'endpoint_admission',owns)
    calls=[]
    @contextmanager
    def delayed(method,url,**kwargs):
        calls.append(url)
        class Response:
            status_code=200;headers={}
            def iter_bytes(self,chunk_size):
                clock.value=13
                yield FIXTURE.read_bytes()
        yield Response()
    monkeypatch.setattr(__import__('data_fetch.market_sources.yahoo_taiwan_news',fromlist=['curl_stream']),'curl_stream',delayed)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']=='timeout' and result.value==[]
    assert len(calls)==1 and result.audit['response_complete'] is False


def test_lost_lease_after_parse_keeps_originals_but_no_evidence(monkeypatch):
    import data_fetch.market_sources.yahoo_taiwan_news as regional
    alive=SimpleNamespace(value=True)
    @contextmanager
    def owns(*args,**kwargs):yield lambda:alive.value
    monkeypatch.setattr(regional,'endpoint_admission',owns)
    parse=regional.parse_yahoo_taiwan_news
    def lose_after_parse(*args,**kwargs):
        records=parse(*args,**kwargs);alive.value=False;return records
    monkeypatch.setattr(regional,'parse_yahoo_taiwan_news',lose_after_parse)
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.status=='error' and result.audit['error_kind']=='lease_lost' and result.value==[]
    assert result.audit['raw_count']==10 and result.audit['rejected_reason_counts']=={'acquisition_unusable':10}
    assert result.audit['response_complete'] is True and len(calls)==1


def test_provider_audit_merge_cache_snapshot_and_single_canonical_sink(monkeypatch):
    from data_fetch.workflow import _audit_entries_from_provider_results
    from data_fetch.enrichment_merge import _merge_optional_http_bundle
    from data_fetch.cache_helpers import _cache_financial_data
    from data_fetch.service import StockDataService
    import data_fetch.service as service
    import data_fetch.enrichment_merge as merge
    import news_freshness_policy
    from news_datetime import parse_news_datetime
    from cache_store import get_cache_json
    from data_trust import append_source_audit
    from prompt_evidence import prompt_evidence_copy
    from data_trust_snapshot import build_data_snapshot
    # Other existing workflow helpers pass numeric cutoffs; preserve that contract.
    monkeypatch.setattr(news_freshness_policy,'news_cutoff',lambda value=None:parse_news_datetime(value) if value is not None else CUTOFF)
    monkeypatch.setattr(merge,'time_module',SimpleNamespace(time=lambda:CUTOFF.timestamp()))
    sink=[]
    monkeypatch.setattr(service,'record_source_audit_entries',lambda entries:sink.append(entries))
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert sink==[]
    data=context()['data']
    for audit in _audit_entries_from_provider_results([result]):append_source_audit(data,audit)
    merged=_merge_optional_http_bundle(data,{'yahoo_news':result.value},refreshed_sources=('recent_catalysts',))
    channel=next(a for a in merged['source_audit'] if a['provider']=='Yahoo Finance news')
    assert channel['status']=='degraded_enrichment' and channel['actual_provider']=='Yahoo Taiwan'
    assert channel['source_url']=='https://tw.stock.yahoo.com/quote/5314/news'
    assert channel['source_record_archive'] and channel['raw_count']==10
    aggregate=merged['source_audit'][-1]
    assert aggregate['status']=='degraded_enrichment' and aggregate['event_kind']=='aggregate'
    _cache_financial_data(merged,'5314.TWO')  # Mandatory runner directs this into isolated test storage.
    cached=get_cache_json('financial_data:5314.TWO')
    cached_channel=next(a for a in cached['source_audit'] if a['provider']=='Yahoo Finance news')
    assert cached_channel['source_record_archive']==channel['source_record_archive']
    assert cached_channel['fetched_at']==channel['fetched_at']
    assert all(row['source_page_url']==channel['source_url'] for row in cached['recent_catalysts'])
    old_title='世紀民生布局水面無人載具'
    assert old_title in str(build_data_snapshot({'data':cached},max_bytes=300000))
    assert old_title not in str(prompt_evidence_copy(cached))
    built=StockDataService()._build_result(FetchRequest.from_ticker('5314.TWO'),cached,1)
    assert len(sink)==1
    assert len([a for a in sink[0] if a['provider']=='Yahoo Finance news'])==1
    assert built.source_audit==sink[0] and len(calls)==1


def test_persistent_transport_failure_does_not_inherit_prior_http_status(monkeypatch):
    from search_provider_runtime import observe_http_response,cooldown_state,scope_key
    observe_http_response(SimpleNamespace(status_code=200))
    monkeypatch.setattr(__import__('data_fetch.market_sources.yahoo_taiwan_news',fromlist=['curl_stream']),'curl_stream',lambda *a,**k:(_ for _ in ()).throw(httpx.ConnectError('offline')))
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    assert result.audit['http_status'] is None
    assert cooldown_state(scope_key('Yahoo Finance news',endpoint='yahoo_tw_quote_news'))['http_status'] is None


def test_single_canonical_sla_preserves_partial_and_actual_provider(monkeypatch):
    import json
    import provider_sla
    from data_fetch.service import StockDataService
    calls=fake_http(monkeypatch)
    result=YahooProvider().fetch(FetchRequest.from_ticker('5314.TWO'),context())
    # No local helper sink: only the normal service owns this observation.
    with provider_sla._connect() as conn:
        assert conn.execute('SELECT count(*) FROM provider_sla_events').fetchone()[0]==0
    data={**context()['data'],'recent_catalysts':result.value,'source_audit':[result.audit]}
    StockDataService()._build_result(FetchRequest.from_ticker('5314.TWO'),data,1)
    with provider_sla._connect() as conn:
        rows=conn.execute('SELECT * FROM provider_sla_events').fetchall()
        stats=conn.execute('SELECT * FROM provider_sla_stats WHERE provider=?',('Yahoo Finance news',)).fetchone()
    assert len(rows)==1 and rows[0]['status']=='degraded_enrichment' and rows[0]['record_count']==3
    details=json.loads(rows[0]['details_json'])
    assert details['actual_provider']=='Yahoo Taiwan' and details['coverage_status']=='partial'
    assert details['raw_count']==10 and details['usable_count']==3 and details['rejected_count']==7
    assert 'source_record_archive' not in details
    assert stats['success_count']==0 and stats['degraded_enrichment_count']==1 and len(calls)==1
