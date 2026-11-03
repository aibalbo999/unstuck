"""Hotai mixed-income routing: synthetic whole-flow and private real originals."""
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest

def synthetic_hotai_transport():
    # Deliberately synthetic issuer substitution for protocol/routing checks;
    # these numbers are NOT Hotai facts or live acquisition evidence.
    if not (Path(__file__).parent / 'fixtures/source_acquisition/mops_public_2905_20261103.json').exists():
        pytest.skip('Private legacy corpus for structural replay intentionally not published')
    from test_mixed_income_annual import transport
    def synthetic(request, raw):
        if '/api/' in str(request.url):
            assert json.loads(request.content)['companyId'] == '2207'
            value = json.loads(raw); result = value['result']
            result['companyAbbreviation'] = '和泰車'
            for reference in result['urlList']:
                reference['url'] = reference['url'].replace('2905', '2207')
            return json.dumps(value, ensure_ascii=False).encode()
        return raw.replace(b'co_id=2905', b'co_id=2207') if '/ajax_' in str(request.url) else raw
    return transport(mutate=synthetic)


def test_full_synthetic_hotai_flow_keeps_income_distinct_and_cross_issuer_rejected():
    from data_fetch.market_sources import mixed_income_annual as m
    value = m.fetch_histories('2207.TW', transport=synthetic_hotai_transport())
    result = m.project_history(value, '2207.TW')
    assert result is not None and value['years'] == ['2021','2022','2023','2024','2025']
    assert result['revenue_history'] == result['gross_profit_history'] == result['operating_income_history'] == [None] * 5
    assert '和泰車' in result['financial_history_basis']['note']
    assert m.project_history(value, '2905.TW') is None
    changed = deepcopy(value); changed['documents'][0]['components'][0]['request']['companyId'] = '2905'
    assert m.project_history(changed, '2207.TW') is None


def test_normal_hotai_source_and_core_paths_use_explicit_schema_without_sdk(monkeypatch):
    from data_fetch.market_sources import mixed_income_annual as m
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    from data_fetch import yfinance_extractors as core
    original = m.fetch_result
    monkeypatch.setattr(m, 'fetch_result', lambda ticker: original(ticker, transport=synthetic_hotai_transport()))
    data = {'ticker':'2207.TW','currency':'TWD','financial_currency':'TWD','instrument_type':'EQUITY',
        'sector':'Consumer Cyclical','company_identity':{'ticker':'2207.TW','official_name':'和泰車','stock_id':'2207','instrument_type':'EQUITY'}}
    from provider_correlation import correlation_scope
    with correlation_scope(replace=True, ticker='2207.TW', fetch_id='isolated-hotai-mixed-source'):
        out = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('2207.TW', force_refresh=False), {'data':data})
    assert out.status == 'success' and out.value['schema'] == m.SCHEMA
    monkeypatch.setenv('STOCK_AGENT_TEST_NO_NETWORK','0')
    class NoSdk:
        def __getattr__(self, name): raise AssertionError('Mixed Hotai must not use SDK ' + name)
    projection = core._extract_financial_histories_uncached(NoSdk(), '2207.TW', [], industry_context='Auto & Truck Dealerships')
    assert projection['revenue_history'] == [None] * 5
    assert projection['sector_specific_financials']['ticker'] == '2207.TW'


@pytest.mark.parametrize('change', ['stock_id','name','type','forbidden'])
def test_hotai_explicit_identity_conflicts_rejected(change):
    from data_fetch.annual_financial_source_provider import validate_context
    identity = {'ticker':'2207.TW','stock_id':'2207','official_name':'和泰車','instrument_type':'EQUITY'}
    key, value = {'stock_id':('stock_id','2905'), 'name':('official_name','三商'),
        'type':('instrument_type','ETF'), 'forbidden':('forbidden_aliases',['和泰車'])}[change]
    identity[key] = value
    with pytest.raises(ValueError):
        validate_context({'ticker':'2207.TW','currency':'TWD','financial_currency':'TWD',
            'instrument_type':'EQUITY','company_identity':identity}, '2207.TW')


@pytest.mark.parametrize('statement', ['BalanceSheet','IncomeStatement'])
def test_private_hotai_2021_native_originals_preserve_parent_amounts(statement):
    from data_fetch.market_sources import mixed_income_annual as m
    path = Path(__file__).parent / 'fixtures/source_acquisition/mops_public_2207_20261104_mixed_parts.json'
    if not path.exists(): pytest.skip('Native originals intentionally private')
    f = json.loads(path.read_text())[statement]
    raw, template = base64.b64decode(f['raw_b64']), base64.b64decode(f['template_b64'])
    assert hashlib.sha256(raw).hexdigest() == f['raw_sha256']
    assert hashlib.sha256(template).hexdigest() == f['template_sha256']
    facts = m.parse_statement(raw, '2207.TW', 2021, statement, template)
    if statement == 'BalanceSheet':
        assert facts[2021]['equity'] == 73770851000
        assert facts[2021]['total_equity'] == 94465965000
    else:
        assert facts[2021]['net_income_attributable'] == 16210758000
        assert facts[2021]['total_income'] == 246917024000
        assert facts[2021]['net_income_attributable'] != 17589052000  # comprehensive income


def private_complete_value():
    path = Path(__file__).parent / 'fixtures/source_acquisition/mops_public_2207_20261104_complete.json'
    if not path.exists(): pytest.skip('Native complete originals intentionally private')
    fixture = json.loads(path.read_text()); value = deepcopy(fixture['value'])
    from official_response_evidence import archive_response
    def rebase(item):
        if isinstance(item, dict):
            if all(k in item for k in ('raw_response_sha256','raw_response_path','raw_response_bytes')):
                body = base64.b64decode(fixture['raw_bodies'][item['raw_response_sha256']]['body_b64'])
                assert hashlib.sha256(body).hexdigest() == item['raw_response_sha256']
                receipt = archive_response(body, source_url=item['source_url'], retrieved_at=item['retrieved_at'])
                item.clear(); item.update(receipt)
            else:
                for v in item.values(): rebase(v)
        elif isinstance(item, list):
            for v in item: rebase(v)
    rebase(value); return value


def test_private_complete_hotai_originals_replay_and_report_keeps_general_revenue_unknown():
    from data_fetch.annual_financial_source_provider import project_source_value
    from annual_financial_source_refresh import apply_annual_history_values
    from quant_input_contract import read_quant_inputs
    from prompt_builder_helpers import _prompt_financial_institution_history
    from report_evidence_gap_details import cash_flow_detail
    value = private_complete_value(); projected = project_source_value(value, '2207.TW')
    assert projected is not None and value['years'] == ['2021','2022','2023','2024','2025']
    assert len(value['documents']) == 5 and all(len(d['components']) == 3 for d in value['documents'])
    data = {'ticker':'2207.TW','financial_currency':'TWD'}
    apply_annual_history_values(data, projected, value, {})
    assert data['revenue_history'] == data['gross_profit_history'] == data['operating_income_history'] == [None] * 5
    assert data['gross_margin_history'] == data['net_margin_history'] == [None] * 5
    assert 'mixed_income_fcf_not_normalized_for_dcf' in read_quant_inputs(data)[2]['dcf']
    prompt = _prompt_financial_institution_history(data)
    assert prompt and '和泰車' in data['financial_history_basis']['note']
    assert 'not_bank_net_revenue' in prompt['basis_note']
    detail = cash_flow_detail(data)
    assert detail['status'] == 'sector_annual_originals_verified'
    assert detail['free_cash_flow_twd'] == value['raw_twd_by_year']['2025']['free_cash_flow']
    assert detail['industrial_dcf_applicable'] is False
    assert project_source_value(value, '2905.TW') is None


@pytest.mark.parametrize('change', ['foreign_request', 'income_value', 'unit_template', 'index', 'attribution'])
def test_private_complete_hotai_proof_tampering_rejected(change):
    from data_fetch.market_sources.mixed_income_annual import project_history
    value = private_complete_value(); part = value['documents'][0]['components'][0]
    if change == 'foreign_request': part['request']['companyId'] = '2905'
    elif change == 'income_value': value['raw_twd_by_year']['2025']['total_income'] += 1000
    elif change == 'unit_template': part['unit_template_receipt']['raw_response_sha256'] = '0' * 64
    elif change == 'index': value.pop('published_index_receipt')
    else: value['raw_twd_by_year']['2025']['net_income_attributable'] = value['raw_twd_by_year']['2025']['group_profit']
    assert project_history(value, '2207.TW') is None
