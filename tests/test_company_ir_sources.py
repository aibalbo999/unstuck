from datetime import date
import hashlib

import httpx
import pytest


TODAY = date(2026, 9, 25)
INDEX = '''<html><title>Latest News - Taiwan Semiconductor Manufacturing Company</title>
<main><h1>Latest News</h1><ul>
<li><a href="/english/news/3326">2026/07/16 TSMC Reports Second Quarter Results</a></li>
<li><a href="/english/news/3399">2099/10/15 TSMC Future Results</a></li>
<li><a href="https://evil.example/english/news/2">2026/09/20 Other results</a></li>
</ul></main></html>'''
ARTICLE = '''<html><title>TSMC Reports Second Quarter Results</title>
<meta property="article:published_time" content="2026-07-16T09:00:00+08:00">
<article><h1>TSMC Reports Second Quarter Results</h1>
<div itemprop="articleBody"><p>TSMC announced second quarter financial results.</p>
<p>For the quarter ended June 30, revenue increased and net income improved.</p></div>
<a href="/system/files/newspdf/attachment/earnings.pdf">Earnings release PDF</a>
</article><footer>Do not include boilerplate</footer></html>'''


@pytest.fixture
def upstream(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    import company_ir_sources as ir
    import search_provider_runtime as runtime
    cache_store.set_cache_backend(InMemoryCache())
    observations, calls = [], []
    monkeypatch.setattr(runtime, 'record_source_audit_entries', lambda rows: observations.extend(rows))
    monkeypatch.setattr(ir, '_today', lambda: TODAY)
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(200, text=INDEX if url.endswith('latest-news') else ARTICLE,
                              headers={'content-type': 'text/html'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', get)
    yield ir, calls, observations
    cache_store.reset_cache_store_for_tests()


def test_index_keeps_real_date_and_issuer_and_rejects_future_and_foreign_links(upstream):
    ir, _, _ = upstream
    docs = ir.parse_ir_index(INDEX, '2330.TW', today=TODAY)
    assert len(docs) == 1
    assert docs[0]['ticker'] == '2330.TW'
    assert docs[0]['published_at'] == '2026-07-16'
    assert docs[0]['document_kind'] == 'financial_results'
    assert docs[0]['coverage_status'] == 'metadata_only'
    assert 'text' not in docs[0]


def test_unknown_publication_not_invented_from_quarter_or_retrieval(upstream):
    ir, _, _ = upstream
    docs = ir.parse_ir_index(INDEX.replace('2026/07/16 ', ''), '2330.TW', today=TODAY)
    assert docs[0]['published_at'] is None
    assert docs[0]['coverage_status'] == 'metadata_only'


def test_article_exact_text_not_index_summary_or_transcript(upstream):
    ir, _, _ = upstream
    doc = ir.parse_ir_index(INDEX, '2330.TW', today=TODAY)[0]
    result = ir.parse_ir_article(ARTICLE, doc, today=TODAY)
    assert result['text'] == ('TSMC announced second quarter financial results.\n'
                              'For the quarter ended June 30, revenue increased and net income improved.')
    assert result['coverage_status'] == 'text_available'
    assert result['published_at'] == '2026-07-16'
    assert result['content_sha256'] == hashlib.sha256(result['text'].encode()).hexdigest()
    assert not result['content_truncated']
    assert 'transcript' not in result
    assert 'boilerplate' not in result['text']


@pytest.mark.parametrize('html', [
    '<html><title>Just a moment...</title>Enable JavaScript and cookies to continue</html>',
    '<html><title>Login</title><form>Password</form></html>',
    '<html><title>WPG</title><main><h1>Financial News</h1></main></html>',
])
def test_denial_and_unknown_or_wrong_issuer_not_healthy_empty(upstream, html):
    ir, _, _ = upstream
    from search_provider_runtime import SourceResponseError
    with pytest.raises(SourceResponseError):
        ir.parse_ir_index(html, '2330.TW', today=TODAY)


def test_valid_empty_requires_recognized_index_and_explicit_empty_marker(upstream):
    ir, _, _ = upstream
    html = '<title>TSMC Latest News</title><main><h1>Latest News</h1><p>No results found.</p></main>'
    assert ir.parse_ir_index(html, '2330.TW', today=TODAY) == []


def test_article_future_publication_never_becomes_current_evidence(upstream):
    ir, _, _ = upstream
    from search_provider_runtime import SourceResponseError
    doc = ir.parse_ir_index(INDEX, '2330.TW', today=TODAY)[0]
    with pytest.raises(SourceResponseError):
        ir.parse_ir_article(ARTICLE.replace('2026-07-16T', '2099-07-16T'), doc, today=TODAY)


def test_wrong_article_identity_is_rejected(upstream):
    ir, _, _ = upstream
    from search_provider_runtime import SourceResponseError
    doc = ir.parse_ir_index(INDEX, '2330.TW', today=TODAY)[0]
    with pytest.raises(SourceResponseError):
        ir.parse_ir_article(ARTICLE.replace('TSMC Reports Second Quarter Results', 'Other Corp Results'), doc, today=TODAY)


def test_cache_preserves_acquisition_and_document_id(upstream):
    ir, calls, _ = upstream
    first = ir.fetch_company_ir_documents('2330.TW')
    second = ir.fetch_company_ir_documents('2330.TW')
    assert len(calls) == 2
    assert second['cache_hit'] is True
    assert second['fetched_at_epoch'] == first['fetched_at_epoch']
    assert second['documents'] == first['documents']
    assert second['documents'][0]['coverage_status'] == 'text_available'
    assert second['status'] == 'partial'


def test_unsupported_issuer_never_fetches_or_claims_provider_failure(upstream):
    ir, calls, _ = upstream
    result = ir.fetch_company_ir_documents('2317.TW')
    assert result['status'] == 'unsupported'
    assert result['coverage_status'] == 'unsupported_issuer'
    assert result['documents'] == [] and calls == []


@pytest.mark.parametrize('status', [403, 429])
def test_endpoint_cooldown_blocks_forced_refresh_and_honors_retry_after(upstream, monkeypatch, status):
    ir, calls, _ = upstream
    def denied(url, **kwargs):
        calls.append(url)
        return httpx.Response(status, headers={'Retry-After': '7200'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', denied)
    first = ir.fetch_company_ir_documents('2330.TW', force_refresh=True)
    second = ir.fetch_company_ir_documents('2330.TW', force_refresh=True)
    assert len(calls) == 1
    assert first['documents'] == second['documents'] == []
    assert first['error_kind'] == ('access_denied' if status == 403 else 'rate_limited')
    assert first['retry_at'] > first['observed_at_epoch'] + 7100
    assert second['http_request_sent'] is False


def test_article_denial_preserves_metadata_only_and_not_full_coverage(upstream, monkeypatch):
    ir, calls, _ = upstream
    original = ir.sync_get
    def get(url, **kwargs):
        if url.endswith('latest-news'):
            return original(url, **kwargs)
        calls.append(url)
        return httpx.Response(403, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', get)
    result = ir.fetch_company_ir_documents('2330.TW')
    assert result['documents'][0]['coverage_status'] == 'metadata_only'
    assert result['component_statuses']['article']['error_kind'] == 'access_denied'
    assert result['status'] == 'partial'


def test_redirect_is_not_followed_or_trusted(upstream, monkeypatch):
    ir, calls, _ = upstream
    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(302, headers={'Location': 'http://127.0.0.1/'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', get)
    result = ir.fetch_company_ir_documents('2330.TW')
    assert result['documents'] == [] and len(calls) == 1
    assert result['error_kind'] == 'redirect_rejected'


@pytest.mark.parametrize('url', [
    'https://pr.tsmc.com.evil.test/english/news/1', 'https://evil.test@pr.tsmc.com/english/news/1',
    'http://pr.tsmc.com/english/news/1', 'https://127.0.0.1/english/news/1',
    'https://pr.tsmc.com:8443/english/news/1', 'https://pr.tsmc.com/english/news/1?redirect=x',
])
def test_url_boundary_is_exact_issuer_https_without_redirect_parameters(upstream, url):
    ir, _, _ = upstream
    assert ir.allowed_ir_url(url, '2330.TW') == ''


def test_provider_keeps_partial_and_unsupported_distinct(upstream):
    from data_fetch.company_ir_provider import CompanyIrProvider
    from data_fetch.types import FetchRequest
    provider = CompanyIrProvider()
    acquired = provider.fetch(FetchRequest.from_ticker('2330.TW'))
    unsupported = provider.fetch(FetchRequest.from_ticker('2317.TW'))
    assert acquired.source == 'company_ir' and acquired.status == 'degraded_enrichment'
    assert acquired.audit['record_count'] == 1
    assert unsupported.status == 'not_applicable'
    assert unsupported.audit['error_kind'] == 'unsupported_issuer'


def test_automatic_workflow_stays_disabled_until_live_text_verification(upstream):
    from data_fetch.company_ir_provider import CompanyIrProvider
    from data_fetch.types import FetchRequest
    provider = CompanyIrProvider()
    contract = provider.capability(FetchRequest.from_ticker('2330.TW'))
    assert provider.execute_in_workflow is False
    assert contract['execute_in_workflow'] is False
    assert contract['live_verification'] == 'blocked_access_denied'
    assert contract['supported_tickers'] == ['2330.TW', '3702.TW']


def test_unknown_article_date_stays_unknown_even_with_dated_quarter_in_text(upstream):
    ir, _, _ = upstream
    docs = ir.parse_ir_index(INDEX.replace('2026/07/16 ', ''), '2330.TW', today=TODAY)
    article = ARTICLE.replace('<meta property="article:published_time" content="2026-07-16T09:00:00+08:00">', '')
    result = ir.parse_ir_article(article, docs[0], today=TODAY)
    assert result['published_at'] is None
    assert 'event_date' not in result


def test_text_is_bounded_and_truncation_explicit(upstream):
    ir, _, _ = upstream
    doc = ir.parse_ir_index(INDEX, '2330.TW', today=TODAY)[0]
    article = ARTICLE.replace('TSMC announced second quarter financial results.', 'TSMC reported. ' * 2000)
    result = ir.parse_ir_article(article, doc, today=TODAY)
    assert len(result['text']) == ir.MAX_TEXT_CHARS
    assert result['content_truncated'] is True
    assert result['content_sha256'] == hashlib.sha256(result['text'].encode()).hexdigest()


def test_unknown_article_shape_stays_metadata_not_arbitrary_page_text(upstream, monkeypatch):
    ir, _, _ = upstream
    original = ir.sync_get
    def get(url, **kwargs):
        if url.endswith('latest-news'):
            return original(url, **kwargs)
        return httpx.Response(200, text='<title>TSMC Results</title><p>Unrelated navigation content</p>',
                              headers={'content-type': 'text/html'}, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', get)
    result = ir.fetch_company_ir_documents('2330.TW')
    assert result['documents'][0]['coverage_status'] == 'metadata_only'
    assert result['component_statuses']['article']['error_kind'] == 'parse_error'
    assert 'text' not in result['documents'][0]


def test_indexing_failure_does_not_erase_acquired_text(upstream, monkeypatch):
    import source_document_index
    ir, _, _ = upstream
    def failed(*args, **kwargs):
        raise OSError('disk unavailable')
    monkeypatch.setattr(source_document_index, 'upsert_source_documents', failed)
    result = ir.fetch_company_ir_documents('2330.TW')
    assert result['index_status'] == 'unavailable'
    assert result['documents'][0]['coverage_status'] == 'text_available'


def test_cached_partial_does_not_claim_another_http_attempt(upstream, monkeypatch):
    ir, calls, _ = upstream
    original = ir.sync_get
    def get(url, **kwargs):
        if url.endswith('latest-news'):
            return original(url, **kwargs)
        calls.append(url)
        return httpx.Response(403, request=httpx.Request('GET', url))
    monkeypatch.setattr(ir, 'sync_get', get)
    first = ir.fetch_company_ir_documents('2330.TW')
    second = ir.fetch_company_ir_documents('2330.TW')
    assert len(calls) == 2
    assert first['component_statuses']['article']['http_request_sent'] is True
    assert second['component_statuses']['article']['http_request_sent'] is False
    assert second['component_statuses']['article']['error_kind'] == 'access_denied'
