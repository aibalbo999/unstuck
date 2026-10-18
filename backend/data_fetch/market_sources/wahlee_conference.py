"""Wahlee official presentation with distinct event and document dates."""
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
from .wahlee_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '3010.TW'
LEGAL = '華立企業股份有限公司'
UBN = '75514419'
POLICY = 'wahlee-original-presentation-v1'
PROJECTION_POLICY = 'wahlee-presentation-role-v1'
KNOWN_SHA = 'f3777f5706851deed1551324b209cf1a7af5c906f95d73eb1f37e6f34cd830fe'
PAGE_TEXT_SHA256 = ('ee58b1ac4f2b4935bf6330e094a79221a6db2af814696a1b1ef7ac324280f3d6', 'b2f6dcf01da755a74676ad724b3c788817e32ee498ca67af32c0ad7ed25ef021', '5bf9ff2027b1ca9cf83a75a81e7951b784b7452452fb2eff54aaf8e4433c28c3', '9d789a0e6e757a2b9b5de61a5fa925b4f5f83a7d74c66d528ab8ab9246ecb61f', '8fa54efc58a791d296495dd8da30172d62e23ab2d7f7c992e52589dc9b7757ec', '667b3070aee7afb66a60520dc29ba4db486e60b9cc5372e713cf8dc09c6f3e60', 'b6b864dcdbc5a7e6cddfd71ee624b244b31308d9f4667effa8d5da25cae2aa64', 'cd7584f7c8b4a844794389b58da43e9ac03377a8d745370d14b2dec27e0aff85', '48f174b5af85dee728a5ea2718537c10c9bc99ac371cdc36522870f799761391', 'af4f80fcc1add3ea61c5a3e2152065bec25d8df4ad61344b6de9b7f6c1d92535', '241388ad9cc06339f55ff1da93276d10ba52c49ce7a1cbe848fe913e2789d02b', '15c053e105e14eb83be23c5659b331ac653cf5936d83f0d98087e90a209de8d9', '0d20981ef82962a44f95fd6aa54fb2cd371b059651e657bb9a0731f25f87ee08', '04da2c496c5978e1d4e77ab305064b43c1f3577d8160b741e14f7de783453698', 'fa9235c206511ce2980c0858df661e5516e7a1ec3f231b31f15f947f07528a18', '799627fa28b0df74dfc4b128f219eb2b77ff7c649860075c39da27d2d9f805c3', '9f96344ab1452e8f072f0d0b93dd40a279842db2f02f5e95b308d775006af23e', '682d6c64513f8ff750b340a8321aca51071959a273a0a8c016f22b4fb12ae400', '8adc5a58b6b8a8054d734bf705f85966994c041b37c50adccc0382879e973cf8', '8625f89dca6ee69df048d10fca10ae4778e415053cbc60c6d690bf2f0d227fac')
ROLE_PAGES = (1,2,3,12,14,15)
NOTE = '華立官方20頁完整簡報，9/4活動連結8月製作原件，財務內容H1／營收到7月，首次發布日未知。原生文字complete但整體partial，非逐字稿或五年查核財報。角色僅讀1/2/3/12/14/15完整頁；16/17長投收益差異未調節、18欄位閱讀順序、19圖表及20ROE期間口徑未核，均不進角色。p3市值為文件當時約數、非即時股價；p12成長及領先地位是公司主張，非今日新事件。p14保留2022/2023歷史日期及原MW用語，不能換算為當期電量或保證ROI；p15為示意圖與建設計畫，不代表完工。'

def supports_wahlee(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'3010', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_wahlee_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Wahlee master size invalid')
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
        raise ValueError('Wahlee complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '3010']
    if len(matched) != 1:
        raise ValueError('Wahlee master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '華立', '營利事業統一編號': UBN, '網址': 'http://www.wahlee.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'WAH LEE'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Wahlee master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Wahlee master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '華立', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}



INDEX_ROW_TEXTS = ('2026-09-04 統一證券所舉辦之「2026年Q3秋季投資論壇」 臺北君悅酒店-台北市信義區松壽路2號', '2026-06-16 群益證券「2026年第二季投資論壇」 臺北茹曦酒店-台北市敦化北路100號', '2026-03-13 華南永昌證券所舉辦之「2026春季投資論壇」 臺北晶華酒店')

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import urljoin, quote
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('Wahlee index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>' in body or trailer.strip() or '</body>' not in body:raise ValueError('Wahlee complete index required')
    soup=BeautifulSoup(text,'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='投資人關係行事曆簡報 - 華立企業股份有限公司':raise ValueError('Wahlee publisher changed')
    if '©WAHLEE. All rights reserved.'not in soup.get_text(' ',strip=True):raise ValueError('Wahlee owner changed')
    if [x.get('data-value')for x in soup.select('.js-replace-field.active[data-replace="year"]')]!=['2026']:raise ValueError('Wahlee selected year changed')
    tables=soup.select('table')
    if len(tables)!=1 or [x.get_text(' ',strip=True)for x in tables[0].select('thead th')]!=['日期','活動','地點','檔案','影片']:raise ValueError('Wahlee table shape changed')
    rows=tables[0].select('tbody > tr')
    if len(rows)!=3 or tuple(r.get_text(' ',strip=True)for r in rows)!=INDEX_ROW_TEXTS:raise ValueError('Wahlee current event history changed')
    for row in rows:
        cells=row.find_all(['th','td'],recursive=False)
        if len(cells)!=5 or any(a.has_attr('onclick')for a in row.select('a')):raise ValueError('Wahlee row malformed')
        files=cells[3].select('a[href]')
        if len(files)!=1 or 'download' not in files[0].attrs or not files[0].get('href','').startswith('/Files/FinancialPresentation/'):raise ValueError('Wahlee published attachment invalid')
    link=rows[0].find_all(['th','td'],recursive=False)[3].select_one('a[href]')
    if quote(urljoin(INDEX_URL,link['href']),safe='/:()?=&%')!=PDF_URL:raise ValueError('Wahlee current original changed')
    if rows[0].find_all(['th','td'],recursive=False)[4].select('a[href]'):raise ValueError('Wahlee current media changed')
    day=date(2026,9,4)
    if not day<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:raise ValueError('Wahlee event date invalid')
    return {'title':'華立2026年8月投資人簡報（9/4秋季投資論壇）','pdf_url':PDF_URL,'event_date':'2026-09-04',
        'document_date':None,'cover_month':'2026-08','period_label':'2026H1','index_record_count':3,
        'selection_policy':'latest_exact_published_event_in_complete_current_year_table',
        'history_scope':'three visible2026 rows; earlier years not claimed complete; changed event requires qualification'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('Wahlee original revision is not qualified')
    try:native=extract_wahlee_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=20 or len(native['pages'])!=20
            or [p['page_number']for p in native['pages']]!=list(range(1,21))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected['period_label']!='2026H1'
            or selected['event_date']!='2026-09-04' or selected['document_date']is not None or selected['cover_month']!='2026-08'):
        raise ValueError('Wahlee complete original projection invalid')
    return native


def _context(selected,native,proof):
    doc={'document_id':'3010:2026-09-04:'+KNOWN_SHA[:16],'ticker':TICKER,'source':PROVIDER,
        'source_type':'issuer_official','document_kind':'presentation','projection_policy':PROJECTION_POLICY,
        'title':selected['title'],'url':PDF_URL,'language':'zh-TW','event_date':selected['event_date'],
        'event_date_basis':'exact_issuer_September_event_links_August_cover_month_original',
        'event_status':'published_past_material_not_independently_occurrence_verified',
        'event_time':None,'event_timezone':'Asia/Taipei','published_at':None,'material_file_date':None,
        'presentation_cover_month':'2026-08','content_period':'2026H1',
        'content_periods':['2026H1 financials','sales through July2026','issuer historical business claims and forward-looking plans'],
        'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':KNOWN_SHA,'page_count':20,'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':[],'garbled_pages':[],'parser_version':native['parser_version'],'role_page_allowlist':list(ROLE_PAGES),
        'excluded_native_text_pages':[n for n in range(1,21)if n not in ROLE_PAGES],
        'native_editorial_caution':'Pages16/17 investment income399.2million versus408435thousand has no reconciliation; exclude both. Page18 column order,19 chart associations and20 ROE period scope are not qualified for roles. Originals unchanged.',
        'index_reuse_caution':'September4 event links an August cover-month original. Actual event occurrence and first publication date are not independently verified.',
        'forward_looking_caution':'Business growth/leadership and ROI are issuer claims at document time. Page14 retains2022/2023 history; MW is a power dimension, not current energy output. Page15 warehouse illustration and future construction are not completion evidence.',
        'period_scope_caution':'Keep event September4, cover month August, H1 financials and sales through July distinct. Market capitalization on page3 is a historical approximate claim, not a current quote. NoQ3 full results or recent-news claim.',
        'financial_scope_caution':'Management presentation is not a five-year audited statement source. Do not overwrite annual,TTM,FCF or existing financial facts.',
        'unit_scope_caution':'Capital in TWD, FY2025 sales in TWD/USD millions and approximate market cap in USD billion must remain distinct. MW,tonnes,ping and ROI have different dimensions. Unverified chart/table numbers are excluded from roles.',
        'visual_semantics_caution':'Only pages1/2/3/12/14/15 original text is role-qualified; all20 original pages preserved. Diagrams and unqualified financial associations are not asserted verified.',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026H1','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'wahlee_conference_receipt':proof}


def role_pages(document):
    if not isinstance(document,dict):return []
    try:
        selected={'title':'華立2026年8月投資人簡報（9/4秋季投資論壇）','event_date':'2026-09-04',
                  'selection_policy':'latest_exact_published_event_in_complete_current_year_table'}
        expected=_context(selected,{'pages':document['pages'],'parser_version':document['parser_version']},
                          {'pdf':{'retrieved_at':document['retrieved_at_epoch']}})['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return []
    except (KeyError,TypeError,ValueError):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=20:return []
    for n,p in enumerate(pages,1):
        if not isinstance(p,dict)or type(p.get('page_number'))is not int or p['page_number']!=n or not isinstance(p.get('text'),str)or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]:return []
    return deepcopy([p for p in pages if p['page_number']in ROLE_PAGES])


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_wahlee(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['wahlee_conference_receipt']
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


def fetch_wahlee_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_wahlee(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'wahlee_presentation_workflow':True}
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
        details.update(wahlee_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(wahlee_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','3010'),('official_name','華立'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'華立',LEGAL.casefold(),'wah lee','wah lee industrial corporation','wah lee industrial corp','wah lee industrial corp.'}
    aliases = names | {'3010','3010.tw'}
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
    return isinstance(value,dict) and ('wahlee_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
