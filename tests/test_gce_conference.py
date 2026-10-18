"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '2368.TW', 'company_name': '金像電 / Gold Circuit Electronics Ltd.', 'raw_company_name': 'Gold Circuit Electronics Ltd.', 'quote_type': 'EQUITY', 'instrument_type': 'EQUITY', 'company_identity': {'ticker': '2368.TW', 'stock_id': '2368', 'official_name': '金像電', 'instrument_type': 'EQUITY', 'allowed_aliases': ['金像電', 'Gold Circuit Electronics Ltd.', 'GOLD CIRCUIT ELECTRONICS CO', '2368.TW', '2368'], 'english_names': ['Gold Circuit Electronics Ltd.', 'GOLD CIRCUIT ELECTRONICS CO'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['root_name', 'alias', 'ubn', 'quote', 'forbidden', 'foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.gce_conference import validate_context
    v = valid_data()
    if change == 'root_name':
        v['company_name'] = 'ARES'
    elif change == 'alias':
        v['company_identity']['english_names'] = {}
    elif change == 'ubn':
        v['company_identity']['official_ubn'] = '00000000'
    elif change == 'quote':
        v['quote_type'] = 'ETF'
    elif change == 'forbidden':
        v['company_identity']['forbidden_aliases'] = ['金像電']
    else:
        v['raw_company_name'] = 'GCE Electric Co.,Ltd. unrelated'
    assert not validate_context(v, '2368.TW')
