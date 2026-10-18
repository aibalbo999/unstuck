"""Sinbon official presentation with distinct event and document dates."""
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
from .sinbon_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '3023.TW'
LEGAL = '信邦電子股份有限公司'
UBN = '23542766'
POLICY = 'sinbon-original-presentation-v1'
PROJECTION_POLICY = 'sinbon-presentation-role-v1'
KNOWN_SHA = '35464cc45f7d76b113cfbda8fb0ed9824e01742c82606c9d0ec370245d635068'
PAGE_TEXT_SHA256 = ('b22d372f6363acec26f250d33ec9f9ba7b92fdfd48528695f51d87d5154a6a70', '5d6173f6ee82379e8ab8ec7b1f915d8b25085655e8fb9dab12a7fb13be7dc46e', '2cbd37227c4a862a5c8a4f343d76fc6ca9e00021624fdf9cb008124ce2a347ed', '9c741e5025d615c0f9d098b26a7d826066d66ae6bf5c0a13de220fa95cd9121e', 'acf440ba57984eb7b75e3f70332fb4c7cd57a5acb24d7286b5361c6a4fc2d2fa', 'bacdb8b1a4a9c64c5e65b11260e2ec752cd9edad65b0f3ba58075481bcaed943', 'c85a1df0ce370ab95a3acd483a8e8e5edfb14db7768854ba883ea8359f971bd3', 'fa13511e7ab637f3e89d6c0f78fc0923e92204a55b51868e9b492f4888a54ecf', '5a4895ca72262dc6d1da9432e6bccdf8c2268a16b074c12c11a407cf88854a30', '1cb8a50a61ed58a40c5ffe0da75939235dae6573eea185b1c8ed3155a90474de', 'c8d31ba0a5a0303e9b8d37be7ce7480d57193eb113955b0005cc6a2d810613d0', 'b7c0c2a4bf0891e7dc345bd6ac76f2e6f57772381d07b896028a5e956a01a8ca', '517adc4e38917fdd88e7a68ecc01eab8b615c35b9d1acbe387b2627106c94727', '1b4f48268dc7e386b9040cd4e8f126925f5f6f750aaa954cb2467b28b8f50e12', 'bab395c6bd174fc8429c2f5c66aede719a9529e4b02aca3626cac82cf4adb0ea', 'cfe81483ec763ac2a0263767678aae012bae84a89d4fb26c314105cf2b39cfd0', '6bbfe644243b40add2f073fc3ffcc72756c6ab17e0bed3b19cf59bab96bac936', 'f70e4c38636222d2d7d8137fd9079db675be60d7d08096f1389fa9a0e0076de8', '6c3296cfeb4542b892fb5a56b16ee6a370704ecafc14d6e5f1d30648fbfae773', 'f103025b2ab2b5aa7b4e66ecd3fd394cb2a46f79a29f8a34afc7b2a97ebca435', 'eb63a2384e517353f49bd708727654deadf3434bc8d71af8cde2fccfea868201', '4836291d094464a34411372f7f2dcf3e1e659124b74207a12c0cc6033da9149b', 'c65a8bebde32cf4a18c31cd25632864d594cc801b085f517236adfd8c724b47e', 'fcb351fb67df8d5dde37614ff05d7e4419432fda55746a1521c0366491d80180', '4c726e1d57805286e458ffb3ad9640fd18e8ac70b48aa21b56186aa9c5940f31', 'cb6ec9cf4ab601f2af717dfb7363946865d6cf3dd8215666c7384a14ce51127b', 'db9df02cf4097b4d2d627ce67d82aa5e2d19a6ca174e6ef2c3ca558d0fbdcbbd', '79b565541b1b8248d2d9dd9be77693749acf5ef75f9aa03ff16babccc4fba19f', 'd18c0e52734da054e88a5d130680ddb7434883dd401c699e51e2e97c4b801389', 'd8dc8264cbd8aa3fba3c47c97dd9f3a251cd22a0c1db2cf8ba75174b2a7573f1', '1880a1083a93177ccc71e02cce85eceed0d6ea9e9892a408107b6e4f1a009c41', '7aaccebe0c2558ab810be54b533054cdd6ea33f40b7a6c388eaba759376ade50', '031637aaf13cf2426c6a345b0a8693e9b56ab26fc81f772edc859b8519d096a7', 'ee60042a365e318fe83aaa5f4fecc3857dd1dc75e681bea7f5f222e867f0d52f', '59704057d5036e1c9d92ff4d9b979a0a4ca62859f8689ccc607d4c7043b8f561', '47b2e779b408deb9c0936849eabf18d6da88b666accad6bb4e4b42b918120b65', '763c49ffc109cdb51ab2e64d81c4356b458317199dd565148f20423c86fd0108', 'face718e1dc19e3cda291dfa414691160b9c54cd041b64b4c1aae768278e1316', 'b86dd3266ad993c8b2ae8314b027529bfacfab128cbe6f4f9e3df9689332ab43', 'b7a86aa822c87e8b42f80c8d79ddbf3596a75415f03f49088a59b650c79fd22a', '914ed161974274a4ea441430999bea92c88cc7cab5b567c22a84b6e2f2d70101', '5ca046cd05bc14a3dedd453bdd46721a681b680eb6f491ff122de5e6bc79722e', '7c80f43fed645bd1eba929d96d8cf85a9bb83cd0b5c51c41d7050614702838ec', '1d44397c72cee9b97a3455040e767d0d26a32f1a828059a7c66dd9ef516c4e19', 'aa5753553f95d552abc9b5f7f1f2aa01b5324e14310c5ffd632ec8dc50c46e86', '875fcb3bcf16fa66cbd727f1e97eeb8d8d9c3d89976675af22f51a48b4295a39', 'b957d452cb18a9b187b46b5461404caceb5c148c3a8f4958e92ae945625da4ff', 'e13d523f8bcd73ce9e63594c0176c6f73061ebfd2622139332e7b909d437547a', '042abee5f962ba5e3f9c850869b23ff5596f0411cba6b85b290922537f2b44ee', '9df44a2a8fc03446e650a71077c18d35cf0f5de5a423aad9b963ef2186f3ca08', 'c60c48f5e246b1c66857eacfed161e6dd8b154d9c489012359ea5e5d36807032', '50bb75a183a9029c5888936577c7adbe2c276ff923655e128232f6937c53dd50', '280421fc52c9a9cb858f5cb4cc4d034e6c9e6d01b7224781ee64ab6f273c53ba', 'd0b0202794854980b60cfa2c28e125eaf2751c19361e0fdbd368bde79db7fcf5', 'f4050ba5034f831a8c3389aa323c69c8f208e03f19d2a9c444b43c56cc23e15c', '9c041179087cdaaf879674f61cd43f8d046a8a24d532160fb2cbc6d87853d1fa', '0f2d0204447855c27d6bf458e00fd35c5ac2013210053c20cae43775fec0967b', 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', 'c7d7d0ad74ae42888b3524491d03621282b5c64962027fe533fda12d7640e5fb', '39fa9ec190eee7b6f4dff1100d6343e10918d044c75eac8f9e9a2596173f80c9', '90c12970db4d693788edc462b57a91e1db514e73ebeac0ae8c9548292693b133', 'f4d5eaebdc98a335d6a4eccb8a3dc805a2c260f8f9c5c82b001722541de4119c', '74ce5299aa1a227475b00566f427ff4ae487f14b058055c80814fa2b60b38b83', '805db90d9adb651810789ea60836a8a087615c4bd686bedc1131f4f488c19095', 'e80d3249f43a8fbf0cfdc4959f7afcf6b61725d2d09bf4a63f3114fe2ad032a2', '6283c56883e1dece061d4eefa94598e9a919fb76feb977f746653eed7cace8b7', '2b0de1257a21135cf13ab6308f9146768ec029417aaee7dfdd7d0a55d04fc6cd', 'e1a37f5e9ecbc288af2b30953bd3435ac625b33b3d9b33a95ce3d3fbc2493e1b', 'e4ca71f8b77df05828c0c7faea67cc61e399c2cb74cc85a050aee5cde055ba23')
ROLE_PAGES = (1, 2, 5, 14, 17, 57)
NOTE = '信邦9/15場次之9/9發布檔名英文69頁準備簡報；封面2026/09、內容2026Q2，非會議逐字稿。全69頁保留，第58頁無原生文字，整體partial；角色限1/2/5/14/17/57完整原生文字及原免責聲明。概況與能力為公司自述，圖像、表格關聯與未來展望未完整驗證，不補零、不當完整年度財報或已實現訂單。'

def supports_sinbon(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'3023', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_sinbon_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Sinbon master size invalid')
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
        raise ValueError('Sinbon complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '3023']
    if len(matched) != 1:
        raise ValueError('Sinbon master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '信邦電子股份有限公司', '公司簡稱': '信邦', '營利事業統一編號': '23542766', '網址': 'www.sinbon.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'SINBON'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Sinbon master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Sinbon master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '信邦', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '信邦2026年9月15日法人說明會英文簡報', 'pdf_url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'event_date': '2026-09-15', 'document_date': '2026-09-09', 'cover_month': '2026-09', 'period_label': '2026Q2', 'filename': '302320260909E001.pdf', 'language': 'en', 'selection_policy': 'latest_exact_MOPS_published_english_attachment', 'history_scope': 'Current2026 index is fully parsed; newer event or changed attachment requires qualification; Chinese and English originals stay separate'}
CURRENT_DESCRIPTOR = {'ticker': '3023.TW', 'symbol': '3023', 'company_name': '信邦', 'event_date': '2026-09-15', 'event_end_date': '2026-09-15', 'event_time': '09:00', 'event_location': 'UBS Taiwan Summit 2026', 'event_summary': '公告本公司受邀參加UBS Taiwan Summit 2026', 'material_file_date': '2026-09-09', 'filename': '302320260909E001.pdf', 'format': 'pdf', 'language': 'en', 'row_sha256': '3dc80827b0007cdaf0b53c0ccfc64d538236cc82903eebec2bc36058b80f4d49', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=302320260909E001.pdf&functionName=t100sb02_1', 'request_sha256': '9363189329cd0a2d93a3cb30b29929a7b6c522a91ae09952256c58e940f6cf80'}

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from mops_published_materials import select_published_material
    selected=select_published_material(raw,TICKER,as_of_epoch=epoch,company_name='信邦')
    current=select_published_material(raw,TICKER,as_of_epoch=time.time()if as_of_epoch is None else as_of_epoch,company_name='信邦')
    if not selected or current!=selected or {k:v for k,v in selected.items()if k!='index_sha256'}!=CURRENT_DESCRIPTOR:
        raise ValueError('latest published event or attachment changed')
    day=date.fromisoformat(selected['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch)or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('published event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 69
DOCUMENT_METADATA = {'document_id': '3023:2026-09-15:35464cc45f7d76b1', 'ticker': '3023.TW', 'source': 'Sinbon published conference presentation', 'source_type': 'regulated_issuer_presentation', 'document_kind': 'presentation', 'projection_policy': 'sinbon-presentation-role-v1', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'language': 'en', 'event_date': '2026-09-15', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': '09:00', 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2026-09-09', 'presentation_cover_month': '2026-09', 'content_period': '2026Q2', 'content_periods': ['2026Q2 financial review', 'Unaudited January-August2026 monthly revenue', '2021-2025 condensed annual results; not complete three statements'], 'content_sha256': '35464cc45f7d76b113cfbda8fb0ed9824e01742c82606c9d0ec370245d635068', 'page_count': 69, 'binary_complete': True, 'text_extraction_complete': False, 'native_text_coverage': 'partial', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [58], 'garbled_pages': [], 'role_page_allowlist': [1, 2, 5, 14, 17, 57], 'excluded_native_text_pages': [3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69], 'native_editorial_caution': 'All69 English pages retained unchanged. Page58 is image-only thank-you, not an empty source page. Only1/2/5/14/17/57 whole native text is role-qualified. Product-advantage heading order on44/45 and column relations on23/27 are excluded.', 'index_reuse_caution': 'Current complete MOPS2026 index selects English E001 for September15event; do not mix Chinese M001 or older issuer-host July presentation. File date September9, event September15 and cover September are distinct; first publication time is unknown.', 'forward_looking_caution': 'Preserve full page2 Safe Harbor Notice. Capabilities, scale and values are issuer statements, not independently confirmed orders or realized forecasts. Follow UL standards is a company claim, not independently verified certification.', 'period_scope_caution': '2026Q2 content, unaudited January-August2026 monthly data,2021-2025 annual summaries and September15event stay distinct. September-December2026 table cells are absent, not zero.', 'unit_scope_caution': 'Page5 company overview states2025revenue995 USDmillion, not995 TWDmillion and not an independently audited financial fact; do not infer FX conversion or replace consolidated TWD financials. Employee/site/customer counts are company overview claims.', 'visual_semantics_caution': 'Only six native-text pages feed roles. Page17 embedded solution-map labels, other images/charts/tables, full layout semantics and footnotes outside these pages are not certified. Full69 original pages remain stored.', 'financial_scope_caution': 'Prepared presentation is not complete five-year financial statements and does not establish2021gross intangible purchase or FCF. No annual/TTM overwrite; figures and source qualifiers remain unchanged.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native MOPS index and published POST attachment; immutable private evidence, no response cache reuse', 'publisher_notice': 'Copyright notices preserved verbatim per page; public download does not prove commercial reuse permission.', 'filename': '302320260909E001.pdf', 'request_method': 'POST'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_sinbon_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='partial'or native['empty_pages']!=[58]or native['garbled_pages']
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
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'sinbon_conference_receipt':proof}

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
        if not supports_sinbon(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['sinbon_conference_receipt']
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


def fetch_sinbon_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_sinbon(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'sinbon_presentation_workflow':True}
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
        details.update(sinbon_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(sinbon_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','3023'),('official_name','信邦'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'信邦', LEGAL, 'sinbon electronics co.,ltd.', 'sinbon electronics co., ltd.', 'sinbon electronics co ltd', 'sinbon'}
    names = {name.casefold() for name in names}
    aliases = names | {'3023','3023.tw'}
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
    return isinstance(value,dict) and ('sinbon_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL and value.get('ticker') == TICKER or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL and d.get('filename') == QUALIFIED_SELECTED['filename']
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
