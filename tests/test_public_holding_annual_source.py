"""Public boundary checks. Original private-data replay cases remain local."""
import base64
from copy import deepcopy
import gzip
from hashlib import sha256
import json
from pathlib import Path
import time
from contextlib import contextmanager
import pytest
FIXTURE = Path(__file__).parent / 'fixtures/source_acquisition/mega_holding_public_UI_captured_20261011.json.gz'
SCHEMA = 'financial_holding_public_annual.v1'
PROVIDER = 'TWSE MOPS public financial-holding annual JSON'
SOURCE = 'https://mops.twse.com.tw/mops/#/web/t164sb03'
STATEMENTS = ('BalanceSheet', 'IncomeStatement', 'CashflowStatement')

@pytest.fixture(autouse=True)
def isolated_provider_state():
    import config
    from provider_resilience import clear_provider_circuits
    from provider_throttle import clear_provider_throttles
    assert 'prompt-boundary-tests-' in str(config.CACHE_DB_PATH)
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)
    yield
    clear_provider_circuits(PROVIDER)
    clear_provider_throttles(PROVIDER)

def captured():
    return json.loads(gzip.decompress(FIXTURE.read_bytes()))

def captured_value():
    from official_response_evidence import archive_response
    from data_fetch.market_sources.mops_public_annual import api_url, template_url, payload
    f = captured()
    from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
    index_receipt = archive_response(base64.b64decode(f['index_body_b64']), source_url=INDEX_URL, retrieved_at=time.time(), http_status=200)
    templates = {s: archive_response(base64.b64decode(raw), source_url=template_url(s), retrieved_at=time.time(), http_status=200) for s, raw in f['unit_templates'].items()}
    docs = []
    for y in f['years']:
        parts = []
        for s in STATEMENTS:
            item = next((v for v in f['parts'] if v['year'] == int(y) and v['statement'] == s))
            raw = base64.b64decode(item['body_b64'])
            assert sha256(raw).hexdigest() == item['sha256']
            receipt = archive_response(raw, source_url=api_url(s), retrieved_at=time.time(), http_status=200)
            parts.append({'year': int(y), 'period_end': y + '-12-31', 'statement': s, 'provider': PROVIDER, 'url': api_url(s), 'request': payload('2886', int(y)), 'sha256': item['sha256'], 'raw_receipt': receipt, 'unit_template_receipt': templates[s]})
        docs.append({'year': int(y), 'period_end': y + '-12-31', 'report_scope': 'consolidated', 'provider': PROVIDER, 'url': api_url('BalanceSheet'), 'components': parts, 'sha256': sha256(';'.join((p['sha256'] for p in parts)).encode()).hexdigest()})
    return {'ticker': '2886.TW', 'schema': SCHEMA, 'statement_taxonomy': 'financial_holding', 'currency': 'TWD', 'report_scope': 'consolidated', 'source_url': SOURCE, 'published_index_receipt': index_receipt, 'years': f['years'], 'documents': docs, 'raw_twd_by_year': f['raw_twd_by_year'], 'comparative_revisions': sorted(f['comparative_revisions'], key=lambda v: (v['year'], v['fact']))}

def test_public_projection_accepts_five_full_holding_UI_originals_with_ten_facts_each():
    from data_fetch.annual_financial_source_provider import project_source_value
    value = captured_value()
    projection = project_source_value(value, '2886.TW')
    assert projection is not None
    assert projection['years'] == ['2021', '2022', '2023', '2024', '2025']
    for key, field in [('net_revenue_history', 'net_revenue'), ('net_income_history', 'net_income_attributable'), ('total_assets_history', 'assets'), ('total_equity_history', 'equity'), ('fcf_history', 'free_cash_flow')]:
        assert projection[key] == [value['raw_twd_by_year'][y][field] / 1000000000.0 for y in value['years']]
    assert projection['revenue_history'] == projection['gross_profit_history'] == projection['operating_income_history'] == [None] * 5
    assert projection['financial_history_basis']['statement_schema'] == SCHEMA

@pytest.mark.parametrize('damage', ['missing_body', 'changed_facts', 'changed_sha', 'wrong_currency', 'wrong_scope', 'wrong_ticker', 'deleted_all_markers', 'missing_comparative'])
def test_public_holding_rejects_unbound_body_and_facts_before_prompt(damage):
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder_helpers import _prompt_financial_institution_history
    value = captured_value()
    if damage == 'missing_body':
        value['documents'][0]['components'][0].pop('raw_receipt')
    elif damage == 'changed_facts':
        value['raw_twd_by_year']['2021']['net_revenue'] += 1
    elif damage == 'changed_sha':
        value['documents'][0]['components'][0]['sha256'] = '0' * 64
    elif damage == 'wrong_currency':
        value['currency'] = 'USD'
    elif damage == 'wrong_scope':
        value['report_scope'] = 'individual'
    elif damage == 'wrong_ticker':
        value['ticker'] = '2885.TW'
    elif damage == 'deleted_all_markers':
        value.pop('statement_taxonomy')
        for d in value['documents']:
            for c in d['components']:
                c.pop('raw_receipt')
                c.pop('unit_template_receipt')
    elif damage == 'missing_comparative':
        value['comparative_revisions'].pop()
    assert project_source_value(value, '2886.TW') is None
    assert _prompt_financial_institution_history({'ticker': '2886.TW', 'sector_specific_financials': value}) == {}

class CapturedTransport:

    def __init__(self, *, fail_at=None):
        self.fixture = captured()
        self.components = []
        self.deadline = time.monotonic() + 45
        self.fail_at = fail_at
        self.batch_count = 0
        self.closed = False

    @contextmanager
    def batch(self):
        self.batch_count += 1
        try:
            yield self
        finally:
            self.closed = True

    def request(self, url, *, request=None, json_body=None):
        from official_response_evidence import archive_response
        from data_fetch.market_sources.official_xbrl_financial import INDEX_URL
        from data_fetch.market_sources.mops_public_annual import api_url, template_url, payload
        from search_provider_runtime import SourceResponseError
        d = {'url': url, 'http_request_sent': True, 'http_status': 200}
        self.components.append(d)
        if len(self.components) == self.fail_at:
            d['http_status'] = 429
            raise SourceResponseError('rate_limited', status_code=429)
        if url == INDEX_URL:
            assert request['co_id'] == '2886' and json_body is None
            raw = base64.b64decode(self.fixture['index_body_b64'])
        elif url in {template_url(s) for s in STATEMENTS}:
            s = next((s for s in STATEMENTS if template_url(s) == url))
            raw = base64.b64decode(self.fixture['unit_templates'][s])
        else:
            s = next((s for s in STATEMENTS if api_url(s) == url))
            y = int(json_body['year']) + 1911
            assert json_body == payload('2886', y)
            part = next((v for v in self.fixture['parts'] if v['year'] == y and v['statement'] == s))
            raw = base64.b64decode(part['body_b64'])
        d.update(response_bytes=len(raw), response_sha256=sha256(raw).hexdigest(), status='complete')
        return (raw, archive_response(raw, source_url=url, retrieved_at=time.time(), http_status=200))

def test_public_holding_fetch_uses_nineteen_bounded_originals_and_rebuilds_comparatives():
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_histories
    from data_fetch.annual_financial_source_provider import project_source_value
    transport = CapturedTransport()
    value = fetch_public_holding_histories('2886.TW', transport=transport)
    assert len(transport.components) == 19 and transport.batch_count == 1 and transport.closed
    assert value['raw_twd_by_year'] == captured()['raw_twd_by_year']
    assert value['comparative_revisions'] == sorted(captured()['comparative_revisions'], key=lambda v: (v['year'], v['fact']))
    assert project_source_value(value, '2886.TW') is not None

def test_refusal_stops_the_same_source_operation_without_implicit_retry():
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_result
    transport = CapturedTransport(fail_at=7)
    result = fetch_public_holding_result('2886.TW', transport=transport)
    assert result['value'] is None and result['audit']['status'] != 'success'
    assert len(transport.components) == 7 and transport.closed and (transport.batch_count == 1)
    assert result['audit']['http_request_count'] == 7 and result['audit']['http_status'] == 429

@pytest.mark.parametrize('damage', ['duplicate_amount', 'duplicate_heading', 'partial_empty_heading', 'wrong_beginning_period', 'wrong_closing_period', 'subsidiary', 'issuer', 'scope', 'missing_intangible', 'dash', 'boolean', 'positive_purchase'])
def test_captured_public_layout_rejects_ambiguous_scope_periods_and_missing_amounts(damage):
    from data_fetch.market_sources.mops_public_holding import parse_holding_statement
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    s = 'CashflowStatement' if damage in {'missing_intangible', 'dash', 'boolean', 'positive_purchase'} else 'BalanceSheet'
    f = captured()
    part = next((v for v in f['parts'] if v['year'] == 2023 and v['statement'] == s))
    value = json.loads(base64.b64decode(part['body_b64']))
    r = value['result']
    rows = r['reportList']
    if damage == 'duplicate_amount':
        rows.append(deepcopy(next((v for v in rows if v[0].strip() == '歸屬於母公司業主之權益' and v[1]))))
    elif damage == 'duplicate_heading':
        rows.append(deepcopy(next((v for v in rows if v[0].strip() == '歸屬於母公司業主之權益' and v[1] == ''))))
    elif damage == 'partial_empty_heading':
        next((v for v in rows if v[0].strip() == '歸屬於母公司業主之權益' and v[1] == ''))[3] = '1'
    elif damage == 'wrong_beginning_period':
        r['titles'][3]['main'] = '111年12月31日'
    elif damage == 'wrong_closing_period':
        r['titles'][2]['main'] = '111年01月01日'
    elif damage == 'subsidiary':
        r['subsidiaryCompanyId'] = '288601'
    elif damage == 'issuer':
        r['urlList'][0]['url'] = r['urlList'][0]['url'].replace('CO_ID=2886', 'CO_ID=2885')
    elif damage == 'scope':
        r['reportType'] = '個體'
    elif damage == 'missing_intangible':
        r['reportList'] = [v for v in rows if v[0].strip() != '取得無形資產']
    elif damage in {'dash', 'boolean', 'positive_purchase'}:
        next((v for v in rows if v[0].strip() == '取得無形資產'))[1] = {'dash': '-', 'boolean': True, 'positive_purchase': '1'}[damage]
    with pytest.raises(FilingError):
        parse_holding_statement(json.dumps(value, ensure_ascii=False).encode(), '2886.TW', 2023, s, base64.b64decode(f['unit_templates'][s]))

def test_normal_holding_extraction_uses_verified_UI_and_avoids_duplicate_sdk_and_finmind(monkeypatch):
    from data_fetch import yfinance_extractors as extractors
    from data_fetch.market_sources import mops_public_holding as native
    from test_financial_institution_history_projection import NoAnnualSdk
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK', '0')
    transport = CapturedTransport()
    monkeypatch.setattr(native, 'PublicMopsHttp', lambda: transport)
    monkeypatch.setattr(extractors, 'fetch_financial_institution_histories', lambda *a: pytest.fail('no repeated old XBRL path'))
    monkeypatch.setattr(extractors, 'fetch_finmind_financial_statement_fallback', lambda *a, **k: pytest.fail('complete verified holding avoids FinMind'))
    value = extractors.extract_financial_histories(NoAnnualSdk(), '2886.TW', [], industry_context='金融保險')
    assert value['financial_history_basis']['statement_schema'] == SCHEMA
    assert value['net_revenue_history'] == [captured()['raw_twd_by_year'][y]['net_revenue'] / 1000000000.0 for y in captured()['years']]
    assert value['revenue_history'] == [None] * 5
    audit = value['sector_specific_financial_audit']
    assert audit['provider'] == PROVIDER and audit['http_request_count'] == 19
    assert len(audit['component_statuses']) == 19

def test_full_public_prompt_has_typed_net_revenue_without_internal_original_paths():
    from data_fetch.annual_financial_source_provider import project_source_value
    from prompt_builder import format_data_for_prompt
    value = captured_value()
    data = {'ticker': '2886.TW', **project_source_value(value, '2886.TW')}
    encoded = format_data_for_prompt(data)
    payload = json.loads(encoded.split('【財務資料 JSON】\n', 1)[1].split('\n\n【使用規則】', 1)[0])
    typed = payload['history']['financial_institution']
    assert typed['schema'] == SCHEMA and len(typed['rows']) == 5
    assert 'net_revenue_is_financial_institution' in typed['basis_note']
    for d in value['documents']:
        for p in d['components']:
            assert p['raw_receipt']['raw_response_path'] not in encoded
            assert p['unit_template_receipt']['raw_response_path'] not in encoded
    assert value['published_index_receipt']['raw_response_path'] not in encoded

def test_public_holding_parser_rejects_changed_unit_contract_and_duplicate_json_keys():
    from data_fetch.market_sources.mops_public_holding import parse_holding_statement
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    f = captured()
    c = next((v for v in f['parts'] if v['year'] == 2025 and v['statement'] == 'IncomeStatement'))
    raw = base64.b64decode(c['body_b64'])
    unit = base64.b64decode(f['unit_templates']['IncomeStatement'])
    with pytest.raises(FilingError):
        parse_holding_statement(raw, '2886.TW', 2025, 'IncomeStatement', unit + b' ')
    with pytest.raises(FilingError):
        parse_holding_statement(b'{"code":200,' + raw[1:], '2886.TW', 2025, 'IncomeStatement', unit)

def test_other_holding_layout_is_not_silently_enabled():
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_histories
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    transport = CapturedTransport()
    with pytest.raises(FilingError):
        fetch_public_holding_histories('2885.TW', transport=transport)
    assert not transport.components and transport.batch_count == 0

@pytest.mark.parametrize('failure', ['unexpected_native_type', 'cleanup_after_complete_read'])
def test_unexpected_exception_and_cleanup_failure_never_restart_whole_acquisition(failure):
    from data_fetch.market_sources.mops_public_holding import fetch_public_holding_result

    class BrokenTransport(CapturedTransport):

        @contextmanager
        def batch(self):
            self.batch_count += 1
            try:
                yield self
            finally:
                self.closed = True
                if failure == 'cleanup_after_complete_read' and self.batch_count == 1:
                    raise RuntimeError('simulated cleanup failure')

        def request(self, url, *, request=None, json_body=None):
            if failure == 'unexpected_native_type' and (not self.components):
                self.components.append({'url': url, 'http_request_sent': True})
                raise TypeError('simulated native archive seam failure')
            return super().request(url, request=request, json_body=json_body)
    transport = BrokenTransport()
    result = fetch_public_holding_result('2886.TW', transport=transport)
    assert result['value'] is None and result['audit']['status'] != 'success'
    assert transport.batch_count == 1 and transport.closed
    assert len(transport.components) == (1 if failure == 'unexpected_native_type' else 19)
