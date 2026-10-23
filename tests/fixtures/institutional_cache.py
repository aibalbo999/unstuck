"""Synthetic institutional observations; never a live acquisition receipt."""
from copy import deepcopy
from datetime import datetime
import json

NOW = datetime.fromisoformat('2026-10-05T23:00:00+08:00').timestamp()


def observed():
    from config import INSTITUTIONAL_LOOKBACK_DAYS
    from institutional_observations import summarize_observations
    from official_institutional_source import TWSE_FIELDS, _parse_report, _url, expected_sessions
    from official_response_evidence import archive_response
    from report_source_admission import institutional_admission

    # Every quantity is invented for this fixture, including the company name.
    row = ['6214', 'Synthetic fixture', 200, 100, 100, 20, 10, 10,
           40, 20, 20, 30, 25, 15, 10, 35, 15, 20, 160]
    body = json.dumps({'stat': 'OK', 'date': '20261005', 'fields': TWSE_FIELDS,
                       'hints': '單位：股；synthetic test fixture', 'data': [row]}).encode()
    parsed = _parse_report(json.loads(body), 'TWSE', '2026-10-05')['rows']['6214']
    days = expected_sessions('6214.TW', NOW, INSTITUTIONAL_LOOKBACK_DAYS)
    records = [{'date': day, 'category': category,
                'net_buy_shares': parsed[category] if day == days[0] else 100,
                'unit': 'shares',
                'source': 'TWSE T86' if day == days[0] else 'FinMind TaiwanStockInstitutionalInvestorsBuySell'}
               for day in days for category in ('foreign', 'investment_trust', 'dealer')]
    value = summarize_observations(records, '6214.TW', limit=INSTITUTIONAL_LOOKBACK_DAYS)
    proof = archive_response(body, source_url=_url('TWSE', days[0]),
                             retrieved_at='2026-10-05T14:45:00+00:00', http_status=200)
    value.update(latest_official_observation={'ticker': '6214.TW', 'market': 'TWSE',
                  'date': days[0], 'raw_evidence': proof}, stale=False, cache_hit=False,
                  fetched_at_epoch=NOW - 10, coverage_status='available')
    value['latest_session_admission'] = institutional_admission(value, days[0])
    assert value['latest_session_admission']['eligible']
    audit = {'source': 'institutional_trading', 'provider': 'FinMind', 'status': 'success',
             'record_count': 10, 'fetched_at_epoch': NOW - 10, 'cache_hit': False,
             'stale': False, 'event_kind': 'aggregate', 'http_request_sent': True,
             'coverage_status': 'available',
             'latest_session_admission': deepcopy(value['latest_session_admission'])}
    return value, audit
