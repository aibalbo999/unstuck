"""Exact-issuer, replayable TCFHC prepared QA summaries, never transcripts."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import re
import time
import zlib
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .tcfhc_conference_transport import HOST, MASTER_URL, PROVIDER, RAW_TTL, ROOT, route_kind
from .tcfhc_qa_transport import ConferenceHttp, original_bytes
from . import conference_issuer_master as master_identity

TICKER = '5880.TW'
LEGAL = '合作金庫金融控股股份有限公司'
LEGACY_POLICY = 'tcfhc-original-qa-v1'
POLICY = 'tcfhc-original-qa-v2'
NOTE = ('合庫金控官方整理的投資人問答摘要，不是逐字稿或獨立查證。'
        '本公司／本集團、銀行本行及子公司的回答須保留各自主體；未指明主體不得自行歸給金控。'
        '未來、預計、目標與預算不是已發生的事實。原生文字已取得，但未驗完整圖像，'
        '不覆寫經核對財報或TTM；活動開始時間已過不等於獨立證明活動舉行。')


def supports_tcfhc(ticker):
    return str(ticker).strip().upper() in {'5880', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, url=MASTER_URL, *, as_of_epoch=None):
    reference = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_identity.master_rows(raw, epoch, url)
    selected = [r for r in rows if r.get('公司代號') == '5880']
    if len(selected) != 1:
        raise ValueError('TCFHC master issuer not unique')
    r = selected[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '合庫金', '營利事業統一編號': '53021433', '網址': 'www.tcfhc.com.tw'}
    if any(r.get(k) != v for k, v in expected.items()) or not re.fullmatch(r'\d{7}', r.get('出表日期', '')):
        raise ValueError('TCFHC master identity invalid')
    d = r['出表日期']
    observed = date(int(d[:3]) + 1911, int(d[3:5]), int(d[5:]))
    if not 0 <= (_today(reference) - observed).days <= 14 or observed > _today(epoch):
        raise ValueError('TCFHC master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': '53021433', 'as_of': observed.isoformat()}


def _html(raw):
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if '©合作金庫金控版權所有' not in soup.get_text(' ', strip=True):
        raise ValueError('TCFHC registered website owner absent')
    return soup


def select_event(raw, index_url):
    if route_kind(index_url) != 'index':
        raise ValueError('TCFHC year index invalid')
    year = int(index_url[-8:-4])
    if not _today().year - 1 <= year <= _today().year:
        raise ValueError('TCFHC year index outside current window')
    links = {}
    for a in _html(raw).select('.c-card__link a[href]'):
        url = urljoin(index_url, a['href'])
        if route_kind(url) != 'event' or not url.startswith(index_url + '/'):
            raise ValueError('TCFHC published event route invalid')
        q = int(url[-1])
        expected = f'前往{year}年?第' + '一二三四'[q - 1] + '季中文線上法說會'
        if not re.fullmatch(expected, a.get('title', '')) or q in links:
            raise ValueError('TCFHC event title or uniqueness invalid')
        links[q] = url
    if not links:
        raise ValueError('TCFHC event index empty')
    return links[max(links)]


def parse_event(raw, url):
    if route_kind(url) != 'event':
        raise ValueError('TCFHC event URL invalid')
    match = re.search(r'/(20\d{2})q([1-4])$', url)
    year, q = int(match[1]), int(match[2])
    soup = _html(raw)
    title = f'{year}年第' + '一二三四'[q - 1] + '季中文線上法說會'
    if title not in soup.get_text(' ', strip=True):
        raise ValueError('TCFHC event title mismatch')
    fields = {}
    for row in soup.select('tr'):
        key, value = row.find('th'), row.find('td')
        if key is None or value is None:
            continue
        key = key.get_text(' ', strip=True)
        if key in {'活動類型', '活動日期', '活動時間'}:
            if key in fields:
                raise ValueError('TCFHC duplicated event field')
            fields[key] = value.get_text(' ', strip=True)
    if fields.get('活動類型') != '法人說明會':
        raise ValueError('TCFHC event type invalid')
    day = date.fromisoformat(fields['活動日期'])
    clock = re.fullmatch(r'(\d{2}):(\d{2})\s*\(GMT\+8\)', fields['活動時間'])
    if clock is None or day.year != year:
        raise ValueError('TCFHC event date/time invalid')
    start = datetime.combine(day, datetime.min.time(), ZoneInfo('Asia/Taipei')).replace(hour=int(clock[1]), minute=int(clock[2]))
    if start.timestamp() > time.time() or (_today() - day).days > 370:
        raise ValueError('TCFHC event is future or too old')
    candidates = []
    for li in soup.select('li.c-list__item'):
        label, version = li.select_one('.c-list__title'), li.select_one('.c-list__date')
        if label is None or label.get_text(' ', strip=True) != '投資人提問重點摘要':
            continue
        links = li.select('.c-list__link a[href]')
        if version is None or len(links) != 1:
            raise ValueError('TCFHC QA version or attachment absent')
        version_text = version.get_text(' ', strip=True)
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2} 版本', version_text):
            raise ValueError('TCFHC QA version date invalid')
        version_date = date.fromisoformat(version_text[:10])
        link = urljoin(url, links[0]['href'])
        expected_path = f'/-/media/files/tcfhc/investors-relations/event/{year}year/{year}q{q}question.pdf'
        if (route_kind(link) != 'qa' or urlsplit(link).path != expected_path
                or not day <= version_date <= _today()):
            raise ValueError('TCFHC QA event/attachment mismatch')
        candidates.append({'event_date': day.isoformat(), 'event_time': start.strftime('%H:%M'),
                           'version_date': version_date.isoformat(), 'period': f'{year}Q{q}',
                           'title': title + '投資人提問重點摘要', 'qa_url': link, 'event_url': url})
    if len(candidates) != 1:
        raise ValueError('TCFHC QA attachment is missing or ambiguous')
    return candidates[0]


def native_qa(raw, selected, deadline):
    _check(deadline)
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline - time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    year, q = selected['period'].split('Q')
    heading = year + '年第' + '一二三四'[int(q) - 1] + '季法人說明會投資人提問重點摘要'
    first = re.sub(r'\s+', '', native['pages'][0]['text'])
    if (heading not in first or native['coverage_status'] != 'complete'
            or native['empty_pages'] or native['garbled_pages']
            or not 1 <= native['page_count'] <= 30
            or not any('答' in p['text'] for p in native['pages'])):
        raise ValueError('TCFHC complete native QA text unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id': '5880:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'title': selected['title'], 'url': selected['qa_url'], 'source': PROVIDER,
           'source_type': 'issuer_official', 'document_kind': 'issuer_qa_summary',
           'event_date': selected['event_date'], 'event_time': selected['event_time'], 'event_timezone': 'Asia/Taipei',
           'event_date_basis': 'issuer_event_page_and_QA_period_match',
           'event_status': 'announced_past_start_not_independently_occurrence_verified',
           'published_at': None, 'material_file_date': selected['version_date'], 'content_period': selected['period'],
           'retrieved_at_epoch': proof['qa']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False, 'parser_version': native['parser_version']}
    return {'ticker': TICKER, 'date': selected['event_date'], 'time': selected['event_time'],
            'period': selected['period'], 'title': selected['title'], 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'source': PROVIDER, 'source_url': selected['event_url'],
            'materials': [{'url': selected['qa_url'], 'kind': 'issuer_qa_summary'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': proof['qa']['retrieved_at'], 'tcfhc_qa_receipt': proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(master_identity.current_at(proof[k], max_age, observed)
               for k in ('identity', 'index', 'event', 'qa'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic() + 10.
    try:
        _check(deadline)
        if not supports_tcfhc(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['tcfhc_qa_receipt']
        if (set(proof) != {'policy', 'identity', 'index', 'event', 'qa', 'selected'}
                or not master_identity.valid_master_policy(proof['policy'], proof['identity'], POLICY, LEGACY_POLICY)):
            return False
        master_url = proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'], master_url, max_age=max_age),
                     proof['identity']['retrieved_at'], master_url)
        index_url = proof['index']['source_url']
        url = select_event(original_bytes(proof['index'], index_url, max_age=max_age), index_url)
        selected = parse_event(original_bytes(proof['event'], url, max_age=max_age), url)
        if selected != proof['selected']:
            return False
        if (date.fromisoformat(selected['event_date']) > _today(proof['event']['retrieved_at'])
                or date.fromisoformat(selected['version_date']) > _today(proof['qa']['retrieved_at'])):
            return False
        raw = original_bytes(proof['qa'], selected['qa_url'], max_age=max_age)
        expected = _context(selected, native_qa(raw, selected, deadline), proof)
        for key, source_url in [('identity', master_url), ('index', index_url), ('event', url), ('qa', selected['qa_url'])]:
            original_bytes(proof[key], source_url, max_age=max_age)
        matches = value == expected
        _check(deadline)
        return matches and _originals_fresh(proof, max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout':
            raise
        return False
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError, EOFError, zlib.error, SourcePdfError):
        return False


def fetch_tcfhc_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_tcfhc(ticker):
        return {}
    deadline = time.monotonic() + 20.
    http = ConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'tcfhc_qa_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL)
        parse_master(raw, identity['retrieved_at'], identity['source_url'])
        _check(deadline)
        index_url = ROOT + str(_today().year) + 'year'
        raw, index = http.get_receipt(index_url)
        event_url = select_event(raw, index_url)
        raw, event = http.get_receipt(event_url)
        selected = parse_event(raw, event_url)
        raw, qa = http.get_receipt(selected['qa_url'])
        native = native_qa(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'event': event, 'qa': qa, 'selected': selected}
        context = _context(selected, native, proof)
        if not verify_context(context, TICKER, deadline=deadline, max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        _check(deadline)
        if not _originals_fresh(proof, RAW_TTL):
            raise SourceResponseError('original_expired')
        details.update(coverage_status='native_qa_text_complete', tcfhc_originals_verified=True,
                       cache_hit=qa['cache_hit'], fetched_at_epoch=qa['retrieved_at'], message=NOTE)
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        details.update(tcfhc_originals_verified=False, error_kind=exc.error_kind, status='error', component_statuses=deepcopy(http.components),
                       http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:
            diagnostics.update(details)
        if exc is original:
            raise
        raise exc from original
    if diagnostics is not None:
        diagnostics.update(details)
    return context


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType'))):
        return False
    identity = data.get('company_identity')
    if identity is None:
        identity = {}
    if not isinstance(identity, dict):
        return False
    for key, expected in [('ticker', TICKER), ('stock_id', '5880'), ('official_name', '合庫金'),
                          ('legal_name', LEGAL), ('official_ubn', '53021433'), ('instrument_type', 'EQUITY')]:
        if identity.get(key) not in (None, '', expected):
            return False
    for key in ('allowed_aliases', 'english_names', 'forbidden_aliases'):
        values = identity.get(key, [])
        if not isinstance(values, (list, tuple)) or any(not isinstance(s, str) for s in values):
            return False
    if data.get('company_name') is not None:
        names = {'合庫金', LEGAL, 'taiwan cooperative financial holding co., ltd.', 'taiwan cooperative financial holding co. ltd.'}
        if (not isinstance(data['company_name'], str)
                or not all(v.strip().casefold() in names for v in data['company_name'].split(' / '))):
            return False
    forbidden = identity.get('forbidden_aliases', [])
    if (not isinstance(forbidden, (list, tuple)) or any(not isinstance(s, str) for s in forbidden)
            or {'合庫金', LEGAL} & {s.strip('* ').strip() for s in forbidden}):
        return False
    return True


def is_marked(value):
    if not isinstance(value, dict):
        return False
    return ('tcfhc_qa_receipt' in value or value.get('source') == PROVIDER
            or route_kind(value.get('source_url')) in {'event', 'qa'}
            or any(isinstance(doc, dict) and (doc.get('source') == PROVIDER or route_kind(doc.get('url')) == 'qa')
                   for key in ('documents', 'materials') for doc in (value.get(key) if isinstance(value.get(key), list) else [])))
