"""Bounded Yahoo Taiwan RSS-first news with quote-page fallback."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import time
from urllib.parse import urlsplit

import httpx
import feedparser

from external_http_client import proxy_url_for_request
from .yahoo_taiwan_transport import curl_stream
from news_record_utils import clean_text, news_record as _news_record, parse_news_datetime
from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError, cooldown_state, remember_failure, scope_key, observe_http_response

PROVIDER = 'Yahoo Finance news'
GUARD_KEY = scope_key(PROVIDER, endpoint='yahoo_tw_quote_news')
TRANSPORT = 'yahoo_taiwan_quote_news_html'
PARSER_VERSION = 'yahoo-tw-quote-news-v1'
RSS_TRANSPORT = 'yahoo_taiwan_stock_rss'
RSS_PARSER_VERSION = 'yahoo-tw-stock-rss-v1'
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_OBJECT_CHARS = 1_000_000
MAX_DEPTH = 64
MAX_TOKENS = 50_000
MAX_STREAM_SLOTS = 200
MAX_ARTICLES = 10
DEADLINE_SECONDS = 12.0
_TICKER = re.compile(r'^(\d{4,6})\.(TW|TWO)$')


def regional_ticker(request_ticker: str, data: dict) -> str | None:
    """Only resolved Taiwan equities opt in; other legacy routes stay unchanged."""
    ticker = str(data.get('ticker') or request_ticker).strip().upper()
    match = _TICKER.fullmatch(ticker)
    request = str(request_ticker or '').strip().upper()
    if (not match or request not in {ticker, match[1]}
            or data.get('quote_type') != 'EQUITY'
            or data.get('exchange') != ('TAI' if match[2] == 'TW' else 'TWO')):
        return None
    identity = data.get('company_identity')
    if isinstance(identity, dict):
        if identity.get('ticker') and identity['ticker'] != ticker:
            return None
        if identity.get('stock_id') and str(identity['stock_id']) != match[1]:
            return None
        if identity.get('instrument_type') and identity['instrument_type'] != 'EQUITY':
            return None
    return ticker


def source_url(ticker: str) -> str:
    match = _TICKER.fullmatch(ticker)
    if not match:
        raise ValueError('Unresolved Taiwan equity')
    return f'https://tw.stock.yahoo.com/quote/{match[1]}/news'


def rss_source_url(ticker: str) -> str:
    if not _TICKER.fullmatch(str(ticker or '').strip().upper()):
        raise ValueError('Unresolved Taiwan equity')
    return f'https://tw.stock.yahoo.com/rss?s={ticker.strip().upper()}'


def parse_yahoo_taiwan_rss(raw: bytes, ticker: str, *, diagnostics: dict) -> list[dict]:
    """Parse Yahoo's official ticker-bound RSS feed without following article links."""
    if not isinstance(raw, bytes) or len(raw) > MAX_BODY_BYTES:
        raise ValueError('RSS response exceeds limit')
    feed = feedparser.parse(raw)
    if getattr(feed, 'bozo', False) or not str(getattr(feed, 'version', '')).startswith('rss'):
        raise ValueError('Invalid Yahoo Taiwan RSS feed')
    entries = list(getattr(feed, 'entries', []) or [])
    if len(entries) > MAX_STREAM_SLOTS:
        raise ValueError('Excessive Yahoo Taiwan RSS items')
    url = rss_source_url(ticker)
    records, rejected, originals = [], [], {}
    for index, entry in enumerate(entries[:MAX_ARTICLES]):
        path = f'$.rss.channel.item[{index}]'
        original = {
            'title': entry.get('title'), 'link': entry.get('link'),
            'published': entry.get('published'), 'source': entry.get('source'),
            'summary': entry.get('summary'), 'id': entry.get('id'),
        }
        originals[path] = original
        title = clean_text(original['title'])
        link = original['link']
        try:
            parsed_link = urlsplit(link) if isinstance(link, str) else None
            valid_link = (parsed_link is not None and parsed_link.scheme == 'https'
                          and parsed_link.hostname == 'tw.stock.yahoo.com'
                          and parsed_link.path.startswith('/news/')
                          and not parsed_link.username and not parsed_link.password
                          and parsed_link.port in (None, 443))
        except ValueError:
            valid_link = False
        if not title:
            rejected.append({'reason': 'invalid_title', 'quality_affecting': True,
                             'source_json_path': path, 'record': original})
            continue
        if not valid_link:
            rejected.append({'reason': 'invalid_link', 'quality_affecting': True,
                             'source_json_path': path, 'record': original})
            continue
        source = original['source']
        if isinstance(source, dict):
            source = source.get('title')
        if isinstance(source, list):
            source = source[0].get('title') if source and isinstance(source[0], dict) else ''
        published = entry.get('published_parsed') or original['published'] or ''
        item = _news_record(
            title=title, link=link, published_date=published,
            source=clean_text(source) or 'Yahoo Finance Taiwan RSS',
            summary=clean_text(original['summary'])[:280],
        )
        if item is None:
            rejected.append({'reason': 'invalid_record', 'quality_affecting': True,
                             'source_json_path': path, 'record': original})
            continue
        item.update(
            # Yahoo's RSS terms require preserving each headline as supplied.
            title=original['title'],
            date=item['published_date'], source_type='yahoo_taiwan_news',
            aggregator_source='Yahoo股市',
            source_record_id=str(original.get('id') or ''), source_json_path=path,
            page_ticker=ticker, source_page_url=url,
        )
        records.append(item)
    diagnostics.update(
        parser_version=RSS_PARSER_VERSION, rss_item_count=len(entries),
        candidate_count=min(len(entries), MAX_ARTICLES),
        capacity_excluded_count=max(0, len(entries) - MAX_ARTICLES),
        _candidate_originals=originals, _parser_rejections=rejected,
        _non_evidence_archive=[],
    )
    return records


def _has_recent_rss_records(records: list[dict]) -> bool:
    from config import CATALYST_LOOKBACK_DAYS
    from news_freshness_policy import news_cutoff

    cutoff = news_cutoff()
    lower = cutoff.timestamp() - max(1, int(CATALYST_LOOKBACK_DAYS)) * 86400
    for record in records:
        published = parse_news_datetime(record.get('date'))
        if published is not None and lower <= published.timestamp() <= cutoff.timestamp():
            return True
    return False


def _component_details(details: dict) -> dict:
    return {key: value for key, value in details.items() if not key.startswith('_')}


def _decode_assignment(raw: bytes) -> tuple[dict, dict]:
    """Linear scan of one bounded object; only bare undefined values become null."""
    if len(raw) > MAX_BODY_BYTES:
        raise ValueError('Response exceeds limit')
    text = raw.decode('utf-8')
    matches = list(re.finditer(r'root\.App\.main\s*=\s*', text))
    if len(matches) != 1:
        raise ValueError('Missing or ambiguous assignment')
    start = matches[0].end()
    if text[start:start + 1] != '{':
        raise ValueError('Expected object')
    output, stack = [], []
    inside = escaped = False
    previous = ''
    tokens = replacements = 0
    i = start
    while i < min(len(text), start + MAX_OBJECT_CHARS):
        char = text[i]
        if inside:
            output.append(char)
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                inside = False
                previous = '"'
            i += 1
            continue
        if char == '"':
            inside = True
            tokens += 1
        elif char in '{[':
            stack.append(char)
            tokens += 1
            if len(stack) > MAX_DEPTH:
                raise ValueError('Excessive nesting')
        elif char in '}]':
            if not stack or stack.pop() != {'}': '{', ']': '['}[char]:
                raise ValueError('Unbalanced object')
        elif text.startswith('undefined', i):
            after = i + 9
            while after < len(text) and text[after] in ' \r\n\t':
                after += 1
            if previous not in (':', '[', ',') or text[after:after + 1] not in (',', '}', ']'):
                raise ValueError('Unsupported undefined expression')
            output.append('null')
            previous = 'l'
            replacements += 1
            tokens += 1
            i += 9
            continue
        elif char in ',:':
            tokens += 1
        if tokens > MAX_TOKENS:
            raise ValueError('Excessive token count')
        output.append(char)
        if not char.isspace():
            previous = char
        i += 1
        if not stack:
            suffix = i
            while suffix < len(text) and text[suffix] in ' \r\n\t':
                suffix += 1
            if text[suffix:suffix + 1] != ';':
                raise ValueError('Unsupported assignment suffix')
            def unique_pairs(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError('Duplicate JSON key')
                    result[key] = value
                return result
            def reject_constant(_value):
                raise ValueError('Nonfinite JSON number')
            value = json.loads(''.join(output), object_pairs_hook=unique_pairs,
                               parse_constant=reject_constant)
            return value, {'undefined_value_count': replacements, 'assignment_chars': i - start}
    raise ValueError('Incomplete or excessive assignment')


def _selected_stream(payload: dict, ticker: str) -> tuple[list, dict]:
    """Bind one page component to one store; never gather news recursively."""
    stock_id, market = _TICKER.fullmatch(ticker).groups()
    stores = payload['context']['dispatcher']['stores']
    page = stores['PageStore']
    canonical_url = f'https://tw.stock.yahoo.com/quote/{ticker}/news'
    info = stores['QuoteFundamental']['currentSymbolInfo']
    if (page['currentPageName'] != 'quoteNews' or page['pageData']['url'] != canonical_url
            or info['symbol'] != ticker or info['strippedSymbol'] != stock_id
            or info['exchange'] != ('TAI' if market == 'TW' else 'TWO')
            or info['holdingType'] != 'EQUITY'):
        raise ValueError('Quote identity mismatch')
    route = stores['RouteStore']['currentNavigate']
    paths = {f'/quote/{stock_id}/news', f'/quote/{ticker}/news'}
    if (route['url'] not in paths or route['externalUrl'] not in {source_url(ticker), canonical_url}
            or route.get('error') is not None or route.get('isComplete') is not True):
        raise ValueError('Unexpected quote route')
    candidates = []
    for key, group in page['compositeConfig'].items():
        if not re.fullmatch(r'main-\d+-QuoteNews', key) or not isinstance(group, dict):
            continue
        for index, component in enumerate(group.get('components', [])):
            if isinstance(component, dict) and component.get('name') == 'Stream':
                candidates.append((key, index, component))
    if len(candidates) != 1:
        raise ValueError('Missing or ambiguous quote news component')
    component_key, component_index, component = candidates[0]
    config = component['config']
    symbols = config['ncpParams']['query']['s']
    if (component['category'] != 'CUSTOM:NEWS' or config['category'] != 'CUSTOM:NEWS'
            or config['ui']['view'] != 'mega' or not isinstance(symbols, list)
            or ticker not in symbols or any(symbol not in {stock_id + '.TW', stock_id + '.TWO'} for symbol in symbols)):
        raise ValueError('Unbound quote stream')
    stream_key = component['category'] + '.' + config['ui']['view']
    stream = stores['StreamStore']['streams'][stream_key]['data']
    slots = stream['stream_items']
    if (stream['category'] != component['category'] or stream['view'] != config['ui']['view']
            or not isinstance(slots, list) or len(slots) > MAX_STREAM_SLOTS):
        raise ValueError('Unknown or excessive news stream')
    return slots, {
        'page_ticker': ticker, 'page_exchange': info['exchange'], 'page_instrument_type': info['holdingType'],
        'canonical_page_url': canonical_url, 'stream_key': stream_key,
        'component_path': f"$.context.dispatcher.stores.PageStore.compositeConfig['{component_key}'].components[{component_index}]",
        'stream_items_path': f"$.context.dispatcher.stores.StreamStore.streams['{stream_key}'].data.stream_items",
    }


def parse_yahoo_taiwan_news(raw: bytes, ticker: str, *, diagnostics: dict) -> list[dict]:
    payload, decoding = _decode_assignment(raw)
    slots, binding = _selected_stream(payload, ticker)
    records, rejected, excluded, originals = [], [], [], {}
    candidates = observed = 0
    for index, row in enumerate(slots):
        path = binding['stream_items_path'] + f'[{index}]'
        provenance = {'source_json_path': path, 'record': deepcopy(row)}
        if isinstance(row, dict) and row.get('type') == 'ad':
            excluded.append({'reason': 'non_article_ad_slot', 'quality_affecting': False, **provenance})
            continue
        observed += 1
        # Unknown/noneligible article slots consume the same budget before validation.
        if candidates >= MAX_ARTICLES:
            excluded.append({'reason': 'capacity_excluded', 'quality_affecting': False, **provenance})
            continue
        candidates += 1
        originals[path] = deepcopy(row)
        reason = ''
        if not isinstance(row, dict) or row.get('type') != 'article':
            reason = 'invalid_article_schema'
        elif row.get('is_eligible') is not True or any(row.get(k) for k in ('isTaboolaAd', 'isGamAd', 'isPromoAd')):
            reason = 'article_unavailable'
        elif not isinstance(row.get('title'), str) or not clean_text(row['title']).strip():
            reason = 'invalid_title'
        elif not isinstance(row.get('publisher'), str) or not clean_text(row['publisher']).strip():
            reason = 'unknown_publisher'
        elif row.get('summary') is not None and not isinstance(row['summary'], str):
            reason = 'invalid_summary'
        else:
            link = row.get('link') or row.get('url')
            try:
                parsed = urlsplit(link) if isinstance(link, str) else None
                if (parsed is None or parsed.scheme != 'https' or parsed.hostname != 'tw.stock.yahoo.com'
                        or not parsed.path.startswith('/news/') or parsed.username or parsed.password
                        or parsed.port not in (None, 443)
                        or (row.get('url') and row.get('link') and row['url'] != row['link'])):
                    reason = 'invalid_link'
            except ValueError:
                reason = 'invalid_link'
        if reason:
            rejected.append({'reason': reason, 'quality_affecting': True, **provenance})
            continue
        date = ''
        stamp = row.get('pubtime')
        if isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and math.isfinite(stamp):
            try:
                date = datetime.fromtimestamp(stamp / 1000, timezone.utc).isoformat()
            except (ValueError, OSError, OverflowError):
                pass
        records.append({
            'date': date, 'title': clean_text(row['title']), 'summary': clean_text(row.get('summary') or '')[:280],
            'source': clean_text(row['publisher']), 'link': link, 'source_type': 'yahoo_taiwan_news',
            'source_record_id': row.get('id') if isinstance(row.get('id'), str) else '',
            'source_json_path': path, 'publication_time_original_ms': stamp,
            'page_ticker': ticker, 'source_page_url': source_url(ticker),
        })
    diagnostics.update(decoding, **binding, candidate_count=candidates, observed_article_slots=observed,
                       non_article_ad_count=sum(r['reason'] == 'non_article_ad_slot' for r in excluded),
                       capacity_excluded_count=max(0, observed - candidates),
                       _candidate_originals=originals, _parser_rejections=rejected, _non_evidence_archive=excluded)
    return records


def fetch_yahoo_taiwan_news(ticker: str, *, diagnostics: dict) -> list[dict]:
    """Prefer Yahoo's public ticker RSS; use the quote page if it has no recent items."""
    diagnostics.update(transport=RSS_TRANSPORT, source_url=rss_source_url(ticker),
                       actual_provider='Yahoo Finance Taiwan RSS',
                       parser_version=RSS_PARSER_VERSION, http_request_sent=False,
                       http_request_count=0)
    deadline = time.monotonic() + DEADLINE_SECONDS
    with endpoint_admission(GUARD_KEY, timeout_seconds=DEADLINE_SECONDS) as owns:
        if owns is None or not owns():
            diagnostics.update(error_kind='single_flight_busy', http_status=None)
            raise SourceResponseError('single_flight_busy', parser_version=PARSER_VERSION)
        blocked = cooldown_state(GUARD_KEY)
        if blocked:
            diagnostics.update(error_kind='cooldown', http_status=None,
                               prior_http_status=blocked.get('http_status'),
                               cooldown_reason=blocked.get('error_kind'), retry_at=blocked['retry_at'],
                               retry_after_seconds=max(0, blocked['retry_at'] - time.time()))
            # A historical 429 is not a new HTTP response or a new cooldown start.
            raise SourceResponseError('cooldown', parser_version=PARSER_VERSION)
        components = []
        request_count = 0
        try:
            rss_diagnostics = {}
            rss_error = None
            try:
                rss_records = _fetch_rss(ticker, rss_diagnostics, deadline, owns)
            except SourceResponseError as error:
                rss_error = error
                rss_diagnostics.update(error.diagnostic, status='error', error_kind=error.error_kind)
                rss_records = []
            request_count += int(rss_diagnostics.get('http_request_sent') is True)
            components.append({'provider': 'Yahoo Finance Taiwan ticker RSS',
                               'status': 'error' if rss_error else 'success' if rss_records else 'valid_empty',
                               'record_count': len(rss_records), **_component_details(rss_diagnostics)})
            # Only a complete-but-unusable RSS representation is worth trying
            # through the alternate page route. A transport/timeout/server
            # failure must not double the load or turn one failed fetch into
            # two provider attempts. A missing RSS route (404) may still fall
            # back while the established quote page remains available.
            may_fallback_after_rss_error = bool(
                rss_error
                and (rss_error.error_kind == 'parse_error'
                     or (rss_error.error_kind == 'http_error' and rss_error.status_code == 404))
            )
            if rss_error and not may_fallback_after_rss_error:
                diagnostics.update(rss_diagnostics, component_statuses=components,
                                   http_request_count=request_count,
                                   http_request_sent=request_count > 0,
                                   actual_provider='Yahoo Finance Taiwan RSS')
                raise rss_error
            if rss_records and _has_recent_rss_records(rss_records):
                diagnostics.update(rss_diagnostics, component_statuses=components,
                                   http_request_count=request_count,
                                   http_request_sent=request_count > 0,
                                   actual_provider='Yahoo Finance Taiwan RSS',
                                   transport=RSS_TRANSPORT, source_url=rss_source_url(ticker),
                                   parser_version=RSS_PARSER_VERSION,
                                   coverage_status='recent_ticker_rss_records')
                return rss_records

            page_diagnostics = {}
            try:
                page_records = _fetch_page(ticker, page_diagnostics, deadline, owns)
            except SourceResponseError as page_error:
                request_count += int(page_diagnostics.get('http_request_sent') is True)
                page_diagnostics.update(transport=TRANSPORT, source_url=source_url(ticker),
                                        actual_provider='Yahoo Taiwan', parser_version=PARSER_VERSION)
                if rss_error is not None:
                    page_error.diagnostic.setdefault('rss_error_kind', rss_error.error_kind)
                diagnostics.update(page_diagnostics, component_statuses=components + [{
                    'provider': 'Yahoo Taiwan quote news page', 'status': 'error',
                    'record_count': 0, **_component_details(page_diagnostics),
                }], http_request_count=request_count,
                                   http_request_sent=request_count > 0)
                raise page_error
            request_count += int(page_diagnostics.get('http_request_sent') is True)
            page_diagnostics.update(transport=TRANSPORT, source_url=source_url(ticker),
                                    actual_provider='Yahoo Taiwan', parser_version=PARSER_VERSION)
            components.append({'provider': 'Yahoo Taiwan quote news page',
                               'status': 'success' if page_records else 'valid_empty',
                               'record_count': len(page_records), **_component_details(page_diagnostics)})
            rss_non_evidence = []
            if rss_records:
                originals = rss_diagnostics.get('_candidate_originals', {})
                for record in rss_records:
                    path = record.get('source_json_path')
                    rss_non_evidence.append({
                        'reason': 'rss_no_recent_records', 'quality_affecting': False,
                        'source_json_path': path,
                        'record': originals.get(path, record), 'normalized_record': record,
                    })
            page_diagnostics['_parser_rejections'] = (
                list(rss_diagnostics.get('_parser_rejections') or [])
                + list(page_diagnostics.get('_parser_rejections') or [])
            )
            page_diagnostics['_non_evidence_archive'] = (
                rss_non_evidence + list(rss_diagnostics.get('_non_evidence_archive') or [])
                + list(page_diagnostics.get('_non_evidence_archive') or [])
            )
            diagnostics.update(page_diagnostics, component_statuses=components,
                               http_request_count=request_count,
                               http_request_sent=request_count > 0)
            return page_records
        except SourceResponseError as error:
            if diagnostics.get('http_request_sent') and owns():
                state = remember_failure(GUARD_KEY, error)
                diagnostics.update(retry_at=state.get('retry_at'),
                                   retry_after_seconds=max(0, state.get('retry_at', 0) - time.time()))
            raise


def _fetch_rss(ticker: str, diagnostics: dict, deadline: float, owns) -> list[dict]:
    url = rss_source_url(ticker)
    body = bytearray()
    observed_bytes = 0
    response_status = None
    complete = False
    diagnostics.update(transport=RSS_TRANSPORT, source_url=url,
                       actual_provider='Yahoo Finance Taiwan RSS',
                       parser_version=RSS_PARSER_VERSION, http_request_sent=False)
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not owns():
            raise SourceResponseError('timeout' if remaining <= 0 else 'lease_lost',
                                      parser_version=RSS_PARSER_VERSION)
        kwargs = {'follow_redirects': False}
        proxy = proxy_url_for_request(url, PROVIDER)
        if proxy:
            kwargs['proxy'] = proxy
        observe_http_response(None)
        diagnostics['http_request_sent'] = True
        with curl_stream('GET', url, deadline=deadline, diagnostics=diagnostics, **kwargs) as response:
            response_status = response.status_code
            observe_http_response(response)
            diagnostics['http_status'] = response_status
            if response_status != 200:
                kind = {401: 'authentication', 402: 'payment_required', 403: 'access_denied',
                        429: 'rate_limited'}.get(response_status,
                                                  'server_error' if response_status >= 500 else 'http_error')
                error = SourceResponseError(kind, status_code=response_status,
                                            parser_version=RSS_PARSER_VERSION)
                error.response = response
                raise error
            length = response.headers.get('Content-Length', '')
            if length.isdigit() and int(length) > MAX_BODY_BYTES:
                raise SourceResponseError('response_too_large', status_code=response_status,
                                          parser_version=RSS_PARSER_VERSION)
            content_type = str(response.headers.get('Content-Type') or '').split(';', 1)[0].strip().lower()
            if content_type and content_type not in {
                'application/rss+xml', 'application/xml', 'text/xml', 'application/atom+xml',
            }:
                raise SourceResponseError('parse_error', status_code=response_status,
                                          parser_version=RSS_PARSER_VERSION)
            for chunk in response.iter_bytes(chunk_size=16_384):
                observed_bytes += len(chunk)
                if time.monotonic() >= deadline or not owns():
                    raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost',
                                              status_code=response_status,
                                              parser_version=RSS_PARSER_VERSION)
                space = MAX_BODY_BYTES - len(body)
                body.extend(chunk[:space])
                if len(chunk) > space:
                    raise SourceResponseError('response_too_large', status_code=response_status,
                                              parser_version=RSS_PARSER_VERSION)
            complete = True
        records = parse_yahoo_taiwan_rss(bytes(body), ticker, diagnostics=diagnostics)
        if time.monotonic() >= deadline or not owns():
            raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost',
                                      status_code=response_status,
                                      parser_version=RSS_PARSER_VERSION)
        return records
    except Exception as original:
        if isinstance(original, SourceResponseError):
            error = original
        else:
            kind = ('timeout' if isinstance(original, (httpx.TimeoutException, TimeoutError))
                    else 'transport_error' if isinstance(original, httpx.TransportError)
                    else 'parse_error')
            error = SourceResponseError(kind, status_code=response_status,
                                        parser_version=RSS_PARSER_VERSION)
        diagnostics.update(error.diagnostic)
        if error is original:
            raise
        raise error from original
    finally:
        diagnostics.update(response_bytes=len(body), response_bytes_read=observed_bytes,
                           response_complete=complete,
                           response_hash_scope='full_decoded_body' if complete else
                           'captured_prefix' if body else 'not_read')
        if complete:
            diagnostics['response_sha256'] = hashlib.sha256(body).hexdigest()
        elif body:
            diagnostics['captured_prefix_sha256'] = hashlib.sha256(body).hexdigest()
        captured = diagnostics.pop('_transport_capture', None)
        if captured is not None:
            diagnostics.update(captured)


def _fetch_page(ticker: str, diagnostics: dict, deadline: float, owns) -> list[dict]:
    url = source_url(ticker)
    body = bytearray()
    observed_bytes = 0
    response_status = None
    complete = False
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not owns():
            raise SourceResponseError('timeout' if remaining <= 0 else 'lease_lost', parser_version=PARSER_VERSION)
        kwargs = {'follow_redirects': False}
        proxy = proxy_url_for_request(url, PROVIDER)
        if proxy:
            kwargs['proxy'] = proxy
        observe_http_response(None)
        diagnostics['http_request_sent'] = True
        with curl_stream('GET', url, deadline=deadline, diagnostics=diagnostics, **kwargs) as response:
            response_status = response.status_code
            observe_http_response(response)
            diagnostics['http_status'] = response_status
            if response_status != 200:
                kind = {401: 'authentication', 402: 'payment_required', 403: 'access_denied',
                        429: 'rate_limited'}.get(response_status, 'server_error' if response_status >= 500 else 'http_error')
                error = SourceResponseError(kind, status_code=response_status, parser_version=PARSER_VERSION)
                error.response = response  # Internal only, for the existing Retry-After parser.
                raise error
            length = response.headers.get('Content-Length', '')
            if length.isdigit() and int(length) > MAX_BODY_BYTES:
                raise SourceResponseError('response_too_large', status_code=response_status, parser_version=PARSER_VERSION)
            for chunk in response.iter_bytes(chunk_size=16_384):
                observed_bytes += len(chunk)
                if time.monotonic() >= deadline or not owns():
                    raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost',
                                              status_code=response_status, parser_version=PARSER_VERSION)
                space = MAX_BODY_BYTES - len(body)
                body.extend(chunk[:space])
                if len(chunk) > space:
                    raise SourceResponseError('response_too_large', status_code=response_status, parser_version=PARSER_VERSION)
            complete = True
        if time.monotonic() >= deadline or not owns():
            raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost',
                                      status_code=response_status, parser_version=PARSER_VERSION)
        records = parse_yahoo_taiwan_news(bytes(body), ticker, diagnostics=diagnostics)
        if time.monotonic() >= deadline or not owns():
            raise SourceResponseError('timeout' if time.monotonic() >= deadline else 'lease_lost',
                                      status_code=response_status, parser_version=PARSER_VERSION)
        return records
    except Exception as original:
        if isinstance(original, SourceResponseError):
            error = original
        else:
            kind = 'timeout' if isinstance(original, (httpx.TimeoutException, TimeoutError)) else 'transport_error' if isinstance(original, httpx.TransportError) else 'parse_error'
            error = SourceResponseError(kind, status_code=response_status, parser_version=PARSER_VERSION)
        diagnostics.update(error.diagnostic)
        if error is original:
            raise
        raise error from original
    finally:
        # These are decoded bytes actually captured, not claimed full/wire bytes.
        diagnostics.update(response_bytes=len(body), response_bytes_read=observed_bytes,
                           response_complete=complete,
                           response_hash_scope='full_decoded_body' if complete else 'captured_prefix' if body else 'not_read')
        if complete:
            diagnostics['response_sha256'] = hashlib.sha256(body).hexdigest()
        elif body:
            # Common SLA metadata drops scope extensions; do not export a prefix
            # digest under its full-response hash field. Full audit keeps it.
            diagnostics['captured_prefix_sha256'] = hashlib.sha256(body).hexdigest()
        # Native curl may already have captured a bounded HTTP error body.
        # Preserve its full/prefix scope even when no body reaches the parser.
        captured = diagnostics.pop('_transport_capture', None)
        if captured is not None:
            diagnostics.update(captured)


def annotate_regional_result(result, data: dict, diagnostics: dict):
    """Retain all parser/selection exclusions without promoting partial evidence."""
    from source_content_selection import annotate_result
    original_rows = diagnostics.pop('_candidate_originals', {})
    parser_rejections = diagnostics.pop('_parser_rejections', [])
    non_evidence = diagnostics.pop('_non_evidence_archive', [])
    if result.status not in {'success', 'degraded_enrichment'} and original_rows:
        already_rejected = {row['source_json_path'] for row in parser_rejections}
        parser_rejections += [
            {'reason': 'acquisition_unusable', 'quality_affecting': True,
             'source_json_path': path, 'record': row}
            for path, row in original_rows.items() if path not in already_rejected
        ]
    result = annotate_result(result, data)
    archive = []
    for excluded in result.audit['source_record_archive']:
        record = excluded['record']
        path = record.get('source_json_path')
        archive.append({**excluded, 'quality_affecting': True, 'source_json_path': path,
                        'record': original_rows.get(path, record), 'normalized_record': record})
    result.audit.update(diagnostics)
    counts = Counter(result.audit['rejected_reason_counts'])
    counts.update(row['reason'] for row in parser_rejections)
    result.audit.update(raw_count=result.audit['raw_count'] + len(parser_rejections),
                        rejected_count=result.audit['rejected_count'] + len(parser_rejections),
                        rejected_reason_counts=dict(counts),
                        source_record_archive=archive + parser_rejections + non_evidence)
    if result.status in {'success', 'degraded_enrichment'}:
        result.status = 'success' if result.value and not result.audit['rejected_count'] else 'degraded_enrichment'
        result.audit.update(status=result.status,
                            coverage_status='success' if result.status == 'success' else 'partial',
                            retrieval_status='records_received' if result.audit['raw_count'] else 'no_records',
                            message='Yahoo 台灣個股新聞已取得；保留公司、日期與格式篩選結果。' if result.value else 'Yahoo 台灣個股頁未取得合格近期新聞；不代表沒有事件。')
    return result
