"""Synthetic market rows for evidence-gap contract tests."""
def daily():
    bar = {'date': '2026-10-02', 'open': 67., 'high': 69.6, 'low': 66.8,
           'close': 68.3, 'volume': 1000.}
    return {'bars': [bar], 'source': 'provider',
        'provider_raw_observation': {**bar, 'ticker': '1301.TW', 'volume_unit': 'shares'},
        'official_observation': {**bar, 'ticker': '1301.TW', 'status': 'observed', 'volume_unit': 'shares'}}


def official_payload():
    return {'stat': 'OK', 'date': '20261002', 'tables': [{
        'fields': ['證券代號', '開盤價', '最高價', '最低價', '收盤價', '成交股數'],
        'data': [['1301', '67', '69.6', '66.8', '68.3', '33,115,055']]}]}


def tpex_payload():
    return {'stat': 'ok', 'code': '3324', 'date': '20261001', 'flagField': '張數',
        'tables': [{'title': '個股日成交資訊', 'date': '20261001',
            'fields': ['日 期', '開盤', '最高', '最低', '收盤', '成交張數'],
            'notes': ['以上資料不含上櫃股票鉅額交易'],
            'data': [['115/10/07', '1540', '1550', '1485', '1525', '2721']]}]}
