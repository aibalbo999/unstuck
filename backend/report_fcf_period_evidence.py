"""Read a dated Yahoo series as a separate reference, never date an info scalar."""
from datetime import date, datetime
from decimal import Decimal
import json
import math
import zlib
from urllib.parse import parse_qs, urlsplit

SCHEMA = 'yahoo-cash-flow-period-review:v1'
FIELDS = ('FreeCashFlow', 'OperatingCashFlow', 'CapitalExpenditure')


def _finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def cash_flow_period_reference(data, review):
    result = {'status': 'unverified', 'raw_scalar_period_verified': False,
        'report_scope_verified': False, 'complete_capex_verified': False,
        'reason': '未保存可核對的期間序列；即期欄位仍不能推定為特定年度或近十二個月。'}
    if not isinstance(review, dict):
        return result
    try:
        ticker = data['ticker']
        if data.get('financial_currency') not in {'TWD', 'USD'}:
            raise ValueError('Financial currency not declared')
        if review.get('schema') != SCHEMA or review.get('ticker') != ticker:
            raise ValueError('Wrong review identity')
        proof = review['series_receipt']
        url = urlsplit(proof['source_url'])
        query = parse_qs(url.query, strict_parsing=True)
        if (url.scheme != 'https' or url.netloc != 'query2.finance.yahoo.com' or url.fragment
                or url.path != '/ws/fundamentals-timeseries/v1/finance/timeseries/'+ticker
                or set(query) != {'symbol', 'type', 'period1', 'period2'}
                or any(len(value) != 1 for value in query.values())
                or query['symbol'] != [ticker] or proof.get('http_status') != 200):
            raise ValueError('Unverified series request')
        requested = query['type'][0].split(',')
        allowed = {prefix+field for prefix in ('annual', 'quarterly', 'trailing') for field in FIELDS}
        if (len(requested) != len(set(requested)) or not set(requested) <= allowed
                or not {f'trailing{field}' for field in FIELDS} <= set(requested)
                or not 0 < int(query['period1'][0]) < int(query['period2'][0])):
            raise ValueError('Unverified series selection')
        at = datetime.fromisoformat(proof['retrieved_at'])
        if at.tzinfo is None:
            raise ValueError('Acquisition timezone missing')
        from official_response_evidence import read_response
        payload = json.loads(read_response(proof))['timeseries']
        if payload.get('error') is not None or not isinstance(payload.get('result'), list):
            raise ValueError('Series not successful')
        series = {}
        seen = set()
        for entry in payload['result']:
            meta = entry['meta']
            types = meta.get('type')
            if (meta.get('symbol') != [ticker] or not isinstance(types, list) or len(types) != 1
                    or types[0] not in requested or types[0] in seen):
                raise ValueError('Ambiguous series identity')
            field = types[0]
            seen.add(field)
            if field not in {f'trailing{name}' for name in FIELDS}:
                continue
            points = entry[field]
            if not isinstance(points, list) or not points or len(points) > 20:
                raise ValueError('Invalid series window')
            dated = {}
            for point in points:
                day = date.fromisoformat(point['asOfDate'])
                value = point['reportedValue']['raw']
                if (point.get('periodType') != 'TTM' or day > at.date() or day.isoformat() in dated
                        or point.get('currencyCode') != data.get('financial_currency')
                        or not _finite(value)):
                    raise ValueError('Period, currency or value not verified')
                dated[day.isoformat()] = value
            series[field] = dated
        if set(series) != {f'trailing{field}' for field in FIELDS}:
            raise ValueError('Incomplete cash flow components')
        days = set.intersection(*(set(values) for values in series.values()))
        if not days:
            raise ValueError('Unaligned cash flow components')
        day = max(days)
        fcf, operating, capex = [series['trailing'+field][day] for field in FIELDS]
        if capex > 0 or Decimal(str(fcf)) != Decimal(str(operating))+Decimal(str(capex)):
            raise ValueError('Cash flow components inconsistent')
        scalar = data.get('free_cash_flow_raw')
        return dict(result, status='dated_series_original_replayed', source='Yahoo Finance cash-flow time series',
            source_kind='secondary_provider', period_type='TTM', period_end=day,
            currency=data['financial_currency'], acquired_at=at.isoformat(),
            free_cash_flow=fcf, operating_cash_flow=operating, capital_expenditure=capex,
            raw_scalar_matches_series=scalar == fcf if _finite(scalar) else None,
            reason='此序列明列截至日與近十二個月，但不是原即期欄位的期間憑據；報表合併範圍與完整資本支出仍未獨立核實，原值及品質警示保留。')
    except (KeyError, TypeError, ValueError, AttributeError, OSError, EOFError, zlib.error):
        result['reason'] = '補充序列的原件、公司、日期、幣別或現金流組成未通過核對；未套用或替換原即期數值。'
        return result
