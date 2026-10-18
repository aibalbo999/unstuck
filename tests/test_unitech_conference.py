"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

@pytest.mark.parametrize('change', ['ticker', 'instrument_type', 'quote_type', 'quoteType', 'ubn', 'legal', 'forbidden', 'malformed', 'name'])
def test_caller_subject_and_all_explicit_type_aliases_are_fail_closed(change):
    from data_fetch.market_sources.unitech_conference import validate_context
    data = {'ticker': '2367.TW', 'instrument_type': 'EQUITY', 'company_name': '燿華', 'company_identity': {}}
    if change == 'ticker':
        data['ticker'] = '2367.TWO'
    elif change in {'instrument_type', 'quote_type', 'quoteType'}:
        data[change] = 'ETF'
    elif change == 'ubn':
        data['company_identity']['official_ubn'] = '00000000'
    elif change == 'legal':
        data['company_identity']['legal_name'] = '他公司'
    elif change == 'forbidden':
        data['company_identity']['forbidden_aliases'] = ['UNITECH']
    elif change == 'malformed':
        data['company_identity'] = False
    else:
        data['company_name'] = '燿華 / 其他公司'
    assert not validate_context(data, '2367.TW')
