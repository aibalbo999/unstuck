"""Tecom official presentation with distinct event and document dates."""
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
from .tecom_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2321.TW'
LEGAL = '東訊股份有限公司'
UBN = '47224065'
POLICY = 'tecom-original-presentation-v1'
PROJECTION_POLICY = 'tecom-presentation-role-v1'
KNOWN_SHA = '0d023d8f026225ee2f22cf1963e9874fae15bc5765e3c7b0c2c26ebc4126c13e'
PAGE_TEXT_SHA256 = ('bba2bd17f5f94f1900b4858f70e0fbacdf0458230364ef9a53d3ad0589ae0e95', '908e9123c17306ac5ab7fed92fa26f76860519313b9af021f45ebbb1cf811ae4', 'a712b87f1a60f79a078fbc36155a805ff610b17bf31c32b73d102ccbcdea8cf2', '2bb92962ee71617c499d679deed6ecbe090b9a6dbaae0ee23be17bbe82c8922b', '04badcfa9a9e132db1b83620191bb947c3ac934420dfc7f6cd664aa8fd653d86', '6443cec08d9f37738e80879c239f3ec51729bbebdf2354e630abdcdf883ea038', '1c27a753774cd4d89ff74170a3b4677cc227875036b858cf6de7539d67cf8613', '774f2b0ae39e77382a05a35fc63848755c3ce0542a3d2cbde43aa29acfebaa21', '0963ea5c412b55dc793d8ef95823c36a04937556c0774a817b9b48c960e9f5c9', '7bc553b03f2edbd17b923232659743a9a0f6318f6f93ccf9836838cf68e9b74f', 'dc14451d3ad8ef04af0be3bbf951024eaa32701ff6854bf2da8ec3ff4ca074ca', 'c7e83eae6aef53fa7b316b0b08500fe3a7d0a98769f8174e9fb3c13c47cab57f', '07178a23f01dda0b5581743fbee584b07fcef29f502e66ee52357933f4b9fc6f', 'b73e87639de4f3cce63f836ef2fd02a7c6dfdb6c3a14b99e69fc30b7bfaa2484', 'cda549fd8dd18254fe18cc6de8640a59bb125158c9d0499dae2ba7af04d43c74', 'ff888ccc57af290297c566e68901e92629e2a48f0a7c4901f8c1d75fc11da09b', 'c4bc81d0fc4d88836fbba9c8ffebe69963653264031eab5c74872661159702d6', 'd27aa86afba61c51d51fc9e2e8244e3f9e4aa7e2493a1c1f1349e1430b22b494', '0ec3f859fadb3a96437b6adb09579fd742135600bfab01f121b2d6f0687e334b', '97c4a7c9b7e0490daec7357fdef5d9b03ef095ea950241317a112cecbe945ee4', '4942e09a8609f9012f35975310fe9059dd89cdfea8b716322232950830b39633')
ROLE_PAGES = (1, 2, 16, 18, 19)
NOTE = '東訊官方21頁2025/12/17法說原件，native與整體皆partial，3/12頁有字形異常。角色限1/2/16/18/19完整原生文字，保留proprietary/confidential與免責聲明；案例與效益均為當時公司陳述，不推定驗收或實際節能。投資額、圖表、展望與未抽出影像資訊不補造，非逐字稿或五年財報。'

def supports_tecom(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2321', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_tecom_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Tecom master size invalid')
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
        raise ValueError('Tecom complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2321']
    if len(matched) != 1:
        raise ValueError('Tecom master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '東訊股份有限公司', '公司簡稱': '東訊', '營利事業統一編號': '47224065', '網址': 'http://www.tecom.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'TECOM'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Tecom master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Tecom master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '東訊', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '東訊2025年12月17日法人說明會', 'pdf_url': 'https://www.tecom.com.tw/wp-content/uploads/2026/01/%E6%9D%B1%E8%A8%8A_2025%E6%B3%95%E8%AA%AA%E6%9C%83%E8%B3%87%E6%96%99.pdf', 'event_date': '2025-12-17', 'document_date': '2025-12-17', 'cover_month': '2025-12', 'period_label': '2025Q3_9M', 'index_record_count': 3, 'selection_policy': 'latest_exact_issuer_event_in_complete_visible_three_card_list', 'history_scope': 'Three visible2023-2025 event cards; not a complete all-year archive; new card or original requires qualification'}
CURRENT_CARDS = [{'data_id': '0426773', 'text': '114年法人說明會 時間 : 2025/12/17 東訊_2025法說會資料 東訊_2025法說會影音', 'links': [['114年法人說明會 時間 : 2025/12/17', '#'], ['東訊_2025法說會資料', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/東訊_2025法說會資料.pdf'], ['東訊_2025法說會影音', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/2321_9_20251217_ch.mp4']]}, {'data_id': '846d822', 'text': '113年法人說明會 時間 : 2024/12/18 東訊_2024法說會資料 東訊_2024法說會影音', 'links': [['113年法人說明會 時間 : 2024/12/18', '#'], ['東訊_2024法說會資料', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/東訊_2024法說會資料.pdf'], ['東訊_2024法說會影音', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/2321_8_20241218_ch.mp4']]}, {'data_id': '785ed8a', 'text': '112年法人說明會 時間 : 2023/12/20 東訊_2023法說會資料 東訊_2023法說會影音', 'links': [['112年法人說明會 時間 : 2023/12/20', '#'], ['東訊_2023法說會資料', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/東訊_2023法說會資料.pdf'], ['東訊_2023法說會影音', 'https://www.tecom.com.tw/wp-content/uploads/2026/01/2321_7_20231220_ch.mp4']]}]
HEAD_TITLE = '法人說明會 - 東訊股份有限公司'
ROOT_TEXT = '投資人專區 法人說明會 首頁 / 投資人專區 /\xa0法人說明會 114年法人說明會 時間 : 2025/12/17 東訊_2025法說會資料 東訊_2025法說會影音 113年法人說明會 時間 : 2024/12/18 東訊_2024法說會資料 東訊_2024法說會影音 112年法人說明會 時間 : 2023/12/20 東訊_2023法說會資料 東訊_2023法說會影音'

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import quote
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:
        raise ValueError('index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or text.count('</html>')!=1 or text.count('</body>')!=1:
        raise ValueError('complete index required')
    # Exact observed WordPress trailer only; generated cache timestamp is not
    # a source retrieval time, event date or publication date.
    if not re.fullmatch(r"\s*<!-- This website is like a Rocket, isn't it\? Performance optimized by WP Rocket\. Learn more: https://wp-rocket\.me - Debug: cached@[0-9]+ -->\s*",trailer):
        raise ValueError('unqualified trailing content')
    soup=BeautifulSoup(body+closing,'html.parser')
    if len(soup.find_all('html'))!=1 or len(soup.find_all('body'))!=1:
        raise ValueError('index document ambiguous')
    if not soup.title or soup.title.get_text(' ',strip=True)!=HEAD_TITLE:
        raise ValueError('publisher changed')
    if [x.get('href')for x in soup.select('link[rel="canonical"]')]!=[INDEX_URL]:
        raise ValueError('canonical changed')
    roots=soup.select('[data-elementor-type="wp-page"]')
    if len(roots)!=1 or roots[0].get('data-elementor-id')!='988728':
        raise ValueError('event page identity changed')
    root=roots[0]
    if [(x.name,x.get('data-id'))for x in root.find_all(recursive=False)if x.name]!=[('section','6c03933'),('div','cc6e9bd'),('section','c14ea1f')]:
        raise ValueError('event sections changed')
    if root.get_text(' ',strip=True)!=ROOT_TEXT:
        raise ValueError('visible event history changed')
    elements=[x for x in root.select('div.elementor-inner-column')if x.select('.elementor-cta__title')]
    cards=[{'data_id':x.get('data-id'),'text':x.get_text(' ',strip=True),'links':[[a.get_text(' ',strip=True),a['href']]for a in x.select('a[href]')]}for x in elements]
    if cards!=CURRENT_CARDS or len(cards)!=3 or quote(cards[0]['links'][1][1],safe=':/%')!=PDF_URL:
        raise ValueError('event or attachment changed')
    if any(a.has_attr('onclick')for x in elements for a in x.select('a[href]')):
        raise ValueError('unqualified link action')
    day=date.fromisoformat(QUALIFIED_SELECTED['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 21
DOCUMENT_METADATA = {'document_id': '2321:2025-12-17:0d023d8f026225ee', 'ticker': '2321.TW', 'source': 'Tecom official conference presentation', 'source_type': 'issuer_official', 'document_kind': 'presentation', 'projection_policy': 'tecom-presentation-role-v1', 'url': 'https://www.tecom.com.tw/wp-content/uploads/2026/01/%E6%9D%B1%E8%A8%8A_2025%E6%B3%95%E8%AA%AA%E6%9C%83%E8%B3%87%E6%96%99.pdf', 'language': 'zh-TW', 'event_date': '2025-12-17', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': None, 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2025-12-17', 'presentation_cover_month': '2025-12', 'content_period': '2025Q3_9M', 'content_periods': ['2025Q3 and January-September financial review, not role-qualified', 'historical project statements as of2025-12-17', '2025Q4 outlook, not achieved results'], 'content_sha256': '0d023d8f026225ee2f22cf1963e9874fae15bc5765e3c7b0c2c26ebc4126c13e', 'page_count': 21, 'binary_complete': True, 'text_extraction_complete': False, 'native_text_coverage': 'partial', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [3, 12], 'role_page_allowlist': [1, 2, 16, 18, 19], 'excluded_native_text_pages': [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 20, 21], 'native_editorial_caution': 'All21 pages retained with original text, including unknown glyphs on3/12. Only1/2/16/18/19 native text is role-qualified. No glyph substitution or repair inferred.', 'index_reuse_caution': 'Latest visible issuer card and cover agree on2025-12-17. Upload path2026/01 is not event date or proven first publication. Three visible cards do not prove exhaustive historical coverage.', 'forward_looking_caution': 'Preserve whole page2 disclaimer. Projects and benefits are issuer claims as of2025-12-17, not independently confirmed delivery or acceptance. Page19 annual electricity savings and expected0.59-year payback are management estimates, not realized cashflow.', 'period_scope_caution': 'Event and cover2025-12-17, financialQ3/January-September, and Q4outlook are distinct. Page19 says2024 EMS installation; do not redatetime project statements as current30day news or current operational results.', 'unit_scope_caution': 'Page19 annual savings760萬 is a customer-benefit estimate with no explicitly stated currency on that page. Do not infer reporting-currency financial revenue, realized savings, or company FCF. Original page7/8 NTDmillion tables excluded.', 'visual_semantics_caution': 'Role view preserves only native text of1/2/16/18/19; photographs, dashboard screenshots and embedded equipment labels are not parsed or verified. Page13 quadrant reading order and page17 image funding/investment labels are excluded.', 'financial_scope_caution': 'Presentation is not a complete five-year audited financial source. Do not overwrite annual/TTM/FCF. Project-benefit estimates are not issuer financial statement amounts.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse', 'publisher_notice': 'TECOM PROPRIETARY AND CONFIDENTIAL. TECOM © 2025'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_tecom_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='partial'or native['empty_pages']or native['garbled_pages']!=[3,12]
            or native['page_count']!=PAGE_COUNT or len(native['pages'])!=PAGE_COUNT
            or [p['page_number']for p in native['pages']]!=list(range(1,PAGE_COUNT+1))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected!=QUALIFIED_SELECTED):
        raise ValueError('complete original projection invalid')
    return native

def _context(selected,native,proof):
    doc=deepcopy(DOCUMENT_METADATA)
    doc.update(title=selected['title'],retrieved_at_epoch=proof['pdf']['retrieved_at'],pages=deepcopy(native['pages']),
               parser_version=native['parser_version'])
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2025Q3_9M','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'tecom_conference_receipt':proof}

def role_pages(document):
    if not isinstance(document,dict):return []
    try:
        native={k:document[k]for k in ('pages','parser_version')}
        expected=_context(QUALIFIED_SELECTED,native,{'pdf':{'retrieved_at':document['retrieved_at_epoch']}})['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return []
    except (KeyError,TypeError,ValueError):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=PAGE_COUNT:return []
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
        if not supports_tecom(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['tecom_conference_receipt']
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


def fetch_tecom_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_tecom(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'tecom_presentation_workflow':True}
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
        details.update(tecom_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(tecom_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2321'),('official_name','東訊'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'東訊', LEGAL, 'tecom co., ltd.', 'tecom co', 'tecom'}
    names = {name.casefold() for name in names}
    aliases = names | {'2321','2321.tw'}
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
    return isinstance(value,dict) and ('tecom_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
