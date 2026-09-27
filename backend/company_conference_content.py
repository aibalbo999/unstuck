"""One verified issuer's official presentation; never a call transcript."""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
import math
import re
import time
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from company_conference_transport import INDEX_URL, PDF_URL, download
from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError, remember_failure, record_observation, scope_key, observe_http_response, error_details
from shared_provider_cache import shared_fetch
from source_pdf_reader import extract_pdf_pages

PROVIDER = 'MYSON official conference presentation'
PARSER_VERSION = 'myson-conference-content-v1'
GUARD_KEY = scope_key(PROVIDER, endpoint='www.myson.com.tw')
COVERAGE_NOTE = '公司法說簡報原文，並非法說逐字稿或獨立查證；圖像、表格閱讀順序及未抽出的頁面仍有內容限制。'
AGGREGATE_MESSAGE = 'optional 外部來源法說簡報取得結果；各次實際請求另列來源觀測。'


def supports_company(ticker: str) -> bool:
    return str(ticker).strip().upper() in {'5314', '5314.TWO'}


def select_presentation(raw: bytes, *, today: date | None = None) -> dict | None:
    """Select the latest explicitly dated Chinese presentation on the issuer page."""
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError('Index exceeds size limit')
    text = raw.decode('utf-8')
    soup = BeautifulSoup(text, 'html.parser')
    if '世紀民生科技股份有限公司' not in soup.get_text():
        raise ValueError('Issuer identity absent from index')
    today = today or datetime.now(ZoneInfo('Asia/Taipei')).date()
    candidates = {}
    for anchor in soup.find_all('a', href=True):
        title = re.sub(r'\s+', '', anchor.get_text())
        match = re.fullmatch(r'(\d{3})(\d{2})(\d{2})世紀民生法說會簡報', title)
        url = anchor['href']
        if not match or not isinstance(url, str) or not PDF_URL.fullmatch(url):
            continue
        try:
            event_date = date(int(match[1]) + 1911, int(match[2]), int(match[3]))
        except ValueError:
            continue
        if event_date > today:
            continue
        candidates[(event_date, url)] = {'event_date': event_date.isoformat(), 'url': url, 'title': title}
    if not candidates:
        return None
    latest = max(key[0] for key in candidates)
    rows = [row for (event, _), row in candidates.items() if event == latest]
    if len(rows) != 1:
        raise ValueError('Ambiguous latest presentation')
    return rows[0]


def _guard():
    from cache_store import get_cache_json
    from provider_resilience import provider_circuit_state
    try:
        saved = get_cache_json(GUARD_KEY)
        if saved is not None:
            retry_at = saved.get('retry_at') if isinstance(saved, dict) else None
            if type(retry_at) not in (int, float) or not math.isfinite(retry_at) or retry_at < 0:
                raise ValueError('Malformed guard')
        saved = saved or {}
        if float(saved.get('retry_at') or 0) > time.time():
            return saved
        circuit = provider_circuit_state(GUARD_KEY)
        if circuit.get('open') and float(circuit.get('opened_until') or 0) > time.time():
            return {'error_kind': 'circuit_open', 'retry_at': circuit['opened_until']}
        return {}
    except Exception:
        return {'error_kind': 'guard_storage_unavailable'}


def _operation(url, parser, *, deadline, endpoint, components, owns):
    started, details = time.monotonic(), {'endpoint': endpoint, 'actual_provider': PROVIDER,
        'parser_version': PARSER_VERSION, 'source_url': url, 'http_request_sent': False}
    blocked = (_guard() if owns() else {'error_kind': 'lease_lost'})
    if time.monotonic() >= deadline:
        blocked = {'error_kind': 'timeout'}
    if blocked:
        details.update(blocked)
        record_observation(PROVIDER, started, outcome='cooldown', source='earnings_call', details=details, sent=False)
        exc = SourceResponseError(blocked.get('error_kind', 'cooldown'))
        exc.diagnostic.update(details)
        raise exc
    observe_http_response(None)
    try:
        raw = download(url, deadline=deadline, diagnostics=details)
        parsed, count, coverage = parser(raw, deadline)
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout', status_code=details.get('http_status'))
        if not owns():
            raise SourceResponseError('lease_lost', status_code=details.get('http_status'))
    except Exception as original:
        if not isinstance(original, SourceResponseError) and isinstance(original, (ValueError, KeyError, TypeError)):
            original = SourceResponseError('parse_error', status_code=details.get('http_status'), parser_version=PARSER_VERSION)
        sent = details.get('http_request_sent') is True
        failure = remember_failure(GUARD_KEY, original) if sent and owns() else error_details(original)
        if not owns():
            failure['state_write_skipped'] = 'lease_lost'
        details.update(failure)
        details['status'] = 'error' if sent else 'unavailable'
        components[endpoint] = deepcopy(details)
        record_observation(PROVIDER, started, outcome='failure', source='earnings_call', details=details, sent=sent)
        exc = SourceResponseError(failure['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details, component_statuses=deepcopy(components))
        raise exc from original
    outcome = 'valid_empty' if count == 0 else 'results' if coverage == 'complete' else 'partial'
    details.update(coverage_status=coverage, outcome=outcome, status='success' if outcome == 'results' else 'degraded_enrichment',
                   fetched_at_epoch=time.time(), record_count=count)
    components[endpoint] = deepcopy(details)
    record_observation(PROVIDER, started, outcome=outcome, count=count, source='earnings_call', details=details)
    return parsed


def _fetch(ticker):
    started, deadline, components = time.monotonic(), time.monotonic() + 40, {}
    with endpoint_admission(GUARD_KEY, timeout_seconds=40) as owns:
        if owns is None:
            details = {'error_kind': 'single_flight_busy', 'http_request_sent': False}
            record_observation(PROVIDER, started, outcome='busy', source='earnings_call', details=details, sent=False)
            exc = SourceResponseError('single_flight_busy')
            exc.diagnostic.update(details)
            raise exc
        def index_parser(raw, _deadline):
            row = select_presentation(raw)
            return row, 1 if row else 0, 'metadata_only'
        selected = _operation(INDEX_URL, index_parser, deadline=deadline, endpoint='index', components=components, owns=owns)
        if not selected:
            return {'context': {}, 'diagnostic': {'coverage_status': 'partial', 'component_statuses': components,
                'actual_provider': PROVIDER, 'fetched_at_epoch': time.time(), 'message': AGGREGATE_MESSAGE}}
        def pdf_parser(raw, end):
            remaining = min(10, end - time.monotonic())
            if remaining <= 0:
                raise SourceResponseError('timeout')
            extracted = extract_pdf_pages(raw, timeout_seconds=remaining)
            cover = re.sub(r'\s+', '', extracted['pages'][0]['text'])
            if not re.search(r'(?<!\d)5314(?!\d)', cover) or '世紀民生' not in cover:
                raise ValueError('PDF issuer mismatch')
            # Native text coverage cannot verify images or chart reading order.
            return extracted, 1, 'partial'
        extracted = _operation(selected['url'], pdf_parser, deadline=deadline, endpoint='pdf', components=components, owns=owns)
        if not owns():
            exc = SourceResponseError('lease_lost')
            exc.diagnostic.update(component_statuses=deepcopy(components), http_request_sent=False,
                                  state_write_skipped='lease_lost')
            raise exc
        at = components['pdf']['fetched_at_epoch']
        digest = components['pdf']['response_sha256']
        document = {'document_id': '5314:' + selected['event_date'] + ':' + digest[:16],
            'ticker': '5314.TWO', 'title': selected['title'], 'url': selected['url'], 'source': PROVIDER,
            'source_type': 'issuer_official', 'document_kind': 'presentation',
            'event_date': selected['event_date'], 'published_at': None, 'retrieved_at_epoch': at,
            'content_sha256': digest, 'binary_complete': True, 'page_count': extracted['page_count'],
            'pages': extracted['pages'], 'missing_text_pages': extracted['empty_pages'],
            'text_extraction_complete': extracted['coverage_status'] == 'complete',
            'coverage_status': 'partial', 'native_text_coverage': extracted['coverage_status'],
            'full_content_coverage_verified': False, 'parser_version': extracted['parser_version']}
        for key in ('garbled_pages', 'text_pages', 'limitations'):
            if key in extracted:
                document[key] = deepcopy(extracted[key])
        coverage = 'partial'
        context = {'ticker': str(ticker).upper(), 'date': selected['event_date'], 'period': selected['event_date'],
            'title': selected['title'], 'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'source': PROVIDER, 'source_url': INDEX_URL, 'materials': [{'url': selected['url'], 'kind': 'presentation'}],
            'documents': [document], 'coverage_status': coverage, 'coverage_notes': [COVERAGE_NOTE], 'fetched_at_epoch': at}
        return {'context': context, 'diagnostic': {'actual_provider': PROVIDER, 'coverage_status': coverage,
            'component_statuses': components, 'fetched_at_epoch': at, 'message': AGGREGATE_MESSAGE, 'record_count': 1}}


def fetch_company_conference(ticker: str, *, diagnostics: dict | None = None) -> dict:
    if not supports_company(ticker):
        return {}
    captured = {}
    def fetch():
        try:
            return _fetch(ticker)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    result, meta = shared_fetch(PARSER_VERSION + ':5314', fetch, freshness_seconds=86400,
        result_ttl=lambda row: 86400 if row['context'] else 600, lock_wait_seconds=0)
    if meta.get('error_kind'):
        details = {**meta, **captured, 'actual_provider': PROVIDER}
        if not captured:
            details.update(http_request_sent=False, event_kind='local_block')
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details)
        raise exc
    details = {**result['diagnostic'], **meta}
    details['http_request_sent'] = not meta.get('cache_hit')
    if meta.get('cache_hit'):
        for component in details['component_statuses'].values():
            component.update(cache_hit=True, http_request_sent=False, event_kind='cache_hit')
    if diagnostics is not None:
        diagnostics.update(details)
    return deepcopy(result['context'])
