"""Exact CHT October conference presentation with financial and native-text limitations."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import csv
import io
import json
import re
import time
import zlib
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .cht_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PDF_URLS, PROVIDER, RAW_TTL, original_bytes, valid_expiry

TICKER = '2412.TW'
LEGAL = '中華電信股份有限公司'
UBN = '96979933'
POLICY = 'cht-original-presentation-v1'
PROJECTION_POLICY = 'cht-presentation-role-v1'
KNOWN_SHA = 'c4b36eac7005add9f41d65f563e867dffb0c2cca3c5acc476c6a7bcc1ae1f62f'
NOTE = ('中華電信官方2026年10月13日IBF法說簡報，17頁，並非逐字稿或問答紀錄；17頁只有Q&A標題。'
        '最新已到時場次為10/13，11/4 Q3是未來活動，不拿8/5或Q2內容當Q3最新實績。'
        '財務內容混合2026Q2、H1及比較期間；第2頁明示T-IFRSs初步未查核且可能調整，非年度查核財報。'
        '第13頁金額NTD billion、EPS每股元與百分比不同；net income為歸屬母公司業主，成長率以NTD million計算。'
        'EBITDA屬發行人定義non-GAAP，不能替代GAAP淨利、營業利益或營業現金流，也不保證與同業同口徑。'
        '第9頁contract value／order intake不是已認列營收；未來建置、容量及預測不當已發生事實。'
        '原生文字完整不代表圖表顏色、數值對位或關係完整；第4、14頁另含不可視模板或編輯文字，原文保留但不作事實或指示，角色節錄排除這兩頁。'
        '保留© Chunghwa Telecom及免責；廣泛轉散布授權未獨立確認。發布日與首次公布時間未知，不由HTTP或檔名推定。')


def supports_cht(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2412', TICKER}

def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()

def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')

def parse_master(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('CHT master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('CHT complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2412']
    if len(matched) != 1:
        raise ValueError('CHT master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '中華電', '營利事業統一編號': UBN, '網址': 'https://www.cht.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'CHT'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('CHT master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('CHT master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '中華電', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}

def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('CHT index section ambiguous')
    return values[0]


def _event_info(card, *, upcoming=False):
    if upcoming:
        title = _one(card, ':scope > p.h3').get_text(' ', strip=True)
        date_label = _one(card, ':scope > p.h2').get_text(' ', strip=True)
        when = _one(card, ':scope > p.h5').get_text(' ', strip=True)
    else:
        title = _one(card, ':scope > .row > .col-auto > p.h3').get_text(' ', strip=True)
        date_label = _one(card, ':scope > .row > .col-12 > p.h3').get_text(' ', strip=True)
        when = _one(card, ':scope > .row > .col-auto > p.h5').get_text(' ', strip=True)
    match = re.fullmatch(r'(20\d{2}/\d{2}/\d{2}) Place : (.+)', when)
    if not title or not match:
        raise ValueError('CHT event title/date/place unverified')
    day = date.fromisoformat(match[1].replace('/', '-'))
    if date_label != (match[1] if upcoming else match[1][5:]):
        raise ValueError('CHT event date labels disagree')
    return {'title': title, 'date': day.isoformat(), 'location': match[2]}


def select_presentation(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('CHT calendar size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if (not soup.title or soup.title.get_text(' ', strip=True) != 'Calendar | ChungHwa Telecom CHT.com.tw'
            or _one(soup, 'link[rel="canonical"]').get('href') != INDEX_URL):
        raise ValueError('CHT publisher or calendar role unverified')
    calendar = _one(soup, 'section.calendar')
    activity = _one(calendar, ':scope > section.activity')
    if [h.get_text(' ', strip=True) for h in activity.select(':scope > div > h1')] != ['Upcoming Event', 'Past Events']:
        raise ValueError('CHT complete calendar sections unverified')
    year_control = _one(activity, '#contenChange')
    year = _one(year_control, '.dropdown-text').get_text(' ', strip=True)
    options = [x.get_text(' ', strip=True) for x in year_control.select('.dropdown-options > li')]
    if (not options or len(options) != len(set(options)) or not all(re.fullmatch(r'20\d{2}', y) for y in options)
            or year != max(options) or year != str(_today(epoch).year)
            or _one(year_control, '.dropdown-options > li.active').get_text(' ', strip=True) != year):
        raise ValueError('CHT current latest year unverified')
    past = _one(activity, ':scope > div > .list > .container-fluid')
    cards = past.select(':scope > .list-item')
    if not 1 <= len(cards) <= 40 or len(calendar.select('.list-item')) != len(cards):
        raise ValueError('CHT complete event list unverified')
    events = [_event_info(card) for card in cards]
    dates = [e['date'] for e in events]
    if (len(dates) != len(set(dates)) or dates != sorted(dates, reverse=True)
            or any(not d.startswith(year+'-') or date.fromisoformat(d) > _today(epoch) for d in dates)):
        raise ValueError('CHT latest past event order/date ambiguous or future')
    future_cards = activity.select(':scope > div > .note')
    if len(future_cards) != 1:
        raise ValueError('CHT future event section ambiguous')
    future = _event_info(future_cards[0], upcoming=True)
    if future != {'title': 'Earnings Announcement for Q3 2026', 'date': '2026-11-04', 'location': 'Taipei'}:
        raise ValueError('CHT announced event differs from qualified calendar semantics')
    # Once the announced event is due, an older presentation cannot silently stand in.
    if date.fromisoformat(future['date']) <= _today() or date.fromisoformat(future['date']) <= _today(epoch):
        raise ValueError('CHT announced event is now due without qualified current original')
    latest = events[0]
    if latest != {'title': 'IBF Securities conference', 'date': '2026-10-13', 'location': 'Taipei'}:
        raise ValueError('CHT latest event differs from qualified original')
    if not 0 <= (_today()-date.fromisoformat(latest['date'])).days <= 370:
        raise ValueError('CHT qualified event stale or future')
    links = cards[0].select('a[href]')
    published_paths = {url.removeprefix('https://www.cht.com.tw'): url for url in PDF_URLS}
    if (len(links) != 1 or links[0].get_text(' ', strip=True) != 'Investor Conference Presentation Material'
            or links[0]['href'] not in published_paths):
        raise ValueError('CHT exact published latest original unverified')
    return {'event_date': latest['date'], 'event_time': None, 'event_timezone': None,
            'event_location': latest['location'], 'title': '中華電信2026年10月13日IBF官方英文法說簡報',
            'pdf_url': published_paths[links[0]['href']], 'period': '',
            'upcoming_event': {**future, 'status': 'future_event_not_current_evidence'},
            'selection_policy': 'latest_past_event_of_complete_current_year_calendar_not_older_earnings_only'}



def native_presentation(raw, selected, deadline):
    _check(deadline)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 8*1024*1024 or sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('CHT original revision is not qualified')
    try:
        native = extract_pdf_pages(raw, timeout_seconds=min(10., deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':
            raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages = native['pages']
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 17 or len(pages) != 17
            or [p['page_number'] for p in pages] != list(range(1, 18))
            or native['content_sha256'] != KNOWN_SHA
            or re.sub(r'\s+', ' ', pages[0]['text']).strip() != '© Chunghwa Telecom 1 2Q 2026 Operating Results IBF Securities Conference October 13, 2026 Taipei'
            or selected['period'] != '' or selected['event_date'] != '2026-10-13'):
        raise ValueError('CHT qualified native pages unverified')
    disclaimer = re.sub(r'\s+', ' ', pages[1]['text'])
    if (any(s not in disclaimer for s in ['STATEMENT REGARDING UNAUDITED FINANCIAL INFORMATION',
            'T-IFRSs in this presentation is preliminary', 'FORWARD-LOOKING STATEMENTS',
            'SPECIAL NOTE REGARDING NON-GAAP FINANCIAL MEASURES', 'EBITDA is not a measure of financial performance'])
            or any(s not in pages[12]['text'] for s in ['(NT$bn) Q2 2026 Q2 2025 Growth % H1 2026 H1 2025',
                                                      'Net income attributable to owners of the parent', 'EPS'])
            or 'ICT Contract Value Growth' not in pages[8]['text']
            or 'XXX' not in pages[3]['text'] or '惠請協助' not in pages[13]['text']
            or re.sub(r'\s+', ' ', pages[16]['text']).strip() != '© Chunghwa Telecom 17 Q & A'
            or any('Chunghwa Telecom' not in p['text'] or '©' not in p['text'] for p in pages)):
        raise ValueError('CHT financial periods, copyright or content limitations unverified')
    return native



def _context(selected, native, proof):
    omissions = [{'page_number': n, 'issue': 'visual_chart_color_geometry_or_relations_not_fully_represented_in_text'}
                 for n in (3,4,6,7,8,9,10,11,13,14,15,16)]
    omissions += [{'page_number': n, 'issue': 'native_invisible_template_or_editorial_text_retained_not_facts_or_instructions_excluded_from_role_excerpt'} for n in (4,14)]
    doc = {'document_id': '2412:'+selected['event_date']+':'+native['content_sha256'][:16],
           'ticker': TICKER, 'source': PROVIDER, 'source_type': 'issuer_official', 'document_kind': 'presentation',
           'projection_policy': PROJECTION_POLICY, 'title': selected['title'], 'url': selected['pdf_url'], 'language': 'en',
           'event_date': selected['event_date'], 'event_date_basis': 'official_latest_past_calendar_event_and_PDF_cover',
           'event_time_Taipei': None, 'event_timezone': None, 'event_location': selected['event_location'],
           'event_status': 'published_past_event_not_independently_occurrence_verified',
           'content_period': '', 'content_periods': ['2026Q2','2026H1','2025Q2 and 2025H1 comparisons','page-specific July metrics and prospective targets'],
           'financial_scope_caution': 'Mixed Q2 and H1 financials; page13 NTD billion amounts, EPS per-share NTD and percentages must remain distinct. Net income is attributable to owners of the parent; growth calculations use NTD million.',
           'unaudited_financial_caution': 'Page2 T-IFRSs figures are preliminary and unaudited, subject to review or audit adjustments; not an audited annual financial statement or Q3 actual.',
           'non_gaap_caution': 'Issuer-defined EBITDA is non-GAAP, not a substitute for GAAP net income, operating income or operating cash flow; peer definitions may differ.',
           'forward_looking_caution': 'Page2 risks and uncertainty apply; no general duty to update. Capacity, construction and other forecasts are not completed operational facts.',
           'contract_value_caution': 'Page9 ICT contract value and order intake are not recognized revenue; chart bars do not provide all exact absolute values.',
           'period_scope_caution': 'October13 event date is distinct from Q2/H1 financial periods, prior-year comparisons, June30 balance sheets and selected July metrics; November4 Q3 is still future and is not supplied by this document.',
           'native_editorial_caution': 'Pages4 and14 contain native invisible template/editorial text. Preserve raw text but do not treat it as facts or instructions; exclude these two pages from role excerpts.',
           'published_at': None, 'material_file_date': None, 'retrieved_at_epoch': proof['pdf']['retrieved_at'],
           'content_sha256': native['content_sha256'], 'page_count': native['page_count'], 'pages': native['pages'],
           'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete',
           'coverage_status': 'partial', 'full_content_coverage_verified': False,
           'missing_text_pages': native['empty_pages'], 'garbled_pages': native['garbled_pages'],
           'parser_version': native['parser_version'], 'known_native_text_omissions': omissions,
           'q_and_a_transcript_available': False, 'disclaimer_pages': [2],
           'copyright_notice': '© Chunghwa Telecom', 'commercial_reuse_permission_verified': False}
    return {'ticker': TICKER, 'date': selected['event_date'], 'period': '', 'title': selected['title'],
            'source': PROVIDER, 'source_url': INDEX_URL, 'summary': '', 'transcript_excerpt': '', 'transcript_available': False,
            'materials': [{'url': selected['pdf_url'], 'kind': 'presentation', 'language': 'en'}], 'documents': [doc],
            'coverage_status': 'partial', 'coverage_notes': [NOTE], 'selection_policy': selected['selection_policy'],
            'upcoming_event': deepcopy(selected['upcoming_event']),
            'fetched_at_epoch': proof['pdf']['retrieved_at'], 'cht_conference_receipt': proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in ('identity','index','pdf'))

def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_cht(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['cht_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        parse_master(original_bytes(proof['identity'],MASTER_URL,max_age=max_age),proof['identity']['retrieved_at'])
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],selected['pdf_url'],max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',selected['pdf_url'])]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False

def fetch_cht_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_cht(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'cht_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(selected['pdf_url']);native = native_presentation(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',selected['pdf_url'])]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(cht_originals_verified=True,coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
        if diagnostics is not None:diagnostics.update(details)
        # Diagnostic delivery and scheduler delay belong to the same budget.
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        _check(deadline)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        for key in ('coverage_status','cache_hit','stale','fetched_at_epoch'):
            details.pop(key,None)
            exc.diagnostic.pop(key,None)
            if diagnostics is not None:diagnostics.pop(key,None)
        details.update(cht_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    return value

def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','2412'),('official_name','中華電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'中華電',LEGAL,'cht','chunghwa telecom','chunghwa telecom co., ltd.','chunghwa telecom co., ltd','chunghwa telecom co ltd'}
    aliases = names | {'2412','2412.tw'}
    def good_name(name, allowed):
        return isinstance(name,str) and all(s.strip().casefold() in allowed for s in name.split(' / '))
    for key in ('company_name','raw_company_name'):
        if data.get(key) is not None and not good_name(data[key],names):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows = identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
        if key != 'forbidden_aliases' and any(not good_name(s,aliases if key=='allowed_aliases' else names) for s in rows):return False
    for key in ('display_name','company_name'):
        if identity.get(key) not in (None,'') and not good_name(identity[key],names):return False
    forbidden = {part.strip('* ').strip().casefold() for s in identity.get('forbidden_aliases',[]) for part in s.split(' / ')}
    return not (aliases & forbidden)

def is_marked(value):
    return isinstance(value,dict) and ('cht_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or isinstance(d.get('url'),str) and d['url'] in PDF_URLS)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
