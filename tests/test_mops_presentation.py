"""Public boundary checks. Original private-data replay cases remain local."""
import pytest

def valid_data(ticker='1229.TW'):
    if ticker == '1229.TW':
        name, legal, en, raw = ('聯華', '聯華實業控股股份有限公司', 'Lien Hwa Industrial Holdings Corporation', 'LIEN HWA INDUSTRIAL HOLDINGS CO')
    elif ticker == '2353.TW':
        name, legal, en, raw = ('宏碁', '宏碁股份有限公司', 'Acer Incorporated', 'ACER INC')
    elif ticker == '2382.TW':
        name, legal, en, raw = ('廣達', '廣達電腦股份有限公司', 'Quanta Computer Inc.', 'QCI')
    elif ticker == '1301.TW':
        name, legal, en, raw = ('台塑', '台灣塑膠工業股份有限公司', 'Formosa Plastics Corporation', 'FORMOSA PLASTICS CORP')
    elif ticker == '1102.TW':
        name, legal, en, raw = ('亞泥', '亞洲水泥股份有限公司', 'Asia Cement Corporation', 'ASIA CEMENT CORP')
    elif ticker == '1216.TW':
        name, legal, en, raw = ('統一', '統一企業股份有限公司', 'Uni-President Enterprises Corp.', 'UNI-PRESIDENT ENTERPRISES CORP')
    elif ticker == '3531.TWO':
        name, legal, en, raw = ('先益', '先益電子工業股份有限公司', 'Shian Yih Electronic Industry Co., Ltd.', 'Shian Yih')
    elif ticker == '1104.TW':
        name, legal, en, raw = ('環泥', '環球水泥股份有限公司', 'Universal Cement Corporation', 'UNIVERSAL CEMENT CORP')
    elif ticker == '2838.TW':
        name, legal, en, raw = ('聯邦銀', '聯邦商業銀行股份有限公司', 'Union Bank of Taiwan', 'UBOT')
    elif ticker == '3703.TW':
        name, legal, en, raw = ('欣陸', '欣陸投資控股股份有限公司', 'Continental Holdings Corporation', 'CHC')
    elif ticker == '2023.TW':
        name, legal, en, raw = ('燁輝', '燁輝企業股份有限公司', 'YP', 'Yieh Phui')
    elif ticker == '2845.TW':
        name, legal, en, raw = ('遠東銀', '遠東國際商業銀行股份有限公司', 'Far Eastern International Bank Ltd.', 'FEIB')
    else:
        name, legal, en, raw = ('台積電', '台灣積體電路製造股份有限公司', 'Taiwan Semiconductor Manufacturing Company Limited', 'TAIWAN SEMICONDUCTOR MANUFACTUR')
    return {'ticker': ticker, 'instrument_type': 'EQUITY', 'company_name': name + ' / ' + en, 'raw_company_name': en, 'company_identity': {'ticker': ticker, 'stock_id': ticker.split('.')[0], 'official_name': name, 'legal_name': legal, 'official_ubn': {'2353.TW': '20828393', '2382.TW': '22822281', '1301.TW': '75708007', '1102.TW': '03244509', '1216.TW': '73251209', '3531.TWO': '52543363', '1104.TW': '07568009', '2838.TW': '86380802', '3703.TW': '28993629', '2023.TW': '75947936', '2845.TW': '86517096'}.get(ticker), 'display_name': name + ' / ' + en, 'allowed_aliases': [name, ticker, ticker.split('.')[0], name + ' / ' + en, raw], 'english_names': [en, raw], 'forbidden_aliases': []}}

@pytest.mark.parametrize(('ticker', 'short_name'), [('3703.TW', 'CONTINENTAL HLDGS CORP'), ('2023.TW', 'YIEH PHUI ENTERPRISE CO'), ('1301.TW', 'FORMOSA PLASTIC'), ('2382.TW', 'QUANTA COMPUTER')])
def test_known_quote_short_names_do_not_reject_consistent_issuer(ticker, short_name):
    from data_fetch.market_sources import mops_presentation as source
    data = valid_data(ticker)
    data['company_identity']['english_names'].append(short_name)
    data['company_identity']['allowed_aliases'].append(short_name)
    assert source.validate_context(data, ticker)
    data['company_identity']['official_ubn'] = '11111111'
    assert not source.validate_context(data, ticker)
    data = valid_data(ticker)
    data['company_identity']['allowed_aliases'].append('UNRELATED COMPANY')
    assert not source.validate_context(data, ticker)

@pytest.mark.parametrize('field,value', [('ticker', '2330.TW'), ('quoteType', 'ETF'), ('company_name', '聯成'), ('company_identity', []), ('company_identity', False)])
def test_conflicting_original_context_is_not_equity_identity(field, value):
    from data_fetch.market_sources.mops_presentation import validate_context
    data = valid_data()
    data[field] = value
    assert not validate_context(data, '1229.TW')

def test_documentless_marker_check_is_total():
    from data_fetch.market_sources.mops_presentation import is_marked
    assert not is_marked({'documents': None}) and (not is_marked({'documents': False}))
