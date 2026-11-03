"""Synthetic contracts; native acquisition evidence is verified separately."""
import pytest
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
import json,time

from test_ordinary_individual_annual import index, synthetic_filing, transport


def test_native_2021_original_accepts_only_its_exact_official_issuer_name():
    from data_fetch.market_sources.ordinary_individual_annual import parse_individual_filing
    path = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261103/chien-shing-annual/2021-individual.xhtml'
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == '1f2de9c4c8f52cea41c18783f9e85a0e7be6556ec5cd734ad8fbfa8d165a0491'
    parsed = parse_individual_filing(raw, '2025', 2021)
    assert set(parsed[2021]) >= {'reported_revenue', 'profit_loss', 'assets', 'equity', 'operating_cash_flow'}


def native_history():
    """Replay real bytes into isolated test receipts; no new HTTP qualification."""
    from official_response_evidence import archive_response
    folder = Path(__file__).resolve().parents[1] / 'docs/evidence/source-acquisition/20261103/chien-shing-annual'
    value = json.loads((folder / 'full-native-value.json').read_text())
    value['published_index_receipt'] = archive_response((folder / 'current-index.body').read_bytes(),
        source_url=value['source_url'], retrieved_at=time.time(), http_status=200)
    for doc in value['documents']:
        raw = (folder / (str(doc['year']) + '-individual.xhtml')).read_bytes()
        assert sha256(raw).hexdigest() == doc['sha256']
        doc['raw_receipt'] = archive_response(raw, source_url=doc['url'], retrieved_at=time.time(), http_status=200)
    return value


def test_five_real_individual_originals_replay_with_parent_attribution_unclaimed():
    from data_fetch.annual_financial_source_provider import project_source_value
    value = native_history(); projection = project_source_value(value, '2025.TW')
    assert projection and projection['years'] == ['2021', '2022', '2023', '2024', '2025']
    assert projection['financial_history_basis']['report_scope'] == 'individual'
    assert projection['financial_history_basis']['field_sources']['net_income_history']['fact'] == 'ifrs-full:ProfitLoss'
    from quant_input_contract import read_quant_inputs
    from test_ordinary_individual_scope import data
    quote_data = {**data(), **projection, 'ticker': '2025.TW'}
    assert 'ordinary_individual_group_basis_unverified' in read_quant_inputs(quote_data)[2]['dcf']
    damaged = deepcopy(value); damaged['raw_twd_by_year']['2025']['profit_loss'] += 1000
    assert project_source_value(damaged, '2025.TW') is None


def test_chien_shing_selects_latest_individual_years_instead_of_old_consolidated_series():
    from data_fetch.market_sources import ordinary_individual_annual as m
    from data_fetch.annual_financial_source_provider import project_source_value
    assert m.ISSUERS['2025.TW'] == '千興不銹鋼股份有限公司'
    body = index(a=range(2019, 2026), c=range(2013, 2019), issuer='2025')
    years = range(2021, 2026)
    http, calls = transport(index_body=body, bodies={
        y: synthetic_filing(y, issuer='2025', company_name='千興不銹鋼股份有限公司') for y in years})
    result = m.fetch_annual_result('2025.TW', transport=http)
    assert result['audit']['status'] == 'success' and len(calls) == 6
    assert result['value']['years'] == [str(y) for y in years]
    projection = project_source_value(result['value'], '2025.TW')
    assert projection['financial_history_basis']['report_scope'] == 'individual'
    assert projection['financial_history_basis']['field_sources']['net_income_history']['fact'] == 'ifrs-full:ProfitLoss'


def test_public_collector_rejects_superseded_consolidated_scope_before_statement_requests():
    from data_fetch.market_sources.mops_public_annual import fetch_public_annual_histories
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    from contextlib import nullcontext
    import time
    class IndexOnly:
        deadline = time.monotonic() + 45
        calls = 0
        def batch(self): return nullcontext()
        def request(self, url, **kwargs):
            self.calls += 1
            assert self.calls == 1, 'Superseded scope must be rejected before any financial query'
            return index(a=range(2019, 2026), c=range(2013, 2019), issuer='2025'), {}
    http = IndexOnly()
    with pytest.raises(FilingError, match='newer individual annual'):
        fetch_public_annual_histories('2025.TW', transport=http)
    assert http.calls == 1


@pytest.mark.parametrize('bad_name', ['千興', '千興建設股份有限公司', '其他公司'])
def test_individual_original_keeps_exact_legal_identity(bad_name):
    from data_fetch.market_sources.ordinary_individual_annual import parse_individual_filing
    from data_fetch.market_sources.official_xbrl_financial import FilingError
    with pytest.raises(FilingError):
        parse_individual_filing(synthetic_filing(2025, issuer='2025', company_name=bad_name), '2025', 2025)


def test_chien_shing_context_preserves_official_master_name_and_rejects_conflicting_ubn():
    from data_fetch.market_sources.ordinary_individual_annual import validate_context
    from copy import deepcopy
    data = {'ticker': '2025.TW', 'stock_id': '2025', 'quote_type': 'EQUITY',
            'company_identity': {'official_name': '千興', 'legal_name': '千興不銹鋼(股)公司',
                                 'official_ubn': '70005915'}}
    validate_context(data, '2025.TW')
    wrong = deepcopy(data); wrong['company_identity']['official_ubn'] = '70005916'
    with pytest.raises(ValueError, match='identity_conflict'):
        validate_context(wrong, '2025.TW')


def test_chien_shing_provider_keeps_individual_income_and_original_scope(monkeypatch):
    from copy import deepcopy
    from data_fetch.market_sources import ordinary_individual_annual as m
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.types import FetchRequest
    years = range(2021, 2026)
    http, calls = transport(index_body=index(a=range(2019, 2026), c=range(2013, 2019), issuer='2025'),
                            bodies={y: synthetic_filing(y, issuer='2025', company_name='千興不銹鋼股份有限公司') for y in years})
    result = m.fetch_annual_result('2025.TW', transport=http)
    result['audit'].pop('fetch_id', None)
    monkeypatch.setattr(m, 'fetch_annual_result', lambda ticker: deepcopy(result))
    data = {'ticker': '2025.TW', 'quote_type': 'EQUITY', 'currency': 'TWD', 'financial_currency': 'TWD',
            'sector': 'Basic Materials', 'industry': 'Steel',
            'company_identity': {'official_name': '千興', 'legal_name': '千興不銹鋼(股)公司', 'official_ubn': '70005915'}}
    output = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('2025.TW', force_refresh=False), {'data': data})
    assert output.status == 'success' and len(calls) == 6
    assert output.value['schema'] == 'ordinary_individual.v1'
    assert output.value['report_scope'] == 'individual' and output.value['years'] == [str(y) for y in years]
    assert all('net_income_attributable' not in row for row in output.value['raw_twd_by_year'].values())
