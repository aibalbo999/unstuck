"""Bounded WebPro public conference index; factual metadata and links only."""
from __future__ import annotations

from datetime import date, datetime
import ipaddress
import re
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from external_http_client import sync_post
from search_provider_runtime import SourceResponseError, cooldown_state, record_observation, remember_failure, scope_key, observe_http_response
from shared_provider_cache import shared_fetch

PROVIDER = 'TWSE WebPro conference metadata'
INDEX_URL = 'https://webpro.twse.com.tw/WebPortal/vod/101/?categoryId=170'
LIST_URL = 'https://webpro.twse.com.tw/WebPortal/service/vodChannel/categoryMaterialList'
PARSER_VERSION = 'webpro-conference-metadata-v2'
COVERAGE_NOTE = '僅取得 WebPro 站外法說會索引的日期與連結；未取得簡報、影音內容或逐字稿，來源涵蓋不完整。'
COOLDOWN_KEY = scope_key(PROVIDER, endpoint='conference_index')


def taiwan_company_symbol(ticker: str) -> str | None:
    match = re.fullmatch(r'(\d{4,6})(?:\.(?:TW|TWO))?', str(ticker or '').strip().upper())
    return match.group(1) if match else None


def fetch_webpro_conference_context(ticker: str, *, diagnostics: dict | None = None) -> dict:
    """Return the latest completed event from one public page, never its content."""
    symbol = taiwan_company_symbol(ticker)
    if not symbol:
        return {}
    captured = {}
    def fetch():
        try:
            return _fetch_index(symbol)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    result, meta = shared_fetch(
        f'{PARSER_VERSION}:{symbol}', fetch, freshness_seconds=86400,
        result_ttl=lambda value: 86400 if value['events'] else 300,
    )
    if meta.get('error_kind'):
        details = {**meta, **cooldown_state(COOLDOWN_KEY), **captured}
        if not captured:
            details.update(http_request_sent=False, event_kind='local_block')
        exc = SourceResponseError(details.get('error_kind') or 'provider_error',
                                  status_code=details.get('http_status'), parser_version=PARSER_VERSION)
        exc.diagnostic.update(details, actual_provider=PROVIDER)
        raise exc
    details = {**result['diagnostic'], **meta, 'actual_provider': PROVIDER, 'coverage_status': 'metadata_only'}
    if meta.get('cache_hit'):
        details.update(http_request_sent=False, event_kind='cache_hit')
    if diagnostics is not None:
        diagnostics.update(details)
    events = result['events']
    if not events:
        return {}
    event = events[0]
    return {
        'ticker': symbol, 'date': event['date'], 'period': event['date'],
        'title': f"{event['company_name'] or symbol} 法人說明會（索引）",
        'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
        'materials': [], 'source': PROVIDER, 'source_url': INDEX_URL,
        'event_url': event['url'], 'event_id': event['event_id'],
        'coverage_status': 'metadata_only', 'coverage_notes': [COVERAGE_NOTE],
        'fetched_at_epoch': meta['fetched_at_epoch'], 'event_date_raw': event['event_date_raw'],
        'upstream_source': 'MOPS-derived WebPro public index',
    }


def _fetch_index(symbol: str) -> dict:
    started = time.monotonic()
    blocked = cooldown_state(COOLDOWN_KEY)
    if blocked:
        record_observation(PROVIDER, started, outcome='cooldown', source='earnings_call', details=blocked, sent=False)
        exc = SourceResponseError(blocked.get('error_kind', 'cooldown'), status_code=blocked.get('http_status'), parser_version=PARSER_VERSION)
        exc.diagnostic.update(blocked, http_request_sent=False, event_kind='local_block')
        raise exc
    response = None
    observe_http_response(None)
    try:
        response = sync_post(LIST_URL, data={
            'categoryId': '170', 'vodChannelId': '101', 'returnType': 'json', 'platform': 'web',
            'pageNumber': '1', 'pagingSize': '3', 'order': 'eventDate', 'sortOrder': 'desc',
            'stockCodeOrCompanyName': symbol,
        }, timeout=(5, 15), provider=PROVIDER)
        observe_http_response(response)
        response.raise_for_status()
        events = _parse_index(response.json(), symbol)
    except Exception as original:
        if isinstance(original, (ValueError, TypeError, KeyError)):
            original = SourceResponseError('parse_error', status_code=getattr(response, 'status_code', None), parser_version=PARSER_VERSION)
        details = remember_failure(COOLDOWN_KEY, original)
        details.update(parser_version=PARSER_VERSION, actual_provider=PROVIDER,
                       http_request_sent=True, event_kind='http_attempt')
        record_observation(PROVIDER, started, outcome='failure', source='earnings_call', details=details)
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'), parser_version=PARSER_VERSION)
        exc.diagnostic.update(details)
        raise exc from original
    details = {'http_status': response.status_code, 'parser_version': PARSER_VERSION,
               'outcome': 'results' if events else 'valid_empty', 'http_request_sent': True,
               'event_kind': 'http_attempt', 'coverage_status': 'metadata_only'}
    record_observation(PROVIDER, started, outcome=details['outcome'], count=len(events), source='earnings_call', details=details)
    return {'events': events, 'diagnostic': details}


def _parse_index(payload: dict, symbol: str) -> list[dict]:
    if not isinstance(payload, dict) or not isinstance(payload.get('status'), dict):
        raise ValueError('Unknown WebPro envelope')
    code = payload['status'].get('code')
    if type(code) not in (str, int) or not str(code).strip():
        raise ValueError('Missing WebPro status code')
    if str(code) != '1':
        raise SourceResponseError('provider_error', status_code=200, parser_version=PARSER_VERSION)
    if not isinstance(payload.get('pagingObject'), dict):
        raise ValueError('Unknown WebPro result shape')
    total = payload['pagingObject'].get('totalCount')
    if type(total) is not int or total < 0:
        raise ValueError('Inconsistent WebPro paging')
    # Official zero-result pages omit materials. Require explicit successful
    # paging evidence; missing/unknown envelopes must remain parser failures.
    if total == 0 and payload.get('result') == {}:
        return []
    rows = payload['result']['materials']['material']
    if not isinstance(rows, list):
        raise ValueError('Unknown WebPro result shape')
    if total < len(rows) or (total and not rows):
        raise ValueError('Inconsistent WebPro paging')
    today = datetime.now(ZoneInfo('Asia/Taipei')).date()
    events, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('agentUserName'), str):
            raise ValueError('Unknown WebPro row')
        if row['agentUserName'].strip() != symbol:
            continue
        if type(row.get('isValid')) is not bool:
            raise ValueError('Missing WebPro row validity')
        if not row['isValid']:
            continue
        if row.get('categoryId') != 170:
            raise ValueError('Unexpected WebPro category')
        raw_date = str(row.get('eventDate') or '')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2} 00:00:00(?:\.0)?', raw_date):
            raise ValueError('Unknown event date')
        event_date = date.fromisoformat(raw_date[:10])
        if event_date > today:
            continue
        url = _https_link(row.get('webLinkPath'))
        if not url:
            raise ValueError('Unusable event link')
        identity = (event_date.isoformat(), url)
        if identity in seen:
            continue
        seen.add(identity)
        events.append({'date': event_date.isoformat(), 'event_date_raw': raw_date, 'url': url,
                       'company_name': str(row.get('agentSimpleName') or '')[:120],
                       'event_id': str(row.get('guid') or '')[:120]})
    return sorted(events, key=lambda row: row['date'], reverse=True)


def _https_link(value) -> str:
    if not isinstance(value, str) or len(value) > 2048 or re.search(r'\s|[\\<>]', value):
        return ''
    try:
        url = urlsplit(value)
        host = url.hostname or ''
        if url.scheme != 'https' or url.username or url.password or url.port not in (None, 443):
            return ''
        if '.' not in host or not re.fullmatch(r'[A-Za-z0-9.-]+', host) or host.endswith(('.local', '.localhost', '.internal')):
            return ''
        try:
            ipaddress.ip_address(host)
            return ''
        except ValueError:
            return value
    except ValueError:
        return ''
