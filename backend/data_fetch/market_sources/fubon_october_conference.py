"""Fubon official presentation with distinct event and document dates."""
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
from .fubon_october_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2881.TW'
LEGAL = '富邦金融控股股份有限公司'
UBN = '03374805'
POLICY = 'fubon-original-presentation-20261014-v1'
PROJECTION_POLICY = 'fubon-presentation-role-20261014-v1'
KNOWN_SHA = '1fe13398664434a4071ecb926e0f29bd3b81ad7a49b794c48318ff0a7fe79c0c'
PAGE_TEXT_SHA256 = ('b55f4fefc431452bba2597cf9c21a04ad8d2884777d461208f06734578745a4c', 'e8609aa8ad057d1deaa1ce21a1c1ac51b2e771ef7c3070f20d74e41c87526509', 'b1b4d8e48684693efedb9a96f947d7047cc10295c5cb7d64afedd437e8158201', '4838fcbd19c8b97b05b5e120dc25aeb0f71f29574a5b12fa5fdaa4de866de181', '27366f6f71f2a3afe47cf1be18605f668ccf6ad882cdfd002a8faa5f76ec850a', '835df08c4a5e46991edde04a21ed52250d9479c8a35e12b05eb8c8c1543f1812', 'c2bd4f18012c93d045762fa3e0f43ca37eefd8471684f106929c228828ffd37c', '638ba28d94e6f65a7d20dcc448ababd19148bd15b6cf9fb693e936452eda07dd', '12e20ea51a9d772380279156f05723bb14c897254585ece2fc4fdd631b798bdd', '1e1cf78010ad9302b1efa4e1bb32835ebcddf35eb57c2c0fce0afffdb5b2da8b', 'c444b472c2c1d87bb4c50ba8350fa9c53adf7cdc242cdd04002f05f4cc5d2505', '260aa02645d7d1d4211d27616aee9d047f22185822a3feffed51132e5598c102', '868e4d94ef9d86a75d924a25c32022bbfb0e27fc87b775b6cca935f43534566b', 'a7e662cbc444d81733f235496cba3af1740a4e23f1bfb524f5633a1ab879d76c', '3250a568e1c8279183fafdb9292d09995c9c75b2a8c39382612c829df20ecb9e', '504908f3925cdcf0a2dda4a46ecdb8de15bcdaec4691736e0dfd1e44ae9de5b3', 'ee8cf933ad7c5174134ccacf6ab4ddececd5efafa79dbaa64204649502762091', 'f3fa9d7ec00966a2e9ced5cd7127319e7a8fc87ee703f6a61e62a60b80d5060d', '0491af0ea97e3e826b01d5f91439de32a2f8b5d39564a84e376dde8f71bfd997', '94685a63431859698aa53a8b32ee50d6b6244862833b08ad8f012d1cd0f952f8', 'e340459aa656ce12916bedf1a2a7621f6ba3eeefc599f7ddca6b4b1045b4213f', '183cda8653011b75e67b54dda70a0f3cb633ff272cc86173d243b62d93e2849a', 'c3e4d30972dedaf45ed8780b48510447f3034a9d0ee2647fcf1143a0b4f06efa', '361b572202ef59b9cf137e256eaae431ed6119e56b7cbe12c4ab47544e46a92e', '8fff71e7053aa6bb79e63f07cee2a58729ca35b0207c67ddf23c3fb2be216c73', '648035cb96f55c1ea1d42e6a20be286dd058e1995cc082fec8f40b9d0892b8b6', 'bcfc7f75e61f11438c234d0c342c0751a454eae78d40fb98c258475f39c23650', '8d482c5cd89f2444ea2e9e699f7b9bb05f4ae3d5a2cd2b06ebc1ff5a8621152d', '577167073c28b35f90634d5097b932fdb35640865d4a63438718d4efbb7d0617', '8cfbf647eea8956437747d377e029fc6d3071120e5896a3458e432eb1e18b9dd', '9609fcb550ce49c4fbc30e5c00aa2b407c95b050aeaf0699eaaeb4b1e0319e79', '369836530ebb05e7aa0403ca26f032846ca5d02d29e04ae8999ad696929cc972', 'b2e54bdf48ee566272527295849bc95f54f15c2b442f323a0f76e652ed373d11', '99774133387a414a4306ec8deee76c91d78f565732fe229823e32c28b1995c4b', '4097e2c63510ccb77dcf0876bba3ac0bf613ccd3eeede461f4bbcbc4ca552dc9', 'ce0bc68ff9ebb9a4306616d27eecf1b5762a582955f8404799429d8d6850d37b', '6e4b7f92d246ebf0d5376fb39cc9a8b4004f763936b658f4a56051351b843620', 'b0b688de9f392cf0e640c4cb8314a40b6b07da3d4c808b1aa6e6b9b8385b687b', 'f484749a3cd49746fcd0476323299358c26812ef9a2fff31b364f1ad67d2ecc9', '93cc2566034b1fed83bb272815b299bdd1d6ee4476a616f03d18ebb1eb30477e', '31ca803c4cba7fc4aa1a7e82d9f97baf52afb69b9d14c399b939cbf6e1192a46', 'cbee79339ed3621eace75a6bc13efb389690d008dbc03615f1f0abe7e0950aa8', 'c3ad08ee39ed200daa60e638feb642759ae3bf8c3c418db3235fb8092bc2ecf3', 'fb65a38abf0c41c0cde5da87785a72e1e0a2938d130a852ce29ba318d598e56b', '78bade70b9670529e856cf0d32ffefea3d65524f52ea4aed49dea331004900a7', '5c9555a770c4e68c6510033f5d8a8e0a50c07b906f5f6ded7b403128904f5cd1', '3530e357ac6765beda8c586fe618adfceb1540db6e192a31aefa64b2b726cb1a', '2a9cdc8fb90c0bd233f65d2b46fe15740bc62b359e9777ede205ac911ba4ea9b', '9bb0a3d86b729d65b5e7d929a6bcb62035c350a2351183da7b17ffda2c02744f', 'b6e9c0a0b447c76968d8a7d4c1e3b7f273a9bc2b55bde13b5378f13f68f2ba94', 'e1500a9352a1a20daafc9eaabdb52598db0dcd6a03cd257cecc9cfbb97ee9e51', '1044f57e4e8c4644a04adc6828b9e683df8eb0baa82ed00739d911460c7a3829', '6eb4e083cecf55a602b5cfa2083df9ded55c0108e42e5ff7ce3af9a2b63008b1', '89339a01905c50f620652a9cb3ba4705263088b2875fe56e298c878d038443a7', 'cc44eed9ba9a547da81cd4c155d8f849614ab8b641e123bf56492059c09513a6', '6a9c86ac21afefe9d27371c695c061b5e4b558c17f2947536aebbd28289da674', '2a4cd04317072ed5487720f41281ab129ac806b48153d58512940a19966d3fe5', '5de9fa17a7983a15aa911a5484e6e2e074f9ee0a54c30a582da042e7661e9b76', 'e249857d0f1ac01265e2fb67a410558979d129ff498bf122bbc7e0e7d2332044', 'ac29066c1510b666b631aeeb05df10d63741defc2aaa06062782f192868e46b3', 'c83a742a9e67c821ca47d2616ab47325d1f0eaaeddc783a4a3bb6f5f9ca2e9ed')
ROLE_PAGES = (1, 2, 3, 25, 33, 41, 44, 47)
NOTE = '已核對富邦金官方主檔、最新已公開場次及2026-10-14英文原件；保留全部61頁文字，但僅8個已覆核敘述頁供角色使用。含免責、未經審計及前瞻陳述限制；子公司敘述不當成金控合併財報，市場排名、優勢與展望僅為公司自述。圖表、頁50-61樣板與宏觀附錄不投餵角色。不具逐字稿、Q&A、完整視覺或完整財報覆蓋，也不證明首次公布或活動實際發生。'

def supports_fubon(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2881', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_fubon_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Fubon master size invalid')
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
        raise ValueError('Fubon complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2881']
    if len(matched) != 1:
        raise ValueError('Fubon master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '富邦金融控股股份有限公司', '公司簡稱': '富邦金', '營利事業統一編號': '03374805', '網址': 'www.fubon.com'}
    # Accept official master padding without changing the issuer name.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'Fubon Financial'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Fubon master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Fubon master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '富邦金', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '富邦金2026年10月15日法人說明會英文簡報', 'pdf_url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'event_date': '2026-10-15', 'document_date': '2026-10-14', 'cover_month': None, 'period_label': '2026H1', 'filename': '288120261014E002.pdf', 'language': 'en', 'selection_policy': 'latest_exact_MOPS_published_english_attachment', 'history_scope': 'Current2026 index is fully parsed; newer event or changed attachment requires qualification; Chinese and English originals stay separate'}
CURRENT_DESCRIPTOR = {'ticker': '2881.TW', 'symbol': '2881', 'company_name': '富邦金', 'event_date': '2026-10-15', 'event_end_date': '2026-10-15', 'event_time': '10:00', 'event_location': '台北', 'event_summary': '討論富邦金控財務及業務相關資訊', 'material_file_date': '2026-10-14', 'filename': '288120261014E002.pdf', 'format': 'pdf', 'language': 'en', 'row_sha256': '1849e21ccada9ad6165edb9f453aaa73950c6cef565d771a7c1b8b75bb460379', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'method': 'POST', 'request_body': 'step=9&filePath=%2Fhome%2Fhtml%2Fnas%2FSTR%2F&fileName=288120261014E002.pdf&functionName=t100sb02_1', 'request_sha256': '5adf674f6d394b8ffb331b38b176fcb7d775e3059d7eb1161fd414589c9e0a32'}

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from mops_published_materials import select_published_material
    selected=select_published_material(raw,TICKER,as_of_epoch=epoch,company_name='富邦金')
    current=select_published_material(raw,TICKER,as_of_epoch=time.time()if as_of_epoch is None else as_of_epoch,company_name='富邦金')
    if not selected or current!=selected or {k:v for k,v in selected.items()if k!='index_sha256'}!=CURRENT_DESCRIPTOR:
        raise ValueError('latest published event or attachment changed')
    day=date.fromisoformat(selected['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch)or not 0<=(_today(as_of_epoch)-day).days<=370:
        raise ValueError('published event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 61
DOCUMENT_METADATA = {'document_id': '2881:2026-10-15:1fe13398664434a4', 'ticker': '2881.TW', 'source': 'Fubon published conference presentation', 'source_type': 'regulated_issuer_presentation', 'document_kind': 'presentation', 'projection_policy': 'fubon-presentation-role-20261014-v1', 'url': 'https://mopsov.twse.com.tw/server-java/FileDownLoad', 'language': 'en', 'event_date': '2026-10-15', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': '10:00', 'event_timezone': None, 'published_at': None, 'material_file_date': '2026-10-14', 'presentation_cover_month': None, 'content_period': '2026H1', 'content_periods': ['Main deck: 1H26 financial results; individual pages retain their own stated dates', 'Pages50-61 contain design templates and unrelated macro appendix; excluded from all roles'], 'content_sha256': '1fe13398664434a4071ecb926e0f29bd3b81ad7a49b794c48318ff0a7fe79c0c', 'page_count': 61, 'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [], 'role_page_allowlist': [1, 2, 3, 25, 33, 41, 44, 47], 'excluded_native_text_pages': [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 31, 32, 34, 35, 36, 37, 38, 39, 40, 42, 43, 45, 46, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61], 'native_editorial_caution': 'All61 native pages retained unchanged; full visual/table relationships are not certified. Roles receive only whole narrative pages1/2/3/25/33/41/44/47. Preserve disclaimer and subsidiary identity. All market rank, strength and growth assertions are issuer statements, not independently verified findings.', 'index_reuse_caution': 'Current complete MOPS2026 index selects October15 event and October14 English attachment. Filename date is not verified first publication. September94-page original is a separate preserved profile.', 'forward_looking_caution': 'Preserve complete page2 disclaimer. Unaudited figures, rounding, forward-looking statements, strategies, ESG and market rankings remain issuer claims, not independently verified facts or realized forecasts.', 'period_scope_caution': '1H26 main results and the October15 event remain distinct. Each page retains its own stated date; excluded macro/template appendix cannot supply business facts. IFRS17 and IFRS4 amounts and ratios are not interchangeable.', 'unit_scope_caution': 'Numbered labels on25/33/41/44/47 are strategy items, not financial values. Keep subsidiary names and issuer-attributed market rankings. Do not infer FX conversion, chart/table associations, denominators or omitted values.', 'visual_semantics_caution': 'Eight visually checked whole native-text pages feed roles. Other53 pages stay in the original only. Complex financial charts, page5 scorecards, page13 IFRS charts and pages50-61 appendix/templates are excluded. All61 native pages do not certify complete visual coverage.', 'financial_scope_caution': 'Holding company, Life(page25), Bank(page33), Insurance(page41), Securities(page44) and Asset Management(page47) are distinct scopes. No subsidiary claim becomes a holding-company metric. Presentation is not a complete audited financial statement.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native MOPS index and published POST attachment; immutable private evidence, no response cache reuse', 'publisher_notice': 'Copyright notices preserved verbatim per page; public download does not prove commercial reuse permission.', 'filename': '288120261014E002.pdf', 'request_method': 'POST', 'event_end_date': '2026-10-15', 'appended_results_cover_date': None}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_fubon_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete'or native['empty_pages']!=[]or native['garbled_pages']
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
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'en','filename':QUALIFIED_SELECTED['filename'],'request_method':'POST'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'fubon_conference_receipt':proof}

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
        if not supports_fubon(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['fubon_conference_receipt']
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


def fetch_fubon_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True, _prefix=None):
    if not supports_fubon(ticker):return {}
    deadline = _prefix[5] if _prefix is not None else time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'fubon_presentation_workflow':True}
    try:
        if _prefix is None:
            http.check_index_guard()
            raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url']);_check(deadline)
            selected,index = http.get_receipt(INDEX_URL,parser=lambda raw,r:select_presentation(raw,r['retrieved_at']));_check(deadline)
        else:
            identity,index,selected,components,count,_ = _prefix
            http.components=deepcopy(components);http.http_request_count=count
            if selected != QUALIFIED_SELECTED:raise ValueError('unqualified prefix selection')
            _check(deadline)
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
        details.update(fubon_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(fubon_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2881'),('official_name','富邦金'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'富邦金', LEGAL, 'Fubon Financial Holding Co., Ltd.', 'Fubon Financial Holding Co.,Ltd.', 'FUBON FINANCIAL HLDG CO LTD', 'Fubon Financial'}
    names = {name.casefold() for name in names}
    aliases = names | {'2881','2881.tw'}
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
    return isinstance(value,dict) and ('fubon_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL and value.get('ticker') == TICKER or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL and d.get('filename') == QUALIFIED_SELECTED['filename']
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
