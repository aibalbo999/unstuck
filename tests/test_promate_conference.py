"""Future normal acquisition must find issuer bodies, with original evidence."""
from copy import deepcopy
from pathlib import Path
import gzip
import json
import time
import pytest

NOW = 1792109100.
MASTER = 'https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
INDEX = 'https://www.promate.com.tw/investors-relations/investor-conference/'
PDF = 'https://www.promate.com.tw/wp-content/uploads/PMT_%E6%B3%95%E8%AA%AA%E6%9C%83_%E4%B8%AD%E6%96%87_202514%E4%B8%8A%E5%82%B3.pdf'
F = Path(__file__).parent / 'fixtures/source_acquisition'


@pytest.fixture
def harness(monkeypatch):
    from cache_backends import InMemoryCache
    import cache_store
    from data_fetch import earnings_call_fetcher
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(time, 'time', lambda: NOW)
    monkeypatch.setattr(earnings_call_fetcher, '_fetch_official_index_context', lambda *a, **k: {})
    bodies = {MASTER: gzip.decompress((F/'tcfhc5880_master_20261013.gz').read_bytes()),
              INDEX: gzip.decompress((F/'promate6189_index_20261016.gz').read_bytes()),
              PDF: gzip.decompress((F/'promate6189_pdf_20261016.gz').read_bytes())}
    calls = []
    if (Path(__file__).parents[1]/'backend/data_fetch/market_sources/promate_conference_transport.py').exists():
        from data_fetch.market_sources.promate_conference_transport import PromateConferenceHttp
        from data_fetch.market_sources import issuer_news_transport as native, gce_conference_transport as master_native
        monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK', raising=False)
        for k in native.PROXY_ENV: monkeypatch.delenv(k, raising=False)
        def process(args, deadline, **options):
            assert args[-1] == MASTER
            raw = bodies[MASTER]; calls.append(MASTER)
            return {'body': raw, 'headers': b'HTTP/2 200\r\nContent-Type: text/csv\r\n\r\n',
                    'metadata': json.dumps({'http_code':200,'url_effective':MASTER,'num_redirects':0,
                        'size_download':len(raw),'content_type':'text/csv','method':'GET','proxy_used':0}).encode(),
                    'process_started':True}, 0, None
        for module in (native, master_native):
            monkeypatch.setattr(module, 'collect_capped_process', process)
            monkeypatch.setattr(module, 'proxy_url_for_request', lambda *a: None)
            monkeypatch.setattr(module, 'observe_http_response', lambda *a: None)
        def download(self, url, diagnostic):
            import base64
            from hashlib import sha256
            calls.append(url); self.http_request_count += 1
            raw = bodies[url]
            diagnostic.update(http_request_sent=True, http_status=200)
            return {'url':url,'body_b64':base64.b64encode(raw).decode(),'sha256':sha256(raw).hexdigest(),
                    'http_status':200,'response_complete':True,'request_method':'GET',
                    'http_status_observed':True,'fetched_at_epoch':time.time()}
        monkeypatch.setattr(PromateConferenceHttp, '_download', download)
    yield bodies, calls
    cache_store.reset_cache_store_for_tests()


def test_public_source_acquires_body_not_date_only_old_link(harness):
    from data_fetch.earnings_call_fetcher import fetch_free_earnings_call_context
    details = {}; value = fetch_free_earnings_call_context('6189.TW', diagnostics=details)
    assert value.get('documents'), 'Normal acquisition must replace metadata with the published body'
    doc = value['documents'][0]
    assert doc['url'] == PDF and doc['page_count'] == 11 and len(doc['pages']) == 11
    assert value['date'] == '2025-11-17' and value['transcript_available'] is False
    assert doc['coverage_status'] == 'partial' and not doc['full_content_coverage_verified']
    assert details['promate_originals_verified'] is True


def test_conflicting_company_blocks_before_network(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('6189.TW'), {'data':{
        'ticker':'6189.TW','company_name':'雙鴻','quote_type':'EQUITY'}})
    assert result.status == 'unavailable' and result.audit['event_kind'] == 'local_block'
    assert not harness[1]


def test_observed_cache_english_punctuation_is_same_issuer(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    result = EarningsCallProvider().fetch(FetchRequest.from_ticker('6189.TW'), {'data':{
        'ticker':'6189.TW', 'quote_type':'EQUITY', 'company_name':'豐藝 / Promate Electronic Co.,Ltd.',
        'company_identity':{'stock_id':'6189', 'official_name':'豐藝', 'official_ubn':'22151585'}}})
    assert result.status == 'success' and result.value['documents'][0]['page_count'] == 11


@pytest.mark.parametrize('change', ['text','date','url','transcript','conflict','receipt','age','identity'])
def test_original_replay_rejects_tampering(harness, change):
    from data_fetch.market_sources import promate_conference as source
    v = source.fetch_promate_context('6189.TW')
    if change == 'text': v['documents'][0]['pages'][0]['text'] += 'fabricated'
    elif change == 'date': v['date'] = '2026-10-16'
    elif change == 'url': v['documents'][0]['url'] += '?new=1'
    elif change == 'transcript': v['transcript_available'] = True
    elif change == 'conflict': v['documents'][0]['period_conflict_pages'] = []
    elif change == 'receipt': v.pop('promate_conference_receipt')
    elif change == 'age': v['promate_conference_receipt']['pdf']['retrieved_at'] = NOW - 86401
    else: v['ticker'] = '6577.TWO'
    assert source.is_marked(v) and not source.verify_context(v, '6189.TW')


def test_dynamic_index_discovers_new_version_without_filename_date_inference(harness):
    from data_fetch.market_sources.promate_conference import select_presentation
    from bs4 import BeautifulSoup
    s = BeautifulSoup(harness[0][INDEX], 'html.parser')
    a = s.new_tag('a', href='https://www.promate.com.tw/wp-content/uploads/2026/10/new-release.pdf')
    a.string = '2026/10/01 線上法人說明會 書面簡報資料'; s.body.append(a)
    selected = select_presentation(str(s).encode(), NOW)
    assert selected['event_date'] == '2026-10-01' and selected['pdf_url'].endswith('/new-release.pdf')
    b = s.new_tag('a', href='https://www.promate.com.tw/wp-content/uploads/second.pdf')
    b.string = a.string; s.body.append(b)
    with pytest.raises(ValueError, match='ambiguous latest'):
        select_presentation(str(s).encode(), NOW)


@pytest.mark.parametrize('change', ['other_master','html_pdf','incomplete_index','cover_year'])
def test_invalid_originals_fail_closed(harness, change):
    from data_fetch.market_sources import promate_conference as source
    from search_provider_runtime import SourceResponseError
    if change == 'other_master': harness[0][MASTER] = harness[0][MASTER].replace('豐藝電子股份有限公司'.encode(), '別家電子股份有限公司'.encode())
    elif change == 'html_pdf': harness[0][PDF] = b'<html>error page</html>'
    elif change == 'incomplete_index': harness[0][INDEX] = harness[0][INDEX].replace(b'</html>', b'')
    else: harness[0][INDEX] = harness[0][INDEX].replace(b'2025/11/17', b'2026/10/01')
    details = {}
    with pytest.raises(SourceResponseError): source.fetch_promate_context('6189.TW', diagnostics=details)
    assert not details.get('promate_originals_verified')


def test_warm_replay_is_not_new_acquisition(harness):
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.types import FetchRequest
    p = EarningsCallProvider(); request = FetchRequest.from_ticker('6189.TW')
    cold = p.fetch(request); calls = len(harness[1]); warm = p.fetch(request)
    assert cold.status == 'success' and cold.audit['record_count'] == 1
    assert warm.audit['status'] == 'skipped_fresh_cache' and len(harness[1]) == calls == 3
    assert warm.value['fetched_at_epoch'] == cold.value['fetched_at_epoch'] == NOW


def test_role_projection_keeps_disclaimer_and_excludes_ambiguous_numeric_pages(harness):
    from data_fetch.market_sources.promate_conference import fetch_promate_context
    from conference_presentation_prompt import presentation_prompt_context
    from prompt_evidence import prompt_evidence_copy
    value = fetch_promate_context('6189.TW'); before = deepcopy(value)
    assert value['documents'][0]['period_conflict_pages'] == [9]
    for role in (3,5,12):
        result = presentation_prompt_context(value, role); d = result['documents'][0]
        assert [p['page_number'] for p in d['pages']] == [1,2,4,10]
        assert all(not p['content_truncated'] for p in d['pages'])
        assert d['period_conflict_pages'] == [9] and d['full_content_coverage_verified'] is False
        assert '子公司' in d['financial_scope_caution'] and not result['transcript_available']
    assert value == before and 'promate_conference_receipt' not in prompt_evidence_copy(value)


@pytest.mark.parametrize('tampered', [False, True])
def test_report_refresh_preserves_conclusions_and_rejects_fabricated_content(harness, tmp_path, monkeypatch, tampered):
    import asyncio
    from fastapi import HTTPException
    from data_fetch import StockDataService, ProviderRegistry
    from data_fetch.enrichment_providers import EarningsCallProvider
    from data_fetch.market_sources import promate_conference as source
    from report_refresh_service import refresh_report_data_snapshot
    from storage.report_storage import InMemoryStorage
    from test_report_source_refresh import saved_report
    from test_report_refresh_acquisition_audit import init_db
    init_db(); storage = InMemoryStorage(); filename, keys, old = saved_report(storage)
    old = json.loads(json.dumps(old, ensure_ascii=False).replace('6214.TW','6189.TW').replace('精誠','豐藝'))
    old['data']['quote_type'] = 'EQUITY'; original = json.dumps(old).encode()
    storage.save_report(keys.data_key, original, content_type='application/json')
    if tampered:
        acquire = source.fetch_promate_context
        def altered(*a, **kw):
            v = acquire(*a, **kw); v['documents'][0]['pages'][7]['text'] += ' fabricated revenue'; return v
        monkeypatch.setattr(source, 'fetch_promate_context', altered)
    service = StockDataService(registry=ProviderRegistry([EarningsCallProvider()]))
    def refresh():
        return asyncio.run(refresh_report_data_snapshot(filename, output_dir=str(tmp_path), storage=storage,
            refresh_service=service, source='earnings_call', return_refreshed_data=True))
    if tampered:
        with pytest.raises(HTTPException) as exc: refresh()
        assert exc.value.status_code == 502 and storage.get_report(keys.data_key).content == original
    else:
        assert refresh()['analysis_text_stale'] is True
        new = json.loads(storage.get_report(keys.data_key).content)
        assert new['data']['earnings_call']['documents'][0]['page_count'] == 11
        for k in ('analysis_evidence','report_lint','final_audit','evidence_exit_gate','content_credibility','report_conformance'):
            assert new[k] == old[k]
    assert storage.get_report(keys.html_key).content == b'<html>original conclusions</html>'
