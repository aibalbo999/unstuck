"""Share monthly observations without renewing their acquisition or provider quota."""
from copy import deepcopy
from datetime import datetime, timedelta
import math
import time
from zoneinfo import ZoneInfo

from data_trust import build_source_audit_entry, iso_from_epoch
from provider_correlation import source_operation
from shared_provider_cache import shared_fetch

from .monthly_revenue_rows import format_monthly_revenue_rows

PROVIDER = 'FinMind TaiwanStockMonthRevenue'
POLICY = 'finmind-monthly-observation-v1'
TTL = 1800


class MonthlyObservationUnavailable(Exception):
    """The actual unsuccessful audit is returned to the caller, never cached as data."""


def _valid_observation(value, meta, ticker):
    stamp = meta.get('fetched_at_epoch')
    return (isinstance(value, dict) and value.get('policy') == POLICY
            and value.get('ticker') == ticker and isinstance(value.get('records'), list)
            and 0 < len(value['records']) <= 6
            and all(isinstance(row, str) and 0 < len(row) <= 160 for row in value['records'])
            and type(stamp) in (int, float) and math.isfinite(stamp)
            and 0 <= time.time() - stamp < TTL and meta.get('stale') is False
            and not meta.get('error_kind'))


def fetch_monthly_records(ticker, loader_cls, *, audit_fetch, force_refresh=False):
    # The calendar-month namespace prevents a warm September query from crossing
    # into October. The short TTL still permits same-month amendments to arrive.
    month = datetime.fromtimestamp(time.time(), ZoneInfo('Asia/Taipei')).strftime('%Y-%m')
    key = f'{POLICY}:{ticker}:{month}'
    started = time.time()
    actual = None

    def acquire():
        nonlocal actual

        def sdk_records():
            if loader_cls is None:
                return []
            frame = loader_cls().taiwan_stock_month_revenue(
                stock_id=ticker.split('.')[0],
                start_date=(datetime.now() - timedelta(days=240)).strftime('%Y-%m-%d'))
            return format_monthly_revenue_rows(frame)

        actual = audit_fetch('monthly_revenue', PROVIDER, sdk_records, default=[],
                             unavailable_message='FinMind 月營收未回傳可用資料。')
        if actual.get('audit', {}).get('status') != 'success' or not actual.get('value'):
            raise MonthlyObservationUnavailable()
        return {'policy': POLICY, 'ticker': ticker, 'records': actual['value']}

    with source_operation('monthly_revenue', PROVIDER):
        value, meta = shared_fetch(key, acquire, freshness_seconds=TTL,
                                   retention_seconds=TTL, error_retry_seconds=60,
                                   lock_wait_seconds=2, force_refresh=force_refresh)
        # A malformed cache is not an observation. Recovery still passes
        # through the original provider circuit and rate-limit admission.
        if actual is None and meta.get('cache_hit') and not meta.get('error_kind') and not _valid_observation(value, meta, ticker):
            value, meta = shared_fetch(key, acquire, freshness_seconds=TTL,
                                       retention_seconds=TTL, error_retry_seconds=60,
                                       lock_wait_seconds=2, force_refresh=True)

        if actual is not None:
            result = deepcopy(actual)
            audit = result['audit']
            audit['monthly_cache_policy'] = POLICY
            if audit.get('status') == 'success' and result.get('value'):
                stamp = meta.get('fetched_at_epoch') or time.time()
                audit.update(fetched_at_epoch=stamp, fetched_at=iso_from_epoch(stamp),
                             cache_hit=False, stale=False)
            return result

        if _valid_observation(value, meta, ticker):
            stamp = meta['fetched_at_epoch']
            audit = build_source_audit_entry(
                'monthly_revenue', PROVIDER, 'skipped_fresh_cache',
                fetched_at_epoch=stamp, started_at_epoch=started,
                finished_at_epoch=time.time(), record_count=len(value['records']),
                cache_hit=True, stale=False,
                message='沿用尚新鮮的月營收觀測，保留原取得時間；本次未呼叫FinMind。')
            audit.update(monthly_cache_policy=POLICY, fetched_at_epoch=stamp,
                         event_kind='cache_hit', http_request_sent=False,
                         http_request_count=0, provider_attempt_count=0, provider_attempts=[])
            return {'value': deepcopy(value['records']), 'audit': audit}

        # Failed forced reads never turn retained data into a fresh success.
        audit = build_source_audit_entry(
            'monthly_revenue', PROVIDER, 'unavailable', started_at_epoch=started,
            finished_at_epoch=time.time(), record_count=0, cache_hit=False, stale=False,
            error_kind=str(meta.get('error_kind') or 'MonthlyObservationUnavailable'),
            message='月營收來源等待重試或共用抓取完成；未取得新資料，保留官方備援。')
        audit.update(monthly_cache_policy=POLICY, event_kind='local_block',
                     provider_admission_blocked=True, http_request_sent=False,
                     http_request_count=0, provider_attempt_count=0, provider_attempts=[],
                     retry_after_epoch=meta.get('retry_after_epoch'))
        return {'value': [], 'audit': audit}
