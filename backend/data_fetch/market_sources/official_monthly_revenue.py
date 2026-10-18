"""Free exchange monthly snapshots, with original bytes and explicit short coverage.

The current and previous month are observations, not a six-month history, TTM,
or a point-in-time filing record. Missing issuers never imply zero revenue.
"""
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal
import io
import re
import time
from zoneinfo import ZoneInfo

from data_trust import build_source_audit_entry, iso_from_epoch
from official_response_evidence import read_response

TAIPEI = ZoneInfo('Asia/Taipei')
PROVIDER = 'TWSE/MOPS official monthly revenue'
POLICY = 'official-monthly-snapshot-v1'
URLS = {'.TW': 'https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv',
        '.TWO': 'https://mopsfin.twse.com.tw/opendata/t187ap05_O.csv'}
FIELDS = ['出表日期', '資料年月', '公司代號', '公司名稱', '產業別',
          '營業收入-當月營收', '營業收入-上月營收', '營業收入-去年當月營收',
          '營業收入-上月比較增減(%)', '營業收入-去年同月增減(%)',
          '累計營業收入-當月累計營收', '累計營業收入-去年累計營收',
          '累計營業收入-前期比較增減(%)', '備註']
MAX_BYTES = 2_500_000


def _today():
    return datetime.now(TAIPEI).date()


def monthly_url(ticker):
    match = re.fullmatch(r'([0-9]{4,6})(\.TW|\.TWO)', str(ticker or ''))
    if not match:
        raise ValueError('monthly_issuer_or_market_unverified')
    return URLS[match[2]]


def parse_monthly_snapshot(raw, url, today):
    if url not in URLS.values() or not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('monthly_source_unverified')
    text = raw.decode('utf-8-sig', errors='strict')
    if '\ufffd' in text:
        raise ValueError('monthly_encoding_unverified')
    reader = csv.DictReader(io.StringIO(text, newline=''), strict=True)
    rows = list(reader)
    if reader.fieldnames != FIELDS or not 100 <= len(rows) <= 5000:
        raise ValueError('monthly_table_shape_unverified')
    seen = set()
    for row in rows:
        if (None in row or any(v is None for v in row.values())
                or not re.fullmatch(r'[0-9]{4,6}', row['公司代號'])
                or row['公司代號'] in seen or not 1 <= len(row['公司名稱'].strip()) <= 80):
            raise ValueError('monthly_table_identity_unverified')
        seen.add(row['公司代號'])
        issued = row['出表日期']
        period = row['資料年月']
        if not re.fullmatch(r'\d{7}', issued) or not re.fullmatch(r'\d{5}', period):
            raise ValueError('monthly_date_unverified')
        day = date(int(issued[:3]) + 1911, int(issued[3:5]), int(issued[5:]))
        month = date(int(period[:3]) + 1911, int(period[3:]), 1)
        if not today - timedelta(days=45) <= day <= today or month >= day.replace(day=1):
            raise ValueError('monthly_date_future_or_expired')
    return rows


def _amount(value):
    # The filed monthly amount is NT$ thousands. Preserve zero and negatives;
    # empty, nonfinite, boolean-like or malformed values are not observations.
    if not isinstance(value, str) or not re.fullmatch(r'-?\d{1,16}', value):
        raise ValueError('monthly_amount_unverified')
    return Decimal(value)


def select_monthly_records(rows, ticker, today):
    monthly_url(ticker)
    matches = [r for r in rows if r['公司代號'] == ticker.split('.')[0]]
    if not matches:
        return [], {}
    if len(matches) != 1:
        raise ValueError('monthly_issuer_ambiguous')
    row = matches[0]
    period = row['資料年月']
    month = date(int(period[:3]) + 1911, int(period[3:]), 1)
    expected = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    if month != expected:
        raise ValueError('monthly_latest_period_unavailable')
    previous = (month - timedelta(days=1)).replace(day=1)
    values = [_amount(row['營業收入-上月營收']), _amount(row['營業收入-當月營收'])]
    records = [f'{day.year}年{day.month}月: NT${value / Decimal(100_000):.2f}億'
               for day, value in zip((previous, month), values)]
    return records, {'issuer_code': row['公司代號'], 'issuer_name': row['公司名稱'],
                     'observed_month': month.strftime('%Y-%m'), 'table_issued_on': row['出表日期'],
                     'currency': 'NTD', 'filed_unit': 'thousands', 'filed_amounts': [str(v) for v in values],
                     'covered_months': [previous.strftime('%Y-%m'), month.strftime('%Y-%m')],
                     'coverage_status': 'partial_two_adjacent_months', 'window_complete': False,
                     'historical_point_in_time_verified': False, 'notes': row['備註']}


def fetch_official_monthly_revenue(ticker):
    from provider_correlation import source_operation
    with source_operation('monthly_revenue', PROVIDER):
        return _fetch_official_monthly_revenue(ticker)


def _fetch_official_monthly_revenue(ticker):
    from .official_monthly_transport import MonthlyRevenueHttp
    started = time.time()
    http = MonthlyRevenueHttp(time.monotonic() + 8)
    audit = build_source_audit_entry('monthly_revenue', PROVIDER, 'error', record_count=0,
                                     started_at_epoch=started, finished_at_epoch=started)
    audit.update(selection_policy=POLICY, http_request_sent=False, cache_hit=False, stale=False,
                 event_kind='aggregate', window_complete=False)
    try:
        url = monthly_url(ticker)
        audit['source_url'] = url
        raw, receipt = http.get(url)
        rows = parse_monthly_snapshot(raw, url, _today())
        records, coverage = select_monthly_records(rows, ticker, _today())
        if time.monotonic() >= http.deadline or time.time() >= receipt['retrieved_at'] + 1800:
            raise ValueError('monthly_original_deadline_or_TTL_exhausted')
        if read_response(receipt) != raw:
            raise ValueError('monthly_original_unverified')
        if time.monotonic() >= http.deadline or time.time() >= receipt['retrieved_at'] + 1800:
            raise ValueError('monthly_original_deadline_or_TTL_exhausted')
        cached = bool(http.components[0].get('cache_hit'))
        audit.update(coverage, status='skipped_fresh_cache' if cached and records else 'success' if records else 'unavailable',
                     record_count=len(records), source_url=url, fetched_at_epoch=receipt['retrieved_at'],
                     original_receipt=receipt, cache_hit=cached,
                     response_sha256=receipt['raw_response_sha256'], response_bytes=receipt['raw_response_bytes'],
                     parser_version=POLICY,
                     fetched_at=iso_from_epoch(receipt['retrieved_at']),
                     coverage_status=coverage.get('coverage_status', 'issuer_missing_unknown'),
                     event_kind='cache_hit' if cached else 'aggregate',
                     message='官方月營收快照，只有兩個相鄰月份；不是六個月完整歷史或TTM。' if records
                             else '官方快照未列該公司；不推定營收為零。')
        return {'value': records, 'audit': audit}
    except Exception as exc:
        audit.update(error_kind=getattr(exc, 'error_kind', type(exc).__name__),
                     message='官方月營收未取得完整可核對原件。', status='error')
        return {'value': [], 'audit': audit}
    finally:
        component = http.components[0] if http.components else {}
        audit.update(component_statuses={'official_monthly': {
                         'status': 'available' if audit.get('record_count') else 'unavailable',
                         'as_of': audit.get('observed_month'), 'provider': PROVIDER,
                         'cache_hit': bool(component.get('cache_hit')), 'stale': False,
                         'fetched_at_epoch': audit.get('fetched_at_epoch'),
                         'http_status': component.get('http_status'),
                         'response_sha256': audit.get('response_sha256'),
                         'response_bytes': audit.get('response_bytes'), 'parser_version': POLICY,
                         'error_kind': audit.get('error_kind', '')}},
                     transport_components=http.components,
                     http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count,
                     duration_ms=max(0, round((time.time() - started) * 1000)))
        if http.components:
            audit['http_status'] = http.components[0].get('http_status')


def apply_monthly_freshness(data, ticker, audit):
    """Merging a short official snapshot must not renew its original acquisition."""
    from .twse_monthly_history import PROVIDER as HISTORY_PROVIDER
    from .auras_monthly_history import PROVIDER as AURAS_PROVIDER
    from .myson_monthly_history import PROVIDER as MYSON_PROVIDER
    from .finmind_monthly_revenue import PROVIDER as FINMIND_PROVIDER, POLICY as FINMIND_POLICY
    supported = audit.get('provider') in {PROVIDER, HISTORY_PROVIDER, AURAS_PROVIDER, MYSON_PROVIDER}
    supported = supported or (audit.get('provider') == FINMIND_PROVIDER and audit.get('monthly_cache_policy') == FINMIND_POLICY)
    if not supported or audit.get('status') not in {'success', 'skipped_fresh_cache'}:
        return
    from data_freshness import build_source_freshness_entry
    data.setdefault('source_freshness', {})['monthly_revenue'] = build_source_freshness_entry(
        'monthly_revenue', ticker, audit['fetched_at_epoch'], bool(audit.get('cache_hit')),
        now_epoch=time.time(), source_data=data.get('recent_monthly_revenue'))
