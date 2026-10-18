"""Discover dated issuer presentations, without upgrading visual or date claims."""
from copy import deepcopy
from datetime import date, datetime
import re
import time
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .promate_conference_transport import PromateConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER, pdf_url, original_bytes
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at
from .tcfhc_conference_transport import valid_epoch

TICKER = '6189.TW'
LEGAL = '豐藝電子股份有限公司'
UBN = '22151585'
POLICY = 'promate-dated-presentation-v1'
NOTE = ('官方法說簡報，非逐字稿；日期來自官方簡報連結標題，不推定首次發布或實際舉行時間。'
        '原生文字完整不代表圖表語意完整；公司、子公司、季度與累計期間不得混用，簡報不替代經查核財報。'
        '標題與表格日期衝突的頁面保留原文但不供角色引用；展望是公司當時陳述，非已實現結果。')


def supports_promate(ticker):
    return str(ticker).strip().upper() == TICKER


def _today(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    observed = reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_rows(raw, epoch, source_url)
    matched = [r for r in rows if r.get('公司代號') == '6189']
    if len(matched) != 1:
        raise ValueError('Promate master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '豐藝', '營利事業統一編號': UBN,
                '網址': 'https://www.promate.com.tw/'}
    if (any(row.get(k) != v for k, v in expected.items()) or row.get('英文簡稱', '').strip() != 'Promate'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Promate master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Promate master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': UBN, 'as_of': day.isoformat()}


def select_presentation(raw, epoch, *, as_of_epoch=None):
    today = _today(reference_epoch(epoch, as_of_epoch=as_of_epoch))
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 500_000:
        raise ValueError('invalid index size')
    text = raw.decode('utf-8-sig', 'strict')
    if text.count('</html>') != 1 or text.count('</body>') != 1:
        raise ValueError('complete index required')
    soup = BeautifulSoup(text, 'html.parser')
    if (not soup.title or soup.title.get_text(' ', strip=True) != '法人說明會 - 豐藝電子'
            or [x.get('href') for x in soup.select('link[rel="canonical"]')] != [INDEX_URL]):
        raise ValueError('index publisher changed')
    candidates = set()
    for a in soup.select('a[href]'):
        title = a.get_text(' ', strip=True)
        if '書面簡報資料' not in title:
            continue  # Date-only links on this page point to older files.
        match = re.match(r'^(20\d{2})/(\d{1,2})/(\d{1,2})\s+', title)
        if not match:
            raise ValueError('undated presentation candidate')
        day = date(*map(int, match.groups()))
        if day.year < today.year - 1:
            continue  # Older index entries include legacy date ranges.
        if '法人說明會' not in title or not re.fullmatch(r'20\d{2}/\d{1,2}/\d{1,2}\s+(?:線上)?法人說明會\s+書面簡報資料', title):
            raise ValueError('current presentation title ambiguous')
        if day > _today(epoch) or (today - day).days > 370:
            continue
        url = a['href']
        if not pdf_url(url):
            raise ValueError('presentation URL outside official uploads')
        u = urlsplit(url)
        url = urlunsplit((u.scheme, u.netloc, quote(unquote(u.path), safe='/'), '', ''))
        candidates.add((day, title, url))
    if not candidates:
        raise ValueError('no current dated presentation')
    latest = max(x[0] for x in candidates)
    selected = [x for x in candidates if x[0] == latest]
    if len(selected) != 1:
        raise ValueError('ambiguous latest presentation')
    day, title, url = selected[0]
    return {'event_date': day.isoformat(), 'event_title': title, 'pdf_url': url,
            'selection_policy': 'latest_past_explicit_presentation_link_not_date_only_anchor'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']; text = '\n'.join(p['text'] for p in pages)
    cover = pages[0]['text'] if pages else ''
    match = re.search(r'(20\d{2})年法人說明會', cover)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or not 3 <= native['page_count'] <= 50 or LEGAL not in cover
            or not re.search(r'股票代號\s*[:：]\s*6189\b', cover) or not match
            or match[1] != selected['event_date'][:4] or '免責聲明' not in text
            or not any(term in text for term in ('營運成果', '營運績效'))):
        raise ValueError('native presentation identity or body unverified')
    conflicts = []
    for p in pages:
        if '資產負債表' not in p['text']:
            continue
        title = re.search(r'(20\d{2})年[^\n]*資產負債表', p['text'])
        columns = re.findall(r'(20\d{2})年\d{1,2}月\d{1,2}日', p['text'])
        if title and columns and int(title[1]) != max(map(int, columns)):
            conflicts.append(p['page_number'])
    return native, conflicts


def _context(selected, native, conflicts, proof):
    doc = {'document_id': '6189:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': selected['pdf_url'], 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_presentation_link_title', 'published_at': None,
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': [], 'garbled_pages': [],
           'period_conflict_pages': conflicts, 'parser_version': native['parser_version'],
           'financial_scope_caution': NOTE}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': selected['event_date'][:4],
            'title': selected['event_title'], 'source': PROVIDER, 'source_url': INDEX_URL,
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'zh-TW'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'promate_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic()+10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_promate(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['promate_conference_receipt']
        if set(proof) != {'policy', 'identity', 'index', 'pdf', 'selected'} or proof['policy'] != POLICY or not is_shared(proof['identity']):
            return False
        identity = proof['identity']; url = identity['source_url']
        parse_master(original_bytes(identity, url, max_age=max_age), identity['retrieved_at'], url)
        selected = select_presentation(original_bytes(proof['index'], INDEX_URL, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        native, conflicts = native_presentation(original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age), selected, deadline)
        expected = _context(selected, native, conflicts, proof)
        _check(deadline)
        return value == expected and current_at(identity, max_age, time.time()) and all(valid_epoch(proof[k]['retrieved_at'], max_age) for k in ('index','pdf'))
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, SourcePdfError):
        return False


def fetch_promate_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_promate(ticker): return {}
    deadline = time.monotonic()+20.
    http = PromateConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'promate_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL); parse_master(raw, identity['retrieved_at'], identity['source_url'])
        raw, index = http.get_receipt(INDEX_URL); selected = select_presentation(raw, index['retrieved_at'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native, conflicts = native_presentation(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'pdf': pdf, 'selected': selected}
        value = _context(selected, native, conflicts, proof)
        if not verify_context(value, ticker, deadline=deadline, max_age=1800):
            raise SourceResponseError('original_unverified')
        _check(deadline)
        details.update(promate_originals_verified=True, coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'], fetched_at_epoch=pdf['retrieved_at'], message=NOTE)
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        details.update(error_kind=exc.error_kind, status='error', component_statuses=deepcopy(http.components),
                       http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None: diagnostics.update(details)
        if exc is original: raise
        raise exc from original
    details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
    if diagnostics is not None: diagnostics.update(details)
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type','quote_type','quoteType'))): return False
    identity = data.get('company_identity')
    if identity is None: identity = {}
    if not isinstance(identity, dict): return False
    for k, expected in [('ticker',TICKER),('stock_id','6189'),('official_name','豐藝'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(k) not in (None, '', expected): return False
    name = data.get('company_name')
    names = {'豐藝', LEGAL, 'promate electronic co., ltd.', 'promate electronic co.,ltd.', 'promate electronic co. ltd.'}
    if name is not None and (not isinstance(name,str) or any(s.strip().casefold() not in names for s in name.split(' / '))): return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key, [])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows): return False
    return not ({'豐藝', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases',[])})


def is_marked(value):
    return isinstance(value,dict) and ('promate_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or pdf_url(d.get('url')))
        for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    # Conservative narrative-only projection survives new document versions.
    # Tables, product-mix charts, group structure and conflicted periods remain
    # archived evidence, not flattened numeric input for an agent.
    if document.get('ticker') != TICKER or document.get('source') != PROVIDER or document.get('coverage_status') != 'partial': return []
    pages = document.get('pages', []); conflicts = document.get('period_conflict_pages', [])
    kept = []
    for p in pages:
        if not isinstance(p,dict) or not isinstance(p.get('text'),str) or p.get('page_number') in conflicts: continue
        text = p['text']
        if any(term in text for term in ('資產負債表','損益表','集團','產品組合','出貨比重')): continue
        if p.get('page_number') == 1 or any(term in text for term in ('免責聲明','核心競爭力','競爭優勢','未來展望')):
            kept.append(deepcopy(p))
    return kept
