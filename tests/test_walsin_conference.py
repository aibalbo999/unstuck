"""Walsin saved originals: real parser/receipts with only HTTP stubbed."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import base64
import importlib
import time
import pytest

ROOT = Path(__file__).parents[1]
D = ROOT / 'docs/evidence/source-acquisition/20261014/free-entry-followup/additional-conferences'
MASTER = ROOT / 'docs/evidence/source-acquisition/20261013/delta-transcript-integration/master.body'
NOW = 1791993000.0


def valid_data():
    return {'ticker': '1605.TW', 'company_name': '華新 / Walsin Lihwa Corporation',
            'raw_company_name': 'Walsin Lihwa Corporation', 'instrument_type': 'EQUITY',
            'quote_type': 'EQUITY', 'company_identity': {
                'ticker': '1605.TW', 'stock_id': '1605', 'official_name': '華新',
                'legal_name': '華新麗華股份有限公司', 'official_ubn': '35412204',
                'instrument_type': 'EQUITY', 'allowed_aliases': ['華新', 'WALSIN', '1605.TW', '1605'],
                'english_names': ['Walsin Lihwa Corporation'], 'forbidden_aliases': []}}


@pytest.fixture
def harness(monkeypatch):
    import cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import walsin_conference_transport as t
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    bodies = {t.MASTER_URL: MASTER.read_bytes(),
              t.INDEX_URL: (D / 'walsin-conference/body.bin').read_bytes(),
              t.PDF_URL: (D / 'walsin-pdf/body.bin').read_bytes()}
    calls = []

    def download(self, url, diagnostic):
        raw = bodies[url]; calls.append(url); self.http_request_count += 1
        ctype = 'text/csv' if url == t.MASTER_URL else 'application/pdf' if url == t.PDF_URL else 'text/html'
        meta = {'http_status': 200, 'effective_url': url, 'num_redirects': 0,
                'size_download': len(raw), 'content_type': ctype, 'content_length': len(raw),
                'method': 'GET', 'proxy_used': 0, 'cache_control': 'no-cache'}
        if url == t.MASTER_URL:
            from data_fetch.market_sources import official_issuer_master
            meta = official_issuer_master.master_metadata(meta, raw, {})
        else:
            meta.update(pragma='', expires='', age=None, cf_cache_status='')
        diagnostic.update(http_request_sent=True, http_status=200, response_metadata=meta)
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                'request_method': 'GET', 'request_body': None, 'response_metadata': meta}

    monkeypatch.setattr(t.ConferenceHttp, 'download_original', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_official_body_is_available_without_promoting_conflicting_numbers(request):
    try:
        source = importlib.import_module('data_fetch.market_sources.walsin_conference')
    except ModuleNotFoundError as exc:
        if exc.name != 'data_fetch.market_sources.walsin_conference':
            raise
        value = {}
    else:
        bodies, calls = request.getfixturevalue('harness'); diagnostic = {}
        value = source.fetch_walsin_context('1605.TW', diagnostics=diagnostic)
        assert diagnostic['http_request_count'] == len(calls) == 3
        assert diagnostic['walsin_originals_verified'] is True
        assert source.validate_context(valid_data(), '1605.TW')
        assert source.verify_context(value, '1605.TW', max_age=1800)
    docs = value.get('documents', [])
    assert len(docs) == 1, 'Official Walsin PDF has no implemented company-source collector'
    doc = docs[0]
    assert doc['page_count'] == len(doc['pages']) == 11
    assert doc['native_text_coverage'] == 'complete' and doc['text_extraction_complete'] is True
    assert doc['coverage_status'] == value['coverage_status'] == 'partial'
    assert doc['excluded_native_text_pages'] == [4, 5, 6, 7, 11]
    assert doc['role_page_allowlist'] == [1, 2, 3, 8, 9, 10]
    assert doc['financial_statement_complete'] is False
    assert doc['full_visual_content_verified'] is False
    assert doc['q_and_a_transcript_available'] is False
    assert doc['published_at'] is None and doc['event_date'] == '2026-08-07'
    assert '27' in doc['pages'][3]['text']
    assert doc['content_period'] == value['period'] == ''


@pytest.mark.parametrize('change', ['date', 'pdf', 'new_history', 'duplicate', 'truncated', 'trailer'])
def test_changed_or_incomplete_index_does_not_fall_back_to_old_material(harness, change):
    from data_fetch.market_sources import walsin_conference as source
    from search_provider_runtime import SourceResponseError
    bodies, calls = harness
    raw = bodies[source.INDEX_URL]
    if change == 'date':
        raw = raw.replace(b'2026-08-07', b'2026-11-07')
    elif change == 'pdf':
        raw = raw.replace('【PBA】2026Q2-法說會報告檔_EN.pdf'.encode(), b'new.pdf')
    elif change == 'new_history':
        raw = raw.replace(b'2026/05/08', b'2026/10/13')
    elif change == 'duplicate':
        raw = raw.replace(b'id="pills-investor-conference-history"', b'id="pills-investor-conference"')
    elif change == 'truncated':
        raw = raw[:raw.index(b'</html>')]
    else:
        raw += b'<p>additional unqualified material</p>'
    bodies[source.INDEX_URL] = raw
    with pytest.raises(SourceResponseError):
        source.fetch_walsin_context('1605.TW')
    assert calls == [source.MASTER_URL, source.INDEX_URL]


@pytest.mark.parametrize('change', ['epoch', 'expiry', 'manifest', 'page', 'coverage', 'financial', 'boolean'])
def test_saved_originals_reject_retiming_or_semantic_changes(harness, change):
    from data_fetch.market_sources import walsin_conference as source
    v = source.fetch_walsin_context('1605.TW')
    receipt = v['walsin_conference_receipt']['pdf']
    if change == 'epoch':
        receipt['retrieved_at'] += 1
    elif change == 'expiry':
        receipt['fresh_until_epoch'] -= 1
    elif change == 'manifest':
        receipt['acquisition_manifest']['raw_response_sha256'] = '0'*64
    elif change == 'page':
        v['documents'][0]['pages'][3]['text'] = 'Corrected EBITDA 2.7'
    elif change == 'coverage':
        v['coverage_status'] = 'complete'
    elif change == 'financial':
        v['documents'][0]['financial_statement_complete'] = True
    else:
        v['documents'][0]['binary_complete'] = 1
    assert source.verify_context(v, '1605.TW', max_age=1800) is False


@pytest.mark.parametrize('change', ['name', 'ubn', 'alias', 'forbidden', 'quote', 'ticker'])
def test_caller_identity_contradictions_are_rejected(change):
    from data_fetch.market_sources.walsin_conference import validate_context
    v = valid_data()
    if change == 'name':
        v['raw_company_name'] = 'TECOM'
    elif change == 'ubn':
        v['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias':
        v['company_identity']['allowed_aliases'].append('Winbond')
    elif change == 'forbidden':
        v['company_identity']['forbidden_aliases'] = ['華新']
    elif change == 'quote':
        v['quote_type'] = 'ETF'
    else:
        v['ticker'] = '1605.TWO'
    assert not validate_context(v, '1605.TW')


@pytest.mark.parametrize('options', [{}, {'force_refresh': True}, {'use_cache': False}])
def test_fresh_body_is_native_even_with_preplanted_success_cache(harness, monkeypatch, options):
    import cache_store
    from data_fetch.market_sources import walsin_conference as source
    from data_fetch.market_sources.walsin_conference_transport import ConferenceHttp
    first = source.fetch_walsin_context('1605.TW')
    cache_store.set_cache_json(ConferenceHttp.raw_cache_prefix+source.PDF_URL,
        {'value': first, 'fresh_until_epoch': NOW+1800}, ttl_seconds=1800)
    monkeypatch.setattr(time, 'time', lambda: NOW+10)
    d = {}; second = source.fetch_walsin_context('1605.TW', diagnostics=d, **options)
    assert len(harness[1]) == 6 and d['http_request_count'] == 3
    assert second['fetched_at_epoch'] == NOW+10 and first['fetched_at_epoch'] == NOW
    assert d['cache_hit'] is False


@pytest.mark.parametrize('stage', ['reader', 'handoff', 'diagnostic'])
def test_whole_deadline_includes_extraction_copies_and_final_delivery(harness, monkeypatch, stage):
    from types import SimpleNamespace
    from data_fetch.market_sources import walsin_conference as source
    from search_provider_runtime import SourceResponseError
    clock = [100.]
    monkeypatch.setattr(source, 'time', SimpleNamespace(monotonic=lambda: clock[0], time=lambda: NOW))
    if stage == 'reader':
        original = source.extract_walsin_presentation_pages
        def slow(*a, **kw):
            result = original(*a, **kw); clock[0] = 126.; return result
        monkeypatch.setattr(source, 'extract_walsin_presentation_pages', slow)
    elif stage == 'handoff':
        original = source.deepcopy
        def slow(v):
            result = original(v)
            if isinstance(v, dict) and 'documents' in v:
                clock[0] = 126.
            return result
        monkeypatch.setattr(source, 'deepcopy', slow)
    class Diagnostics(dict):
        def update(self, *a, **kw):
            super().update(*a, **kw)
            if stage == 'diagnostic' and self.get('walsin_originals_verified'):
                clock[0] = 126.
    d = Diagnostics()
    with pytest.raises(SourceResponseError) as caught:
        source.fetch_walsin_context('1605.TW', diagnostics=d)
    assert caught.value.error_kind == 'timeout'
    assert d['walsin_originals_verified'] is False and 'fetched_at_epoch' not in d


def test_historical_original_does_not_change_current_delivery_expiry(harness, monkeypatch):
    from data_fetch.market_sources import walsin_conference as source
    v = source.fetch_walsin_context('1605.TW'); original = deepcopy(v)
    monkeypatch.setattr(time, 'time', lambda: NOW+1801)
    assert not source.verify_context(v, '1605.TW', max_age=1800)
    assert source.verify_context(v, '1605.TW', max_age=86400)
    assert v == original and len(harness[1]) == 3
