"""Qualified Allis August presentation, preserving mixed financial and visual scopes."""
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
from .allis_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '1514.TW'
LEGAL = '亞力電機股份有限公司'
UBN = '03213392'
POLICY = 'allis-original-presentation-v1'
PROJECTION_POLICY = 'allis-presentation-role-v1'
KNOWN_SHA = 'ceb64fce96a13c58e113f132ca2bc98d6efa77f5b4c4f2191054bea5fdefd312'
NOTE = ('亞力官方2026年8月中文法說簡報，封面日期2026-08-27，29頁；非逐字稿或問答紀錄。'
        '主要數據2026H1，保留2025H1與2021–2025年度比較；不以8月場次推定第三季財報。'
        '原生文字完整不代表圖表、照片與數字配對完整；ARES/雅瑞科技等子公司範圍不可當母公司實績。'
        '第18–19頁千元與EPS每股元及年度/半年不可混用，第20頁0.81為百分點差。'
        '第7–17、22–28頁產品、潛在商機、未來訂單及計畫並非已實現營收或已完成事件。'
        '索引僅發布月份，封面不是獨立發生證明；時刻及首次發布時間未知。'
        '原站no-store/no-cache，重新取得必須新HTTP；原件僅私存稽核，不主張商業再利用授權。')


def supports_allis(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'1514', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_allis_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from allis_presentation_pdf_reader import extract_allis_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Allis master size invalid')
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
        raise ValueError('Allis complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '1514']
    if len(matched) != 1:
        raise ValueError('Allis master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '亞力', '營利事業統一編號': UBN, '網址': 'www.allis.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'AEC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Allis master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('Allis master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '亞力', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('Allis index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('Allis index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if not soup.title or soup.title.get_text(' ', strip=True) != '115年 - '+LEGAL:
        raise ValueError('Allis publisher or year differs')
    if _one(soup, 'h1').get_text(' ', strip=True) != '115年':
        raise ValueError('Allis published year missing')
    published_years = [int(m[1])+1911 for a in soup.select('a[href]')
                       if (m := re.fullmatch(r'(\d{3})年', a.get_text(' ',strip=True)))]
    if not published_years or max(published_years) != 2026:
        raise ValueError('Allis latest published year changed')
    cards = soup.select('#wb-list > .card')
    amount = _one(soup, '#wb-toolbar .toolbar-amount').get_text(' ',strip=True)
    match = re.fullmatch(r'第 1 到 (\d+) 筆。共 (\d+) 筆。', amount)
    if not match or int(match[1]) != int(match[2]) or int(match[1]) != len(cards) or not cards:
        raise ValueError('Allis index is incomplete or paginated')
    rows = []
    for card in cards:
        title = _one(card, '.download-title').get_text(' ',strip=True)
        m = re.fullmatch(r'(\d{3})年(\d{2})月法說會簡報', title)
        if not m or int(m[1])+1911 != 2026:
            raise ValueError('Allis presentation month malformed')
        month = date(2026, int(m[2]), 1)
        rows.append((month,card,title))
    latest = max(r[0] for r in rows)
    selected = [r for r in rows if r[0] == latest]
    if len(selected) != 1 or latest > _today(epoch) or latest != date(2026,8,1):
        raise ValueError('Allis latest revision unknown, ambiguous or future')
    link = _one(selected[0][1], '.download-button-page a[href]')
    if link['href'] != '/zh-tw/download/file/42604' or not link.get_text(' ',strip=True).startswith('下載'):
        raise ValueError('Allis latest attachment unavailable or changed')
    if _today(epoch) < date(2026,8,27) or not 0 <= (_today()-date(2026,8,27)).days <= 370:
        raise ValueError('Allis cover date not eligible')
    return {'event_date':'2026-08-27','event_time':None,'event_timezone':None,'event_location':None,
            'title':'亞力2026年8月官方中文法說簡報','pdf_url':PDF_URL,'period':'',
            'index_period':'2026-08','selection_policy':'latest_published_year_and_month_card_exact_qualified_cover'}


def native_presentation(raw, selected, deadline):
    from allis_presentation_pdf_reader import glyph_evidence, PAGE_TEXT_SHA256
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('Allis original revision is not qualified')
    try:
        native = extract_allis_presentation_pages(raw, timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 29 or len(native['pages']) != 29
            or [p['page_number'] for p in native['pages']] != list(range(1,30))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA
            or json.dumps(native.get('allis_glyph_evidence'),sort_keys=True,allow_nan=False) != json.dumps(glyph_evidence(),sort_keys=True)
            or selected['event_date'] != '2026-08-27' or selected['index_period'] != '2026-08'):
        raise ValueError('Allis original pages or symbol proof unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'1514:'+selected['event_date']+':'+KNOWN_SHA[:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'zh-TW',
           'event_date':selected['event_date'],'event_date_basis':'issuer_index_month_and_exact_native_cover_day',
           'event_time':None,'event_timezone':None,'event_location':None,
           'event_status':'published_past_material_not_independently_occurrence_verified',
           'content_period':'','content_periods':['2026H1','2025H1 comparison','2021–2025 annual comparison','2026 onward business outlook'],
           'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
           'content_sha256':KNOWN_SHA,'page_count':29,'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':[],'garbled_pages':[],
           'parser_version':native['parser_version'],'allis_glyph_evidence':deepcopy(native['allis_glyph_evidence']),
           'known_native_text_omissions':[{'page_number':p,'issue':'visual chart/image geometry and value associations not fully verified'} for p in [3,4,*range(7,20),*range(22,29)]],
           'subsidiary_scope_caution':'Page3 ARES/雅瑞科技 and subsidiaries are distinct from Allis parent results.',
           'financial_scope_caution':'2026H1, prior H1 and annual series differ; pages18–19 TWD thousands and EPS per share differ; page20 0.81 is a percentage-point difference. No financial-history replacement.',
           'period_scope_caution':'The August presentation is not Q3 financial results; native page-specific periods govern.',
           'forward_looking_caution':'Pages7–17 and22–28 products, market opportunities, future orders and plans are not realized revenue or completed outcomes.',
           'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
           'response_reuse_policy':'no-store; new acquisitions require fresh HTTP; private immutable evidence only'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['title'],'source':PROVIDER,
            'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'allis_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_allis(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['allis_conference_receipt']
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


def fetch_allis_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_allis(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'allis_presentation_workflow':True}
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
        details.update(allis_originals_verified=True,coverage_status='native_presentation_text_complete',
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
        details.update(allis_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','1514'),('official_name','亞力'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'亞力',LEGAL,'aec','allis electric co.,ltd.','allis electric co., ltd.','allis electric co ltd','allis electric co., ltd','allis electric co ltd.'}
    aliases = names | {'1514','1514.tw'}
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
    return isinstance(value,dict) and ('allis_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
