"""Issuer-published English presentation with replayable originals and visual limits."""
from . import conference_issuer_master as master_identity
from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo
import json
import re
import time
import zlib
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .tewc_conference_transport import (ConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER,
    RAW_TTL, PDF_LIMIT, original_bytes, verify_redirect_receipt, route_kind)

TICKER = '1623.TW'
LEGAL = '大東電業廠股份有限公司'
LEGACY_POLICY = 'tewc-published-English-presentation-v1'
POLICY = 'tewc-published-English-presentation-v2'
KNOWN_SHA = '4514db4ca2c720a5113298397baff01075175ff1ac4d16e1b9d23c2732a38c48'
NOTE = ('大東電官網發布的英文法說簡報，並非逐字稿；英文翻譯、實際會議及公司陳述未獨立驗證。'
        '僅原生文字可讀，圖片、圖表數值與閱讀順序未全部驗證；Q&A末頁沒有問答正文。'
        '財年與第一季分開，展望保持公司說法；不得推算圖中訂單序列或覆寫已核對財報。')
KNOWN_NOTE = '本份2026年5月簡報第19、29、34頁有圖像內容缺漏，第22頁以6.6億推算EPS，不能當法定EPS或TTM。'


def supports_tewc(ticker):
    return str(ticker).strip().upper() in {'1623', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, url=MASTER_URL, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_identity.master_rows(raw, epoch, url)
    matches = [r for r in rows if r.get('公司代號') == '1623']
    if len(matches) != 1:
        raise ValueError('TEWC master issuer not unique')
    row = matches[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '大東電', '營利事業統一編號': '18523000',
                '英文簡稱': 'TEWC', '網址': 'http://tewc.com.tw/'}
    if any(row.get(k) != v for k, v in expected.items()) or not re.fullmatch(r'\d{7}', row.get('出表日期', '')):
        raise ValueError('TEWC master identity invalid')
    d = row['出表日期']; day = date(int(d[:3]) + 1911, int(d[3:5]), int(d[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('TEWC master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': '18523000', 'as_of': day.isoformat()}


def select_presentation(raw, epoch, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    text = soup.get_text(' ', strip=True)
    if (not soup.title or soup.title.get_text() != '股東服務 | 大東電業' or LEGAL not in text
            or not re.search(r'股票代號《\s*1623\s*》', text)
            or 'TEWC All Rights Reserved' not in text):
        raise ValueError('TEWC index owner unverified')
    headings = [h for h in soup.find_all('h2') if h.get_text(' ', strip=True) == '法人說明會資訊']
    if len(headings) != 1:
        raise ValueError('TEWC current event ambiguous')
    tables, links, ended = [], [], False
    for node in headings[0].find_all_next(['h2', 'table', 'a']):
        if node.name == 'h2':
            ended = node.get_text(' ', strip=True) == '歷年法人說明會相關資料'
            break
        if node.name == 'table': tables.append(node)
        if node.name == 'a' and node.has_attr('href'): links.append(node)
    if not ended or len(tables) != 1:
        raise ValueError('TEWC event section boundary invalid')
    rows = [[c.get_text(' ', strip=True) for c in r.find_all('td', recursive=False)] for r in tables[0].find_all('tr')]
    if len(rows) != 3 or any(len(r) != 2 for r in rows) or [r[0] for r in rows] != ['召開日期', '召開地點', '擇要訊息']:
        raise ValueError('TEWC event table invalid')
    stamp = re.sub(r'\s+', '', rows[0][1]).replace('：', ':')
    match = re.fullmatch(r'(\d{3})/(\d{2})/(\d{2})時間(\d{2}):(\d{2})', stamp)
    if not match:
        raise ValueError('TEWC event date missing')
    y, m, d, h, minute = map(int, match.groups()); day = date(y + 1911, m, d)
    if not 0 <= h < 24 or not 0 <= minute < 60 or day > _today(epoch) or not 0 <= (_today(observed) - day).days <= 370:
        raise ValueError('TEWC event time outside current window')
    english = [a['href'] for a in links if a.get_text(' ', strip=True) == '英文檔案']
    chinese = [a['href'] for a in links if a.get_text(' ', strip=True) == '中文檔案']
    if len(english) != 1 or len(chinese) != 1 or any(route_kind(u) != 'viewer' for u in english + chinese) or english == chinese:
        raise ValueError('TEWC published attachments ambiguous')
    file_id = english[0].split('/d/')[1].split('/')[0]
    return {'event_date': day.isoformat(), 'event_time': f'{h:02}:{minute:02}',
            'event_title': f'大東電 {day.isoformat()} 法人說明會英文簡報',
            'viewer_url': english[0], 'file_id': file_id,
            'uc_url': f'https://drive.usercontent.google.com/uc?id={file_id}&export=download',
            'pdf_url': f'https://drive.usercontent.google.com/download?id={file_id}&export=download'}


def parse_viewer(raw, selected):
    html = raw.decode('utf-8', 'strict')
    if html.count('itemJson: ') != 1:
        raise ValueError('TEWC viewer metadata ambiguous')
    items, _ = json.JSONDecoder().raw_decode(html.split('itemJson: ', 1)[1])
    if not isinstance(items, list) or len(items) <= 34:
        raise ValueError('TEWC viewer metadata incomplete')
    day = selected['event_date'].replace('-', '')
    filename = items[1]
    if (not isinstance(filename, str) or not re.fullmatch(r'大東電業法說會' + day + r'-EN-finalV\.\d+\.pdf', filename)
            or items[11] != 'application/pdf' or items[16] != selected['viewer_url'].split('?')[0]
            or items[18] != selected['uc_url'] or items[32] != 'pdf'
            or not isinstance(items[25], list) or len(items[25]) != 3
            or not isinstance(items[25][2], str) or not re.fullmatch(r'[1-9]\d{0,7}', items[25][2])
            or not isinstance(items[34], list) or len(items[34]) != 3 or items[34][2] != [selected['file_id']]):
        raise ValueError('TEWC viewer attachment does not match published event')
    size = int(items[25][2])
    if not 0 < size <= PDF_LIMIT:
        raise ValueError('TEWC PDF exceeds bounded original size')
    return {'filename': filename, 'bytes': size}


def native_presentation(raw, selected, file_info, deadline):
    _check(deadline)
    if len(raw) != file_info['bytes']:
        raise ValueError('TEWC original length differs from viewer')
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline - time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout': raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    cover = re.sub(r'\s+', '', native['pages'][0]['text']).casefold()
    day = date.fromisoformat(selected['event_date'])
    month = day.strftime('%B%Y').casefold()
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or not 2 <= native['page_count'] <= 60 or '大東電業廠(股)公司' not in cover
            or '1623tatunelectricwire&cableco.,ltd.' not in cover or month not in cover
            or 'Safe Harbor Notice' not in native['pages'][1]['text']
            or 'forward-looking statements' not in native['pages'][1]['text']):
        raise ValueError('TEWC native identity, date, or text incomplete')
    return native


def _context(selected, file_info, native, proof):
    known = native['content_sha256'] == KNOWN_SHA
    omissions = ([{'page_number': n, 'issue': issue} for n, issue in (
        (19, 'image_tables_and_map_not_fully_extracted'), (29, 'chart_period_values_not_extracted'),
        (34, 'image_diagram_not_extracted'))] if known else [])
    doc = {'document_id': '1623:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'title': selected['event_title'], 'url': selected['pdf_url'],
           'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation', 'language': 'en',
           'translation_accuracy_verified': False, 'event_date': selected['event_date'],
           'event_time': selected['event_time'], 'event_timezone': 'Asia/Taipei',
           'event_date_basis': 'issuer_current_event_table_and_attachment_filename',
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'content_period': None, 'presentation_cover_month': selected['event_date'][:7], 'published_at': None,
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'page_count': native['page_count'], 'pages': native['pages'],
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'known_native_text_omissions': omissions, 'calculated_eps_caution':
               '第22頁以6.6億推算EPS，非已核對法定EPS或TTM' if known else None,
           'parser_version': native['parser_version']}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': None, 'title': selected['event_title'],
            'source': PROVIDER, 'source_url': INDEX_URL, 'summary': '', 'transcript_excerpt': '',
            'transcript_available': False, 'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'en'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE + (KNOWN_NOTE if known else '')],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'tewc_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic() + 10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_tewc(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['tewc_conference_receipt']
        if set(proof) != {'policy', 'identity', 'index', 'viewer', 'redirect', 'pdf', 'selected', 'file_info'} or not master_identity.valid_master_policy(proof['policy'], proof['identity'], POLICY, LEGACY_POLICY):
            return False
        parse_master(original_bytes(proof['identity'], proof['identity']['source_url'], max_age=max_age), proof['identity']['retrieved_at'], proof['identity']['source_url'])
        selected = select_presentation(original_bytes(proof['index'], INDEX_URL, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected']:
            return False
        info = parse_viewer(original_bytes(proof['viewer'], selected['viewer_url'], max_age=max_age), selected)
        if info != proof['file_info']:
            return False
        if verify_redirect_receipt(proof['redirect'], selected['uc_url'], selected['pdf_url'], max_age=max_age) is not True:
            return False
        raw = original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age)
        expected = _context(selected, info, native_presentation(raw, selected, info, deadline), proof)
        # Extraction and decompression cannot extend any original's expiry.
        for key, url in [('identity', proof['identity']['source_url']), ('index', INDEX_URL), ('viewer', selected['viewer_url']), ('pdf', selected['pdf_url'])]:
            original_bytes(proof[key], url, max_age=max_age)
        if verify_redirect_receipt(proof['redirect'], selected['uc_url'], selected['pdf_url'], max_age=max_age) is not True:
            return False
        matches = value == expected
        _check(deadline)
        # A later large original may consume the remaining lifetime of an
        # earlier receipt. Check all five against the same delivery instant.
        completed_at = time.time()
        return matches and all(master_identity.current_at(proof[key], max_age, completed_at)
                               for key in ('identity', 'index', 'viewer', 'redirect', 'pdf'))
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError, OSError, EOFError, zlib.error, SourcePdfError):
        return False


def fetch_tewc_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_tewc(ticker): return {}
    deadline = time.monotonic() + 20.
    http = ConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'tewc_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL); parse_master(raw, identity['retrieved_at'], identity['source_url'])
        raw, index = http.get_receipt(INDEX_URL); selected = select_presentation(raw, index['retrieved_at'])
        raw, viewer = http.get_receipt(selected['viewer_url']); info = parse_viewer(raw, selected)
        redirect = http.get_redirect_receipt(selected['uc_url'], selected['pdf_url'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native = native_presentation(raw, selected, info, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'viewer': viewer, 'redirect': redirect,
                 'pdf': pdf, 'selected': selected, 'file_info': info}
        value = _context(selected, info, native, proof)
        if not verify_context(value, TICKER, deadline=deadline, max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        details.update(tewc_originals_verified=True, coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'], fetched_at_epoch=pdf['retrieved_at'], message=value['coverage_notes'][0])
        _check(deadline)
        details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        _check(deadline)
        completed_at = time.time()
        if not all(master_identity.current_at(proof[k], RAW_TTL, completed_at) for k in ('identity', 'index', 'viewer', 'redirect', 'pdf')):
            raise SourceResponseError('original_expired')
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        details.update(tewc_originals_verified=False, error_kind=exc.error_kind, status='error', component_statuses=deepcopy(http.components),
                       http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None: diagnostics.update(details)
        if exc is original: raise
        raise exc from original
    if diagnostics is not None: diagnostics.update(details)
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type', 'quote_type', 'quoteType'))):
        return False
    identity = data.get('company_identity')
    if identity is None: identity = {}
    if not isinstance(identity, dict): return False
    for k, v in [('ticker', TICKER), ('stock_id', '1623'), ('official_name', '大東電'), ('legal_name', LEGAL),
                 ('official_ubn', '18523000'), ('instrument_type', 'EQUITY')]:
        if identity.get(k) not in (None, '', v): return False
    for k in ('allowed_aliases', 'english_names', 'forbidden_aliases'):
        values = identity.get(k, [])
        if not isinstance(values, (list, tuple)) or any(not isinstance(v, str) for v in values): return False
    names = {'大東電', LEGAL, 'ta tun electric wire & cable co., ltd.', 'ta tun electric wire & cable co. ltd.'}
    name = data.get('company_name')
    if name is not None and (not isinstance(name, str) or not all(v.strip().casefold() in names for v in name.split(' / '))):
        return False
    return not ({'大東電', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases', [])})


def is_marked(value):
    return isinstance(value, dict) and ('tewc_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d, dict) and d.get('source') == PROVIDER
           for k in ('documents', 'materials') for d in (value.get(k) if isinstance(value.get(k), list) else [])))
