"""SYSTEX's original public event index, with explicit content limitations."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
import json
import math
import re
import time
from urllib.parse import urlencode, urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from official_response_evidence import archive_response, read_response
from search_admission import endpoint_admission
from search_provider_runtime import SourceResponseError, scope_key, remember_failure, record_observation
from shared_provider_cache import shared_fetch
from systex_conference_transport import API_URL, HOME_URL, PROVIDER, NONCE, download

INDEX_URL = 'https://tw.systex.com/systex/ch/app/tabfolder/22344'
PARSER_VERSION = 'systex-conference-index-v1'
GUARD_KEY = scope_key(PROVIDER, endpoint='tw.systex.com')
AGGREGATE_MESSAGE = 'optional 外部來源法說活動索引取得結果；完整原件與請求明細另存。'
NOTE = '僅取得精誠官方活動描述、日期與資料連結；未讀取簡報、影音或逐字稿，不能當作營運展望摘要。'


def supports_systex(ticker):
    return str(ticker or '').strip().upper() in {'6214', '6214.TW'}


def parse_nonce(raw):
    text = raw.decode('utf-8')
    if re.search(r'FOR SECURITY REASONS|PAGE CAN NOT BE ACCESSED|驗證碼|captcha|access denied', text, re.I):
        raise SourceResponseError('access_denied', status_code=200)
    values = re.findall(r'window\.__X_UNIQUE_ID__\s*=\s*"([^"\r\n]+)"\s*;', text)
    if len(values) != 1 or not NONCE.fullmatch(values[0]):
        raise ValueError('public bootstrap parameter absent or ambiguous')
    return values[0]


def select_event(raw, *, now=None):
    now = now or datetime.now(ZoneInfo('Asia/Taipei'))
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 512_000:
        raise ValueError('index size invalid')
    body = json.loads(raw)
    if not isinstance(body, dict):
        raise ValueError('issuer index schema mismatch')
    panels = body.get('viewModelList')
    if body.get('title') != '法人說明會資訊' or not isinstance(panels, list) or not 1 <= len(panels) <= 32:
        raise ValueError('issuer index schema mismatch')
    years, records, dated_panels = set(), [], []
    for panel in panels:
        info = panel.get('artWebSiteViewModel') if isinstance(panel, dict) else None
        match = re.fullmatch(r'(20\d{2})年度', str(info.get('subject') or '')) if isinstance(info, dict) else None
        if not match or panel.get('module') != 'artwebsite' or int(match[1]) in years:
            raise ValueError('year panel invalid or duplicated')
        year = int(match[1]); years.add(year)
        if year <= now.year:
            dated_panels.append((year, panel))
    # The full response contains older templates. They cannot outrank an
    # eligible event in a newer year; parse older years only when needed.
    for year, panel in sorted(dated_panels, reverse=True, key=lambda item: item[0]):
        tabs = panel.get('tabViewModels')
        if not isinstance(tabs, list) or len(tabs) > 100:
            raise ValueError('event panels invalid')
        for tab in tabs:
            rows = tab.get('dataViewModels') if isinstance(tab, dict) else None
            if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
                raise ValueError('event body missing')
            html = rows[0].get('detailContent')
            if not isinstance(html, str) or not 0 < len(html) <= 20_000:
                raise ValueError('event content invalid')
            soup = BeautifulSoup(html, 'html.parser'); text = soup.get_text(' ', strip=True)
            date_match = re.search(r'時間[：:]\s*(20\d{2})年\s*(\d{1,2})月\s*(\d{1,2})日\s*(\d{1,2}):(\d{2})', text)
            if not date_match or '法人說明會' not in text or int(date_match[1]) != year:
                raise ValueError('event identity or date absent')
            event = datetime(*map(int, date_match.groups()), tzinfo=ZoneInfo('Asia/Taipei'))
            pdfs, videos = set(), set()
            for anchor in soup.find_all('a', href=True):
                link = urljoin('https://tw.systex.com/', anchor['href']); label = anchor.get_text(' ', strip=True)
                if '中文' in label and '簡報' in label:
                    if not re.fullmatch(r'https://tw\.systex\.com/userfiles/systexch/files/\d{8,20}\.pdf', link):
                        raise ValueError('issuer presentation link invalid')
                    pdfs.add(link)
                elif '影音' in label:
                    if not re.fullmatch(r'https://(?:youtu\.be/[A-Za-z0-9_-]{11}|www\.youtube\.com/watch\?v=[A-Za-z0-9_-]{11})', link):
                        raise ValueError('official video link invalid')
                    videos.add(link)
            if len(pdfs) != 1 or len(videos) > 1:
                raise ValueError('event materials absent or ambiguous')
            if event <= now:
                records.append({'date': event.date().isoformat(), 'time': event.strftime('%H:%M'),
                    'title': text.split('時間', 1)[0].strip(), 'summary': text,
                    'presentation_url': next(iter(pdfs)), 'video_url': next(iter(videos), '')})
        if records:
            break
    if not records:
        return None
    latest = max((r['date'], r['time']) for r in records)
    matches = [r for r in records if (r['date'], r['time']) == latest]
    if len(matches) != 1:
        raise ValueError('latest event ambiguous')
    return matches[0]


def _guard():
    from cache_store import get_cache_json
    from provider_resilience import provider_circuit_state
    try:
        state = get_cache_json(GUARD_KEY)
        if state is not None:
            stamp = state.get('retry_at') if isinstance(state, dict) else None
            if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp < 0:
                raise ValueError('invalid guard')
            if stamp > time.time():
                return state
        circuit = provider_circuit_state(GUARD_KEY)
        return {'error_kind': 'circuit_open'} if circuit.get('open') else {}
    except Exception:
        return {'error_kind': 'guard_storage_unavailable'}


def _check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def _recent_epoch(stamp, now):
    # Compare before float conversion: an arbitrary-size cached integer must
    # remain a rejected receipt, rather than overflowing out of the fallback.
    return (type(stamp) in (int, float) and 0 < stamp <= now
            and math.isfinite(stamp) and now-stamp <= 1800)


def _fetch(started, deadline):
    components = {}
    details = {'actual_provider': PROVIDER, 'parser_version': PARSER_VERSION,
               'source_url': INDEX_URL, 'http_request_sent': False, 'source_http_request_count': 0}
    with endpoint_admission(GUARD_KEY, timeout_seconds=12) as owns:
        blocked = _guard() if owns else {'error_kind': 'single_flight_busy'}
        if blocked:
            details.update(blocked)
            record_observation(PROVIDER, started, outcome='cooldown', source='earnings_call', details=details, sent=False)
            exc = SourceResponseError(details['error_kind']); exc.diagnostic.update(details); raise exc
        receipts = {}
        try:
            for name, url in [('bootstrap', HOME_URL), ('event_index', None)]:
                if not owns() or time.monotonic() >= deadline:
                    raise SourceResponseError('lease_lost' if not owns() else 'timeout')
                if name == 'event_index':
                    url = API_URL+'?'+urlencode({'cspstr': parse_nonce(home)})
                component = components.setdefault(name, {})
                raw = download(url, deadline=deadline, diagnostics=component)
                at = time.time(); component['fetched_at_epoch'] = at
                safe_url = API_URL if name == 'event_index' else HOME_URL
                receipt = archive_response(raw, source_url=safe_url, retrieved_at=at)
                _check_deadline(deadline)
                if receipt.get('status') != 'archived':
                    raise SourceResponseError('raw_archive_failed')
                receipts[name] = receipt
                if name == 'bootstrap':
                    home = raw
                else:
                    selected = select_event(raw)
            if not owns() or time.monotonic() >= deadline:
                raise SourceResponseError('lease_lost' if not owns() else 'timeout')
        except Exception as original:
            if isinstance(original, (ValueError, KeyError, TypeError, UnicodeError)):
                original = SourceResponseError('parse_error')
            sent = any(c.get('http_request_sent') is True for c in components.values())
            failure = remember_failure(GUARD_KEY, original) if sent and owns() else {'error_kind': getattr(original, 'error_kind', 'provider_error')}
            details.update(failure, component_statuses=components, http_request_sent=sent,
                           source_http_request_count=sum(c.get('http_request_sent') is True for c in components.values()))
            record_observation(PROVIDER, started, outcome='failure', source='earnings_call', details=details, sent=sent)
            exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status')); exc.diagnostic.update(details); raise exc from original
    at = components['event_index']['fetched_at_epoch']
    details.update(http_request_sent=True, http_status=200, source_http_request_count=2,
        fetched_at_epoch=at, coverage_status='metadata_only', component_statuses=components,
        raw_http_receipt=receipts['event_index'], bootstrap_receipt=receipts['bootstrap'],
        message=AGGREGATE_MESSAGE, record_count=int(bool(selected)))
    record_observation(PROVIDER, started, outcome='results' if selected else 'valid_empty',
                       count=int(bool(selected)), source='earnings_call', details=details)
    return {'context': _context(selected, at), 'diagnostic': details}


def _context(selected, at):
    if not selected:
        return {}
    materials = [{'url': selected['presentation_url'], 'kind': 'presentation_link', 'content_retrieved': False}]
    if selected['video_url']:
        materials.append({'url': selected['video_url'], 'kind': 'official_video_link', 'content_retrieved': False})
    return {'ticker': '6214.TW', 'date': selected['date'], 'period': selected['date'],
        'time': selected['time'], 'title': selected['title'], 'summary': selected['summary'],
        'materials': materials, 'source': PROVIDER, 'source_url': INDEX_URL,
        'coverage_status': 'metadata_only', 'coverage_notes': [NOTE],
        'transcript_available': False, 'transcript_excerpt': '', 'fetched_at_epoch': at}


def fetch_systex_conference_context(ticker, *, diagnostics=None):
    if not supports_systex(ticker):
        return {}
    started = time.monotonic()
    deadline = started + 12.
    captured = {}
    def fetch():
        try:
            return _fetch(started, deadline)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic); raise
    value, meta = shared_fetch(PARSER_VERSION+':6214', fetch, freshness_seconds=1800,
        retention_seconds=1800, error_retry_seconds=120, lock_wait_seconds=0)
    if meta.get('error_kind') or meta.get('stale'):
        exc = SourceResponseError(meta.get('error_kind') or 'stale_receipt')
        exc.diagnostic.update(meta, **captured); raise exc
    details = {}
    try:
        _check_deadline(deadline)
        cached_diagnostic = value['diagnostic']
        if not isinstance(cached_diagnostic, dict):
            raise ValueError('original diagnostic is not a mapping')
        details = deepcopy(cached_diagnostic); stamp = details['fetched_at_epoch']
        now = time.time()
        if not _recent_epoch(stamp, now):
            raise ValueError('invalid original time')
        originals = {}
        for name, url, limit in (('bootstrap_receipt', HOME_URL, 64_000),
                                 ('raw_http_receipt', API_URL, 512_000)):
            _check_deadline(deadline)
            receipt = details[name]; received = receipt['retrieved_at']
            size = receipt.get('raw_response_bytes')
            if (receipt.get('status') != 'archived'
                    or receipt.get('evidence_kind') != 'raw_http_response_bytes'
                    or type(size) is not int or not 0 < size <= limit
                    or receipt.get('source_url') != url or receipt.get('http_status') != 200
                    or not _recent_epoch(received, now) or received > stamp
                    or (name == 'raw_http_receipt' and received != stamp)):
                raise ValueError('original source receipt invalid')
            raw = read_response(receipt)
            _check_deadline(deadline)
            if len(raw) != size:
                raise ValueError('original response size differs')
            originals[name] = raw
        parse_nonce(originals['bootstrap_receipt'])
        _check_deadline(deadline)
        selected = select_event(originals['raw_http_receipt'])
        _check_deadline(deadline)
        if value['context'] != _context(selected, stamp):
            raise ValueError('cached index differs from original')
    except (ValueError, KeyError, TypeError, OverflowError, OSError, EOFError, SourceResponseError) as cause:
        kind = 'timeout' if isinstance(cause, SourceResponseError) and cause.error_kind == 'timeout' else 'cache_receipt_invalid'
        record_observation(PROVIDER, started, outcome=kind, source='earnings_call',
            details={'error_kind': kind}, sent=False)
        exc = SourceResponseError(kind)
        exc.diagnostic.update(details, error_kind=kind, cache_hit=bool(meta.get('cache_hit')),
            http_request_sent=not meta.get('cache_hit'), source_http_request_count=0 if meta.get('cache_hit') else 2)
        raise exc from cause
    details.update(cache_hit=bool(meta.get('cache_hit')), http_request_sent=not meta.get('cache_hit'),
                   source_http_request_count=0 if meta.get('cache_hit') else 2)
    if diagnostics is not None:
        diagnostics.update(details)
    return deepcopy(value['context'])
