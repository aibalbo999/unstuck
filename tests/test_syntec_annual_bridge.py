"""Public boundary checks. Original private-data replay cases remain local."""
from pathlib import Path
from copy import deepcopy
from contextlib import nullcontext
from hashlib import sha256
import gzip, json, time
import pytest
from official_response_evidence import archive_response
from data_fetch.market_sources.mops_public_annual import INDEX_URL, api_url, template_url
from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider, project_source_value
from data_fetch.types import FetchRequest
F = Path(__file__).parent / 'fixtures/source_acquisition/syntec_annual_bridge_full_20261012'
M = json.loads((F / 'manifest.json').read_text())
DATA = {'ticker': '7750.TW', 'company_name': '新代', 'instrument_type': 'EQUITY', 'currency': 'TWD', 'financial_currency': 'TWD', 'industry': '其他電子業', 'sector': 'Technology', 'company_identity': {'ticker': '7750.TW', 'stock_id': '7750', 'official_name': '新代', 'legal_name': '新代科技股份有限公司', 'official_ubn': '89660813', 'instrument_type': 'EQUITY', 'allowed_aliases': ['新代', 'Syntec'], 'forbidden_aliases': []}}

class Http:

    def __init__(self, *, seconds=45, **kwargs):
        self.deadline = time.monotonic() + seconds
        self.components = []
        self.calls = []
        self.raw = {}
        for key, p in M['parts'].items():
            b = gzip.open(F / p['filename'], 'rb').read()
            assert len(b) == p['bytes'] and sha256(b).hexdigest() == p['sha256']
            self.raw[key] = b

    def batch(self):
        return nullcontext(self)

    def request(self, url, *, request=None, json_body=None):
        if url == INDEX_URL:
            key = 'index'
        elif url == M['parts']['master']['url']:
            key = 'master'
        elif url == M['parts']['catalog']['url']:
            key = 'catalog'
        elif url == M['parts']['download_form']['url']:
            assert request == {'colorchg': '1', 'step': '9', 'kind': 'A', 'co_id': '7750', 'filename': '202204_7750_AI1.pdf', 'DEBUG': ''}
            key = 'download_form'
        elif url == M['parts']['book']['url']:
            key = 'book'
        elif url in {template_url(s) for s in ('BalanceSheet', 'IncomeStatement', 'CashflowStatement')}:
            key = 'template_' + next((s for s in ('BalanceSheet', 'IncomeStatement', 'CashflowStatement') if template_url(s) == url))
        elif json_body:
            assert json_body['companyId'] == '7750' and json_body['dataType'] == '2' and (json_body['season'] == '4') and (json_body['subsidiaryCompanyId'] == '')
            year = int(json_body['year']) + 1911
            key = str(year) + '_' + next((s for s in ('BalanceSheet', 'IncomeStatement', 'CashflowStatement') if api_url(s) == url))
        else:
            raise AssertionError(('unexpected fixture request', url, request, json_body))
        raw = self.raw[key]
        p = M['parts'][key]
        self.calls.append((url, deepcopy(request), deepcopy(json_body)))
        receipt = archive_response(raw, source_url=url, retrieved_at=p['retrieved_at'], http_status=200)
        self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200, 'status': 'complete', 'response_bytes': len(raw), 'response_sha256': sha256(raw).hexdigest(), 'fetched_at_epoch': p['retrieved_at']})
        return (raw, receipt)

def wiring(monkeypatch):
    from data_fetch.market_sources import mops_public_annual
    try:
        from data_fetch.market_sources import syntec_annual_bridge as bridge
    except ImportError:
        bridge = None
    h = Http()
    monkeypatch.setattr(mops_public_annual, 'PublicMopsHttp', lambda **k: h)
    if bridge is not None:
        monkeypatch.setattr(bridge, 'BridgeHttp', lambda **k: h)
    return h

def test_actual_missing2021_is_recovered_as_five_complete_periods_through_provider(monkeypatch):
    from provider_correlation import source_operation
    h = wiring(monkeypatch)
    with source_operation('financial_statements', 'TWSE MOPS Syntec audited annual bridge'):
        r = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('7750.TW'), {'data': DATA})
    assert r.status == 'success', r.audit
    assert r.value['years'] == ['2021', '2022', '2023', '2024', '2025'] and r.value['net_income_history'][0] == 0.941291
    assert r.value['fcf_history'][0] == -0.153714 and r.value['fcf_history'][3] == 1.206991
    assert r.audit['record_count'] == 5 and len(r.value['documents']) == 4
    assert project_source_value(r.value, '7750.TW') is not None
    assert not any((call[2] and call[2]['year'] == '111' for call in h.calls))

def test_new_source_repairs_first_year_without_quote_TTM_news_or_old_analysis_mutation(monkeypatch):
    import asyncio
    from report_source_refresh import fetch_report_source_data
    from data_fetch.service import StockDataService
    wiring(monkeypatch)
    old = deepcopy(DATA)
    old.update(current_price=700.0, revenue_ttm_raw=13960426000, years=['2021', '2022', '2023', '2024', '2025'], revenue_history=[None, 7.27, 7.87, 10.81, 13.96], net_income_history=[None, 0.54, 0.65, 1.37, 2.28], gross_profit_history=[None, 2.84, 3.24, 4.74, 6.39], operating_income_history=[None, 0.7, 0.79, 1.65, 2.82], fcf_history=[None, 0.82, 1.07, 1.22, 2.17], total_assets_history=[None, 6.75, 7.32, 9.43, 17.66], total_equity_history=[None, 2.79, 3.11, 4.9, 11.37], recent_catalysts=[{'title': '原新聞'}], social_sentiment={'sample_count': 0})
    audits = [{'source': 'market_data', 'provider': 'saved quote', 'status': 'success', 'record_count': 1, 'fetched_at_epoch': time.time() - 600}, {'source': 'financial_statements', 'provider': 'original saved SDK', 'status': 'degraded_enrichment', 'record_count': 4, 'fetched_at_epoch': time.time() - 700}]
    snapshot = {'ticker': '7750.TW', 'data': old, 'source_audit': audits}
    before = deepcopy(snapshot)
    merged = asyncio.run(fetch_report_source_data(snapshot, 'financial_statements', StockDataService()))
    assert merged['fcf_history'][0] == -0.153714 and merged['net_income_history'][0] == 0.941291 and (snapshot == before)
    for key in ('company_identity', 'current_price', 'revenue_ttm_raw', 'recent_catalysts', 'social_sentiment'):
        assert merged[key] == old[key]
    assert [r for r in merged['source_audit'] if r.get('source') != 'financial_statements'] == [audits[0]]
    assert any((r.get('reason') == 'superseded_by_annual_source_refresh' and r['audit'] == audits[1] for r in merged['source_record_archive']))

def test_saved_source_audit_contains_complete_identity_index_and_facts_replay_without_duplicate_PDF(monkeypatch):
    from provider_correlation import source_operation
    from data_fetch.annual_financial_source_provider import HISTORY_FIELDS
    wiring(monkeypatch)
    with source_operation('financial_statements', 'TWSE MOPS Syntec audited annual bridge'):
        result = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('7750.TW'), {'data': DATA})
    a = result.audit
    fields = ('source_url', 'source_basis', 'issuer_anchor', 'issuer_master_receipt', 'published_annual_index_receipt', 'source_origin_note', 'documents', 'comparative_revisions', 'raw_twd_by_year')
    assert all((k in a for k in fields))
    reconstructed = {**{k: result.value[k] for k in HISTORY_FIELDS}, **{k: deepcopy(a[k]) for k in fields}, 'ticker': '7750.TW', 'schema': a['statement_schema'], 'report_scope': a['report_scope'], 'currency': 'TWD'}
    assert project_source_value(reconstructed, '7750.TW') is not None
    assert 'annual_history_receipt' not in a

def test_normal_financial_path_uses_complete_bridge_and_keeps_native_transport_diagnostics(monkeypatch):
    from data_fetch.yfinance_extractors import extract_financial_histories
    from provider_correlation import correlation_scope
    h = wiring(monkeypatch)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    notes = []

    class NoSDK:

        def __getattr__(self, name):
            raise AssertionError('complete official source must not read annual SDK ' + name)
    with correlation_scope(replace=True, ticker='7750.TW', fetch_id='isolated-normal-syntec'):
        result = extract_financial_histories(NoSDK(), '7750.TW', notes, quote_type='EQUITY', industry_context='其他電子業')
    a = result['official_financial_audit']
    assert result['years'] == ['2021', '2022', '2023', '2024', '2025'] and result['fcf_history'][0] == -0.153714
    assert a['status'] == 'success' and a['http_request_count'] == len(h.calls) == 17
    assert len(a['component_statuses']) == 17 and sum((x['http_request_sent'] is True for x in a['component_statuses'].values())) == 17
    assert result['primary_financial_audit'] is None and result['finmind_financial_fallback_audit'] is None
    assert notes[0].startswith('2021、2022年度採證交所') and (not any(('原始 XBRL' in x for x in notes)))

@pytest.mark.parametrize('conflict', [{'company_identity': {**DATA['company_identity'], 'official_ubn': '00000000'}}, {'company_identity': {**DATA['company_identity'], 'legal_name': '別家公司'}}, {'company_identity': {**DATA['company_identity'], 'forbidden_aliases': ['Syntec']}}, {'quote_type': 'ETF'}, {'financial_currency': 'USD'}, {'currency': 'USD'}])
def test_explicit_identity_instrument_or_currency_conflict_refuses_before_http(monkeypatch, conflict):
    h = wiring(monkeypatch)
    with pytest.raises(ValueError):
        AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('7750.TW'), {'data': {**DATA, **conflict}})
    assert h.calls == []

@pytest.fixture(scope='module')
def packet():
    from data_fetch.market_sources.syntec_annual_bridge import fetch_bridge_histories
    return fetch_bridge_histories('7750.TW', transport=Http())

@pytest.mark.parametrize('mutation', [lambda v: v.update(currency='USD'), lambda v: v.update(ticker='7750.TWO'), lambda v: v.update(years=['2020', '2021', '2022', '2023', '2024']), lambda v: v['documents'].pop(), lambda v: v['documents'][0].update(format='public_annual_JSON'), lambda v: v['documents'][0]['first_period_basis'].update(no_separate2021_primary_filing_claimed=False), lambda v: v['documents'][0]['raw_receipt'].update(raw_response_sha256='0' * 64), lambda v: v['documents'][0]['raw_receipt'].update(retrieved_at=1000), lambda v: v['documents'][0]['parsed_book_basis']['facts']['2021'].update(Revenue=1), lambda v: v['documents'][1]['components'][0]['request'].update(companyId='2330'), lambda v: v['raw_twd_by_year']['2021'].update(free_cash_flow=0), lambda v: v['fcf_history'].__setitem__(0, 0), lambda v: v.update(comparative_revisions=[]), lambda v: v.update(source_origin_note='五份原始申報'), lambda v: v['issuer_master_receipt'].update(http_status_observed=False), lambda v: v['issuer_master_receipt'].update(cache_source='official-company-roster:v2:.TW'), lambda v: v['documents'][0]['raw_receipt'].update(http_status_observed=False)])
def test_full_original_receipt_projection_rejects_scope_time_hash_fact_formula_or_revision_tamper(packet, mutation):
    v = deepcopy(packet)
    mutation(v)
    assert project_source_value(v, '7750.TW') is None

def native_coordinates():
    v = json.loads((F / 'selected_native_coordinates.json').read_text())
    v['coverage_status'] = 'selected_native_text_complete'
    return v

@pytest.mark.parametrize('kind', ['currency', 'scope', 'parent_definition', 'preferred', 'missing_purchase', 'annual_column_order', 'EPS_mismatch'])
def test_selected_physical_financial_rows_refuse_ambiguous_or_incomplete_facts(kind):
    from data_fetch.market_sources.syntec_audited_book import parse_positioned_book, _rows
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    v = native_coordinates()
    p = {p['page_number']: p for p in v['pages']}
    if kind == 'currency':
        p[11]['text'] = p[11]['text'].replace('新台幣', '美元')
    elif kind == 'scope':
        p[7]['text'] = p[7]['text'].replace('合併資產負債表', '個別資產負債表')
    elif kind == 'parent_definition':
        p[62]['text'] = p[62]['text'].replace('母公司', '集團')
    elif kind == 'preferred':
        p[8]['text'] += '特別股'
    elif kind == 'missing_purchase':
        y = next((r['y'] for r in _rows(p[11]) if 'B02700' in r['text']))
        p[11]['segments'] = [s for s in p[11]['segments'] if abs(s['y'] - y) > 1.5]
    elif kind == 'annual_column_order':
        for s in p[7]['segments']:
            s['text'] = s['text'].replace('一一一年十二月三十一日', 'SWAP').replace('一一○年十二月三十一日', '一一一年十二月三十一日').replace('SWAP', '一一○年十二月三十一日')
    else:
        y = next((r['y'] for r in _rows(p[63]) if '本期淨利' in r['text']))
        for s in p[63]['segments']:
            if abs(s['y'] - y) <= 1.5:
                s['text'] = s['text'].replace('2', '3')
    with pytest.raises(FilingError):
        parse_positioned_book(v)

def test_exact_native_book_all_nine_facts_negative_FCF_and_opening_balance_not_substituted():
    from data_fetch.market_sources.syntec_audited_book import parse_positioned_book
    r = parse_positioned_book(native_coordinates())
    a = r['facts'][2021]
    assert len(a) == 9 and a['Assets'] == 7382223000 and (a['Assets'] != 5212213000)
    assert a['CashFlowsFromUsedInOperatingActivities'] == -59823000 and a['ProfitLossAttributableToOwnersOfParent'] == 941291000
    assert a['CashFlowsFromUsedInOperatingActivities'] + a['PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities'] + a['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities'] == -153714000
    assert r['whole_book_text_coverage_claimed'] is False

def test_native_profile_does_not_raise_generic_page_limit_or_claim_whole_book():
    from source_pdf_reader import extract_pdf_pages, SourcePdfError
    from syntec_annual_pdf_reader import extract_syntec_book
    raw = gzip.open(F / M['parts']['book']['filename'], 'rb').read()
    with pytest.raises(SourcePdfError, match='page_limit'):
        extract_pdf_pages(raw)
    r = extract_syntec_book(raw)
    assert r['page_count'] == 104 and len(r['pages']) == 10 and (r['coverage_status'] == 'selected_native_text_complete')

@pytest.mark.parametrize('bad', [0, True, float('nan'), 11, -1])
def test_private_profile_invalid_deadline_refuses_before_child(monkeypatch, bad):
    import syntec_annual_pdf_reader as r
    monkeypatch.setattr(r, '_run_worker', lambda *a, **k: pytest.fail('must not spawn'))
    with pytest.raises(r.SourcePdfError):
        r.extract_syntec_book(b'%PDF-', timeout_seconds=bad)

def test_private_fixed_native_profile_keeps_decompression_limit():
    from test_source_pdf_reader import make_pdf
    from syntec_annual_pdf_reader import extract_syntec_book, SourcePdfError
    raw = make_pdf([b''] * 104, compressed=True, stream_override=b' ' * (8 * 1024 * 1024 + 1))
    with pytest.raises(SourcePdfError, match='stream_limit'):
        extract_syntec_book(raw)

def test_private_fixed_native_profile_refuses_encrypted_book():
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    from test_source_pdf_reader import make_pdf
    from syntec_annual_pdf_reader import extract_syntec_book, SourcePdfError
    out = BytesIO()
    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(make_pdf([b'A'] * 104))))
    writer.encrypt('secret')
    writer.write(out)
    with pytest.raises(SourcePdfError, match='encrypted_pdf'):
        extract_syntec_book(out.getvalue())

@pytest.mark.parametrize('mutation', [lambda v: v.update(content_sha256='0' * 64), lambda v: v.update(page_count=True), lambda v: v.update(coverage_status='complete'), lambda v: v['pages'][0].update(rotation=90), lambda v: v['pages'][0]['segments'][0].update(x=float('nan')), lambda v: v['pages'][0]['segments'][0].update(end_x=1001), lambda v: v['pages'][0].update(page_number=True)])
def test_private_profile_rejects_invalid_child_results(monkeypatch, mutation):
    import syntec_annual_pdf_reader as r
    raw = gzip.open(F / M['parts']['book']['filename'], 'rb').read()
    v = native_coordinates()
    mutation(v)
    monkeypatch.setattr(r, '_run_worker', lambda *a, **k: json.dumps(v))
    with pytest.raises(r.SourcePdfError, match='invalid_worker_result'):
        r.extract_syntec_book(raw)

@pytest.mark.parametrize('status,kind', [(403, 'access_denied'), (429, 'rate_limited'), (504, 'server_error')])
def test_published_doc_transport_records_actual_failure_and_never_retries(monkeypatch, status, kind):
    from data_fetch.market_sources import syntec_annual_transport as t
    from search_provider_runtime import SourceResponseError
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    for key in t.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(t, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(t, 'cooldown_state', lambda *a: None)
    monkeypatch.setattr(t, 'observe_http_response', lambda *a: None)
    failures = []
    monkeypatch.setattr(t, 'remember_failure', lambda *a: failures.append(a))
    calls = []

    def run(args, deadline, **kwargs):
        calls.append(args)
        return ({'process_started': True, 'headers': ('HTTP/2 ' + str(status) + '\r\ncontent-type: text/html\r\n\r\n').encode(), 'metadata': b'{}', 'body': b'failure'}, 0, None)
    monkeypatch.setattr(t, 'collect_capped_process', run)
    h = t.BridgeHttp()
    with pytest.raises(SourceResponseError) as e:
        h.request(t.CATALOG)
    assert e.value.error_kind == kind and len(calls) == len(failures) == 1
    assert h.components[0]['http_status'] == status and h.components[0]['http_request_sent'] is True
    assert calls[0][calls[0].index('--retry') + 1] == '0' and '--location' not in calls[0] and ('--insecure' not in calls[0])

def test_local_host_cooldown_sends_no_request(monkeypatch):
    from data_fetch.market_sources import syntec_annual_transport as t
    from search_provider_runtime import SourceResponseError
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    for key in t.PROXY_ENV:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(t, 'proxy_url_for_request', lambda *a: None)
    monkeypatch.setattr(t, 'cooldown_state', lambda *a: {'active': True})
    monkeypatch.setattr(t, 'collect_capped_process', lambda *a, **k: pytest.fail('must not send HTTP'))
    h = t.BridgeHttp()
    with pytest.raises(SourceResponseError) as e:
        h.request(t.CATALOG)
    assert e.value.error_kind == 'cooldown'
    assert h.components[0]['http_request_sent'] is False

def test_roster_transport_does_not_relabel_unobserved_cache_as_native200():
    from data_fetch.market_sources import syntec_annual_transport as t
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    fixture = Http()
    raw, receipt = fixture.request(t.ROSTER_URL)

    class Master:
        components = []

        def get(self, url):
            self.components = [{'url': url, 'http_request_sent': False, 'cache_hit': True, 'http_status_observed': False, 'fetched_at_epoch': receipt['retrieved_at']}]
            return raw
    h = t.BridgeHttp()
    h.master = Master()
    with pytest.raises(FilingError):
        h.request(t.ROSTER_URL)

def test_honest_cached_full_roster_keeps_unknown_HTTP_and_original_epoch(packet):
    from data_fetch.market_sources.syntec_annual_transport import CACHED_MASTER_KIND
    v = deepcopy(packet)
    p = v['issuer_master_receipt']
    stamp = p['retrieved_at']
    p.update(evidence_kind=CACHED_MASTER_KIND, http_status=None, http_status_observed=False, cache_source='official-company-roster:v2:.TW', source_payload_sha256=p['raw_response_sha256'], source_payload_bytes=p['raw_response_bytes'])
    r = project_source_value(v, '7750.TW')
    assert r is not None and r['issuer_master_receipt']['retrieved_at'] == stamp and (r['issuer_master_receipt']['http_status'] is None)

def test_real_native_raw_cache_cold_warm_keeps_original_time_without_HTTP_or_hard_refresh(monkeypatch):
    import base64, cache_store
    from cache_backends import InMemoryCache
    from data_fetch.market_sources import syntec_annual_transport as t, issuer_news_transport as native, official_company_legal_name as names
    raw = Http().raw['master']
    calls = []
    cache_store.set_cache_backend(InMemoryCache())
    monkeypatch.setattr(names, 'read_cached_listed_roster_bytes', lambda: None)

    def download(self, url, diagnostic):
        calls.append(url)
        diagnostic.update(http_request_sent=True, http_status=200)
        return {'url': url, 'body_b64': base64.b64encode(raw).decode(), 'sha256': sha256(raw).hexdigest()}
    monkeypatch.setattr(native.IssuerNewsHttp, '_download', download)
    try:
        first = t.BridgeHttp()
        b, cold = first.request(t.ROSTER_URL)
        assert b == raw and len(calls) == 1 and (cold['http_status'] == 200)
        second = t.BridgeHttp()
        b, warm = second.request(t.ROSTER_URL)
        assert b == raw and len(calls) == 1
        assert warm['retrieved_at'] == cold['retrieved_at'] and warm['http_status'] is None and (warm['http_status_observed'] is False)
        assert warm['evidence_kind'] == t.CACHED_NATIVE_MASTER_KIND and second.components[0]['http_request_sent'] is False
    finally:
        cache_store.reset_cache_store_for_tests()

@pytest.mark.parametrize('bad', ['none', 'namespace', 'TTL', 'read_time'])
def test_native_raw_cached_master_receipt_requires_actual_namespace_and_original_fresh_at_use_proof(packet, bad):
    from data_fetch.market_sources.syntec_annual_transport import CACHED_NATIVE_MASTER_KIND, NATIVE_MASTER_CACHE
    v = deepcopy(packet)
    p = v['issuer_master_receipt']
    stamp = p['retrieved_at']
    p.update(evidence_kind=CACHED_NATIVE_MASTER_KIND, http_status=None, http_status_observed=False, cache_source=NATIVE_MASTER_CACHE, source_payload_sha256=p['raw_response_sha256'], source_payload_bytes=p['raw_response_bytes'], cache_verified_at_epoch=stamp + 1, cache_fresh_until_epoch=stamp + 1800)
    assert project_source_value(v, '7750.TW') is not None
    if bad == 'none':
        p['http_status'] = 200
    elif bad == 'namespace':
        p['cache_source'] = 'unknown-cache'
    elif bad == 'TTL':
        p['cache_fresh_until_epoch'] = stamp + 3600
    else:
        p['cache_verified_at_epoch'] = stamp + 1801
    assert project_source_value(v, '7750.TW') is None

def test_actual_published_temporary_path_one_second_clock_quantization_keeps_original_receipt():
    from data_fetch.market_sources.syntec_annual_transport import parse_download
    f = Path(__file__).parent / 'fixtures/source_acquisition/syntec_download_clock_20261012'
    m = json.loads((f / 'manifest.json').read_text())
    raw = gzip.open(f / 'download_form.raw.gz', 'rb').read()
    assert len(raw) == m['bytes'] and sha256(raw).hexdigest() == m['sha256']
    before = deepcopy(m)
    assert parse_download(raw, m) == m['published_temporary_pdf_url'] and m == before
    assert m['receipt_minus_server_path_stamp_seconds'] == pytest.approx(-0.940944, abs=1e-06)

@pytest.mark.parametrize('difference,accepted', [(-1.0, True), (-1.000001, False), (300.0, True), (300.000001, False)])
def test_temp_generation_clock_bound_does_not_change_financial_publication_or_freshness(difference, accepted):
    from data_fetch.market_sources.syntec_annual_transport import parse_download
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    f = Path(__file__).parent / 'fixtures/source_acquisition/syntec_download_clock_20261012'
    m = json.loads((f / 'manifest.json').read_text())
    raw = gzip.open(f / 'download_form.raw.gz', 'rb').read()
    stamp = m['retrieved_at'] - m['receipt_minus_server_path_stamp_seconds']
    receipt = {**m, 'retrieved_at': stamp + difference}
    if accepted:
        assert parse_download(raw, receipt) == m['published_temporary_pdf_url']
    else:
        with pytest.raises(FilingError, match='temporary PDF time unverified'):
            parse_download(raw, receipt)
