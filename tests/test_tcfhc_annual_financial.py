"""Public boundary checks. Original private-data replay cases remain local."""
from copy import deepcopy
import pytest
DATA = {'ticker': '5880.TW', 'company_name': '合庫金', 'instrument_type': 'EQUITY', 'currency': 'TWD', 'financial_currency': 'TWD', 'sector': 'Financial Services', 'industry': 'Banks - Regional', 'company_identity': {'ticker': '5880.TW', 'stock_id': '5880', 'official_name': '合庫金', 'legal_name': '合作金庫金融控股股份有限公司', 'official_ubn': '53021433', 'instrument_type': 'EQUITY'}}

@pytest.mark.parametrize('identity', [{'ticker': '2886.TW'}, {'legal_name': '合作金庫商業銀行股份有限公司'}, {'official_ubn': '70796754'}, {'stock_id': '2886'}, {'official_name': '兆豐金'}, {'forbidden_aliases': ['合庫金']}])
def test_public_annual_refresh_rejects_tcfhc_identity_conflict_before_provider(identity):
    from data_fetch.annual_financial_source_provider import validate_context
    data = deepcopy(DATA)
    data['company_identity'].update(identity)
    with pytest.raises(ValueError):
        validate_context(data, '5880.TW')

def test_public_source_refresh_routes_the_failed_5880_issuer_to_published_books(monkeypatch):
    from data_fetch.annual_financial_source_provider import AnnualFinancialSourceProvider
    from data_fetch.market_sources import tcfhc_annual_financial as books, financial_institution_xbrl as old
    from data_fetch.types import FetchRequest
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(kwargs)
        return {'value': None, 'audit': {'source': 'financial_statements', 'provider': books.PROVIDER, 'status': 'unavailable', 'record_count': 0, 'message': 'isolated route boundary', 'cache_hit': False, 'stale': False}}
    monkeypatch.setattr(books, 'fetch_annual_result', unavailable)
    monkeypatch.setattr(old, 'fetch_financial_institution_histories', lambda *a, **k: None)
    result = AnnualFinancialSourceProvider().fetch(FetchRequest.from_ticker('5880.TW'), {'data': deepcopy(DATA)})
    assert len(calls) == 1 and calls[0].get('force_refresh') is True
    assert result.audit['provider'] == books.PROVIDER
