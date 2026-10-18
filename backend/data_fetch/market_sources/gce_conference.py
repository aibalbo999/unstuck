"""Qualified GCE August presentation, preserving mixed financial and visual scopes."""
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
from .gce_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2368.TW'
LEGAL = '金像電子(股)公司'
UBN = '30955404'
POLICY = 'gce-original-presentation-v1'
PROJECTION_POLICY = 'gce-presentation-role-v1'
KNOWN_SHA = '5cf45269fd71405896244573487fff93966ca6b68514d611993bfb7e8cfe315d'
NOTE = ('金像電官方2026-08-28英文法說簡報，11頁；非逐字稿或問答紀錄。'
        '第3頁僅六個已核對箭頭符號轉換，其餘原生文字、數字與順序保持。'
        '原生文字完整不代表圖表、圖片或配對完整；第6頁產品應用圖表與數字無原生文字，'
        '第9頁30L斷為3及0L且幾何關係未取得，不可猜修或推算；第10頁Q&A只有標題。'
        '第5頁歷年全年及2026 JUL口徑、第7頁2026H1/2025H1、第8頁2025Q1–Q4/2026Q1–Q2不可混用；沒有2026Q3/Q4實績。'
        '表格金額單位新台幣億元；EPS每股元、差額9.09及百分率不同；14.31%不是14.31百分點。'
        '第2頁預測與估計不確定、非承諾，不以公司展望當已完成實績；簡報不替代完整財報。'
        '場次日期由官網與封面一致核對，不是獨立發生證明；時刻及首次發布時間未知。'
        '原站no-cache且索引meta no-store，重新取得必須新HTTP；原件僅私存稽核，不主張商業再利用授權。')


def supports_gce(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2368', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_gce_presentation_pages(raw, *, timeout_seconds):
    # Lazy import keeps unsupported stocks independent of the source-specific worker.
    from gce_presentation_pdf_reader import extract_gce_presentation_pages as extract
    return extract(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('GCE master size invalid')
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
        raise ValueError('GCE complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2368']
    if len(matched) != 1:
        raise ValueError('GCE master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '金像電', '營利事業統一編號': UBN, '網址': 'http://www.gce.com.tw/'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'GCE'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('GCE master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('GCE master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '金像電', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('GCE index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 1_048_576:
        raise ValueError('GCE index size invalid')
    soup = BeautifulSoup(raw.decode('utf-8', 'strict'), 'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True) != 'GCE金像電子':
        raise ValueError('GCE index publisher invalid')
    if _one(soup,'h1').get_text(' ',strip=True) != '法人說明會':
        raise ValueError('GCE conference index missing')
    table = _one(soup,'table')
    entries = table.select('tbody > tr')
    # This qualified index is a complete single table. Unknown shape is held.
    if len(entries) != 32:
        raise ValueError('GCE complete index shape changed')
    rows = []
    for entry in entries:
        cells = entry.select(':scope > td')
        if len(cells) != 3:
            raise ValueError('GCE index row malformed')
        title = cells[0].get_text(' ',strip=True)
        match = re.fullmatch(r'(\d{3})年度本公司法人說明會資料 \((\d{3})\.(\d{1,2})\.(\d{1,2}) 中文版,英文版\)',title)
        if not match or match[1] != match[2]:
            raise ValueError('GCE event date malformed')
        day = date(int(match[2])+1911,int(match[3]),int(match[4]))
        rows.append((day,entry))
    days = [row[0] for row in rows]
    if len(set(days)) != len(days) or days != sorted(days,reverse=True):
        raise ValueError('GCE date list ambiguous')
    latest,entry = rows[0]
    if latest != date(2026,8,28) or latest > _today(epoch) or not 0 <= (_today()-latest).days <= 370:
        raise ValueError('GCE latest revision unknown or future')
    links = entry.select('a[href]')
    if [a['href'] for a in links] != ['file/法說會20260828中文版.pdf','file/法說會20260828英文版.pdf']:
        raise ValueError('GCE latest published attachments missing or changed')
    return {'event_date':latest.isoformat(),'event_time':None,'event_timezone':None,'event_location':None,
            'title':'金像電2026-08-28官方英文法說簡報','pdf_url':PDF_URL,'period':'',
            'index_period':'2026-08','selection_policy':'latest_complete_official_table_exact_qualified_native_cover'}


def native_presentation(raw, selected, deadline):
    from gce_presentation_pdf_reader import glyph_evidence, PAGE_TEXT_SHA256
    _check(deadline)
    if sha256(raw).hexdigest() != KNOWN_SHA:
        raise ValueError('GCE original revision is not qualified')
    try:
        native = extract_gce_presentation_pages(raw, timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind == 'timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    if (native['coverage_status'] != 'complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count'] != 11 or len(native['pages']) != 11
            or [p['page_number'] for p in native['pages']] != list(range(1,12))
            or tuple(sha256(p['text'].encode()).hexdigest() for p in native['pages']) != PAGE_TEXT_SHA256
            or native['content_sha256'] != KNOWN_SHA
            or json.dumps(native.get('gce_glyph_evidence'),sort_keys=True,allow_nan=False) != json.dumps(glyph_evidence(),sort_keys=True)
            or selected['event_date'] != '2026-08-28' or selected['index_period'] != '2026-08'):
        raise ValueError('GCE original pages or symbol proof unverified')
    return native


def _context(selected, native, proof):
    doc = {'document_id':'2368:'+selected['event_date']+':'+KNOWN_SHA[:16],
           'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
           'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'en',
           'event_date':selected['event_date'],'event_date_basis':'issuer_index_and_exact_native_cover_day',
           'event_time':None,'event_timezone':None,'event_location':None,
           'event_status':'published_past_material_not_independently_occurrence_verified',
           'content_period':'','content_periods':['2026H1','2025H1 comparison','2016–2025 annual revenue history','2026 through July sales label','2025Q1–Q4 and2026Q1–Q2 comparisons','forward-looking estimates'],
           'published_at':None,'material_file_date':None,'retrieved_at_epoch':proof['pdf']['retrieved_at'],
           'content_sha256':KNOWN_SHA,'page_count':11,'pages':native['pages'],'binary_complete':True,
           'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
           'full_content_coverage_verified':False,'missing_text_pages':[],'garbled_pages':[],
           'parser_version':native['parser_version'],'gce_glyph_evidence':deepcopy(native['gce_glyph_evidence']),
           'known_native_text_omissions':[
               {'page_number':3,'issue':'factory photos not native evidence; only six verified arrow glyphs normalized'},
               {'page_number':4,'issue':'geographic and plant/service legend associations are visual'},
               {'page_number':6,'issue':'product application chart and all table figures lack native text; title only'},
               {'page_number':9,'issue':'technology/layer geometry unavailable; native 30L split as 3 newline0L; do not guess or repair'},
               {'page_number':10,'issue':'Q&A title only; no questions or answers'}],
           'financial_scope_caution':'Consolidated H1 and quarterly comparisons, annual and through-July sales scopes differ. No complete financial-history replacement.',
           'unit_scope_caution':'Pages7–8 amounts NT$ hundred million; margins/growth percentages, EPS per-share and EPS difference9.09 differ; GPM comparison14.31% is not14.31percentage points.',
           'period_scope_caution':'2026H1/Q1/Q2, prior periods and2026 JUL sales label differ; no2026Q3/Q4 actuals.',
           'forward_looking_caution':'Page2 projections/estimates uncertain and nonbinding, not independently verified future outcomes.',
           'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
           'response_reuse_policy':'HTTP no-cache and index meta no-store; new acquisitions require fresh HTTP; private immutable evidence only'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['title'],'source':PROVIDER,
            'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'en'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'gce_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_gce(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['gce_conference_receipt']
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


def fetch_gce_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_gce(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'gce_presentation_workflow':True}
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
        details.update(gce_originals_verified=True,coverage_status='native_presentation_text_complete',
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
        details.update(gce_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2368'),('official_name','金像電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'金像電',LEGAL.casefold(),'gce','gold circuit electronics','gold circuit electronics ltd.','gold circuit electronics ltd','gold circuit electronics co','金像電子股份有限公司'}
    aliases = names | {'2368','2368.tw'}
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
    return isinstance(value,dict) and ('gce_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
