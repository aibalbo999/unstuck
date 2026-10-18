"""Qualified HIWIN Q1 presentation with original bytes and bounded visible-role excerpts."""
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
from source_pdf_reader import SourcePdfError
from .official_issuer_master import JSON_URL
from .hiwin_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2049.TW'
LEGAL = '上銀科技股份有限公司'
UBN = '23503047'
POLICY = 'hiwin-original-presentation-v1'
PROJECTION_POLICY = 'hiwin-presentation-role-v1'
KNOWN_SHA = 'ebb6150526e26f75787f30db984ecac363ee95997770c905530491eaf078affb'
NOTE = ('上銀官方2026-05-08英文法說簡報，13頁；非逐字稿或問答紀錄。'
        '只對已核定原檔修正xref讀取位置及11個嵌入字型圓點；原始bytes、數字、文字順序保持。'
        '原生文字完整不代表可見內容完整；第2、3、7、8、12頁含不可見文字，整頁不供角色引用。'
        '第4頁產品圖例沒有原生文字，其餘圖表亦缺幾何配對；不得從抽字順序推算數據。'
        '內容為2026Q1與2025各季比較，並非今日資料；金額NT$ million、比率%、EPS每股NT$ dollar不同。'
        '第10頁116.8%與排除未分配盈餘稅NT$45M的註記必須保留，不可混成一般有效稅率。'
        '簡報不替代完整財報，沒有Q&A內容或未來實績保證。'
        '日期與封面一致、14:00由索引取得，時區及首次發布時間未知。'
        '原站Pragma no-cache；每次取得均新HTTP，CDN Age仍保留，原件僅私存稽核，不主張商業再利用授權。')


def supports_hiwin(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2049', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_hiwin_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from hiwin_presentation_pdf_reader import extract_hiwin_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('HIWIN master size invalid')
    if source_url == JSON_URL:
        from .official_issuer_master_json import parse_rows
        rows = parse_rows(raw, epoch); fields = list(rows[0])
    elif source_url == MASTER_URL:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
        rows = list(reader); fields = reader.fieldnames
    else:
        raise ValueError('unqualified master URL')
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('HIWIN complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2049']
    if len(matched) != 1:
        raise ValueError('HIWIN master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '上銀', '營利事業統一編號': UBN, '網址': 'http://www.hiwin.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'HIWIN'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('HIWIN master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('HIWIN master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '上銀', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('HIWIN index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('HIWIN index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True) != '法說會資訊\r\n    | HIWIN 上銀科技':
        raise ValueError('HIWIN index publisher invalid')
    if '最近期法人說明會' not in soup.get_text(' ',strip=True):
        raise ValueError('HIWIN latest conference section missing')
    table = _one(soup,'table.hs_table')
    rows = table.select(':scope > tr')
    expected = ['日期','時間','地點','連結網址','中文簡報','英文簡報','備註']
    if len(rows) != len(expected) or [r.select_one('th').get_text(' ',strip=True) if r.select_one('th') else '' for r in rows] != expected:
        raise ValueError('HIWIN latest index shape changed')
    def field(suffix):
        # Unique IDs across the whole document and membership in the same table.
        selector = '#mainCPH_FormView1_' + suffix
        item = _one(soup,selector)
        if item is not _one(table,selector):
            raise ValueError('HIWIN event fields outside latest table')
        return item
    text = field('fn_ic_dateLabel').get_text(' ',strip=True)
    match = re.fullmatch(r'(\d{4})年(\d{1,2})月(\d{1,2})日',text)
    if not match:
        raise ValueError('HIWIN event date invalid')
    day = date(*map(int,match.groups()))
    if day != date(2026,5,8) or day > _today(epoch) or not 0 <= (_today()-day).days <= 370:
        raise ValueError('HIWIN latest revision unknown or future')
    if (field('fn_ic_timeLabel').get_text(' ',strip=True) != '14 點 00 分 (24小時制)'
            or field('fn_ic_locationLabel').get_text(' ',strip=True) != '線上法說會'
            or field('fn_ic_memoLabel').get_text(' ',strip=True)):
        raise ValueError('HIWIN event details changed')
    links = [('CPDFHL','/uploadfiles/file/conference/20260508_final_C.pdf','final_C.pdf'),
             ('EPDFHL','/uploadfiles/file/conference/20260508_final_E.pdf','final_E.pdf')]
    for suffix,href,label in links:
        a = field(suffix)
        if a.name != 'a' or a.get('href') != href or a.get_text(' ',strip=True) != label:
            raise ValueError('HIWIN latest published attachment changed')
    if field('applyHL').get('href') != 'https://www.zucast.com/webcast/MCJJSxmS' or len(table.select('a[href]')) != 3:
        raise ValueError('HIWIN latest webcast metadata changed')
    return {'event_date':day.isoformat(),'event_time':'14:00','event_timezone':None,'event_location':'線上法說會',
            'title':'上銀2026Q1官方英文法說簡報','pdf_url':PDF_URL,'period':'2026Q1',
            'index_period':'2026-05','selection_policy':'latest_official_single_event_exact_qualified_native_cover'}


def native_presentation(raw, selected, deadline):
    from hiwin_presentation_pdf_reader import glyph_evidence, xref_evidence, PAGE_TEXT_SHA256
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('HIWIN original revision is not qualified')
    try:
        native = extract_hiwin_presentation_pages(raw, timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 13 or len(native['pages']) != 13
            or [p['page_number'] for p in native['pages']] != list(range(1,14))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA
            or json.dumps(native.get('hiwin_glyph_evidence'),sort_keys=True,allow_nan=False) != json.dumps(glyph_evidence(),sort_keys=True)
            or json.dumps(native.get('xref_validation_evidence'),sort_keys=True,allow_nan=False) != json.dumps(xref_evidence(),sort_keys=True)
            or selected['event_date'] != '2026-05-08' or selected['index_period'] != '2026-05'):
        raise ValueError('HIWIN original pages or symbol proof unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'2049:'+selected['event_date']+':'+KNOWN_SHA[:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'en',
           'event_date':selected['event_date'],'event_date_basis':'issuer_index_and_exact_native_cover_day',
           'event_time':selected['event_time'],'event_timezone':None,'event_location':selected['event_location'],
           'event_status':'published_past_material_not_independently_occurrence_verified',
           'content_period':'2026Q1','content_periods':['2026Q1','2025Q1–Q4 comparisons'],
           'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
           'content_sha256':KNOWN_SHA,'page_count':13,'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':[],'garbled_pages':[],
           'parser_version':native['parser_version'],'hiwin_glyph_evidence':deepcopy(native['hiwin_glyph_evidence']),
           'xref_validation_evidence':deepcopy(native['xref_validation_evidence']),
           'known_native_text_omissions':[
               {'page_number':2,'issue':'native trailing sales note not visible; whole page excluded from role excerpts'},
               {'page_number':3,'issue':'native Chinese region labels not visible; whole page excluded from role excerpts'},
               {'page_number':4,'issue':'Ballscrew/Linear Guideway/Robot/Others legend has no native text; no numeric product pairing'},
               {'page_number':7,'issue':'native page-number template not visible; whole page excluded from role excerpts'},
               {'page_number':8,'issue':'native Chinese FX label not visible; whole page excluded from role excerpts'},
               {'page_number':12,'issue':'native QoQ+0.33 not visible; whole page excluded from role excerpts'},
               {'page_number':13,'issue':'Thank You only; no Q&A or transcript'}],
           'excluded_native_text_pages':[2,3,7,8,12],
           'visual_semantics_caution':'All charts lose geometric relationships in native extraction; no automatic numeric pairing or calculations.',
           'financial_scope_caution':'Quarterly management performance presentation; no complete financial-statement or five-year-history replacement.',
           'unit_scope_caution':'NT$ million, percentages of sales, growth rates and EPS NT$ per share differ. Page10 tax116.8% callout relates to2Q/25 excluding NT$45M unappropriated earnings tax, not1Q/26; preserve the note and do not assign by text order.',
           'period_scope_caution':'2026Q1 versus2025Q1–Q4 comparisons; no2026Q2/Q3/Q4 actuals or fresh-current period implied.',
           'forward_looking_caution':'No future result is established by this historical issuer presentation.',
           'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
           'response_reuse_policy':'Pragma no-cache and Expires0; always fresh HTTP; CDN Age is retained as upstream history, not origin freshness; private immutable evidence only'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q1','title':selected['title'],'source':PROVIDER,
            'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'en'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'hiwin_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_hiwin(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['hiwin_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        identity_url=proof['identity']['source_url']
        parse_master(original_bytes(proof['identity'],identity_url,max_age=max_age),proof['identity']['retrieved_at'],identity_url)
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_hiwin_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_hiwin(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'hiwin_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        raw,index = http.get_receipt(INDEX_URL);selected = select_presentation(raw,index['retrieved_at']);_check(deadline)
        raw,pdf = http.get_receipt(PDF_URL);native = native_presentation(raw,selected,deadline)
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',proof['identity']['source_url']),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(hiwin_originals_verified=True,coverage_status='native_presentation_text_complete',
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
        details.update(hiwin_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2049'),('official_name','上銀'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'上銀',LEGAL.casefold(),'hiwin','hiwin technologies corp.','hiwin technologies corp','hiwin technologies corporation'}
    aliases = names | {'2049','2049.tw'}
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
    return isinstance(value,dict) and ('hiwin_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
