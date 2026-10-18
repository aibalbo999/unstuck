"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '6861.TW', 'company_name': '睿生光電 / InnoCare Optoelectronics Corporation', 'raw_company_name': 'InnoCare Optoelectronics Corporation', 'instrument_type': 'EQUITY', 'quote_type': 'EQUITY', 'company_identity': {'ticker': '6861.TW', 'stock_id': '6861', 'official_name': '睿生光電', 'legal_name': '睿生光電股份有限公司', 'official_ubn': '69764396', 'instrument_type': 'EQUITY', 'allowed_aliases': ['睿生光電', 'INCX', '6861', '6861.TW'], 'english_names': ['InnoCare Optoelectronics Corporation'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['name', 'ubn', 'alias', 'forbidden', 'quote', 'ticker'])
def test_conflicting_caller_identity_is_rejected(change):
    from data_fetch.market_sources.innocare_conference import validate_context
    d = valid_data()
    if change == 'name':
        d['raw_company_name'] = 'Other company'
    elif change == 'ubn':
        d['company_identity']['official_ubn'] = '00000000'
    elif change == 'alias':
        d['company_identity']['allowed_aliases'].append('Winbond')
    elif change == 'forbidden':
        d['company_identity']['forbidden_aliases'] = ['睿生光電']
    elif change == 'quote':
        d['quote_type'] = 'ETF'
    else:
        d['ticker'] = '6861.TWO'
    assert not validate_context(d, '6861.TW')
