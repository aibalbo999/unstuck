"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '1605.TW', 'company_name': '華新 / Walsin Lihwa Corporation', 'raw_company_name': 'Walsin Lihwa Corporation', 'instrument_type': 'EQUITY', 'quote_type': 'EQUITY', 'company_identity': {'ticker': '1605.TW', 'stock_id': '1605', 'official_name': '華新', 'legal_name': '華新麗華股份有限公司', 'official_ubn': '35412204', 'instrument_type': 'EQUITY', 'allowed_aliases': ['華新', 'WALSIN', '1605.TW', '1605'], 'english_names': ['Walsin Lihwa Corporation'], 'forbidden_aliases': []}}

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
