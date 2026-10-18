"""Unitech's published native presentation, with explicit visual/use limits."""
from . import conference_issuer_master as master_identity
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import re
import time
import zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .unitech_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes
from .tcfhc_conference_transport import valid_epoch

TICKER = '2367.TW'
LEGAL = '燿華電子股份有限公司'
LEGACY_POLICY = 'unitech-published-native-presentation-v1'
POLICY = 'unitech-published-native-presentation-v2'
KNOWN_SHA = '7ac756ca1494d09869df27e51d5e1441451e04d0acb8e5bde5d106c7654b7700'
NOTE = ('燿華官網發布的法說簡報，不是逐字稿；官網日期時間與封面日期一致，未獨立證實實際舉行或公司陳述。'
        '全16頁原生文字可讀不代表所有視覺內容已讀；第3、5、9、10、11頁有圖像內容缺漏，不能補造圖表數字。'
        '內容含不同期間、比較及預估，期間未知不套用場次年份，展望不當已實現。'
        '第2頁免責聲明與「機密性質、保留所有權」原文保留；公開官網發布不代表開放授權，商業再利用權未驗證。')


def supports_unitech(ticker):
    return str(ticker).strip().upper() in {'2367', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, url=MASTER_URL, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_identity.master_rows(raw, epoch, url)
    matched = [r for r in rows if r.get('公司代號') == '2367']
    if len(matched) != 1:
        raise ValueError('Unitech master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '燿華', '營利事業統一編號': '05637971',
                '英文簡稱': 'UNITECH', '網址': 'https://www.pcbut.com.tw'}
    if any(row.get(k) != v for k, v in expected.items()) or not re.fullmatch(r'\d{7}', row.get('出表日期', '')):
        raise ValueError('Unitech master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Unitech master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '燿華', 'official_ubn': '05637971',
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def select_presentation(raw, epoch, *, as_of_epoch=None):
    observed = master_identity.reference_epoch(epoch, as_of_epoch=as_of_epoch)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 200_000:
        raise ValueError('Unitech index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    headings = [h for h in soup.find_all('span') if h.get_text(' ', strip=True) == '法人說明會']
    if len(headings) != 1:
        raise ValueError('Unitech conference role unverified')
    expected_header = ['日期', '時間', '地點', '法人說明會擇要訊息', '簡報檔']
    headers = [r for r in soup.find_all('tr') if [c.get_text(' ', strip=True) for c in r.find_all('td', recursive=False)] == expected_header]
    if len(headers) != 1:
        raise ValueError('Unitech conference table unverified')
    table = headers[0].find_parent('table')
    if headings[0].find_next('table') is not table:
        raise ValueError('Unitech conference section mismatch')
    rows = table.find_all('tr'); candidates = []; identities = set()
    if not 2 <= len(rows) <= 100:
        raise ValueError('Unitech conference table length invalid')
    for row in rows[1:]:
        cells = row.find_all('td', recursive=False)
        if len(cells) != 5:
            raise ValueError('Unitech conference row malformed')
        texts = [c.get_text(' ', strip=True) for c in cells]
        stamp = re.fullmatch(r'(\d{3})/(\d{2})/(\d{2})', texts[0])
        clock = re.fullmatch(r'(\d{2})[：:](\d{2})', texts[1])
        links = cells[4].find_all('a', href=True)
        if not stamp or not clock or len(links) != 1 or not texts[2] or texts[3] != '本公司近期營運概況說明':
            raise ValueError('Unitech published row fields invalid')
        y, m, d = map(int, stamp.groups()); day = date(y + 1911, m, d)
        hour, minute = map(int, clock.groups()); href = links[0]['href']
        if not 0 <= hour < 24 or not 0 <= minute < 60 or not re.fullmatch(r'/downloads/InvestorConference20\d{2}(?:-\d+)?\.pdf', href):
            raise ValueError('Unitech published time or PDF path invalid')
        identity = (day.isoformat(), f'{hour:02}:{minute:02}')
        if identity in identities:
            raise ValueError('Unitech event ambiguous')
        identities.add(identity)
        if day <= _today(epoch) and 0 <= (_today(observed) - day).days <= 370:
            candidates.append((day, hour, minute, href, texts[2]))
    if not candidates:
        raise ValueError('Unitech current past event absent')
    day, hour, minute, href, place = max(candidates)
    if 'https://www.pcbut.com.tw' + href != PDF_URL or day.isoformat() != '2026-06-26':
        raise ValueError('Unitech latest presentation outside qualified original profile')
    return {'event_date': day.isoformat(), 'event_time': f'{hour:02}:{minute:02}', 'event_location': place,
            'event_title': f'燿華 {day.isoformat()} 法人說明會簡報', 'pdf_url': PDF_URL,
            'selection_policy': 'latest_explicit_past_event_date_and_time_in_published_conference_table'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('Unitech original revision is not qualified')
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline - time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 16 or len(pages) != 16
            or LEGAL not in pages[0]['text'] or 'Unitech Printed Circuit Board Corp.' not in pages[0]['text']
            or 'www.pcbut.com.tw' not in pages[0]['text']
            or re.findall(r'20\d{2}/\d{2}/\d{2}', pages[0]['text']) != [selected['event_date'].replace('-', '/')]
            or any(s not in pages[1]['text'] for s in ('免責聲明', '機密性質', '保留其所有權', '未來性陳述'))):
        raise ValueError('Unitech native identity, date or limitations unverified')
    _check(deadline)
    return native


def _context(selected, native, proof):
    doc = {'document_id': '2367:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': PDF_URL, 'language': 'zh-TW', 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_conference_table_and_exact_PDF_cover_date',
           'event_time': selected['event_time'], 'event_timezone': None,
           'event_time_basis': 'issuer_table_unzoned_time', 'event_location': selected['event_location'],
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'content_period': None, 'published_at': None, 'material_date': None,
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': native['empty_pages'],
           'garbled_pages': native['garbled_pages'], 'parser_version': native['parser_version'],
           'known_native_text_omissions': [{'page_number': p, 'issue': 'visual_content_not_fully_represented_in_native_text'} for p in (3,5,9,10,11)],
           'ownership_confidentiality_notice_present': True, 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': None, 'title': selected['event_title'],
            'source': PROVIDER, 'source_url': INDEX_URL, 'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': PDF_URL, 'kind': 'presentation', 'language': 'zh-TW'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE], 'selection_policy': selected['selection_policy'],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'unitech_conference_receipt': proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(master_identity.current_at(proof[k], max_age, observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic() + 10.
    try:
        _check(deadline)
        if not supports_unitech(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['unitech_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or not master_identity.valid_master_policy(proof['policy'], proof['identity'], POLICY, LEGACY_POLICY):
            return False
        parse_master(original_bytes(proof['identity'], proof['identity']['source_url'], max_age=max_age), proof['identity']['retrieved_at'], proof['identity']['source_url'])
        selected = select_presentation(original_bytes(proof['index'], INDEX_URL, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'], PDF_URL, max_age=max_age)
        expected = _context(selected, native_presentation(raw, selected, deadline), proof)
        # Recheck originals after parsing, then all epochs at one handoff time.
        for key, url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_unitech_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_unitech(ticker): return {}
    deadline = time.monotonic() + 25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'unitech_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected=select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native=native_presentation(raw,selected,deadline)
        proof={'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value=_context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value=deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(unitech_originals_verified=True,coverage_status='native_presentation_text_complete',
                       # A fresh index with the same cached PDF is not new body data.
                       cache_hit=pdf['cache_hit'],stale=False,
                       fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
    except Exception as original:
        exc=original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        details.update(unitech_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    if diagnostics is not None:diagnostics.update(details)
    return value


def validate_context(data,ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity=data.get('company_identity')
    if identity is None:identity={}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','2367'),('official_name','燿華'),('legal_name',LEGAL),
                         ('official_ubn','05637971'),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows=identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
    names={'燿華',LEGAL,'unitech','unitech printed circuit board corp.'}
    name=data.get('company_name')
    if name is not None and (not isinstance(name,str) or not all(s.strip().casefold() in names for s in name.split(' / '))):return False
    return not (names & {s.strip('* ').strip().casefold() for s in identity.get('forbidden_aliases',[])})


def is_marked(value):
    return isinstance(value,dict) and ('unitech_conference_receipt' in value or value.get('source')==PROVIDER
        or value.get('source_url')==INDEX_URL or any(isinstance(d,dict) and (d.get('source')==PROVIDER or d.get('url')==PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
