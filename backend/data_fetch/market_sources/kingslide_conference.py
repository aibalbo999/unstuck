"""Discover dated issuer presentations, without upgrading visual or date claims."""
from copy import deepcopy
from datetime import date, datetime
import re
import json
import time
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .kingslide_conference_transport import KingSlideConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER, pdf_url, original_bytes
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at
from .tcfhc_conference_transport import valid_epoch

TICKER = '2059.TW'
LEGAL = '川湖科技股份有限公司'
UBN = '22274989'
POLICY = 'kingslide-dated-presentation-v1'
NOTE = ('川湖官方準備簡報，非逐字稿；場次日期來自官網清單，並非首次發布或實際舉行證明。'
        '包含母公司與川益子公司及各頁明示的單季與累計期間，不能混用；不覆寫年度查核財報。'
        '原生文字不代表圖片及表格語意完整，只有股票代號與頁碼的頁面另列缺漏。'
        '競爭地位、產品效益與未來成長均為公司說法，並非已獨立查證或已實現結果。'
        '官網資料供非商業瀏覽使用，未驗證商業重製或散布授權；引用限必要片段並附來源。')


def supports_kingslide(ticker):
    return str(ticker).strip().upper() == TICKER


def _today(epoch):
    return datetime.fromtimestamp(epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    observed = reference_epoch(epoch, as_of_epoch=as_of_epoch)
    rows = master_rows(raw, epoch, source_url)
    matched = [r for r in rows if r.get('公司代號') == '2059']
    if len(matched) != 1:
        raise ValueError('KingSlide master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '川湖', '營利事業統一編號': UBN,
                '網址': 'http://www.kingslide.com'}
    if (any(row.get(k) != v for k, v in expected.items()) or row.get('英文簡稱', '').strip() != 'king slide'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('KingSlide master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(observed) - day).days <= 14 or day > _today(epoch):
        raise ValueError('KingSlide master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_ubn': UBN, 'as_of': day.isoformat()}


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate index key')
        value[key] = item
    return value


def _event_dates(value):
    # The issuer uses either a same-month end day or a complete end date.
    match = re.fullmatch(r'(20\d{2})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})(?:\s*~\s*(?:(20\d{2})\s*/\s*(\d{1,2})\s*/\s*)?(\d{1,2}))?', value)
    if not match:
        raise ValueError('event date ambiguous')
    y,m,d,ey,em,ed = match.groups()
    start = date(int(y),int(m),int(d));end = date(int(ey or y),int(em or m),int(ed or d))
    if not 0 <= (end-start).days <= 7:
        raise ValueError('event range invalid')
    return start,end


def select_presentation(raw, epoch, *, as_of_epoch=None):
    today = _today(reference_epoch(epoch, as_of_epoch=as_of_epoch))
    if not isinstance(raw,bytes) or not 0 < len(raw) <= 500_000:
        raise ValueError('invalid index size')
    text = raw.decode('utf-8-sig','strict')
    soup = BeautifulSoup(text,'html.parser')
    if (text.count('</html>') != 1 or text.count('</body>') != 1 or not soup.title
            or soup.title.get_text(' ',strip=True) != '法說會 - KingSlide'):
        raise ValueError('complete issuer index required')
    scripts = [x.get_text() for x in soup.find_all('script') if 'let dataList=' in x.get_text()]
    if len(scripts) != 1:
        raise ValueError('unique event list required')
    script = scripts[0]
    prefix = "https://www.kingslide.com/media/wysiwyg/company/investor/document/"
    if "href=\""+prefix+"'+dataList[maxYear][key]['pdf']+'" not in script:
        raise ValueError('published attachment route changed')
    blocks = re.findall(r'let dataList=(\{.*?\});\s*let html',script,re.S)
    if len(blocks) != 1:
        raise ValueError('event literal boundary changed')
    # Tokenize a restricted data literal; never evaluate website JavaScript.
    tokens = re.findall(r'"(?:[^"\\]|\\.)*"|[{}:,]|[0-9]+|[^\s]+',blocks[0])
    clean = []
    for i, token in enumerate(tokens):
        following = tokens[i+1] if i+1 < len(tokens) else ''
        if re.fullmatch(r'20\d{2}',token) and following == ':':token = '"'+token+'"'
        if token == ',' and following == '}':continue
        clean.append(token)
    years = json.loads(''.join(clean),object_pairs_hook=_unique)
    if not isinstance(years,dict) or not 1 <= len(years) <= 50:
        raise ValueError('event years invalid')
    candidates = []
    for year, events in years.items():
        if not re.fullmatch(r'20\d{2}',year) or not isinstance(events,dict):raise ValueError('event year invalid')
        if int(year) < today.year-1:continue
        for row in events.values():
            if (not isinstance(row,dict) or set(row)-{'year','date','local','video','pdf','title'}
                    or any(not isinstance(row.get(k),str) for k in ('year','date','local','video','pdf'))
                    or row['year'] != year):raise ValueError('event row invalid')
            start,end = _event_dates(row['date'])
            if str(start.year) != year:raise ValueError('event year mismatch')
            if end > min(today,_today(epoch)) or (today-start).days > 370:continue
            candidates.append((start,end,row))
    if not candidates:raise ValueError('no current past event')
    latest = max(x[0] for x in candidates);selected = [x for x in candidates if x[0] == latest]
    if len(selected) != 1:raise ValueError('ambiguous latest presentation')
    start,end,row = selected[0];url=prefix+row['pdf']
    if not pdf_url(url):raise ValueError('latest event attachment unavailable')
    filedate = date(int(row['pdf'][4:8]),int(row['pdf'][8:10]),int(row['pdf'][10:12]))
    if not 0 <= (start-filedate).days <= 120:raise ValueError('attachment date inconsistent')
    return {'event_date':start.isoformat(),'event_end_date':end.isoformat(),
            'event_title':row.get('title') or row['year']+' '+row['local']+' 法說會',
            'material_file_date':filedate.isoformat(),'pdf_url':url,
            'selection_policy':'latest_past_issuer_event_with_published_attachment'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    native = extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    _check(deadline)
    pages = native['pages'];cover = pages[0]['text'] if pages else ''
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or not 3 <= native['page_count'] <= 50 or LEGAL not in cover
            or not re.search(r'TICKER:\s*2059\b',cover)):
        raise ValueError('native presentation identity or text unverified')
    text = '\n'.join(p['text'] for p in pages)
    if not all(term in text for term in ('核心競爭能力','未來的成長動能','營業活動之淨現金流入')):
        raise ValueError('native presentation sections unverified')
    anchors = re.findall(r'至(20\d{2})年(\d{1,2})月(\d{1,2})日止',text)
    if len(anchors) != 1:raise ValueError('native content date ambiguous')
    as_of = date(*map(int,anchors[0]))
    if not 0 <= (date.fromisoformat(selected['material_file_date'])-as_of).days <= 120:
        raise ValueError('native content date inconsistent')
    omissions = [p['page_number'] for p in pages if re.fullmatch(r'\s*2059\s+\d{1,2}\s*',p['text'])]
    return native, omissions


def _context(selected, native, conflicts, proof):
    doc = {'document_id': '2059:' + selected['event_date'] + ':' + native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'title': selected['event_title'], 'url': selected['pdf_url'], 'event_date': selected['event_date'],
           'event_date_basis': 'issuer_published_event_data_literal', 'event_end_date': selected['event_end_date'], 'material_file_date': selected['material_file_date'], 'published_at': None,
           'event_status': 'announced_past_date_not_independently_occurrence_verified',
           'retrieved_at_epoch': proof['pdf']['retrieved_at'], 'content_sha256': native['content_sha256'],
           'page_count': native['page_count'], 'pages': native['pages'], 'binary_complete': True,
           'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial',
           'full_content_coverage_verified': False, 'missing_text_pages': [], 'garbled_pages': [],
           'known_native_text_omission_pages': conflicts, 'parser_version': native['parser_version'],
           'financial_scope_caution': NOTE, 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': selected['event_date'][:4],
            'title': selected['event_title'], 'source': PROVIDER, 'source_url': INDEX_URL,
            'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'zh-TW'}],
            'documents': [doc], 'coverage_status': 'partial', 'coverage_notes': [NOTE],
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'kingslide_conference_receipt': proof}


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = time.monotonic()+10. if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_kingslide(ticker) or not isinstance(value, dict) or value.get('ticker') != TICKER:
            return False
        proof = value['kingslide_conference_receipt']
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
        return value == expected and current_at(identity, max_age, time.time()) and all(valid_epoch(proof[k]['retrieved_at'], max_age) for k in ('index','pdf'))
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError, SourcePdfError):
        return False


def fetch_kingslide_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_kingslide(ticker): return {}
    deadline = time.monotonic()+20.
    http = KingSlideConferenceHttp(deadline, force_refresh=force_refresh, use_cache=use_cache)
    details = {'actual_provider': PROVIDER, 'kingslide_presentation_workflow': True}
    try:
        raw, identity = http.get_receipt(MASTER_URL); parse_master(raw, identity['retrieved_at'], identity['source_url'])
        raw, index = http.get_receipt(INDEX_URL); selected = select_presentation(raw, index['retrieved_at'])
        raw, pdf = http.get_receipt(selected['pdf_url']); native, conflicts = native_presentation(raw, selected, deadline)
        proof = {'policy': POLICY, 'identity': identity, 'index': index, 'pdf': pdf, 'selected': selected}
        value = _context(selected, native, conflicts, proof)
        if not verify_context(value, ticker, deadline=deadline, max_age=1800):
            raise SourceResponseError('original_unverified')
        _check(deadline)
        details.update(kingslide_originals_verified=True, coverage_status='native_presentation_text_complete',
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
        details.update(error_kind=exc.error_kind, status='error', kingslide_originals_verified=False,
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
    for k, expected in [('ticker',TICKER),('stock_id','2059'),('official_name','川湖'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(k) not in (None, '', expected): return False
    name = data.get('company_name')
    names = {'川湖', LEGAL, 'king slide works co., ltd.', 'king slide', 'king slide works co. ltd.'}
    if name is not None and (not isinstance(name,str) or any(s.strip().casefold() not in names for s in name.split(' / '))): return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key, [])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows): return False
    return not ({'川湖', LEGAL} & {s.strip('* ').strip() for s in identity.get('forbidden_aliases',[])})


def is_marked(value):
    return isinstance(value,dict) and ('kingslide_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or pdf_url(d.get('url')))
        for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    # Current and future editions use the same complete narrative-page rules.
    if document.get('ticker') != TICKER or document.get('source') != PROVIDER or document.get('coverage_status') != 'partial':return []
    kept=[]
    for page in document.get('pages',[]):
        if not isinstance(page,dict) or not isinstance(page.get('text'),str):continue
        text=page['text']
        if page.get('page_number') in document.get('known_native_text_omission_pages',[]):continue
        if any(term in text for term in ('銷售分析','市場占有率','市占率分析','財務狀況','(單位:新台幣千元)','每股稅後盈餘','利益率%','成長率%')):continue
        if page.get('page_number') == 1 or any(term in text for term in ('企業總部:','專利申請總數','核心競爭能力','高產品客製化能力','致力於研發','未來的成長動能','全新整合完整開發的')):
            kept.append(deepcopy(page))
    return kept
