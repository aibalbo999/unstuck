"""Summarize exact-date category observations without filling missing sessions."""
from collections import defaultdict


def summarize_observations(records, ticker, *, limit, rejected_count=0):
    from data_fetch.institutional_provider import institutional_window_status
    dates = sorted({row['date'] for row in records})[-limit:]
    selected = sorted((dict(row) for row in records if row['date'] in dates),
                      key=lambda row: (row['date'], row['category']))
    totals, daily = defaultdict(int), defaultdict(int)
    for row in selected:
        totals[row['category']] += row['net_buy_shares']
        daily[row['date']] += row['net_buy_shares']
    last_five = sum(daily[day] for day in dates[-5:])
    total = sum(totals.values())
    last_status = institutional_window_status(dates, ticker, 5)
    sources = list(dict.fromkeys(row['source'] for row in selected))
    return {'source': ' + '.join(sources), 'lookback_trading_days': len(dates), 'observed_date_count': len(dates),
            'observation_dates': dates, 'window_basis': 'available_observations; not proof of complete exchange sessions',
            'window_coverage_status': institutional_window_status(dates, ticker, limit),
            'last_5_window_status': last_status, 'rejected_record_count': rejected_count,
            'latest_date': dates[-1] if dates else '', 'daily_category_observations': selected,
            'net_buy_shares_by_category': dict(totals),
            'net_buy_thousand_shares_by_category': {key:round(value/1000,2) for key,value in totals.items()},
            'total_net_buy_shares': total, 'total_net_buy_thousand_shares': round(total/1000,2),
            'last_5_trading_days_net_buy_thousand_shares': round(last_five/1000,2) if last_status=='complete' else None,
            'trend': 'accumulation' if total>0 and last_five>0 else 'distribution' if total<0 and last_five<0 else 'mixed',
            'daily_total_net_buy_last_10': [{'date':day,'net_buy_thousand_shares':round(daily[day]/1000,2)}
                                          for day in dates[-10:]]}


# Only these display projections may be repaired on a warm primary result.
_THOUSAND_SHARE_FIELDS = {
    'net_buy_thousand_shares_by_category', 'total_net_buy_thousand_shares',
    'last_5_trading_days_net_buy_thousand_shares', 'daily_total_net_buy_last_10',
}
_PRIMARY_SOURCE = 'FinMind TaiwanStockInstitutionalInvestorsBuySell'
_SDK_CATEGORIES = {
    'Foreign_Investor': 'foreign', 'Foreign_Dealer_Self': 'foreign',
    'Investment_Trust': 'investment_trust',
    'Dealer_self': 'dealer', 'Dealer_Hedging': 'dealer',
}
_SDK_MAX_BYTES = 512 * 1024


def rebuild_cached_primary_summary(value, ticker, *, now_epoch, limit):
    """Repair display projections only after replaying a bounded archived SDK body.

    Keep the saved observations, provenance and acquisition metadata untouched.
    A missing or inconsistent proof leaves the original value for normal gates;
    this function never fetches, writes a cache or promotes a partial window.
    """
    import json
    import math
    import zlib
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    from official_institutional_source import expected_sessions
    from official_response_evidence import read_response

    try:
        if (not isinstance(value, dict) or type(limit) is not int or limit != 30
                or value.get('source') != _PRIMARY_SOURCE
                or type(value.get('rejected_record_count')) is not int
                or value['rejected_record_count'] != 0
                or value.get('window_coverage_status') != 'complete'
                or value.get('last_5_window_status') != 'complete'
                or value.get('coverage_status') not in (None, 'available')
                or value.get('stale') or value.get('error_kind')
                or (value.get('official_recovery') or {}).get('conflicts')):
            return value
        days = expected_sessions(ticker, now_epoch, limit)
        records = value.get('daily_category_observations')
        if len(days) != limit or not isinstance(records, list) or len(records) != 3 * limit:
            return value
        required = {(day, category) for day in days
                    for category in ('foreign', 'investment_trust', 'dealer')}
        saved = {}
        for row in records:
            if (not isinstance(row, dict) or row.get('unit') != 'shares'
                    or row.get('source') != _PRIMARY_SOURCE
                    or type(row.get('net_buy_shares')) is not int):
                return value
            key = (row.get('date'), row.get('category'))
            if key not in required or key in saved:
                return value
            saved[key] = row['net_buy_shares']
        rebuilt = summarize_observations(records, ticker, limit=limit,
                                          rejected_count=value['rejected_record_count'])
        # Never use reconstruction to change whole-share facts or window status.
        for key, item in rebuilt.items():
            if key not in _THOUSAND_SHARE_FIELDS | {'source', 'daily_category_observations'}:
                if json.dumps(value.get(key), sort_keys=True, allow_nan=False) != json.dumps(item, sort_keys=True, allow_nan=False):
                    return value
        if all(value.get(key) == rebuilt[key] for key in _THOUSAND_SHARE_FIELDS):
            return value
        proof = value.get('source_provenance')
        if (not isinstance(proof, dict) or proof.get('status') != 'archived'
                or proof.get('source_url') != 'https://api.finmindtrade.com/api/v4/data'
                or proof.get('evidence_kind') != 'sdk_dataframe_json_not_raw_http'
                or proof.get('http_status') is not None
                or type(proof.get('raw_response_bytes')) is not int
                or not 0 < proof['raw_response_bytes'] <= _SDK_MAX_BYTES):
            return value
        query = proof.get('query') or {}
        code = ticker.split('.')[0]
        if query.get('dataset') != 'TaiwanStockInstitutionalInvestorsBuySell' or query.get('data_id') != code:
            return value
        start = date.fromisoformat(query['start_date'])
        query_end = date.fromisoformat(query['end_date'])
        acquired = datetime.fromisoformat(proof['retrieved_at'])
        if (acquired.tzinfo is None or not math.isfinite(acquired.timestamp())
                or acquired.timestamp() > now_epoch or start.isoformat() > min(days)
                or query_end.isoformat() != days[0]
                or query_end < start or query_end > acquired.astimezone(ZoneInfo('Asia/Taipei')).date()):
            return value
        end = acquired.astimezone(ZoneInfo('Asia/Taipei')).date()
        body = read_response(proof, max_bytes=_SDK_MAX_BYTES)
        if len(body) != proof['raw_response_bytes']:
            return value
        original = json.loads(body)
        if not isinstance(original, list) or not 1 <= len(original) <= 2000:
            return value
        replayed, seen = defaultdict(int), set()
        for row in original:
            if not isinstance(row, dict) or str(row.get('stock_id', '')).strip() != code:
                return value
            observed = date.fromisoformat(row['date'])
            name = row['name']
            if (observed.isoformat() != row['date'] or not start <= observed <= end
                    or name not in _SDK_CATEGORIES or (row['date'], name) in seen):
                return value
            seen.add((row['date'], name))
            numbers = []
            for key in ('buy', 'sell'):
                number = row[key]
                if (type(number) not in (int, float) or not math.isfinite(number)
                        or number < 0 or int(number) != number):
                    return value
                numbers.append(int(number))
            day_key = (row['date'], _SDK_CATEGORIES[name])
            replayed[day_key] += numbers[0] - numbers[1]
        selected = {key: number for key, number in replayed.items() if key[0] in days}
        if selected != saved:
            return value
        # Shallow copy intentionally keeps the exact original record array/order.
        return {**value, **{key: rebuilt[key] for key in _THOUSAND_SHARE_FIELDS}}
    except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError, OverflowError,
            RecursionError, zlib.error):
        return value
