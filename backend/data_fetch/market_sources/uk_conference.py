"""Verified Universal issuer presentation originals; never a call transcript."""
from copy import deepcopy
from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import re
import time
from uuid import uuid4
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from official_response_evidence import archive_response, read_response
from search_admission import endpoint_admission
from search_provider_runtime import (SourceResponseError, cooldown_state, remember_failure,
                                     record_observation, scope_key)
from shared_provider_cache import shared_fetch
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .official_company_legal_name import (read_cached_listed_roster_bytes,
                                         parse_roster, select_legal_name)
from .uk_conference_transport import PROVIDER, INDEX_URL, presentation_url, download

POLICY = 'universal-original-presentation-v1'
GUARD = scope_key(PROVIDER, endpoint='www.uk.com.tw')
ROSTER_URL = 'https://openapi.twse.com.tw/v1/opendata/t187ap03_L'
NOTE = '恒大官方法說簡報原件及原生文字頁面已取得；不是逐字稿，影像、圖表閱讀順序及各項陳述尚未獨立驗證。活動日期不是首次發布日期。'


def supports_uk(ticker):
    return str(ticker).strip().upper() in {'1325', '1325.TW'}


def _today(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now, ZoneInfo('Asia/Taipei')).date()


def _anchor(raw, today):
    roster = parse_roster(raw, '.TW')
    anchor = select_legal_name(roster, '1325.TW', '恆大', today=today)
    rows = [r for r in json.loads(raw) if r.get('公司代號') == '1325']
    if (not anchor or anchor.get('legal_name') != '恒大股份有限公司'
            or anchor.get('official_ubn') != '11455800' or len(rows) != 1
            or rows[0].get('網址') not in {'www.uk.com.tw', 'https://www.uk.com.tw', 'https://www.uk.com.tw/'}):
        raise ValueError('Universal official identity differs')
    return anchor


def select_index(raw, *, today=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 200_000:
        raise ValueError('Universal index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8'), 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if title != '法人說明會 - 恒大股份有限公司' or '恒大股份有限公司' not in soup.get_text():
        raise ValueError('Universal index owner absent')
    candidates = set()
    today = today or _today()
    for link in soup.find_all('a', href=True):
        label = re.sub(r'\s+', '', link.get_text())
        match = re.fullmatch(r'(\d{3})年度法人說明會簡報檔\((\d{3})/(\d{2})/(\d{2})\)。?', label)
        if not match:
            if '法人說明會簡報檔' in label:
                raise ValueError('Universal presentation label invalid')
            continue
        event = date(int(match[2]) + 1911, int(match[3]), int(match[4]))
        url = urljoin(INDEX_URL, link['href'])
        if match[1] != match[2] or not presentation_url(url):
            raise ValueError('Universal presentation date or link invalid')
        if event <= today:
            candidates.add((event, url, label))
    if not candidates:
        return None
    latest = max(row[0] for row in candidates)
    selected = [row for row in candidates if row[0] == latest]
    if len(selected) != 1:
        raise ValueError('Universal latest presentation ambiguous')
    event, url, label = selected[0]
    return {'event_date': event.isoformat(), 'url': url, 'label': label}


def _native_pdf(raw, selected, deadline):
    remaining = min(10., deadline - time.monotonic())
    if remaining <= 0:
        raise SourceResponseError('timeout')
    native = extract_pdf_pages(raw, timeout_seconds=remaining)
    cover = re.sub(r'\s+', '', native['pages'][0]['text'])
    expected = date.fromisoformat(selected['event_date'])
    if (native['coverage_status'] != 'complete'
            or '恒大股份有限公司' not in cover or '股票代號：1325' not in cover
            or '法人說明會' not in cover
            or f'{expected.year}年{expected.month}月{expected.day}日' not in cover):
        raise ValueError('Universal native content, issuer, or event not verified')
    return native


def _stamp(receipt):
    stamp = receipt.get('retrieved_at')
    if type(stamp) not in (int, float) or not math.isfinite(stamp) or stamp <= 0 or stamp > time.time() + 300:
        raise ValueError('Universal original timestamp invalid')
    return stamp


def _saved(receipt, url, *, identity=False):
    if (not isinstance(receipt, dict) or receipt.get('status') != 'archived'
            or receipt.get('source_url') != url
            or receipt.get('http_status') != (None if identity else 200)):
        raise ValueError('Universal original receipt invalid')
    _stamp(receipt)
    raw = read_response(receipt)
    limit = 2_500_000 if identity else 200_000 if url == INDEX_URL else 8 * 1024 * 1024
    if not 0 < len(raw) <= limit or receipt.get('raw_response_bytes') != len(raw):
        raise ValueError('Universal original length invalid')
    return raw


def _context(selected, native, receipt):
    pdf = receipt['pdf']
    doc = {'document_id': '1325:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': '1325.TW', 'title': selected['label'], 'url': selected['url'], 'source': PROVIDER,
           'source_type': 'issuer_official', 'document_kind': 'presentation',
           'event_date': selected['event_date'], 'published_at': None,
           'retrieved_at_epoch': pdf['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'parser_version': native['parser_version']}
    if native.get('symbol_mapping_evidence'):
        doc['symbol_mapping_evidence'] = deepcopy(native['symbol_mapping_evidence'])
    return {'ticker': '1325.TW', 'date': selected['event_date'], 'period': selected['event_date'],
            'title': selected['label'], 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'source': PROVIDER, 'source_url': INDEX_URL,
            'materials': [{'url': selected['url'], 'kind': 'presentation'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': pdf['retrieved_at'], 'uk_conference_receipt': receipt}


def verify_context(value, ticker, *, deadline=None):
    try:
        if not supports_uk(ticker) or not isinstance(value, dict) or value.get('ticker') != '1325.TW':
            return False
        proof = value['uk_conference_receipt']
        if proof.get('policy') != POLICY:
            return False
        _anchor(_saved(proof['identity'], ROSTER_URL, identity=True), _today())
        selected = select_index(_saved(proof['index'], INDEX_URL))
        if not selected or selected != proof['selected']:
            return False
        raw = _saved(proof['pdf'], selected['url'])
        if not 0 <= time.time() - _stamp(proof['pdf']) <= 86400:
            return False
        native = _native_pdf(raw, selected, deadline or time.monotonic() + 10.)
        expected = _context(selected, native, proof)
        return all(value.get(k) == v for k, v in expected.items())
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError, OSError, EOFError, SourceResponseError, SourcePdfError):
        return False


def _operation(url, parser, endpoint, deadline, components, owns):
    started = time.monotonic()
    diagnostic = {'source_url': url, 'endpoint': endpoint, 'actual_provider': PROVIDER,
                  'parser_version': POLICY, 'attempt_id': uuid4().hex, 'http_request_sent': False}
    try:
        if not owns():
            raise SourceResponseError('lease_lost')
        if cooldown_state(GUARD):
            raise SourceResponseError('cooldown')
        raw = download(url, deadline=deadline, diagnostics=diagnostic)
        parsed = parser(raw)
        if time.monotonic() >= deadline:
            raise SourceResponseError('timeout')
        if not owns():
            raise SourceResponseError('lease_lost')
        stamp = time.time()
        receipt = archive_response(raw, source_url=url, retrieved_at=stamp)
        if receipt.get('status') != 'archived':
            raise SourceResponseError('original_archive_unavailable')
        if _saved(receipt, url) != raw:
            raise SourceResponseError('original_unverified')
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        if diagnostic.get('http_request_sent') and owns():
            diagnostic.update(remember_failure(GUARD, exc))
        diagnostic.update(error_kind=exc.error_kind, status='error')
        components[endpoint] = deepcopy(diagnostic)
        record_observation(PROVIDER, started, outcome='failure', details=diagnostic,
                           source='earnings_call', sent=diagnostic.get('http_request_sent') is True)
        exc.diagnostic.update(diagnostic, component_statuses=deepcopy(components))
        if exc is original:
            raise
        raise exc from original
    diagnostic.update(record_count=1 if parsed else 0, fetched_at_epoch=stamp,
                      coverage_status='native_text_complete' if endpoint == 'pdf' else 'metadata_only',
                      original_receipt=receipt, status='success' if parsed else 'degraded_enrichment')
    components[endpoint] = deepcopy(diagnostic)
    record_observation(PROVIDER, started, outcome='results' if parsed else 'valid_empty',
                       count=1 if parsed else 0, details=diagnostic, source='earnings_call', sent=True)
    return parsed, receipt


def _fetch(*, deadline=None):
    deadline = deadline if deadline is not None else time.monotonic() + 20.
    with endpoint_admission(GUARD, timeout_seconds=20.) as owns:
        if not owns:
            raise SourceResponseError('single_flight_busy')
        master = read_cached_listed_roster_bytes()
        if master is None:
            raise SourceResponseError('identity_anchor_unavailable')
        raw, meta = master
        try:
            _anchor(raw, _today())
        except (ValueError, TypeError, KeyError) as exc:
            raise SourceResponseError('identity_anchor_unverified') from exc
        identity = archive_response(raw, source_url=ROSTER_URL,
                                    retrieved_at=meta['fetched_at_epoch'], http_status=None,
                                    evidence_kind='cached_complete_source_payload_verified_by_digest')
        if identity.get('status') != 'archived':
            raise SourceResponseError('original_archive_unavailable')
        components = {}
        selected, index = _operation(INDEX_URL, select_index, 'index', deadline, components, owns)
        if selected is None:
            return {'context': {}, 'diagnostic': {'actual_provider': PROVIDER,
                    'coverage_status': 'partial', 'component_statuses': components,
                    'http_request_sent': True, 'http_request_count': 1}}
        native, pdf = _operation(selected['url'], lambda raw: _native_pdf(raw, selected, deadline),
                                 'pdf', deadline, components, owns)
        proof = {'policy': POLICY, 'identity': identity, 'index': index,
                 'pdf': pdf, 'selected': selected}
        context = _context(selected, native, proof)
        if not verify_context(context, '1325.TW', deadline=deadline) or not owns():
            raise SourceResponseError('original_unverified' if owns() else 'lease_lost')
        return {'context': context, 'diagnostic': {'actual_provider': PROVIDER,
                'coverage_status': 'native_text_complete', 'uk_originals_verified': True,
                'component_statuses': components, 'http_request_sent': True,
                'http_request_count': 2, 'fetched_at_epoch': pdf['retrieved_at'],
                'message': NOTE}}


def fetch_uk_context(ticker, *, diagnostics=None):
    if not supports_uk(ticker):
        return {}
    deadline = time.monotonic() + 20.
    captured = {}
    def collect():
        try:
            return _fetch(deadline=deadline)
        except SourceResponseError as exc:
            captured.update(exc.diagnostic)
            raise
    result, meta = shared_fetch(POLICY + ':1325.TW', collect, freshness_seconds=86400,
                               result_ttl=lambda row: 86400 if row['context'] else 600,
                               lock_wait_seconds=0)
    if meta.get('error_kind'):
        details = {**meta, **captured}
        exc = SourceResponseError(details['error_kind'], status_code=details.get('http_status'))
        exc.diagnostic.update(details)
        raise exc
    if (not isinstance(result, dict) or not isinstance(result.get('context'), dict)
            or not isinstance(result.get('diagnostic'), dict)):
        raise SourceResponseError('cached_original_unverified')
    context = result['context']
    if context and not verify_context(context, '1325.TW', deadline=deadline):
        exc = SourceResponseError('cached_original_unverified')
        exc.diagnostic.update(http_request_sent=False, cache_hit=bool(meta.get('cache_hit')))
        raise exc
    details = {**result['diagnostic'], **meta}
    if context:
        details['fetched_at_epoch'] = context['fetched_at_epoch']
    if meta.get('cache_hit'):
        details.update(http_request_sent=False, http_request_count=0)
        details['component_statuses'] = {k: {**v, 'http_request_sent': False,
                                            'cache_hit': True, 'event_kind': 'cache_hit'}
                                        for k, v in details['component_statuses'].items()}
    if diagnostics is not None:
        diagnostics.update(details)
    return deepcopy(context)
