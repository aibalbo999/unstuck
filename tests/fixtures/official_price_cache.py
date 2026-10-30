"""Synthetic official price bytes for cache-admission tests, never live quotes."""
import json


def observation(ticker='6214.TW', day='2026-10-05', retrieved_at='2026-10-05T14:45:00+00:00'):
    from data_fetch.market_sources.twse_session_observation import DATED_URL, parse_session
    from official_response_evidence import archive_response
    body = json.dumps({'stat': 'OK', 'date': day.replace('-', ''), 'tables': [{
        'fields': ['證券代號', '開盤價', '最高價', '最低價', '收盤價', '成交股數'],
        'data': [[ticker.split('.')[0], '100', '100', '100', '100', '0']],
        'notes': ['本統計資訊含一般、零股、盤後定價、鉅額交易，不含拍賣、標購；synthetic fixture'],
    }]}).encode()
    proof = archive_response(body, source_url=DATED_URL+'?date='+day.replace('-', '')+'&type=ALL&response=json',
                             retrieved_at=retrieved_at, http_status=200)
    return {**parse_session(json.loads(body), day)[ticker.split('.')[0]],
            'ticker': ticker, 'status': 'observed', 'volume_unit': 'shares', 'raw_evidence': proof}
