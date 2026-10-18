"""Recover a known official event from one exact month after annual empty results.

This retrieves event metadata/material links only. It never downloads, parses,
or certifies a presentation body, and never retries a failed monthly request.
"""
from datetime import date
import math
import time

from search_provider_runtime import SourceResponseError

MOPS = 'MOPS investor conference'


def request_count(details):
    if details.get('http_request_sent') is False or details.get('cache_hit') is True:
        return 0
    count = details.get('http_request_count')
    if type(count) is int and count >= 0:
        return count
    categories = details.get('category_observations')
    if isinstance(categories, list):
        # Each category fetch is a single bounded WebPro request. Cached
        # categories must not carry a native request into the parent total.
        return sum(row.get('http_request_sent') is True for row in categories if isinstance(row, dict))
    return int(details.get('http_request_sent') is True)


def recover_event_month(ticker, context, diagnostics, *, components,
                        year_observations, use_cache=True, force_refresh=False):
    from official_financials import fetch_mops_investor_conference_events
    from official_financials_webpro_conference import PROVIDER, taiwan_company_symbol

    detail = {'actual_provider': 'MOPS investor conference monthly query',
              'status': 'unavailable', 'http_request_sent': False, 'http_request_count': 0,
              'matched_event_date': None}
    components['MOPS_event_month'] = detail
    diagnostics['component_statuses'] = components
    symbol = taiwan_company_symbol(ticker)
    try:
        day = date.fromisoformat(context['date'])
        if (not symbol or day.isoformat() != context['date'] or day > date.today()
                or context.get('source') != PROVIDER
                or taiwan_company_symbol(context.get('ticker')) != symbol):
            raise ValueError('invalid event identity or date')
    except (KeyError, TypeError, ValueError):
        detail.update(error_kind='invalid_event_identity_or_date')
        return None
    detail.update(source_query_year=day.year, source_query_month=day.month,
                  event_date=day.isoformat())
    try:
        events = fetch_mops_investor_conference_events(
            ticker, year=day.year, month=day.month, limit=3,
            use_cache=use_cache, force_refresh=force_refresh, diagnostics=detail)
    except SourceResponseError as exc:
        detail.update(exc.diagnostic, status='error', error_kind=exc.error_kind)
        return None
    matches = [row for row in events if isinstance(row, dict)
               and taiwan_company_symbol(row.get('ticker')) == symbol
               and row.get('date') == day.isoformat() and row.get('source') == MOPS]
    stamp = detail.get('fetched_at_epoch')
    fresh = (detail.get('stale') is False and type(stamp) in (int, float)
             and math.isfinite(stamp) and 0 <= time.time() - stamp <= 86400)
    native = (fresh and detail.get('status') == 'success'
              and detail.get('http_request_sent') is True and detail.get('cache_hit') is False)
    cached = (fresh and detail.get('status') in {'success', 'skipped_fresh_cache'}
              and detail.get('cache_hit') is True and detail.get('http_request_sent') is False)
    if len(matches) != 1 or not (native or cached):
        detail.update(recovery_status='unverified_or_ambiguous_event', matched_event_date=None)
        return None
    status = 'success' if native else 'skipped_fresh_cache'
    detail.update(status=status, matched_event_date=day.isoformat(),
                  message='MOPS 月頁與 WebPro 所列公司及場次日期一致；僅取得公告與連結。')
    upstream = [*year_observations, components.get('WebPro', {})]
    total_requests = sum(request_count(row) for row in [*upstream, detail])
    diagnostics.update(
        status=status, actual_provider=MOPS, coverage_status='official_event_record',
        cache_hit=cached, stale=False, fetched_at_epoch=stamp,
        http_request_sent=total_requests > 0, http_request_count=total_requests,
        mops_year_observations=year_observations, webpro_month_recovery=True,
        message='optional 外部來源 MOPS 月份法說資訊彙總；原生請求與快取另列觀測。')
    if context.get('recency_comparison_complete') is False:
        # The month confirms this event, not which WebPro category has the
        # latest event. Preserve that uncertainty in the parent assessment.
        diagnostics.update(coverage_status='partial', recency_comparison_complete=False)
    return matches[0]
