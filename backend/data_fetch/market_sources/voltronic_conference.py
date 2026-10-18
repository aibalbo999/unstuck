"""Voltronic official presentation with distinct event and document dates."""
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
from .voltronic_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '6409.TW'
LEGAL = '旭隼科技股份有限公司'
UBN = '28865032'
POLICY = 'voltronic-original-presentation-v1'
PROJECTION_POLICY = 'voltronic-presentation-role-v1'
KNOWN_SHA = 'df2e5df2eed796be2286edeb8566b1a5b84615e9b675ef2f123e12977a024e6b'
PAGE_TEXT_SHA256 = ('7063bbd5d9d11422b641057e1caa8227934bb05e8285472ff835cca4d20a7221', '4cce0e7d110e9f5f33eb78966ca0702bcafefbede2a1e26742c7de0863114d45', 'c53bd29a551d5f7bca91a9403b0965fd643d8390be45d363714401c871084d57', '1cce777b07e6beeb9cb87810d36a86e76e137718c3d2455cefd8fd4f50bd11b4', '69d4966da50621ca55c2ff857eb5ed87472c4acba5db04140e6e458409bea146', '0990af1a417cd4033ac72fa35805db1b1d2d98c55d43353d775c6a9bd285b5c4', '744b32497e1f78719f9bd31194403dd719537a5bee1bc0701f2fd1ca2b7c1b13', '5f1e40dccd27e615d4603cdf2b48b2321c7469472d3a4cea1caedb682cc6b654', '2fcf82709db21cbc4631df72da7be789c767bc61c1a40d99fe3251f8463a264c', 'e73bd45b4c1d37299ddb425dc24c3b03408cca192c318bfb4d8ed8949a7c7640', '95a72cd5bedbd8a2d8bd7e6c027d6fb5afdfccadbb5175ece8bc508666e47c6a', '1d41712f583d124c3903558dcb580e6b5a1847a4d828dc0d0bed6d4937a8d8de', 'fddb36c0afb37533cb52c1d480bb0b697dac0d953c249214b985e5aad6e26ed3', '0f1d2ab41491dabf98014917dd48862e272a5fb94ecd6f254df89339bc2464da', '79dba2f921214d85edcdbda8eb6687267e6b5fd60ce1da126148d4ae2859d64c', '88bd925583db36b3df1b5ac822782ba74f41dbcc5dce83839443429f158d92eb', '7b4714ab6359cd05f81990935811dec47579f6950b59060dbb82035a387cc143', 'c6921d4693f2f1dbc3d3ad13af49a06cbd4720343fca6125fa4bdce87004cb81', '2086a209bf89246f5f370ff8fcadaf92177ad3ca57cbd474b98a7010164f8cdc', 'c8ccd85475a5689b30f372809d40a43e334c94cdb60b083ab3709af7691a252d', '728d9ccc39ba8fa361fc7838e35178de54000f7c9eb32e59f7f6d8975d4e5ae2', 'e93a0ce8c645f4fa3ac137d11d69590d7d44f46f3057719918743d8b8158be67', '829e64559739826f9b12dea7ebf2298b06b83ec5153b8352aea350a2f2e9f5f5', '3c05de074361c67ebb598181249c9234106df5e9ff751113a10fcf4f6288ccf8', 'bf3223f2550e2cc717da7a827ab4de39277b76be839085d8c195bc285fcd8f21', '870d2f714ac0ba7b49e3f5af7980c5adcdcb90601dbdf7ecf72746b8cb44c0fb', '02d4007df4aff7f25fb880349e1134c7695ccfa34b90896beedd0413ba6c1024', '29f656ed33999350793a819284f2779e26e0fc3951840f5248a3c83a60ff7102', '7dbb31937911ac4865d8f313a0a00cddfcaa75feb98e4a2dad066fe9817d511b', '530da530f461da380f127d5b5f7a8f4af29e5a4b9617193592429c58089bf052', '69c93af81c9856e7169a6b4a9828f826469e07c35ca3f33e382e5bc45cb6c430', '90c6d6f905b73ee65b52d1d196732d80050536bb890b201ec3a6059c9349559c')
ROLE_PAGES = (1, 6, 7, 8, 10, 11)
NOTE = '旭隼9/14場次、9/10檔名日期、2026Q2內容之32頁英文簡報；非逐字稿。修復限原檔217處xref位置並保留憑據，其他警告仍拒收。全頁及原文保留，原生文字與整體partial；角色限已逐頁核對的1/6/7/8/10/11整頁，私用區項目符號原樣保留。公司概況、競爭力與獎項為公司自述，圖表與認證圖示未資格化，不當完整財報或今日新聞。'

def supports_voltronic(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'6409', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_voltronic_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Voltronic master size invalid')
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
        raise ValueError('Voltronic complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '6409']
    if len(matched) != 1:
        raise ValueError('Voltronic master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '旭隼科技股份有限公司', '公司簡稱': '旭隼', '營利事業統一編號': '28865032', '網址': 'https://voltronicpower.com/zh-TW'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'VOLTRONIC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Voltronic master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Voltronic master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '旭隼', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '旭隼2026年9月14日法人說明會英文簡報', 'pdf_url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'event_date': '2026-09-14', 'document_date': '2026-09-10', 'cover_month': None, 'period_label': '2026Q2', 'filename': '640920260910E001.pdf', 'language': 'en', 'selection_policy': 'latest_exact_MOPS_published_english_attachment', 'history_scope': 'Current2026 index is fully parsed; newer event or changed attachment requires qualification; Chinese and English originals stay separate'}
CURRENT_DESCRIPTOR = {'ticker': '6409.TW', 'symbol': '6409', 'company_name': '旭隼', 'event_date': '2026-09-14', 'event_end_date': '2026-09-14', 'event_time': '14:00', 'event_location': '台北W飯店 110台北市信義區忠孝東路五段10號', 'event_summary': '本公司受邀參加瑞銀證券所舉辦之『UBS Taiwan Summit 2026』，會中介紹公司之營運與財務狀況。', 'material_file_date': '2026-09-10', 'filename': '640920260910E001.pdf', 'format': 'pdf', 'language': 'en', 'row_sha256': '3b6084dc1d2fc98b13d9af517e38b35406fafd911708263124bd276b0374a441', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=640920260910E001.pdf&functionName=t100sb02_1', 'request_sha256': '41cabfba9c952b2bfdf48404b4cfcaa35cf65bb846c6861b75558921ec13409e'}

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from mops_published_materials import select_published_material
    selected=select_published_material(raw,TICKER,as_of_epoch=epoch,company_name='旭隼')
    current=select_published_material(raw,TICKER,as_of_epoch=time.time()if as_of_epoch is None else as_of_epoch,company_name='旭隼')
    if not selected or current!=selected or {k:v for k,v in selected.items()if k!='index_sha256'}!=CURRENT_DESCRIPTOR:
        raise ValueError('latest published event or attachment changed')
    day=date.fromisoformat(selected['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch)or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('published event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 32
DOCUMENT_METADATA = {'document_id': '6409:2026-09-14:df2e5df2eed796be', 'ticker': '6409.TW', 'source': 'Voltronic published conference presentation', 'source_type': 'regulated_issuer_presentation', 'document_kind': 'presentation', 'projection_policy': 'voltronic-presentation-role-v1', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'language': 'en', 'event_date': '2026-09-14', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': '14:00', 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2026-09-10', 'presentation_cover_month': None, 'content_period': '2026Q2', 'content_periods': ['2026Q2 and2026H1 results', '2021-2025 condensed annual comparisons; not complete audited statements', '2026Q2-E_B1 cover label; no exact cover date'], 'content_sha256': 'df2e5df2eed796be2286edeb8566b1a5b84615e9b675ef2f123e12977a024e6b', 'page_count': 32, 'binary_complete': True, 'text_extraction_complete': False, 'native_text_coverage': 'partial', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [6, 7, 8, 10, 11, 13], 'role_page_allowlist': [1, 6, 7, 8, 10, 11], 'excluded_native_text_pages': [2, 3, 4, 5, 9, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32], 'native_editorial_caution': 'All32 original pages and text retained unchanged.217 exact xref-to-leading-LF observations are recorded; no raw byte rewrite or generic warning suppression. Native extraction remains partial:6/7/8/10/11/13 contain private-use bullet characters. Only1/6/7/8/10/11 complete native text was visually checked for role use; these bullets remain unchanged, not interpreted as missing numbers.', 'index_reuse_caution': 'Complete current-year MOPS index selects September14event with exact English E001 attachment dated September10 in filename. The cover says2026Q2-E_B1 and has no month/day. Event date, filename date, content period and unknown first-publication time must stay distinct.', 'forward_looking_caution': 'Capabilities, market position, customer reach, rankings, awards and forecasts are issuer statements, not independently verified performance, certifications, orders or future outcomes. Page6 certification logos are images and are not evidence of valid current certification.', 'period_scope_caution': 'Page7 top-ten customer revenue share38.5% refers to2025. Page11 payout86.3% and ROE43% are past-ten-year company averages, not2026quarter values. Awards and ranks keep their stated years; this presentation is not current30-day news.', 'unit_scope_caution': 'Role pages contain customer/country/engineer counts and percentages, not independently audited financial amounts. Preserve percentages and periods; do not convert them to revenue or cash-flow estimates. Financial charts and five-year summary tables remain outside role-qualified text.', 'visual_semantics_caution': 'Six rendered pages checked against whole native text. Map locations, certification logos, photos and page8 embedded R&D chart are not native-text evidence and remain unqualified; no OCR or chart values inferred. Other26 pages stay archived but outside role projection.', 'financial_scope_caution': 'Prepared presentation does not replace five-year audited financial statements or prove gross intangible purchases/FCF. No annual,TTM or current-period financial inputs are overwritten.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native MOPS index and published POST attachment; immutable private evidence, no response cache reuse', 'publisher_notice': 'Copyright notices preserved verbatim per page; public download does not prove commercial reuse permission.', 'filename': '640920260910E001.pdf', 'request_method': 'POST', 'object_header_whitespace_evidence': {'policy': 'exact-original-xref-leading-LF-v1', 'content_sha256': 'df2e5df2eed796be2286edeb8566b1a5b84615e9b675ef2f123e12977a024e6b', 'warning_count': 217, 'observations_sha256': '9c05eaeb25e2f42a0a8036acc1fac72bbf203bfa4385f8f55aba298e45597764', 'raw_bytes_modified': False, 'generic_warning_suppression': False}}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_voltronic_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='partial'or native['empty_pages']or native['garbled_pages']!=[6,7,8,10,11,13]
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
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'en','filename':QUALIFIED_SELECTED['filename'],'request_method':'POST'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'voltronic_conference_receipt':proof}

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
        if not supports_voltronic(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['voltronic_conference_receipt']
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


def fetch_voltronic_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_voltronic(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'voltronic_presentation_workflow':True}
    try:
        http.check_index_guard()
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
        selected,index = http.get_receipt(INDEX_URL,parser=lambda raw,r:select_presentation(raw,r['retrieved_at']));_check(deadline)
        native,pdf = http.get_receipt(PDF_URL,parser=lambda raw,r:native_presentation(raw,selected,deadline))
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
        details.update(voltronic_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(voltronic_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','6409'),('official_name','旭隼'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'旭隼', LEGAL, 'Voltronic Power Technology Corp.', 'VOLTRONIC POWER TECHNOLOGY CORP', 'VOLTRONIC'}
    names = {name.casefold() for name in names}
    aliases = names | {'6409','6409.tw'}
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
    return isinstance(value,dict) and ('voltronic_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL and value.get('ticker') == TICKER or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL and d.get('filename') == QUALIFIED_SELECTED['filename']
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
