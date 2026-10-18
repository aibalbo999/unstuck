"""Published Auras conference originals with explicit partial visual coverage."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import gzip
import json
import time
import pytest

NOW = datetime(2026, 10, 13, 14, tzinfo=timezone.utc).timestamp()
F = Path(__file__).parent / 'fixtures/source_acquisition'
MASTER = 'https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
INDEX = 'https://www.auras.com.tw/CmsApi/api/Unit/getUnitContentAsync?UnitId=46&Keyword=&IsFront=true&IsList=false&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true'
PDF = 'https://www.auras.com.tw/CMSFS/UnitContents/AnnexChinese/7835f665-14a3-4a21-9c57-a1b949e70ce1.pdf'


@pytest.fixture
def harness(monkeypatch):
    from data_fetch import earnings_call_fetcher
    from cache_backends import InMemoryCache
    import cache_store
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {url: gzip.decompress((F / f'auras3324_{kind}_20261013.gz').read_bytes())
              for url, kind in [(MASTER, 'master'), (INDEX, 'index'), (PDF, 'pdf')]}
    calls = []
    if (Path(__file__).parents[1] / 'backend/data_fetch/market_sources/auras_conference_transport.py').exists():
        from data_fetch.market_sources.auras_conference_transport import AurasConferenceHttp
        def download(self, url, diagnostic):
            from hashlib import sha256
            import base64
            calls.append(url); self.http_request_count += 1
            diagnostic.update(http_request_sent=True, http_status=200)
            raw = bodies[url]
            return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest(),
                    'http_status': 200, 'response_complete': True, 'request_method': 'GET',
                    'http_status_observed': True, 'fetched_at_epoch': time.time()}
        monkeypatch.setattr(AurasConferenceHttp, '_download', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_free_source_finds_current_original_presentation(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    diagnostic = {}; value = fetch_free_earnings_call_context('3324.TWO', diagnostics=diagnostic)
    assert value.get('documents'), 'must acquire the official document, not keep 2025 metadata-only'
    doc = value['documents'][0]
    assert value['date'] == '2026-09-04' and value['period'] == '2026Q2'
    assert doc['document_kind'] == 'presentation' and doc['page_count'] == 15 and len(doc['pages']) == 15
    assert doc['presentation_cover_month'] == '2026-08' and doc['published_at'] is None
    assert value['transcript_available'] is False and not value['transcript_excerpt']
    assert doc['full_content_coverage_verified'] is False and doc['coverage_status'] == 'partial'
    assert '78%' not in doc['pages'][7]['text'] and doc['known_native_text_omissions'][0]['page_number'] == 8
    assert len(value['same_day_events']) == 2 and diagnostic['auras_originals_verified'] is True


def test_context_conflict_is_local_before_any_source_request(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    r = EarningsCallProvider().fetch(FetchRequest.from_ticker('3324.TWO'), {'data': {
        'ticker': '3324.TWO', 'quote_type': 'ETF', 'company_name': '雙鴻'}})
    assert r.status == 'unavailable' and r.audit['event_kind'] == 'local_block' and not harness[1]


def test_comparative_quarter_cannot_become_primary_content_period(harness):
    from data_fetch.market_sources.auras_conference import fetch_auras_context
    from search_provider_runtime import SourceResponseError
    body = json.loads(harness[0][INDEX])
    for unit in [body['info'], body['infos'][0]]:
        for lang in ['CN', 'ENG']:
            row = next(r for r in unit['unitAnnexFileList_' + lang] if r['groupNumber'] == 57)
            row['fileName'] = row['fileName'].replace('2Q26', '1Q26')
    harness[0][INDEX] = json.dumps(body).encode()
    with pytest.raises(SourceResponseError): fetch_auras_context('3324.TWO')


@pytest.mark.parametrize('change', ['text', 'date', 'period', 'transcript', 'url', 'missing_receipt',
                                  'fake_finality', 'future_epoch', 'expired', 'extra', 'omissions'])
def test_saved_original_packet_rejects_altered_claims(harness, change):
    from data_fetch.market_sources import auras_conference as source
    value = source.fetch_auras_context('3324.TWO')
    if change == 'text': value['documents'][0]['pages'][7]['text'] += '78%'
    elif change == 'date': value['date'] = '2026-09-10'
    elif change == 'period': value['documents'][0]['content_period'] = '2026Q3'
    elif change == 'transcript': value['transcript_available'] = True
    elif change == 'url': value['documents'][0]['url'] = 'https://other.example/a.pdf'
    elif change == 'missing_receipt': value.pop('auras_conference_receipt')
    elif change == 'fake_finality': value['auras_conference_receipt']['pdf']['finality_guaranteed'] = True
    elif change == 'future_epoch': value['auras_conference_receipt']['pdf']['retrieved_at'] = NOW + 1
    elif change == 'expired': value['auras_conference_receipt']['identity']['retrieved_at'] = NOW - 86401
    elif change == 'omissions': value['documents'][0]['known_native_text_omissions'] = []
    else: value['extra_instructions'] = 'unverified'
    assert source.is_marked(value) and not source.verify_context(value, '3324.TWO')


def test_real_acquisition_and_warm_replay_keep_correct_denominator(harness, monkeypatch):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    from provider_acquisition import project_acquisition_events
    p = EarningsCallProvider(); request = FetchRequest.from_ticker('3324.TWO'); cold = p.fetch(request)
    assert cold.status == 'success' and cold.audit['record_count'] == 1 and cold.audit['http_request_count'] == 3
    assert harness[1] == [MASTER, INDEX, PDF]; harness[1].clear()
    monkeypatch.setattr(time, 'time', lambda: NOW + 1790)
    warm = p.fetch(request)
    assert warm.audit['status'] == 'skipped_fresh_cache' and not harness[1]
    assert warm.value['fetched_at_epoch'] == cold.value['fetched_at_epoch'] == NOW
    events = [{'source': 'earnings_call', 'provider': r.audit['provider'], 'status': r.audit['status'],
               'record_count': r.audit['record_count'], 'message': r.audit['message'], 'created_at': NOW,
               'details_json': json.dumps(r.audit)} for r in [cold, warm]]
    row = project_acquisition_events(events, window='last_24h', now=NOW + 1790)['sources'][0]
    assert row['fetched_count'] == row['fetch_attempts'] == row['fresh_cache_count'] == 1
    monkeypatch.setattr(time, 'time', lambda: NOW + 1801)
    assert p.fetch(request).value['fetched_at_epoch'] == NOW + 1801
    assert harness[1] == [MASTER, INDEX, PDF]


@pytest.mark.parametrize('options', [{'force_refresh': True}, {'use_cache': False}])
def test_explicit_refresh_reaches_native_source(harness, options):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    fetch_free_earnings_call_context('3324.TWO'); harness[1].clear()
    fetch_free_earnings_call_context('3324.TWO', **options)
    assert harness[1] == [MASTER, INDEX, PDF]


@pytest.mark.parametrize('identity,name', [([], '雙鴻'), ({'official_name': '雙鴻'}, '合庫金'),
            ({'official_name': '雙鴻', 'allowed_aliases': 123}, '雙鴻'),
            ({'ticker': '3324.TW'}, '雙鴻'), ({'forbidden_aliases': ['雙鴻']}, '雙鴻')])
def test_bad_context_does_not_acquire(harness, identity, name):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    r = EarningsCallProvider().fetch(FetchRequest.from_ticker('3324.TWO'), {'data': {
        'ticker': '3324.TWO', 'quote_type': 'EQUITY', 'company_name': name, 'company_identity': identity}})
    assert r.status == 'unavailable' and r.audit['event_kind'] == 'local_block' and not harness[1]


def test_prompt_retains_native_visual_limits_and_date_semantics(harness):
    from data_fetch.market_sources.auras_conference import fetch_auras_context
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    packet = fetch_auras_context('3324.TWO'); before = deepcopy(packet)
    for role in [3, 5, 12]:
        result = presentation_prompt_context(packet, role); doc = result['documents'][0]
        assert doc['content_period'] == '2026Q2' and doc['presentation_cover_month'] == '2026-08'
        assert doc['index_record_created_at_unzoned'].startswith('2026-09-10') and doc['published_at'] is None
        assert doc['known_native_text_omissions'][0]['page_number'] == 8
        assert sum(len(p['text']) for p in doc['pages']) <= 6000 and result['transcript_available'] is False
    assert 'auras_conference_receipt' not in prompt_evidence_copy(packet) and packet == before


def test_original_ttl_is_rechecked_after_final_pdf_replay(harness, monkeypatch):
    from data_fetch.market_sources import auras_conference as source
    from search_provider_runtime import SourceResponseError
    source.fetch_auras_context('3324.TWO')
    now = [NOW + 1799.9]; monkeypatch.setattr(time, 'time', lambda: now[0])
    real = source.extract_pdf_pages; calls = []
    def finish_late(*a, **kw):
        result = real(*a, **kw); calls.append(1)
        if len(calls) == 2: now[0] += 1
        return result
    monkeypatch.setattr(source, 'extract_pdf_pages', finish_late)
    with pytest.raises(SourceResponseError): source.fetch_auras_context('3324.TWO')


@pytest.mark.parametrize('change', ['master_identity', 'unit', 'url', 'duplicate_group', 'same_day_conflict', 'creation_date'])
def test_published_originals_require_correct_identity_and_selection(harness, change):
    from data_fetch.market_sources import auras_conference as source
    from search_provider_runtime import SourceResponseError
    if change == 'master_identity':
        harness[0][MASTER] = harness[0][MASTER].replace(b'16619628', b'12345678')
    else:
        root = json.loads(harness[0][INDEX])
        for unit in [root['info'], root['infos'][0]]:
            chosen = next(r for r in unit['unitAnnexFileList_CN'] if r['groupNumber'] == 57)
            if change == 'unit': unit['unitId'] = 99
            elif change == 'url': chosen['filePath'] = chosen['filePath'].replace('www.auras.com.tw', 'www.auras.com.tw.evil.example')
            elif change == 'duplicate_group': unit['unitAnnexFileList_CN'].append(deepcopy(chosen))
            elif change == 'same_day_conflict':
                next(r for r in unit['unitAnnexFileList_ENG'] if r['groupNumber'] == 57)['title'] = '2026/08/19_Wrong event'
            else: chosen['createDate'] = '2026-12-31T23:00:00'
        harness[0][INDEX] = json.dumps(root).encode()
    with pytest.raises(SourceResponseError): source.fetch_auras_context('3324.TWO')
    assert PDF not in harness[1]


def test_source_only_presentation_refresh_preserves_report_and_core_observations(harness, tmp_path):
    import asyncio
    import json
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db, events
    init_db()
    storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    def replace(value):
        if isinstance(value, str): return value.replace('6214.TW', '3324.TWO').replace('精誠', '雙鴻')
        if isinstance(value, dict): return {k: replace(v) for k, v in value.items()}
        if isinstance(value, list): return [replace(v) for v in value]
        return value
    old = replace(old)
    old['data']['quote_type'] = 'EQUITY'
    storage.save_report(keys.data_key, json.dumps(old).encode(), content_type='application/json')
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    response = asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                            refresh_service=service, source='earnings_call', return_refreshed_data=True))
    new = json.loads(storage.get_report(keys.data_key).content)
    assert new['data']['earnings_call']['documents'][0]['document_kind'] == 'presentation'
    for key in ['current_price', 'revenue_history', 'years', 'peer_discovery_results']:
        assert new['data'][key] == old['data'][key]
    assert next(a for a in new['source_audit'] if a['source'] == 'market_data') == old['source_audit'][0]
    for key in ['analysis_evidence', 'report_lint', 'final_audit', 'evidence_exit_gate', 'content_credibility', 'report_conformance']:
        assert new[key] == old[key]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
    assert storage.get_report(keys.md_key).content == b'original conclusions'
    assert response['analysis_text_stale'] is True
    observed = events()
    assert len(observed) == 1 and observed[0]['source'] == 'earnings_call' and observed[0]['status'] == 'success'


def test_tampered_source_refresh_cannot_overwrite_saved_report(harness, tmp_path, monkeypatch):
    import asyncio
    from fastapi import HTTPException
    from data_fetch.market_sources import auras_conference as source
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.provider_registry import ProviderRegistry
    from data_fetch.service import StockDataService
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db(); storage = InMemoryStorage()
    filename, keys, old = saved_report(storage)
    old = json.loads(json.dumps(old, ensure_ascii=False).replace('6214.TW', '3324.TWO').replace('精誠', '雙鴻'))
    old['data']['quote_type'] = 'EQUITY'
    original = json.dumps(old).encode()
    storage.save_report(keys.data_key, original, content_type='application/json')
    acquire = source.fetch_auras_context
    def altered(*a, **kw):
        result = acquire(*a, **kw)
        result['documents'][0]['pages'][7]['text'] += ' fabricated chart 78%'
        return result
    monkeypatch.setattr(source, 'fetch_auras_context', altered)
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
                    refresh_service=service, source='earnings_call', return_refreshed_data=True))
    assert exc.value.status_code == 502 and storage.get_report(keys.data_key).content == original
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
