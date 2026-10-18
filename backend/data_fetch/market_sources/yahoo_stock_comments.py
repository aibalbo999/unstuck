"""Signed-out Yahoo quote-board samples; never a population sentiment score.

Use the same public resource observed when expanding the site's comment UI.
No cookie, login, supplied OAuth credential, browser state or JS evaluation.
Quote identity binds its own board to each original PUBLIC/TEXT comment.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
import time

from bs4 import BeautifulSoup
from external_http_client import proxy_url_for_request
from news_record_utils import clean_text, parse_news_datetime
from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError, cooldown_state, remember_failure, scope_key
from source_content_selection import company_aliases
from .yahoo_taiwan_news import _decode_assignment, regional_ticker
from .yahoo_taiwan_transport import curl_stream, comment_url

PROVIDER = 'Yahoo Taiwan stock-board comments'
GUARD = scope_key(PROVIDER, endpoint='yahoo_tw_stock_board')
MAX_COMMENTS = 10
DEADLINE_SECONDS = 15
_UUID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def _now():
    return datetime.now(timezone.utc)


def verified_sample(record, data):
    """Reselection must retain the quote/board/date receipt, including old caches."""
    ticker = regional_ticker(str(data.get('ticker') or ''), data)
    if not ticker or record.get('quote_ticker') != ticker:
        return False
    name, board, mid, stamp = (record.get(k) for k in
                              ('quote_company', 'message_board_id', 'message_id', 'created_at_epoch'))
    body = record.get('text')
    if (not isinstance(name, str) or name.strip().strip('*').casefold() not in company_aliases(data)
            or not isinstance(body, str) or not 5 <= len(body.strip()) <= 5000
            or clean_text(body) != body or re.search(r'https?://|www\.', body, re.I)
            or not isinstance(board, str) or not re.fullmatch(r'finmb_[0-9]{1,16}_lang_zh', board)
            or not isinstance(mid, str) or not _UUID.fullmatch(mid) or type(stamp) is not int
            or record.get('source') != PROVIDER or record.get('issuer_evidence_basis') != 'verified_public_quote_board'
            or record.get('message_namespace') != 'yahoo_tw_finance' or record.get('message_visibility') != 'PUBLIC'
            or record.get('message_type') != 'TEXT' or record.get('message_entity') != 'COMMENT'
            or record.get('publication_time_basis') != 'meta.createdAt'
            or record.get('link') != 'https://tw.stock.yahoo.com/quote/' + ticker
            or record.get('source_document_url') != comment_url(board)
            or any(not isinstance(record.get(k), str) or not re.fullmatch(r'[0-9a-f]{64}', record[k])
                   for k in ('quote_response_sha256', 'response_sha256'))):
        return False
    try:
        return parse_news_datetime(record.get('date')) == datetime.fromtimestamp(stamp, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return False


def quote_board(raw, ticker, data):
    payload, _ = _decode_assignment(raw)
    stores = payload['context']['dispatcher']['stores']
    page, route = stores['PageStore'], stores['RouteStore']['currentNavigate']
    info = stores['QuoteFundamental']['currentSymbolInfo']
    url = 'https://tw.stock.yahoo.com/quote/' + ticker
    market = 'TWO' if ticker.endswith('.TWO') else 'TAI'
    if (page['currentPageName'] != 'quoteOverview' or page['pageData']['url'] != url
            or route['url'] != '/quote/' + ticker or route['externalUrl'] != url
            or route.get('error') is not None or route.get('isComplete') is not True
            or info['symbol'] != ticker or info['strippedSymbol'] != ticker.split('.')[0]
            or info['exchange'] != market or info['holdingType'] != 'EQUITY'):
        raise ValueError('Quote identity mismatch')
    name, board = info['symbolName'], info['messageBoardId']
    if (not isinstance(name, str) or name.strip().strip('*').casefold() not in company_aliases(data)
            or not isinstance(board, str) or not re.fullmatch(r'finmb_[0-9]{1,16}_lang_zh', board)):
        raise ValueError('Quote company/board identity unverified')
    instance = 'commentCanvass-' + board
    state = stores['CanvassStore']['comments'][instance]
    if (state['context'] != board or state['instanceId'] != instance
            or state.get('namespace') != 'yahoo_tw_finance' or state.get('disabled') is not False
            or state.get('error') is not False):
        raise ValueError('Unbound public board')
    soup = BeautifulSoup(raw, 'html.parser')
    if len(soup.select('[id="' + instance + '"]')) != 1:
        raise ValueError('Missing or ambiguous rendered board')
    return {'ticker': ticker, 'company': name, 'board': board, 'url': url,
            'quote_response_sha256': sha256(raw).hexdigest()}


def _json(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ValueError('Duplicate JSON key')
            out[k] = v
        return out
    def constant(_):
        raise ValueError('Nonfinite JSON number')
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 250_000:
        raise ValueError('Comment response exceeds limit')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except RecursionError as exc:
        raise ValueError('Excessive JSON nesting') from exc


def parse_comments(raw, board, *, now):
    payload = _json(raw)
    rows = payload['canvassMessages']
    if (not isinstance(rows, list) or len(rows) > MAX_COMMENTS
            or type(payload.get('messagesLength')) is not int or payload['messagesLength'] != len(rows)):
        raise ValueError('Malformed public comment batch')
    accepted, excluded, reasons, seen = [], [], Counter(), set()
    digest = sha256(raw).hexdigest()
    for row in rows:
        reason = ''
        if not isinstance(row, dict):
            reasons['malformed_comment'] += 1
            excluded.append({'reason': 'malformed_comment'})
            continue
        meta = row.get('meta') if isinstance(row.get('meta'), dict) else {}
        details = row.get('details') if isinstance(row.get('details'), dict) else {}
        stamp, mid, body = meta.get('createdAt'), row.get('messageId'), details.get('userText')
        published = None
        if type(stamp) is int:
            try:
                published = datetime.fromtimestamp(stamp, timezone.utc)
            except (ValueError, OverflowError, OSError):
                pass
        if row.get('contextId') != board['board'] or row.get('namespace') != 'yahoo_tw_finance':
            reason = 'board_mismatch'
        elif meta.get('visibility') != 'PUBLIC' or meta.get('type') != 'TEXT' or meta.get('messageEntity') != 'COMMENT':
            reason = 'not_public_original_text'
        elif not isinstance(mid, str) or not _UUID.fullmatch(mid):
            reason = 'invalid_message_id'
        elif mid in seen:
            reason = 'duplicate_message_id'
        elif published is None:
            reason = 'unknown_date'
        elif published > now:
            reason = 'future'
        elif published < now - timedelta(days=30):
            reason = 'historical'
        elif (not isinstance(body, str) or not 5 <= len(body.strip()) <= 5000
              or '<' in body or re.search(r'https?://|www\.', body, re.I)):
            reason = 'unusable_text'
        if reason:
            reasons[reason] += 1
            excluded.append({'reason': reason, 'message_id': mid if isinstance(mid, str) else None,
                             'created_at': stamp if type(stamp) is int else None})
            continue
        body = clean_text(body)
        if not 5 <= len(body) <= 5000 or re.search(r'https?://|www\.', body, re.I):
            reasons['unusable_text'] += 1
            excluded.append({'reason': 'unusable_text', 'message_id': mid, 'created_at': stamp})
            continue
        seen.add(mid)
        accepted.append({'title': f"{board['company']} ({board['ticker'].split('.')[0]}) 個股留言：{body[:120]}",
            'text': body, 'date': published.isoformat(), 'source': PROVIDER, 'link': board['url'],
            'message_id': mid, 'message_board_id': board['board'], 'created_at_epoch': stamp,
            'message_namespace': 'yahoo_tw_finance', 'message_visibility': 'PUBLIC',
            'message_type': 'TEXT', 'message_entity': 'COMMENT',
            'issuer_evidence_basis': 'verified_public_quote_board', 'publication_time_basis': 'meta.createdAt',
            'quote_ticker': board['ticker'], 'quote_company': board['company'],
            'quote_response_sha256': board['quote_response_sha256'], 'response_sha256': digest,
            'source_document_url': comment_url(board['board']), 'sentiment_assessment': 'not_assessed',
            'coverage_notes': ['個股板前十則近期樣本；平台未提供逐篇分享連結，原件以 message_id 與批次收據識別。',
                               '留言未經獨立查證，不代表社群母體、事實或投資結論。']})
    return accepted, {'raw_count': len(rows), 'usable_count': len(accepted), 'rejected_count': sum(reasons.values()),
                      'rejected_reason_counts': dict(reasons), 'excluded_comments': excluded,
                      'response_sha256': digest, 'sample_limit': MAX_COMMENTS, 'population_coverage': 'not_verified'}


def _download(url, deadline, diagnostic):
    with curl_stream('GET', url, deadline=deadline, diagnostics=diagnostic,
                     proxy=proxy_url_for_request(url, PROVIDER)) as response:
        if response.status_code != 200:
            exc = SourceResponseError({403: 'access_denied', 429: 'rate_limited'}.get(response.status_code,
                                      'server_error' if response.status_code >= 500 else 'http_error'),
                                      status_code=response.status_code)
            exc.response = response
            raise exc
        return response.content


def fetch_yahoo_stock_comments(ticker, data, *, diagnostics=None):
    diagnostics = diagnostics if diagnostics is not None else {}
    resolved = regional_ticker(ticker, data)
    if not resolved or not re.fullmatch(r'[0-9]{4}\.(TW|TWO)', resolved):
        diagnostics.update(status='not_applicable', http_request_sent=False)
        return []
    if cooldown_state(GUARD):
        diagnostics.update(status='cooldown', http_request_sent=False)
        return []
    deadline = time.monotonic() + DEADLINE_SECONDS
    components = {}
    diagnostics.update(provider=PROVIDER, component_statuses=components, cache_hit=False, stale=False)
    try:
        with endpoint_admission(GUARD, timeout_seconds=DEADLINE_SECONDS) as owns:
            if owns is None:
                diagnostics.update(status='single_flight_busy', http_request_sent=False)
                return []
            components['quote'] = {}
            raw = _download('https://tw.stock.yahoo.com/quote/' + resolved, deadline, components['quote'])
            board = quote_board(raw, resolved, data)
            if not owns():
                raise SourceResponseError('lease_lost')
            components['comments'] = {}
            raw = _download(comment_url(board['board']), deadline, components['comments'])
            if time.monotonic() >= deadline or not owns():
                raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost')
            records, selection = parse_comments(raw, board, now=_now())
            if time.monotonic() >= deadline or not owns():
                raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost')
            diagnostics.update(selection, status='records_received' if records else 'no_eligible_records',
                               quote_response_sha256=board['quote_response_sha256'],
                               message_board_id=board['board'], fetched_at_epoch=time.time())
            return records
    except (SourceResponseError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, SourceResponseError) and exc.status_code is not None:
            remember_failure(GUARD, exc)
        diagnostics.update(status='unavailable', error_kind=getattr(exc, 'error_kind', 'parse_error'),
                           http_status=getattr(exc, 'status_code', None))
        return []
