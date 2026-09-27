"""Issuer content through the real workflow/service and isolated SLA SQLite.

Only the external process, PDF text extraction, and unrelated core market data
are synthetic. Provider, merge, cache, audit persistence, and projection are real.
"""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import sqlite3
import time
from types import SimpleNamespace

import pytest


INDEX = ('<title>世紀民生科技股份有限公司</title><a href="https://www.myson.com.tw/public/uploads/pdf/contract.pdf">'
         '1150415世紀民生法說會簡報</a>').encode()
PDF = b'%PDF-OFFLINE-CONTRACT'


@pytest.fixture
def flow(monkeypatch):
    import bounded_curl_process
    import cache_store
    import company_conference_content as content
    import company_conference_transport as transport
    import external_http_client
    import provider_resilience
    import search_provider_runtime as runtime
    import official_financials
    import official_financials_webpro_conference as webpro
    from data_fetch import FetchRequest, StockDataService
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_base import CallableProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.types import ProviderResult

    store, calls = {}, []
    monkeypatch.setattr(bounded_curl_process.subprocess, 'Popen', lambda *a, **k: pytest.fail('no subprocess'))
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
    for name in transport.PROXY_ENV:monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(transport, '_VERSION', '8.7.1')
    monkeypatch.setattr(external_http_client, 'proxy_url_for_request', lambda *_a: None)
    monkeypatch.setattr(provider_resilience, '_CIRCUITS', {})
    monkeypatch.setattr(provider_resilience, '_SHARED_CIRCUIT_STORE', None)
    monkeypatch.setattr(cache_store, 'get_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(cache_store, 'set_cache_json', lambda key, value, ttl_seconds: store.__setitem__(key, deepcopy(value)))
    monkeypatch.setattr(runtime, 'get_cache_json', lambda key: deepcopy(store.get(key)))
    monkeypatch.setattr(runtime, 'set_cache_json', lambda key, value, ttl_seconds: store.__setitem__(key, deepcopy(value)))
    def collect(argv, deadline, **kwargs):
        url = argv[-1]; calls.append(url)
        raw = INDEX if url == transport.INDEX_URL else PDF
        kind = b'text/html' if url == transport.INDEX_URL else b'application/pdf'
        return {'body': raw, 'headers': b'HTTP/2 200\r\nContent-Type: '+kind+b'\r\n',
                'metadata': json.dumps({'http_code':200,'url_effective':url,'num_redirects':0,'http_version':'2'}).encode(),
                'process_started':True}, 0, None
    monkeypatch.setattr(transport, 'collect_capped_process', collect)
    def extract(raw, **kwargs):
        assert raw == PDF and 0 < kwargs['timeout_seconds'] <= 10
        return {'pages':[{'page_number':1,'text':'世紀民生（5314）財務原文'}, {'page_number':2,'text':''}],
                'page_count':2,'empty_pages':[2],'coverage_status':'partial','parser_version':'offline-text-fixture',
                'content_sha256':hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(content, 'extract_pdf_pages', extract)
    monkeypatch.setattr(official_financials,'fetch_mops_investor_conference_events',lambda *a,**k:pytest.fail('unexpected MOPS'))
    monkeypatch.setattr(webpro,'fetch_webpro_conference_context',lambda *a,**k:pytest.fail('unexpected WebPro'))
    def core(request, _context):
        return ProviderResult('market_data','synthetic core','success',
                              {'ticker':request.ticker,'company_name':'世紀民生科技股份有限公司','current_price':10.0,
                               'data_source_notes':[], 'source_audit':[]})
    service = StockDataService(registry=ProviderRegistry([CallableProvider('market_data','synthetic core',core), EarningsCallProvider()]))
    def fetch():
        # Force fresh *workflow* core so round two exercises the shared issuer
        # content cache, not a bypassed provider or a manually rebuilt result.
        return asyncio.run(service.fetch_async(FetchRequest.from_ticker('5314.TWO',force_refresh=True)))
    return SimpleNamespace(content=content,transport=transport,store=store,calls=calls,fetch=fetch,
                           collect=collect,official=official_financials,webpro=webpro)


def rows_and_summary():
    import provider_sla
    from provider_acquisition import project_acquisition_events
    with sqlite3.connect(provider_sla.TASK_DB_PATH) as db:
        db.row_factory=sqlite3.Row
        rows=list(db.execute("SELECT * FROM provider_sla_events WHERE source='earnings_call' ORDER BY id"))
    summary=project_acquisition_events(rows,window='last_24h',now=time.time())['sources'][0]
    return rows,summary


def audit(result):
    return next(row for row in result.source_audit if row.get('source')=='earnings_call')


def test_provider_workflow_service_sqlite_counts_two_partial_http_and_cache_never_replays(flow):
    first=flow.fetch();rows,summary=rows_and_summary()
    assert not first.data.get('error')
    context=first.data['earnings_call'];doc=context['documents'][0]
    assert doc['content_sha256']==hashlib.sha256(PDF).hexdigest()
    assert doc['pages'][0]['text']=='世紀民生（5314）財務原文' and doc['missing_text_pages']==[2]
    assert (summary['http_attempt_count'],summary['fetch_attempts'],summary['degraded_count'],summary['fetched_count'])==(2,2,2,0)
    assert len(rows)==4 and summary['aggregate_count']==2  # Provider and workflow summaries.
    details=[json.loads(row['details_json']) for row in rows]
    actual=[row for row in details if row.get('event_kind')=='http_attempt']
    assert len(actual)==2 and {row['response_sha256'] for row in actual}=={
        hashlib.sha256(INDEX).hexdigest(),hashlib.sha256(PDF).hexdigest()}
    assert all(row['http_request_sent'] is True for row in actual)
    primary=audit(first)
    assert primary['event_kind']=='aggregate' and primary['status']=='degraded_enrichment'
    assert primary['provider']==flow.content.PROVIDER and primary['fetch_id']
    assert len(primary['component_statuses'])==2

    second=flow.fetch();second_rows,after=rows_and_summary()
    assert second.data['earnings_call']==context and len(flow.calls)==2
    assert len(second_rows)==6 and after['aggregate_count']==4
    assert (after['http_attempt_count'],after['fetch_attempts'],after['degraded_count'],after['fetched_count'])==(2,2,2,0)
    assert audit(second)['cache_hit'] is True
    assert all(item['cache_hit'] is True and item['http_request_sent'] is False
               for item in audit(second)['component_statuses'].values())
    assert audit(first)['component_statuses']['pdf']['http_request_sent'] is True


def test_presentation_does_not_clear_agent20_skip_or_research_completeness(flow):
    from agent_runtime.deterministic_skips import deterministic_agent_result
    from report_analysis_completeness import assess_report_analysis_completeness
    result=flow.fetch()
    context={'analyses':{},'structured_outputs':{}}
    skipped=deterministic_agent_result(20,result.data,context)
    assert skipped is not None and '資料不足' in skipped
    before={'ticker':'5314.TWO','earnings_call':{'transcript_available':False,'transcript_excerpt':''}}
    base={'pipeline_id':'v2','structured_outputs':{20:{'guidance_tone':'資料不足'}}}
    prior=assess_report_analysis_completeness({**base,'data':before})
    after=assess_report_analysis_completeness({**base,'data':result.data})
    assert after==prior
    assert after['status']=='degraded' and after['mode_assessment']['positive_completeness_certified'] is False
    assert 'earnings_call_transcript_unavailable' in after['reason_codes']


def mops_success(*args,**kwargs):
    return [{'ticker':'5314.TWO','date':'2026-04-15','title':'法說會索引',
             'summary':'只有索引','materials':[],'source_url':'https://mops.twse.com.tw/'}]


@pytest.mark.parametrize('failure', ['wrong_issuer',403,429])
def test_issuer_failure_then_mops_success_retains_failed_component_and_correct_provider(flow,monkeypatch,failure):
    if failure=='wrong_issuer':
        monkeypatch.setattr(flow.content,'extract_pdf_pages',lambda *a,**k:{
            'pages':[{'page_number':1,'text':'其他公司（2330）'}], 'page_count':1,'empty_pages':[],
            'coverage_status':'complete','parser_version':'offline-wrong-issuer'})
    else:
        def collect(argv,*args,**kwargs):
            if argv[-1]==flow.transport.INDEX_URL:return flow.collect(argv,*args,**kwargs)
            flow.calls.append(argv[-1])
            return {'body':b'refused','headers':f'HTTP/2 {failure}\r\nRetry-After: 3600\r\n'.encode(),
                    'metadata':b'{}','process_started':True},28,'timeout'
        monkeypatch.setattr(flow.transport,'collect_capped_process',collect)
    monkeypatch.setattr(flow.official,'fetch_mops_investor_conference_events',mops_success)
    result=flow.fetch();primary=audit(result)
    assert primary['provider']=='MOPS investor conference' and primary['status']=='degraded_enrichment'
    assert result.data['earnings_call']['source']=='MOPS investor conference'
    assert not result.data['earnings_call'].get('documents')
    issuer=primary['component_statuses']['issuer_content']
    assert issuer['error_kind']==('parse_error' if failure=='wrong_issuer' else 'access_denied' if failure==403 else 'rate_limited')
    assert issuer['component_statuses']['pdf']['status']=='error'
    rows,summary=rows_and_summary()
    assert len(flow.calls)==2 and len(rows)==4  # Two summaries; mocked MOPS metadata is not an invented HTTP.
    assert (summary['http_attempt_count'],summary['fetch_attempts'],summary['failed_count'],summary['degraded_count'],summary['fetched_count'])==(2,2,1,1,0)
    if failure==429:
        assert flow.store[flow.content.GUARD_KEY]['retry_at'] >= time.time()+3590


def test_issuer_mops_webpro_failure_summary_never_adds_a_fourth_attempt(flow,monkeypatch):
    from search_provider_runtime import SourceResponseError, record_observation
    def issuer_error(argv,*args,**kwargs):
        flow.calls.append(argv[-1])
        return {'body':b'refused','headers':b'HTTP/2 403\r\n','metadata':b'{}','process_started':True},0,None
    monkeypatch.setattr(flow.transport,'collect_capped_process',issuer_error)
    def failure(provider):
        def call(*args,**kwargs):
            error=SourceResponseError('access_denied',status_code=403)
            error.diagnostic.update(actual_provider=provider,http_request_sent=True)
            record_observation(provider,time.monotonic(),outcome='failure',source='earnings_call',
                               details=error.diagnostic)
            raise error
        return call
    monkeypatch.setattr(flow.official,'fetch_mops_investor_conference_events',failure('MOPS investor conference'))
    monkeypatch.setattr(flow.webpro,'fetch_webpro_conference_context',failure('TWSE WebPro'))
    result=flow.fetch();primary=audit(result);rows,summary=rows_and_summary()
    assert len(flow.calls)==1 and not result.data.get('earnings_call')
    assert primary['status']=='error' and primary['message'].startswith('optional 外部來源')
    assert primary['component_statuses']['issuer_content']['error_kind']=='access_denied'
    assert {'MOPS','WebPro'} <= primary['component_statuses']['official_index']['component_statuses'].keys()
    assert len(rows)==5 and summary['aggregate_count']==2
    assert (summary['http_attempt_count'],summary['fetch_attempts'],summary['failed_count'],summary['fetched_count'])==(3,3,3,0)


def test_lost_lease_after_index_never_sends_pdf_or_publishes_fresh_cache(flow,monkeypatch):
    from search_provider_runtime import SourceResponseError
    ownership={'held':True}
    @contextmanager
    def admission(*args,**kwargs):yield lambda:ownership['held']
    monkeypatch.setattr(flow.content,'endpoint_admission',admission)
    original=flow.content.select_presentation
    def parse(*args,**kwargs):
        value=original(*args,**kwargs);ownership['held']=False;return value
    monkeypatch.setattr(flow.content,'select_presentation',parse)
    with pytest.raises(SourceResponseError) as error:flow.content.fetch_company_conference('5314.TWO')
    assert error.value.error_kind=='lease_lost' and len(flow.calls)==1
    assert flow.content.GUARD_KEY not in flow.store
    cached=[row for key,row in flow.store.items() if key.startswith('shared_provider:')]
    assert len(cached)==1 and 'value' not in cached[0] and 'fresh_until_epoch' not in cached[0]
    rows,summary=rows_and_summary()
    assert len(rows)==1 and summary['http_attempt_count']==1 and summary['fetched_count']==0


def test_active_endpoint_guard_blocks_index_before_native_transfer(flow):
    from search_provider_runtime import SourceResponseError
    flow.store[flow.content.GUARD_KEY]={'retry_at':time.time()+600,'error_kind':'rate_limited'}
    with pytest.raises(SourceResponseError):flow.content.fetch_company_conference('5314.TWO')
    rows,summary=rows_and_summary()
    assert not flow.calls and len(rows)==1
    assert summary['http_attempt_count']==0 and summary['fetch_attempts']==0 and summary['local_block_count']==1


@pytest.mark.parametrize('kind', ['lease_lost', 'timeout', 'single_flight_busy', 'guard_storage_unavailable'])
def test_local_or_deadline_failure_stops_entire_earnings_provider_without_fallback(flow, monkeypatch, kind):
    """A lost operation budget/ownership is not permission for a new source call."""
    from search_provider_runtime import SourceResponseError
    fallbacks = []
    def issuer_failure(*args, **kwargs):
        error = SourceResponseError(kind)
        error.diagnostic.update(actual_provider=flow.content.PROVIDER, http_request_sent=False,
                                event_kind='local_block')
        raise error
    def mops(*args, **kwargs):
        fallbacks.append('MOPS')
        return mops_success(*args, **kwargs)
    def webpro(*args, **kwargs):
        fallbacks.append('WebPro')
        return {}
    monkeypatch.setattr(flow.content, 'fetch_company_conference', issuer_failure)
    monkeypatch.setattr(flow.official, 'fetch_mops_investor_conference_events', mops)
    monkeypatch.setattr(flow.webpro, 'fetch_webpro_conference_context', webpro)
    result = flow.fetch()
    assert fallbacks == [] and flow.calls == []
    assert not result.data.get('earnings_call')
    primary = audit(result)
    assert primary['status'] == 'error' and primary['error_kind'] == kind
    assert primary['provider'] == flow.content.PROVIDER
    rows, summary = rows_and_summary()
    assert len(rows) == 2 and summary['aggregate_count'] == 2
    assert summary['http_attempt_count'] == 0 and summary['fetch_attempts'] == 0
