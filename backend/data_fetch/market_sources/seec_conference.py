"""Discover dated issuer presentations, without upgrading visual or date claims."""
from copy import deepcopy
from datetime import date, datetime
import re
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .seec_conference_transport import SeecConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER, pdf_url, original_bytes
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at
from .tcfhc_conference_transport import valid_epoch

TICKER = '1503.TW'
LEGAL = '士林電機廠股份有限公司'
UBN = '11039306'
POLICY = 'seec-dated-presentation-v1'
NOTE = ('士電官方準備簡報，非逐字稿；場次日期來自官網清單，並非首次發布或實際舉行證明。'
        '包含公司對未來的預期，受已知及未知風險影響，實際結果可能不同；公司除法令要求外無主動更新義務。'
        '財務頁為當年上半年對前一年上半年合併損益，金額新台幣佰萬，EPS單位元，不能當全年或年度查核財報。'
        '原生文字仍有缺漏：免責與公司簡介頁有未映射符號，合作伙伴文字部分被圖片遮擋；'
        '圖表數值與股利頁的向上箭頭未完整抽取，不能推論精確配發率。'
        '據點地圖的座標與工廠欄位關係未保留；海外共8家僅指大陸地區，非全部海外。'
        '公司陳述未獨立查證；事業產品清單不代表各項已有營收或訂單，末端分類字樣不能當逐項歸屬證據。'
        '未驗證商業重製或散布授權；引用限必要片段並附來源。')


def supports_seec(ticker):
    return str(ticker).strip().upper() == TICKER


def _today(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    observed = reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_rows(raw, epoch, source_url)
    matched = [r for r in rows if r.get('公司代號') == '1503']
    if len(matched) != 1:
        raise ValueError('Seec master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '士電', '營利事業統一編號': UBN,
                '網址': 'www.seec.com.tw'}
    if (any(row.get(k) != v for k, v in expected.items()) or row.get('英文簡稱', '').strip() != 'SEEC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Seec master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Seec master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': UBN, 'as_of': day.isoformat()}


def select_presentation(raw, epoch, *, as_of_epoch=None):
    today = _today(reference_epoch(epoch, as_of_epoch=as_of_epoch))
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 500_000:
        raise ValueError('invalid index size')
    text = raw.decode('utf-8-sig', 'strict')
    soup = BeautifulSoup(text, 'html.parser')
    if (text.count('</html>') != 1 or text.count('</body>') != 1 or not soup.title
            or soup.title.get_text(' ', strip=True) != '法人說明會 - 投資人專區 - 士林電機'):
        raise ValueError('complete issuer index required')
    tables = [t for t in soup.find_all('table') if
              [x.get_text(' ', strip=True) for x in t.find_all('th')] == ['開會日期', '會議名稱']]
    if len(tables) != 1:
        raise ValueError('unique event table required')
    events = {}
    for row in tables[0].find_all('tr'):
        cells = row.find_all('td')
        if not cells:
            continue
        if len(cells) != 2:
            raise ValueError('event row invalid')
        match = re.fullmatch(r'(20\d{2})年(\d{2})月(\d{2})日', cells[0].get_text(strip=True))
        title = cells[1].get_text(' ', strip=True)
        if not match or title != match[1] + '年法人說明會':
            raise ValueError('event date or title ambiguous')
        day = date(*map(int, match.groups()))
        if day.year in events:
            raise ValueError('multiple same-year events cannot bind one attachment')
        events[day.year] = (day, title)
    past = [v for v in events.values() if v[0] <= min(today, _today(epoch)) and 0 <= (today-v[0]).days <= 370]
    if not past:
        raise ValueError('no current past event')
    day, title = max(past, key=lambda v: v[0])
    label = str(day.year) + '年法說會簡報檔(PDF)(檔案下載)'
    links = [a for a in soup.find_all('a', href=True) if a.get_text(' ', strip=True) == label]
    if len(links) != 1:
        raise ValueError('latest event requires unique year-bound attachment')
    url = urljoin(INDEX_URL, links[0]['href'])
    if not pdf_url(url):
        raise ValueError('latest event attachment unavailable')
    return {'event_date': day.isoformat(), 'event_end_date': day.isoformat(), 'event_title': title,
            'pdf_url': url, 'selection_policy': 'latest_past_issuer_event_with_unique_year_bound_attachment'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    _check(deadline)
    pages = native['pages']; cover = pages[0]['text'] if pages else ''
    year = date.fromisoformat(selected['event_date']).year
    roc = year - 1911
    if (not 3 <= native['page_count'] <= 50 or 1 in native['garbled_pages']
            or not re.search(r'\b1503TW\b', cover) or '士林電機' not in cover
            or 'SHIHLIN ELECTRIC & ENGINEERING CORP' not in ' '.join(cover.split())
            or not re.search(rf'\b{roc}年\s*法人說明會', cover)):
        raise ValueError('native presentation identity or year unverified')
    text = '\n'.join(p['text'] for p in pages)
    if not all(t in text for t in ('免責聲明', '四大事業領域', '公司財務概況')):
        raise ValueError('native presentation sections unverified')
    periods = re.findall(r'公司財務概況-(\d{3})年上半年合併損益表', text)
    if periods != [str(roc)] or date.fromisoformat(selected['event_date']) < date(year, 7, 1):
        raise ValueError('native financial period inconsistent')
    # Preserve incomplete pages in storage, but never project their chart-only text.
    omissions = [p['page_number'] for p in pages if
                 any(t in p['text'] for t in ('營收及淨利', '營收佔比', '股利政策'))]
    return native, omissions


def _context(selected, native, conflicts, proof):
    doc = {'document_id': '1503:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': selected['pdf_url'], 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_event_table_year_bound_attachment', 'event_end_date': selected['event_end_date'], 'published_at': None,
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': native['coverage_status'] == 'complete', 'native_text_coverage': native['coverage_status'], 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'known_native_text_omission_pages': conflicts, 'parser_version': native['parser_version'],
           'financial_scope_caution': NOTE, 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': selected['event_date'][:4],
            'title': selected['event_title'], 'source': PROVIDER, 'source_url': INDEX_URL,
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'zh-TW'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'seec_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic()+10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_seec(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['seec_conference_receipt']
        if set(proof) != {'policy', 'identity', 'index', 'pdf', 'selected'} or proof['policy'] != POLICY or not is_shared(proof['identity']):
            return False
        if proof['index'].get('cache_hit') is not False:return False
        identity = proof['identity']; url = identity['source_url']
        parse_master(original_bytes(identity, url, max_age=max_age), identity['retrieved_at'], url)
        selected = select_presentation(original_bytes(proof['index'], INDEX_URL, max_age=max_age), proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        native, conflicts = native_presentation(original_bytes(proof['pdf'], selected['pdf_url'], max_age=max_age), selected, deadline)
        expected = _context(selected, native, conflicts, proof)
        _check(deadline)
        verified = value == expected and current_at(identity, max_age, time.time()) and all(valid_epoch(proof[k]['retrieved_at'], max_age) for k in ('index','pdf'))
        _check(deadline)
        return verified
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, SourcePdfError):
        return False


def fetch_seec_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_seec(ticker): return {}
    deadline = time.monotonic()+20.
    http = SeecConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'seec_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL); parse_master(raw, identity['retrieved_at'], identity['source_url'])
        raw, index = http.get_receipt(INDEX_URL); selected = select_presentation(raw, index['retrieved_at'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native, conflicts = native_presentation(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'pdf': pdf, 'selected': selected}
        value = _context(selected, native, conflicts, proof)
        if not verify_context(value, ticker, deadline=deadline, max_age=1800):
            raise SourceResponseError('original_unverified')
        _check(deadline)
        details.update(seec_originals_verified=True, coverage_status='native_presentation_text_partial',
                       cache_hit=pdf['cache_hit'], fetched_at_epoch=pdf['retrieved_at'], message=NOTE)
        details.update(component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        if diagnostics is not None: diagnostics.update(details)
        # Diagnostics serialization and lock cleanup are part of this delivery.
        _check(deadline)
        observed=time.time()
        if (not current_at(identity,1800,observed) or any(
                type(proof[k]['retrieved_at']) not in (int,float)
                or not 0 <= observed-proof[k]['retrieved_at'] < 1800 for k in ('index','pdf'))):
            raise SourceResponseError('original_expired')
        return value
    except Exception as original:
        exc = original if isinstance(original, SourceResponseError) else SourceResponseError('parse_error')
        # A late delivery failure must not retain successful body/cache markers.
        # Keep the actual HTTP/component evidence so the failed attempt is counted.
        for target in (details, diagnostics, exc.diagnostic):
            if target is not None:
                for key in ('cache_hit', 'coverage_status', 'fetched_at_epoch', 'message'):
                    target.pop(key, None)
        details.update(error_kind=exc.error_kind, status='error', seec_originals_verified=False,
                       component_statuses=deepcopy(http.components), http_request_sent=bool(http.http_request_count), http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None: diagnostics.update(details)
        if exc is original: raise
        raise exc from original


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data, dict) or data.get('ticker') != ticker
            or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None, '', 'EQUITY') for k in ('instrument_type','quote_type','quoteType'))): return False
    identity = data.get('company_identity')
    if identity is None: identity = {}
    if not isinstance(identity, dict): return False
    for k, expected in [('ticker',TICKER),('stock_id','1503'),('official_name','士電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(k) not in (None, '', expected): return False
    name = data.get('company_name')
    names = {'士電', '士林電機', LEGAL, 'shihlin electric & engineering corp.', 'shihlin electric & engineering corporation', 'seec'}
    if name is not None and (not isinstance(name,str) or any(s.strip().casefold() not in names for s in name.split(' / '))): return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key, [])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows): return False
    return not ({'士電', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases',[])})


def is_marked(value):
    return isinstance(value,dict) and ('seec_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or pdf_url(d.get('url')))
        for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    if document.get('ticker') != TICKER or document.get('source') != PROVIDER or document.get('coverage_status') != 'partial':
        return []
    excluded = set(document.get('missing_text_pages', [])) | set(document.get('garbled_pages', [])) | set(document.get('known_native_text_omission_pages', []))
    kept = []
    for page in document.get('pages', []):
        if not isinstance(page, dict) or not isinstance(page.get('text'), str) or page.get('page_number') in excluded:
            continue
        text = page['text']
        business = '四大事業領域' in text and all(t in text for t in (
            'Heavy Electric System', 'Breaker & Switchgear System',
            'Automobile Equipment System', 'Factory Automation System'))
        if page.get('page_number') == 1 or business or _half_year_table(text, document.get('event_date')):
            kept.append(deepcopy(page))
    return kept


def _half_year_table(text, event_date):
    """Keep complete native rows and their period columns together; infer no values."""
    try:
        roc = date.fromisoformat(event_date).year - 1911
    except (TypeError, ValueError):
        return False
    if (f'公司財務概況-{roc}年上半年合併損益表' not in text or '單位：新台幣佰萬' not in text
            or re.findall(r'(\d{3})年H1', text) != [str(roc), str(roc-1)]):
        return False
    number = r'-?\d[\d,]*(?:\.\d+)?'
    row = rf'\s+{number}\s+{number}\s+{number}\s+{number}\s+{number}%\s*'
    for label in ('營業收入', '營業毛利', '營業費用', '營業利益', '營業外收支', '稅前利益', '所得稅', '稅後淨利'):
        if len(re.findall(rf'^\s*{label}{row}$', text, re.M)) != 1:
            return False
    return len(re.findall(rf'^EPS\s+{number}\s+{number}\s*$', text, re.M)) == 1
