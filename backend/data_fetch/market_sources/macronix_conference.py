"""Macronix official presentation with distinct event and document dates."""
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
from .macronix_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2337.TW'
LEGAL = '旺宏電子股份有限公司'
UBN = '22099548'
POLICY = 'macronix-original-presentation-v1'
PROJECTION_POLICY = 'macronix-presentation-role-v1'
KNOWN_SHA = '6eea155a87d9d69b6d1fa72abec394a56093d915a027138d37f09f9e0787ef32'
PAGE_TEXT_SHA256 = ('92f5f81651cc2211f8bdc3811cbc8f4fdbc73bc2b0446ef296a48f9f4358269d', 'c2b8e9f86ae1d8759baa6b07f9cd3c2ace19c0d8adc39110660d32ce286d9534', '4cbdea3dcaa38d48dcae4abbef06697a2138e906439bb168e75fc4213336a49a', '3c51756cdebab36450c0e3f1e8c6df13910526dcb779c0416e77f0546711727d', '1432e5e9e5787d13e0107aa409322f59ad24a837449efd5ea2c79d7667026fd9', 'c8c56768dab76cd0f808977618084a3feffaad931acd5a4edc02bd951d7a6d14', 'f2c983159dd28744017faa159f52ae3c7c0901e4c16892b8f01ac7065cd987ac', 'fe47f5acb3962e2dc0b3ee3b4f8ff5eee0e054a42931589b509937bbf2e846a1', '68f3312448734c6bff0a3816764634bbdeb36fede82fd526284c0851b965881b', '4a7075e734aa02caaf2b082bab622fbeeb2253438ab7782068ef1666926e704a', '5930eac3357d4f2bc7fe772346f81dcfaf858e81f49d3a2e6ee163f59f73a942', 'e782484f2bdf9e5b2caf4c9d4dfe89c7e022af156cad0382bee18fd581ffeed0', '785958ef88bdafc8d5a48853c8ee3a7b3eb830a7fd287f023e7372c99df4f339', 'dcb01dabbea08a98d7cd517998e3c12784e6281579ccfc575843f0dfe00b3fd4', 'fc5b79cd2d33f1e2450d4f294e8c7903d068ee7ff1b2af8ffbbc952915187bae', 'a909c96205ccfd74c4c460b6f0e67efe8389935e22fbabf48c2229cc41f4b182', 'aaba3ffa3b81a586fde9aafd8af61cba90860a058e7bb259b8932660bdc9476b', '7e604aef11d0ca7c690d79ccf52a5ede615059ebd5df93dcfe259dc1ca0bf97b', '39abb15a11543d492f7eba4507bfb824bc9ecae32ae827c2a999b5065d0a1105', '50ad2eb04d4500aed87ca295932a8d69a328a2e630afba39eb734319d0341d14', 'f951aedf81a9e16e0141f97a3fa8daef37df46688f3475571f478a3b56869b4c', '6dd17a0738abd93d027cdb14989a965f0058ebbc0c8e7fb013395f8e7460ae2a', '7fcf1cc4fe67d8bfd89439845d81a14bca96be977b1b66c38d6cdc97f21cfff6')
ROLE_PAGES = (1, 2, 7, 8, 12)
NOTE = '旺宏官方23頁2026Q2法說簡報；全頁保留，原生文字與整體皆partial，13/16/17/18/20頁保留未解字形。角色只使用1/2/7/8/12完整核對頁。保留原單位、期間、括號負值與免責聲明；非逐字稿、完整五年財報或當前新聞，第三季尚未發布的場次不替代第二季資料。'

def supports_macronix(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2337', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_macronix_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Macronix master size invalid')
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
        raise ValueError('Macronix complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2337']
    if len(matched) != 1:
        raise ValueError('Macronix master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '旺宏電子股份有限公司', '公司簡稱': '旺宏', '營利事業統一編號': '22099548', '網址': 'http://www.macronix.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'Macronix'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Macronix master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Macronix master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '旺宏', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': 'Macronix Second Quarter 2026 Results', 'pdf_url': 'https://www.macronix.com/Lists/QuarterlyResults/Attachments/656/2026q2%20webcast_ppt_en.pdf', 'event_date': '2026-07-28', 'document_date': '2026-07-28', 'cover_month': '2026-07', 'period_label': '2026Q2', 'selection_policy': 'latest_published_past_quarter_in_complete_current_year_public_json', 'history_scope': '2026 current-year index; upcoming2026Q3 has no attachment and is excluded; changed index requires qualification'}
CURRENT_ROWS = [{'Year': '2026', 'Quarter': '1', 'AnnounceDate': '2026/04/27', 'Webcast': 'https://www.zucast.com/webcast/jTcJYhVn', 'Id': '652', 'release': '2026q1_release_en.pdf', 'fcon': '2026q1_fcon_en.pdf', 'webcast_PPT': '2026q1 webcast_ppt_en.pdf', 'FI': None}, {'Year': '2026', 'Quarter': '2', 'AnnounceDate': '2026/07/28', 'Webcast': 'https://www.zucast.com/webcast/MNDe70Sa', 'Id': '656', 'release': '2026q2_release_en.pdf', 'fcon': '2026q2_fcon_en.pdf', 'webcast_PPT': '2026q2 webcast_ppt_en.pdf', 'FI': None}, {'Year': '2026', 'Quarter': '3', 'AnnounceDate': '2026/10/27', 'Webcast': 'https://www.zucast.com/webcast/1rPAcPDa', 'Id': '658', 'release': None, 'fcon': None, 'webcast_PPT': None, 'FI': None}]
def select_presentation(raw, epoch, *, as_of_epoch=None):
    # Exact anonymous data endpoint published by the official page script.
    if not isinstance(raw,bytes) or not 0<len(raw)<=200_000:
        raise ValueError('index size invalid')
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate index field')
            d[k]=v
        return d
    values=json.loads(raw.decode('utf-8-sig','strict'),object_pairs_hook=pairs)
    if values!=CURRENT_ROWS:raise ValueError('published quarterly index changed')
    now=_today(as_of_epoch)
    if now.year!=2026 or _today(epoch).year!=2026:
        raise ValueError('current year index no longer qualified')
    if date(2026,10,27)<=now:
        raise ValueError('newer event must be requalified')
    past=[r for r in values if date.fromisoformat(r['AnnounceDate'].replace('/','-'))<now and r['webcast_PPT']]
    latest=max(past,key=lambda r:r['AnnounceDate'])if past else None
    if latest!=CURRENT_ROWS[1]:raise ValueError('latest past publication differs')
    from urllib.parse import quote
    url='https://www.macronix.com/Lists/QuarterlyResults/Attachments/'+latest['Id']+'/'+quote(latest['webcast_PPT'],safe='')
    if url!=PDF_URL:raise ValueError('published attachment differs')
    day=date.fromisoformat(QUALIFIED_SELECTED['event_date'])
    if not day<=_today(epoch)<=now or not 0<=(now-day).days<=370:
        raise ValueError('event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 23
DOCUMENT_METADATA = {'document_id': '2337:2026-07-28:6eea155a87d9d69b', 'ticker': '2337.TW', 'source': 'Macronix official conference presentation', 'source_type': 'issuer_official', 'document_kind': 'presentation', 'projection_policy': 'macronix-presentation-role-v1', 'url': 'https://www.macronix.com/Lists/QuarterlyResults/Attachments/656/2026q2%20webcast_ppt_en.pdf', 'language': 'en', 'event_date': '2026-07-28', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': None, 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2026-07-28', 'presentation_cover_month': '2026-07', 'content_period': '2026Q2', 'content_periods': ['2026Q2 compared with2026Q1 and2025Q2', '2026H1 compared with2025H1', 'June30/March31 balance sheet snapshots'], 'content_sha256': '6eea155a87d9d69b6d1fa72abec394a56093d915a027138d37f09f9e0787ef32', 'page_count': 23, 'binary_complete': True, 'text_extraction_complete': False, 'native_text_coverage': 'partial', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [13, 16, 17, 18, 20], 'role_page_allowlist': [1, 2, 7, 8, 12], 'excluded_native_text_pages': [3, 4, 5, 6, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23], 'native_editorial_caution': 'All23 original pages retained, including unresolved glyphs13/16/17/18/20. Only1/2/7/8/12 whole native pages are role-qualified. No glyph or chart values inferred.', 'index_reuse_caution': 'Official public2026 JSON lists Q1/Q2 originals and a future October27Q3 event with null files. Latest published past result is July28Q2. No future occurrence or whole archive coverage claimed.', 'forward_looking_caution': 'Keep whole page2 Safe Harbor Statement and copyright notices. Management projections are not achieved outcomes. No Q&A or transcript inferred.', 'period_scope_caution': 'Page7 is2Q26/1Q26/2Q25; page8 is1H26/1H25; page12 is June30/Mar31 balance snapshots. Do not treat first-half amounts as quarterly,annual,TTM or current30day news.', 'unit_scope_caution': 'Pages7/8 use NTDmillion except EPS; page12 NTDmillion except book value per share. Parentheses denote negatives; ppt means percentage points. Weighted-average shares differ from June30outstanding shares. Preserve reported rounding without rebalancing.', 'visual_semantics_caution': 'Only1/2/7/8/12 rendered pages checked against native text. Other tables, diagrams, glyph pages and chart associations remain excluded from roles.', 'financial_scope_caution': 'Presentation summaries do not replace complete five-year audited financial statements. Do not overwrite annual,TTM,FCF or historical financial inputs.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native public JSON and PDF; no HTTP success reuse. Cache-Control private,no-store,no-cache kept. Immutable original archives are audit evidence.', 'publisher_notice': 'Copyright notices kept. Public download does not establish commercial redistribution rights.'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_macronix_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='partial'or native['empty_pages']or native['garbled_pages']!=[13,16,17,18,20]
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
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'en'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'macronix_conference_receipt':proof}

def role_pages(document):
    if not isinstance(document,dict):return []
    if document.get('projection_policy') == 'macronix-presentation-role-v2':
        from .macronix_dynamic_presentation import role_pages as dynamic_role_pages
        return dynamic_role_pages(document)
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
    if isinstance(value, dict) and isinstance(value.get('macronix_conference_receipt'), dict) and value['macronix_conference_receipt'].get('policy') == 'macronix-original-presentation-v2':
        from .macronix_dynamic_presentation import verify_context as verify_dynamic
        return verify_dynamic(value, ticker, deadline=deadline, max_age=max_age)
    try:
        _check(deadline)
        if not supports_macronix(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['macronix_conference_receipt']
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


def _fetch_legacy_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_macronix(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'macronix_presentation_workflow':True}
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
        details.update(macronix_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(macronix_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    return value


def fetch_macronix_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    from .macronix_dynamic_presentation import fetch_context
    return fetch_context(ticker, diagnostics=diagnostics, force_refresh=force_refresh, use_cache=use_cache)


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','2337'),('official_name','旺宏'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'旺宏', LEGAL, 'macronix international co., ltd.', 'macronix international', 'macronix'}
    names = {name.casefold() for name in names}
    aliases = names | {'2337','2337.tw'}
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
    from .macronix_conference_transport import route_kind
    return isinstance(value,dict) and ('macronix_conference_receipt' in value or value.get('source') == PROVIDER
        or route_kind(value.get('source_url')) in {'years','index','pdf'} or any(isinstance(d,dict) and (d.get('source') == PROVIDER or route_kind(d.get('url')) == 'pdf'
            or d.get('projection_policy') in {PROJECTION_POLICY,'macronix-presentation-role-v2'})
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
