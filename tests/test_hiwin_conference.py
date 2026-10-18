"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '2049.TW', 'company_name': '上銀 / Hiwin Technologies Corp.', 'raw_company_name': 'Hiwin Technologies Corp.', 'quote_type': 'EQUITY', 'instrument_type': 'EQUITY', 'company_identity': {'ticker': '2049.TW', 'stock_id': '2049', 'official_name': '上銀', 'instrument_type': 'EQUITY', 'allowed_aliases': ['上銀', 'Hiwin Technologies Corp.', 'HIWIN TECHNOLOGIES CORP', '2049.TW', '2049'], 'english_names': ['Hiwin Technologies Corp.', 'HIWIN TECHNOLOGIES CORP'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('change', ['root_name', 'alias', 'ubn', 'quote', 'forbidden', 'foreign_suffix'])
def test_identity_does_not_borrow_good_name_to_hide_contradiction(change):
    from data_fetch.market_sources.hiwin_conference import validate_context
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
        v['company_identity']['forbidden_aliases'] = ['上銀']
    else:
        v['raw_company_name'] = 'HIWIN Electric Co.,Ltd. unrelated'
    assert not validate_context(v, '2049.TW')
