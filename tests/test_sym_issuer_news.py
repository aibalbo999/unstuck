"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data():
    return {'ticker': '2206.TW', 'company_name': '三陽工業 / Sanyang Motor Co., Ltd.', 'instrument_type': 'EQUITY', 'company_identity': {'ticker': '2206.TW', 'stock_id': '2206', 'official_name': '三陽工業', 'legal_name': None, 'english_names': ['Sanyang Motor Co., Ltd.', 'SANYANG MOTOR CO LTD'], 'allowed_aliases': ['三陽工業', 'SANYANG MOTOR CO LTD', '2206', '2206.TW'], 'forbidden_aliases': []}}

@pytest.mark.parametrize('field,value', [('ticker', '2206.TWO'), ('instrument_type', 'ETF'), ('quote_type', False), ('quoteType', 'ETF'), ('company_identity', False), ('company_name', '其他公司')])
def test_contradictory_root_context_is_rejected(field, value):
    from data_fetch.market_sources.sym_issuer_news import validate_context
    data = valid_data()
    data[field] = value
    assert not validate_context(data)

@pytest.mark.parametrize('field,value', [('ticker', '2206.TWO'), ('stock_id', '2207'), ('official_name', '其他公司'), ('legal_name', '同名公司'), ('official_ubn', '99999999'), ('instrument_type', False), ('forbidden_aliases', ['SYM'])])
def test_nested_context_is_not_overridden_by_good_root(field, value):
    from data_fetch.market_sources.sym_issuer_news import validate_context
    data = valid_data()
    data['company_identity'][field] = value
    assert not validate_context(data)
