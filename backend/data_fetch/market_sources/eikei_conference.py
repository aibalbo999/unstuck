"""Eikei official presentation with distinct event and document dates."""
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
from .eikei_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '6924.TW'
LEGAL = '榮惠集團(開曼)股份有限公司'
UBN = '00532122'
POLICY = 'eikei-original-presentation-v1'
PROJECTION_POLICY = 'eikei-presentation-role-v1'
KNOWN_SHA = 'f1fe6ad9131d67e5d2d07a7f1da7afdaba2efb7e26105a37a5859cf663b44c8e'
PAGE_TEXT_SHA256 = ('641f20bcb59b52d870357d29f0f2e3d6bf8d87d16830237f8047f26b1d395491', '59b676e4f009855cee6c4e89d10abb76c2ed7b40bda6194d9b471b066ea578e0', '40742addb228f5f42907b49dd4d052b6ffef7489143f60bd5146c7165c65151e', '2ad3dc49552869bc22ddde0fa1b6d4422286e65008d8b2b561ae6f79679446b7', '5543d79009d4fa00adb080468f7e1798f46e50788cadb4bdf554e7de5d18eb28', '7e494af233f6829ef86a2ef123291d3107f8ef531e8dbc871ad2122d7d433ee3', 'c55b16dcbfca4dda7c781f1ac5c4da86752899bbdcb4cbfbb1a9fb201af4a889', '0e7b5dff75956070e7fafa3835dbb1e47ef97127bd0192fd10d18a1263c4e9e2', '3fc19525de017036f42788ed89970087753fb7ae8885e2bb64f5997c77da8a3f', '8fc0aca146bf69d3682c15741b26adb1aae377e164324a937cc89ddfa44a8353', 'ab91334a262cf549a982f5682d4e87325e0e15a01a8a9525f4f3ce197dbab639', '75cd82d0e545fe79417d66b170a63b0c57e757869efaacdc4a368168bf1fa931', '053a3fe27231f3e0042bb3631f6b0dfcdbca9b6d9a09b9df0641bbe0b09fca39', '7f7eafa39083e3175f384f1484e5521350abf227ec043fc872b5f9511001ee4a', '066409273aa828a1484e38f60871dee6fb5f73c72e51ee67ee63f2d96fe9dabf', '758641ed9029ccb1ed902793a952f559fd14e47102577faa51ff9e0d2f7230d3', 'abf3525f850055c4eb1caf94cbc5c9489e247132d86c7cb1e42dd4a575ca2dc4', '0e3b8df42445e395c063e72fa1774a70a58b98d5b84440cb9402590e0b972863', 'b9d9a4161ae0b97d2c8c1a6337822d78910b390d4cd66f2f58f7697097d6e8b8', 'da47e7a8ccb4f85dfe8fdb25feb01ca3202e81f27dc972f5d029d60d6b975741', 'c039c7c4c54787b5d28394c4b8d665cdb59921d659338fd220bb1ba2e158516c', '3dd7f8e9c247a369b4c7788b1e0ebc7a044696b2ee48d1db1c325937ce6fc934', '10f58ddf9e00bd749de9df0334fa893ce4b8d1eb047d1fb946afb8292d648856')
ROLE_PAGES = (1, 2, 13)
NOTE = '榮惠8/20官方23頁法說原件，原生文字complete但整體partial。角色僅1/2/13完整頁，保留免責聲明；營運模式、稽核實績、近十億基板年度採購等均為公司自述且採購期間未明，不當營收或已查核事實。圖像資訊、遮罩客戶及展望不補造，非逐字稿或完整五年財報。'

def supports_eikei(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'6924', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_eikei_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Eikei master size invalid')
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
        raise ValueError('Eikei complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '6924']
    if len(matched) != 1:
        raise ValueError('Eikei master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '榮惠集團(開曼)股份有限公司', '公司簡稱': '榮惠-KY創', '營利事業統一編號': '00532122', '網址': 'https://www.ei-kei.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'EIKEI-KY'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Eikei master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Eikei master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '榮惠-KY創', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '榮惠-KY創2026年8月20日法人說明會', 'pdf_url': 'https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260820_Investor_Conference_zh.pdf', 'event_date': '2026-08-20', 'document_date': '2026-08-20', 'cover_month': '2026-08', 'period_label': '2026H1', 'index_record_count': 6, 'selection_policy': 'latest_exact_published_event_in_complete_static_embedded_table', 'history_scope': '6 published embedded rows2024-2026; new event or changed binding requires qualification'}
CURRENT_ROWS = [{'cells': ['113/11/06', '14:00', '台北寒舍艾美酒店 三樓琥珀廳', '上市前業績發表會', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/doc.pdf', 'https://youtu.be/kIlAxfka9_w']}, {'cells': ['114/04/16', '15:00', '台北市南港區經貿二路188號13樓 中國信託金融園區B棟13樓1302會議室', '法人說明會', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/doc-zh-1140416-v2.pdf', 'https://youtu.be/SfkXGj3G6wA']}, {'cells': ['114/08/13', '11:20', '台北市信義區菸廠路88號6樓', '2025台灣創投年會-證交所專場', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/doc-zh-1140813.pdf', 'https://webpro.twse.com.tw/WebPortal/vod/101/A95147A291A0-173AAC28-7816-11F0-BC98/?categoryId=101']}, {'cells': ['115/03/25', '15:00', '台北市中山區明水路700號12樓', '法人說明會', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260325_Investor_Conference_zh.pdf', 'https://youtu.be/lQg4Yt6O3zc']}, {'cells': ['115/05/14', '14:30', '台北市中正區忠孝西路一段6號4樓', '法人說明會', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260514_Investor_Conference_zh.pdf', 'https://youtu.be/NwgrQ3K4JP8']}, {'cells': ['115/08/20', '15:00', '台北市樂群三路128號七樓', '法人說明會', '', '進入連結'], 'links': ['https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260820_Investor_Conference_zh.pdf', 'https://youtu.be/kf_-pfgItTw']}]
INDEX_SCRIPT_SHA256 = '8d85e4faaad08e93f77ec208c3467dda63938741822fd9daa2ca78a6e008105a'
INDEX_TRAILER_SHA256 = '4299d57889051b813c40cfd73b8d31198ae1bcaeffb220d830a818cd07834539'
HEADERS = ['會議日期', '會議時間', '地點', '說明', '簡報下載', '影音連結']
HEAD_TITLE = '股東專區 - Eikei'
OWNER = 'Copyright © EIKEI GROUP (CAYMAN) CO., LTD.'
HEADING_SELECTOR = '.section_scroll_right_item.section_scroll_right_item_4 .section_scroll_1_content.section_table_summary .section__item_heading'

def select_presentation(raw, epoch, *, as_of_epoch=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:
        raise ValueError('index size invalid')
    text=raw.decode('utf-8-sig','strict')
    body,closing,trailer=text.rpartition('</html>')
    if not closing or text.count('</html>')!=1 or text.count('</body>')!=1:
        raise ValueError('complete index required')
    if sha256(trailer.encode()).hexdigest()!=INDEX_TRAILER_SHA256:
        raise ValueError('publisher trailer changed')
    soup=BeautifulSoup(text,'html.parser')
    if len(soup.find_all('html'))!=1 or len(soup.find_all('body'))!=1:
        raise ValueError('index document ambiguous')
    if not soup.title or soup.title.get_text(' ',strip=True)!=HEAD_TITLE or OWNER not in soup.get_text(' ',strip=True):
        raise ValueError('publisher changed')
    if [x.get_text(' ',strip=True)for x in soup.select(HEADING_SELECTOR)]!=['聯絡窗⼝','年度行事曆']:
        raise ValueError('publisher insertion target changed')
    scripts=[str(s.string)for s in soup.select('script')if 'let mark ='in(s.string or '')]
    if len(scripts)!=1 or sha256(scripts[0].encode()).hexdigest()!=INDEX_SCRIPT_SHA256:
        raise ValueError('static table or insertion binding changed')
    # This exact publisher literal contains no JS interpolation or escapes.
    # It is parsed as data, never evaluated or executed.
    literals=re.findall(r'let mark = `(.*?)`;',scripts[0],re.S)
    if len(literals)!=1 or '${'in literals[0] or chr(92)in literals[0]:
        raise ValueError('not a static HTML literal')
    table=BeautifulSoup(literals[0],'html.parser')
    if len(table.select('#invest'))!=1 or len(table.select('#result_table_investors'))!=6:
        raise ValueError('embedded table ambiguous')
    if [s.get_text(' ',strip=True)for s in table.select('.section_table__heading > div')]!=HEADERS:
        raise ValueError('table headers changed')
    rows=[{'cells':[s.get_text(' ',strip=True)for s in r.select('.section_table__row_content')],
           'links':[a['href']for a in r.select('a[href]')]}for r in table.select('.section_table__row_item')]
    if rows!=CURRENT_ROWS or len(rows)!=6 or PDF_URL not in rows[-1]['links']:
        raise ValueError('published event or attachment changed')
    day=date.fromisoformat(QUALIFIED_SELECTED['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 23
DOCUMENT_METADATA = {'document_id': '6924:2026-08-20:f1fe6ad9131d67e5', 'ticker': '6924.TW', 'source': 'Eikei official conference presentation', 'source_type': 'issuer_official', 'document_kind': 'presentation', 'projection_policy': 'eikei-presentation-role-v1', 'url': 'https://www.ei-kei.com/themes/rainlab-bonjour-child/assets/20260820_Investor_Conference_zh.pdf', 'language': 'zh-TW', 'event_date': '2026-08-20', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': '15:00', 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2026-08-20', 'presentation_cover_month': '2026-08', 'content_period': '2026H1', 'content_periods': ['2026H1/Q2 financial presentation, excluded from role projection', 'issuer operating-model statements as of2026-08-20, dates not always specified', 'forward-looking views subject to complete page2 disclaimer'], 'content_sha256': 'f1fe6ad9131d67e5d2d07a7f1da7afdaba2efb7e26105a37a5859cf663b44c8e', 'page_count': 23, 'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [], 'role_page_allowlist': [1, 2, 13], 'excluded_native_text_pages': [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'native_editorial_caution': 'Only pages1/2/13 whole native text role-qualified. All23 pages preserved; pages11/18/22 contain unextracted image facts and remain excluded.', 'index_reuse_caution': 'Exact static mark literal and its publisher DOM insertion binding qualified without executing JavaScript. Latest row August20 15:00 agrees with cover; first publication and event occurrence not independently verified.', 'forward_looking_caution': 'Preserve page2 complete disclaimer. Operating advantages, supplier audits and liquid-cooling positioning are issuer assertions, not independently verified facts or guaranteed future results.', 'period_scope_caution': 'August20 event/cover and H1/Q2 financial content differ. Page13 near TWD1b annual substrate procurement has no explicit fiscal year; do not infer current revenue, sales or audited procurement.', 'unit_scope_caution': 'Page13 near ten hundred-million TWD is an approximate procurement claim, not revenue or cash flow. No annual/TTM/FCF substitution; excluded chart ratios remain unverified.', 'visual_semantics_caution': 'Pages1/2/13 text visually checked. Page13 native order flattens supplier/customer arrows; do not infer causal or contractual relationships. Other charts and image labels are not verified.', 'financial_scope_caution': 'Management presentation is not a complete five-year audited financial source. No annual/TTM/FCF overwrite. Masked customers on excluded page22 remain masked; no identity inference.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_eikei_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete'or native['empty_pages']or native['garbled_pages']
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
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026H1','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'eikei_conference_receipt':proof}

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
        if not supports_eikei(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['eikei_conference_receipt']
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


def fetch_eikei_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_eikei(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'eikei_presentation_workflow':True}
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
        details.update(eikei_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(eikei_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','6924'),('official_name','榮惠-KY創'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'榮惠-KY創', LEGAL, 'eikei group (cayman) co., ltd.', 'eikei group cayman co ltd', 'eikei-ky'}
    names = {name.casefold() for name in names}
    aliases = names | {'6924','6924.tw'}
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
    return isinstance(value,dict) and ('eikei_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
