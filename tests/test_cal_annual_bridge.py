"""Public boundary checks. Original private-data replay cases remain local."""
from contextlib import nullcontext
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import gzip, json, time
import pytest
F = Path(__file__).parent / 'fixtures/source_acquisition/cal_annual_20261013'
M = json.loads((F / 'manifest.json').read_text())

def raw(key):
    p = M['parts'][key]
    b = gzip.open(F / p['filename'], 'rb').read()
    assert len(b) == p['bytes'] and sha256(b).hexdigest() == p['sha256']
    return b

def test_complete_native_ir_index_publishes_three_consolidated_pdf_urls():
    from data_fetch.market_sources.cal_annual_transport import parse_index
    assert parse_index(raw('ir-index')) == {str(y): M['parts']['book' + str(y)]['url'] for y in (2022, 2024, 2025)}

@pytest.mark.parametrize('year', [2022, 2024, 2025])
def test_full_native_books_supply_both_annual_cash_columns(year):
    from data_fetch.market_sources.cal_audited_cash import parse_book
    parsed = parse_book(raw('book' + str(year)), year)
    assert parsed['complete_original_sha256'] == M['parts']['book' + str(year)]['sha256']
    for y, facts in parsed['facts'].items():
        assert facts == {k: M['facts'][str(y)][k] for k in facts}
        assert len(facts) == 3
    assert set(parsed['facts']) == {year - 1, year}
    assert parsed['whole_book_text_coverage_claimed'] is False

def test_other_issuer_or_individual_statement_index_cannot_supply_missing_cash_fact():
    from data_fetch.market_sources.cal_annual_transport import parse_index
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    with pytest.raises(FilingError):
        parse_index(raw('ir-index').replace(b'Consolidated-Financial-Statements/EN/2025Q4', b'Financial-Statement/EN/2025Q4'))

def test_prior_formal_failure_now_returns_five_complete_replayable_years():
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_histories, project_bridge_history
    h = Http()
    value = fetch_bridge_histories('2610.TW', transport=h)
    assert value['years'] == ['2021', '2022', '2023', '2024', '2025']
    assert len(h.calls) == 24 and len(set(h.calls)) == 24
    for year, facts in M['facts'].items():
        assert value['raw_twd_by_year'][year]['intangible_purchase'] == facts['PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities']
    assert project_bridge_history(value, '2610.TW') == value

class Http:

    def __init__(self, **kwargs):
        self.deadline = time.monotonic() + 45
        self.components = []
        self.calls = []

    def batch(self):
        return nullcontext(self)

    def request(self, url, *, request=None, json_body=None):
        from data_fetch.market_sources.mops_public_annual import INDEX_URL, STATEMENTS, template_url, api_url
        from official_response_evidence import archive_response
        for k in ('master', 'ir-index', 'book2022', 'book2024', 'book2025'):
            if url == M['parts'][k]['url']:
                key = k
                break
        else:
            if url == INDEX_URL:
                key = 'mops0'
            elif url in [template_url(s) for s in STATEMENTS]:
                key = 'mops' + str(1 + [template_url(s) for s in STATEMENTS].index(url))
            else:
                assert url in [api_url(s) for s in STATEMENTS]
                year = int(json_body['year']) + 1911
                key = 'mops' + str(4 + (year - 2021) * 3 + [api_url(s) for s in STATEMENTS].index(url))
        b = raw(key)
        self.calls.append(key)
        p = archive_response(b, source_url=url, retrieved_at=time.time(), http_status=200)
        self.components.append({'url': url, 'http_request_sent': True, 'http_status': 200, 'status': 'complete', 'response_sha256': sha256(b).hexdigest(), 'response_bytes': len(b)})
        return (b, p)
DATA = {'ticker': '2610.TW', 'company_name': '華航', 'instrument_type': 'EQUITY', 'currency': 'TWD', 'financial_currency': 'TWD', 'industry': 'Airlines', 'sector': 'Industrials', 'company_identity': {'ticker': '2610.TW', 'stock_id': '2610', 'official_name': '華航', 'legal_name': '中華航空股份有限公司', 'official_ubn': '11145904', 'instrument_type': 'EQUITY'}}

def wiring(monkeypatch):
    from data_fetch.market_sources import cal_annual_bridge as bridge
    h = Http()
    monkeypatch.setattr(bridge, 'BridgeHttp', lambda **kwargs: h)
    return h

def test_typed_source_refresh_preserves_full_receipts_and_truthful_new_attempt(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider, project_source_value, HISTORY_FIELDS
    from data_fetch.types import FetchRequest
    from provider_correlation import source_operation
    from data_fetch.market_sources.cal_annual_bridge import PROVIDER
    h = wiring(monkeypatch)
    with source_operation('financial_statements', PROVIDER):
        result = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('2610.TW'), {'data': DATA})
    a = result.audit
    assert a['status'] == 'success' and a['record_count'] == 5 and (a['http_request_count'] == 24)
    assert len(h.calls) == 24 and len(a['component_statuses']) == 24
    fields = ('source_url', 'source_basis', 'source_origin_note', 'issuer_anchor', 'issuer_master_receipt', 'published_annual_index_receipt', 'issuer_ir_index_receipt', 'supplement_documents', 'documents', 'comparative_revisions', 'raw_twd_by_year')
    packet = {**{k: result.value[k] for k in HISTORY_FIELDS}, **{k: a[k] for k in fields}, 'ticker': '2610.TW', 'schema': a['statement_schema'], 'currency': 'TWD', 'report_scope': a['report_scope']}
    assert project_source_value(packet, '2610.TW') == result.value

def test_normal_financial_path_uses_bridge_once_without_annual_sdk(monkeypatch):
    from data_fetch.yfinance_extractors import extract_financial_histories
    from provider_correlation import correlation_scope
    h = wiring(monkeypatch)
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    notes = []

    class NoSDK:

        def __getattr__(self, name):
            raise AssertionError('unexpected annual SDK ' + name)
    with correlation_scope(replace=True, ticker='2610.TW', fetch_id='isolated-cal-annual'):
        result = extract_financial_histories(NoSDK(), '2610.TW', notes, quote_type='EQUITY', industry_context='Airlines')
    audit = result['official_financial_audit']
    assert result['years'] == ['2021', '2022', '2023', '2024', '2025']
    assert audit['status'] == 'success' and len(audit['component_statuses']) == 24 and (audit['http_request_count'] == len(h.calls) == 24)
    assert notes[0].startswith('五年年度財報採MOPS') and '英文' in notes[0]
    assert result['primary_financial_audit'] is None and result['finmind_financial_fallback_audit'] is None

@pytest.fixture(scope='module')
def packet():
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_histories
    return fetch_bridge_histories('2610.TW', transport=Http())

@pytest.mark.parametrize('change', [lambda v: v.update(ticker='2618.TW'), lambda v: v.update(currency='USD'), lambda v: v.update(report_scope='individual'), lambda v: v.update(source_origin_note='原始五年申報'), lambda v: v.update(years=['2020', '2021', '2022', '2023', '2024']), lambda v: v['issuer_anchor'].update(official_ubn='00000000'), lambda v: v['issuer_master_receipt'].update(http_status_observed=False), lambda v: v['issuer_ir_index_receipt'].update(raw_response_sha256='0' * 64), lambda v: v['issuer_ir_index_receipt'].update(retrieved_at=time.time() + 3600), lambda v: v['supplement_documents'][0]['raw_receipt'].update(cache_hit=True), lambda v: v['supplement_documents'][0]['raw_receipt'].update(retrieved_at=1000), lambda v: v['supplement_documents'][0]['parsed_book_basis']['facts']['2021'].update(PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities=0), lambda v: v['supplement_documents'][1].update(url=M['parts']['book2025']['url']), lambda v: v['documents'][0]['components'][0]['request'].update(companyId='2618'), lambda v: v['documents'][0]['components'][0]['unit_template_receipt'].update(raw_response_sha256='0' * 64), lambda v: v['documents'][0]['intangible_purchase_basis'].update(not_original_period_filing_time_evidence=False), lambda v: v['raw_twd_by_year']['2021'].update(intangible_purchase=0), lambda v: v['fcf_history'].__setitem__(0, 0), lambda v: v['documents'].pop()])
def test_original_replay_rejects_changed_identity_period_receipt_or_cash_fact(packet, change):
    from data_fetch.market_sources.cal_annual_bridge import project_bridge_history
    v = deepcopy(packet)
    change(v)
    assert project_bridge_history(v, '2610.TW') is None

@pytest.fixture(scope='module')
def coordinates():
    from cal_annual_pdf_reader import extract_cal_book
    return extract_cal_book(raw('book2025'), 2025)

@pytest.mark.parametrize('kind', ['reverse_year', 'wrong_unit', 'wrong_issuer', 'wrong_scope', 'positive_purchase', 'blank_purchase', 'duplicate_purchase', 'cross_column', 'extra_value', 'missing_translation_notice'])
def test_cash_row_rejects_ambiguous_or_conflicting_native_positions(coordinates, kind):
    from data_fetch.market_sources.cal_audited_cash import parse_positioned_book
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    v = deepcopy(coordinates)
    pages = {p['page_number']: p for p in v['pages']}
    p = pages[12]
    if kind == 'reverse_year':
        for s in p['segments']:
            if s['text'].strip() == '2025':
                s['text'] = '2024'
            elif s['text'].strip() == '2024':
                s['text'] = '2025'
    elif kind in ('wrong_unit', 'wrong_issuer', 'wrong_scope'):
        before, after = {'wrong_unit': ('New Taiwan Dollars', 'US Dollars'), 'wrong_issuer': ('CHINA AIRLINES', 'EVA AIRWAYS'), 'wrong_scope': ('CONSOLIDATED', 'INDIVIDUAL')}[kind]
        p['text'] = p['text'].replace(before, after)
    elif kind == 'missing_translation_notice':
        pages[6]['text'] = pages[6]['text'].replace('shall', 'might')
    else:
        from data_fetch.market_sources.syntec_audited_book import _rows, _compact
        rows = _rows(p)
        row = next((r for r in rows if _compact(r['text']).startswith('Increaseinotherintangibleassets')))
        h = next((r for r in rows if _compact(r['text']) == '20252024'))
        split = (h['spans'][0]['end_x'] + h['spans'][1]['x']) / 2
        cells = [s for s in p['segments'] if abs(s['y'] - row['y']) < 1.5 and h['spans'][0]['x'] - 45 <= s['x'] < split]
        assert '269,314' in _compact(''.join((s['text'] for s in cells)))
        if kind == 'positive_purchase':
            for s in cells:
                s['text'] = s['text'].replace('(', '').replace(')', '')
        elif kind == 'blank_purchase':
            for s in cells:
                s['text'] = ''
        elif kind == 'cross_column':
            for s in cells:
                s['x'] += 100
                s['end_x'] += 100
        elif kind == 'extra_value':
            cells[-1]['text'] += ' 1'
        else:
            row = [deepcopy(s) for s in p['segments'] if abs(s['y'] - cells[0]['y']) < 1.5]
            for s in row:
                s['y'] -= 2
            p['segments'].extend(row)
    with pytest.raises(FilingError):
        parse_positioned_book(v, 2025)

@pytest.mark.parametrize('conflict', [{'company_identity': {**DATA['company_identity'], 'official_ubn': '00000000'}}, {'company_identity': {**DATA['company_identity'], 'forbidden_aliases': ['China Airlines']}}, {'quote_type': 'ETF'}, {'financial_currency': 'USD'}, {'currency': 'USD'}])
def test_conflicting_context_stops_before_new_http(monkeypatch, conflict):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    h = wiring(monkeypatch)
    with pytest.raises(ValueError):
        AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('2610.TW'), {'data': {**DATA, **conflict}})
    assert h.calls == []

def test_changed_mops_cash_rejects_instead_of_overwriting_with_pdf():
    from data_fetch.market_sources.cal_annual_bridge import fetch_bridge_histories
    from data_fetch.market_sources.official_xbrl_financial import FilingError

    class Conflict(Http):

        def request(self, *args, **kwargs):
            from official_response_evidence import archive_response
            b, p = super().request(*args, **kwargs)
            if self.calls[-1] == 'mops18':
                assert b'49,385,273' in b
                b = b.replace(b'49,385,273', b'49,385,274')
                p = archive_response(b, source_url=args[0], retrieved_at=time.time(), http_status=200)
            return (b, p)
    with pytest.raises(FilingError, match='cash conflict'):
        fetch_bridge_histories('2610.TW', transport=Conflict())

@pytest.mark.parametrize('status', [200, 403, 429, 504])
def test_native_transport_reports_actual_status_and_never_retries(monkeypatch, status):
    from data_fetch.market_sources import issuer_news_transport as native
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp, IR_URL
    from search_provider_runtime import SourceResponseError
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    calls = []
    monkeypatch.setattr(native, 'cooldown_state', lambda key: None)
    monkeypatch.setattr(native, 'remember_failure', lambda *args: None)

    def curl(args, deadline, **kwargs):
        calls.append(args)
        return ({'body': raw('ir-index'), 'headers': f'HTTP/2 {status}\r\ncontent-type: text/html\r\n\r\n'.encode(), 'metadata': json.dumps({'http_code': status, 'url_effective': IR_URL, 'num_redirects': 0, 'method': 'GET', 'proxy_used': 0, 'ssl_verify_result': 0, 'size_download': len(raw('ir-index')), 'content_type': 'text/html'}).encode(), 'process_started': True}, 0, None)
    monkeypatch.setattr(native, 'collect_capped_process', curl)
    h = BridgeHttp()
    if status == 200:
        b, p = h.request(IR_URL)
        assert b == raw('ir-index') and p['http_status'] == 200
    else:
        with pytest.raises(SourceResponseError):
            h.request(IR_URL)
    assert len(calls) == 1 and h.components[0]['http_status'] == status and (h.components[0]['http_request_sent'] is True)

def test_native_shared_deadline_and_existing_host_cooldown_stop_http(monkeypatch):
    from data_fetch.market_sources import issuer_news_transport as native
    from data_fetch.market_sources.cal_annual_transport import BridgeHttp, IR_URL
    from search_provider_runtime import SourceResponseError
    monkeypatch.delenv('STOCK_AGENT_TEST_NO_NETWORK')
    monkeypatch.setattr(native, 'collect_capped_process', lambda *a, **k: pytest.fail('deadline/cooldown must prevent HTTP'))
    monkeypatch.setattr(native, 'cooldown_state', lambda key: None)
    with pytest.raises(SourceResponseError) as expired:
        BridgeHttp(seconds=0).request(IR_URL)
    assert expired.value.error_kind == 'timeout'
    monkeypatch.setattr(native, 'cooldown_state', lambda key: {'retry_at': time.time() + 10})
    with pytest.raises(SourceResponseError) as cooled:
        BridgeHttp().request(IR_URL)
    assert cooled.value.error_kind == 'cooldown'

def test_expired_projection_budget_fails_closed(packet):
    from data_fetch.market_sources.cal_annual_bridge import project_bridge_history
    assert project_bridge_history(packet, '2610.TW', deadline=time.monotonic() - 1) is None

@pytest.mark.parametrize('flag', ['historical_point_in_time_verified', 'finality_guaranteed'])
def test_original_replay_cannot_add_point_in_time_or_finality_claims(packet, flag):
    from data_fetch.market_sources.cal_annual_bridge import project_bridge_history
    v = deepcopy(packet)
    v['supplement_documents'][0]['raw_receipt'][flag] = True
    assert project_bridge_history(v, '2610.TW') is None
