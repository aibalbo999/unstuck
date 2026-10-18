"""Project exact issuer notices from a complete official market original.

Empty selection remains unknown. Reuse never changes the original retrieval
time or becomes a new successful acquisition. Historical individual receipts
continue to be verified by their original contract.
"""
from collections import Counter
from datetime import datetime, timedelta
import math
import re
import time
from urllib.parse import urlencode

from official_response_evidence import archive_response, read_response
from .twse_market_notice_transport import ENDPOINT, MarketNoticeHttp, query_params
from .twse_trading_notices import (
    FIELDS, PROVIDER, SOURCE, SOURCE_TYPE, TAIPEI, _canonical_day,
    _digest, _json, _notice_text, _record, _roc_day,
)

POLICY = 'twse-official-market-trading-notice.v1'


def source_url(now):
    return ENDPOINT + '?' + urlencode({
        'querytype': '1', 'stockNo': '', 'selectType': '',
        'startDate': (now.date() - timedelta(days=30)).strftime('%Y%m%d'),
        'endDate': now.strftime('%Y%m%d'), 'sortKind': 'DATE', 'response': 'json',
    })


def parse_market_rows(raw, url, observed):
    params = query_params(url)
    start, end = [datetime.strptime(params[k], '%Y%m%d').date() for k in ('startDate', 'endDate')]
    if end > observed.date():
        raise ValueError('future market notice query')
    p = _json(raw)
    title = f'公布注意有價證券資訊 ({start.year-1911}年{start:%m月%d日} 至 {end.year-1911}年{end:%m月%d日} 全部上市有價證券)'
    if not isinstance(p, dict) or p.get('stat') != 'OK' or p.get('title') != title or p.get('fields') != FIELDS:
        raise ValueError('market notice envelope unverified')
    echoed = p.get('params')
    if (not isinstance(echoed, dict) or any(echoed.get(k) != v for k, v in params.items())
            or any(echoed.get(k) != v for k, v in {'controller': 'announcement', 'action': 'notice', 'lang': 'zh'}.items())):
        raise ValueError('market notice query not echoed')
    rows = p.get('data')
    if (not isinstance(rows, list) or len(rows) > 5000 or type(p.get('total')) is not int
            or p['total'] != len(rows) or type(p.get('count')) is not int):
        raise ValueError('market notice rows incomplete')
    parsed, seen, securities, groups, sizes = [], set(), set(), [], Counter()
    for index, row in enumerate(rows):
        if (not isinstance(row, list) or len(row) != len(FIELDS) or type(row[0]) is not int
                or not isinstance(row[1], str) or not re.fullmatch(r'[A-Z0-9]{4,6}', row[1])
                or not isinstance(row[2], str) or not 2 <= len(row[2]) <= 80 or row[2].strip() != row[2]
                or not isinstance(row[3], str) or not re.fullmatch(r'[1-9]\d{0,3}', row[3])):
            raise ValueError('market notice row unverified')
        _notice_text(row[4])
        day = _roc_day(row[5])
        if not start <= day <= end or (row[1], day) in seen:
            raise ValueError('market notice date outside query or duplicate')
        if not groups or groups[-1] != day:
            if groups and day >= groups[-1]:
                raise ValueError('market notice date order unverified')
            groups.append(day)
        if row[0] != len(groups):
            raise ValueError('market notice date group unverified')
        seen.add((row[1], day))
        securities.add(row[1])
        sizes[day] += 1
        parsed.append((index, row, day))
    if p['count'] != len(securities) or any(int(row[3]) != sizes[day] for _, row, day in parsed):
        raise ValueError('market notice totals unverified')
    return parsed


def _market_record(ticker, row, day, url, receipt, index):
    result = _record(ticker, row, day, url, receipt, index)
    result['trading_notice_receipt']['policy'] = POLICY
    return result


def verified_market_record(record, data):
    try:
        ticker = str(data.get('ticker') or '').strip().upper()
        proof = record['trading_notice_receipt']
        if (not re.fullmatch(r'[1-9]\d{3}\.TW', ticker) or not isinstance(proof, dict)
                or proof.get('policy') != POLICY or record.get('ticker') != ticker
                or record.get('source') != SOURCE or record.get('source_type') != SOURCE_TYPE
                or record.get('content_truncated') is not False or record.get('publication_date_precision') != 'day'
                or record.get('source_role') != 'exchange_trading_risk_notice'
                or record.get('event_assessment') != 'not_assessed' or proof.get('parsed_content_sha256') != _digest(record)):
            return None
        receipt = proof['original']
        stamp = receipt['retrieved_at']
        if (receipt.get('status') != 'archived' or receipt.get('http_status') != 200
                or receipt.get('http_status_observed') is not True
                or receipt.get('request_method') != 'GET' or receipt.get('response_complete') is not True
                or any(k in receipt for k in ('cache_source', 'source_payload_sha256', 'source_payload_bytes',
                                              'cache_verified_at_epoch', 'cache_fresh_until_epoch'))
                or type(stamp) not in (int, float) or not math.isfinite(stamp) or not 0 < stamp <= time.time()
                or receipt.get('evidence_kind') != 'raw_http_response_bytes'
                or receipt.get('source_url') != record.get('source_document_url')):
            return None
        raw = read_response(receipt)
        if type(receipt.get('raw_response_bytes')) is not int or receipt['raw_response_bytes'] != len(raw):
            return None
        rows = parse_market_rows(raw, receipt['source_url'], datetime.fromtimestamp(stamp, TAIPEI))
        index = proof['row_index']
        if type(index) is not int or not 0 <= index < len(rows):
            return None
        _, row, day = rows[index]
        if row[1] != ticker.split('.')[0]:
            return None
        expected = _market_record(ticker, row, day, receipt['source_url'], receipt, index)
        if _digest(expected) != _digest(record) or expected['link'] != record.get('link'):
            return None
        if 'published_date' in record and _canonical_day(record['published_date']) != day.isoformat():
            return None
        return row[1]
    except (KeyError, ValueError, TypeError, AttributeError, OSError, EOFError, OverflowError, RecursionError):
        return None


def fetch_market_trading_notices(ticker, *, now=None, get=None):
    ticker = str(ticker or '').strip().upper()
    audit = {'source': 'recent_catalysts', 'provider': PROVIDER, 'selection_policy': POLICY,
             'status': 'not_applicable', 'record_count': 0, 'http_request_sent': False,
             'http_request_count': 0, 'cache_hit': False, 'stale': False, 'window_complete': False}
    if not re.fullmatch(r'[1-9]\d{3}\.TW', ticker):
        return [], audit
    now = now or datetime.now(TAIPEI)
    if now.tzinfo is None:
        raise ValueError('market notice cutoff must be timezone-aware')
    now = now.astimezone(TAIPEI)
    deadline = time.monotonic() + 8
    http = MarketNoticeHttp(deadline)
    url = source_url(now)
    audit.update(status='error', source_url=url)
    try:
        raw = (get or http.get)(url)
        component = http.components[0] if http.components else {}
        stamp = component.get('fetched_at_epoch', time.time())
        until = component.get('fresh_until_epoch', stamp + 1800)

        def check_lifetime():
            if time.monotonic() >= deadline:
                raise TimeoutError('market notice acquisition deadline exhausted')
            if (type(stamp) not in (int, float) or not math.isfinite(stamp)
                    or not 0 <= time.time() - stamp < 1800):
                raise ValueError('market notice original expired')
            if (type(until) not in (int, float) or not math.isfinite(until)
                    or not stamp < until <= stamp + 1800 or time.time() >= until):
                raise ValueError('market notice cache admission expired')

        check_lifetime()
        rows = parse_market_rows(raw, url, datetime.fromtimestamp(stamp, TAIPEI))
        selected = [(i, r, day) for i, r, day in rows if r[1] == ticker.split('.')[0]]
        if len({r[2] for _, r, _ in selected}) > 1:
            raise ValueError('market notice issuer names conflict')
        receipt = archive_response(raw, source_url=url, retrieved_at=stamp, http_status=200)
        receipt.update(http_status_observed=True, request_method='GET', response_complete=True)
        if receipt.get('status') != 'archived' or read_response(receipt) != raw:
            raise ValueError('market notice original not preserved')
        audit['raw_response_receipt'] = receipt
        records = [_market_record(ticker, r, day, url, receipt, i) for i, r, day in selected]
        for record in records:
            check_lifetime()
            if not verified_market_record(record, {'ticker': ticker}):
                raise ValueError('market notice saved evidence unverified')
        cached = bool(component.get('cache_hit'))
        requests = http.http_request_count if get is None else 1
        audit.update(status='skipped_fresh_cache' if cached and records else 'success' if records else 'unavailable',
                     record_count=len(records), cache_hit=cached, fetched_at_epoch=stamp, fresh_until_epoch=until,
                     http_request_sent=bool(requests), http_request_count=requests,
                     event_kind='cache_hit' if cached else 'aggregate',
                     coverage_status='issuer_query_complete' if records else 'empty_unknown',
                     quality_status='eligible_evidence' if records else 'no_eligible_evidence',
                     market_original_record_count=len(rows),
                     message='官方注意交易資訊；影響未評估，未涵蓋其他公司事件。' if records else '官方查詢無公告；不推論無風險或無其他事件。')
        check_lifetime()
        return records, audit
    except Exception as exc:
        component = http.components[0] if http.components else {}
        details = getattr(exc, 'diagnostic', {})
        if isinstance(details, dict):
            audit.update(details)
        requests = http.http_request_count if get is None else 1
        if component:
            audit.update(component_statuses={'official_market_notice': component},
                         http_status=component.get('http_status', audit.get('http_status')),
                         fetched_at_epoch=component.get('fetched_at_epoch'))
        audit.update(status='error', record_count=0, cache_hit=False, event_kind='aggregate',
                     error_kind=getattr(exc, 'error_kind', type(exc).__name__),
                     http_request_sent=bool(requests), http_request_count=requests,
                     message='官方注意交易公告未取得完整可驗證原件。')
        return [], audit
