"""NPC official presentation with distinct event and document dates."""
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
from .npc_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '1303.TW'
LEGAL = '南亞塑膠工業股份有限公司'
UBN = '75370905'
POLICY = 'npc-original-presentation-v1'
PROJECTION_POLICY = 'npc-presentation-role-v1'
KNOWN_SHA = 'ed8c44e1b807c58fcb9102c6987093f88d916919cf97713a8faa6cf5b3abdf1d'
PAGE_TEXT_SHA256 = ('ae252df6f6e50ef19cd388bad569f61c565e75a442ed68abd751f48e957740ac', 'ea267dd22e3b4ce20e60c83ff9a59e0828682b7c6904ae076e7211babf7afb73', '48085bf1c935abd82866a9136a9185898d1a075470a3ed56f232004d4db8ac2d', '7e973b8eceabd3b32d3a61f43f61eeb0a0dee15e0586f00c444b48c3777ec074', '6ad96fc03d5834bd3e17c49f2cec87af00f377b32ed56d8580d87fc86426b7b7', 'b225128df3050e0f192d2e219de18430d8551cecca73903317154ed7a4549d20', '5399f3d73991a6ceb63d779d7dac3bddc14c9a4f4c7768abe5b395b1f5ee3537', '826f54f7821e81abceb33b09380323fc5ed87efee43d7fd41c5360b75d3e8d6d', '5264bd36988f13433263ac48815c7aeb9004ca598d511c169fa79ff2febd9e1e', 'e085fb0d436b6b608f33fc9d597dfbd4db8946a9f6f87de0e5a16b7bda2f7a79', 'b6dc888c4288410d87cefde9a696ff88c7f6b284e98c85a9d1a4d0a7aa02b33e', 'd8c36d2aac9b69ef32625aee0d2e9d824d46cee73c8c2e3dd20e0ad26ebd0d45', 'b6674d7ab26dffaba6de884f3fc14144bdb9d1910bb1109c4e161e46b470a293', '549782f1f5f1dd08e62476cafe5fb51fc97693706e3a38ae9aabe0f13a71da78', 'e020d1ee91e4e1ec9ee2651a4cc856a41b73f22486ebffb25459700b594b92ba')
ROLE_PAGES = (1, 3, 13)
NOTE = '南亞官方15頁完整簡報，10/13活動連結9月封面原件；H1營運、2025營收及Q3展望期間分開，首次發布日未知。只核對方塊與菱形符號，數字及原PDF保持。文字complete但整體partial，角色限1/3/13完整頁；未核圖表及p14擴產表不進角色，非逐字稿或五年查核財報。'

def supports_npc(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'1303', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_npc_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('NPC master size invalid')
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
        raise ValueError('NPC complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '1303']
    if len(matched) != 1:
        raise ValueError('NPC master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '南亞塑膠工業股份有限公司', '公司簡稱': '南亞', '營利事業統一編號': '75370905', '網址': 'http://www.npc.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'NPC'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('NPC master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('NPC master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '南亞', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '南亞2026年上半年營運概況（10/13摩根大通法人說明會）', 'pdf_url': 'https://www.npc.com.tw/npcfile/public/report/premat/20261012171625560.pdf', 'event_date': '2026-10-13', 'document_date': None, 'cover_month': '2026-09', 'period_label': '2026H1', 'index_record_count': 8, 'selection_policy': 'latest_exact_published_event_in_complete_current_year_table', 'history_scope': '8 visible2026 rows; earlier history retained but not qualified complete; new publication requires qualification'}
CURRENT_ROWS = [{'cells': ['2026/10/13', '法說會簡報-2026年上半年營運概況(受邀參加摩根大通法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20261012171625560.pdf']}, {'cells': ['2026/09/11', '法說會簡報-2026年上半年營運概況(受邀參加群益證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260910134353986.pdf']}, {'cells': ['2026/09/04', '法說會簡報-2026年上半年營運概況(受邀參加統一證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260910134527482.pdf']}, {'cells': ['2026/08/25', '法說會簡報-2026年上半年營運概況(受邀參加國泰證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260824161019665.pdf']}, {'cells': ['2026/08/21', '法說會簡報-2026年上半年營運概況(受邀參加玉山證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260824160957650.pdf']}, {'cells': ['2026/05/26', '法說會簡報-2026年第1季營運概況(受邀參加台新證券2026年第2季投資論壇)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260526174059828.pdf', 'https://www.youtube.com/embed/20Yb9RUeFA4']}, {'cells': ['2026/03/13', '法說會簡報-2025年度營運概況(受邀參加中國信託證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260312174349573.pdf', 'https://www.youtube.com/embed/_JQfFu5ywMg']}, {'cells': ['2026/03/03', '法說會簡報-2025年度營運概況(自結數)(受邀參加元大證券法人說明會)', '', ''], 'links': ['https://www.npc.com.tw/npcfile/public/report/premat/20260302180315125.pdf']}]
SYMBOL_EVIDENCE_SHA256 = '361b213ba12c78342ce00bb74796ea7a11c092c3ad7ff01180937c1ad55e873a'
HEAD_TITLE = '法人說明會資料|南亞塑膠'
OWNER = 'Copyright © 2015 南亞塑膠工業股份有限公司 All Rights Reserved.'
HEADERS = ['日期', '說明', '下載', '影音']
ROW_COUNT = 55
DATE_COLUMN = 0

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import urljoin
    if not isinstance(raw,bytes)or not 0<len(raw)<=1_048_576:raise ValueError('index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>'in body or trailer.strip()or '</body>'not in body:raise ValueError('complete index required')
    soup=BeautifulSoup(text,'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!=HEAD_TITLE or OWNER not in soup.get_text(' ',strip=True):raise ValueError('publisher changed')
    # PCB publishes unclosed th tags: compare individual strings, not nested th text.
    tables=[t for t in soup.select('table')if t.find('thead')and list(t.find('thead').stripped_strings)==HEADERS]
    if len(tables)!=1:raise ValueError('conference table ambiguous')
    rows=[r for r in tables[0].find_all('tr')if r.find_all('td',recursive=False)]
    if len(rows)!=ROW_COUNT:raise ValueError('event history changed')
    current=[];past=False
    for row in rows:
        cells=row.find_all('td',recursive=False)
        if len(cells)!=len(HEADERS):raise ValueError('event row malformed')
        day=cells[DATE_COLUMN].get_text(strip=True);match=re.match(r'^(\d{4})/',day)
        if not match or int(match[1])>2026:raise ValueError('event year unqualified')
        if int(match[1])<2026:
            past=True;continue
        if past:raise ValueError('current event order invalid')
        current.append({'cells':[x.get_text(' ',strip=True)for x in cells],
                        'links':[urljoin(INDEX_URL,a['href'])for a in row.select('a[href]')]})
    if current!=CURRENT_ROWS:raise ValueError('current published event or attachment changed')
    day=date.fromisoformat(QUALIFIED_SELECTED['event_date'])
    if not day<=_today(epoch)<=_today(as_of_epoch)or not 0<=(_today(as_of_epoch)-day).days<=370:raise ValueError('event date invalid')
    return deepcopy(QUALIFIED_SELECTED)

PAGE_COUNT = 15
DOCUMENT_METADATA = {'document_id': '1303:2026-10-13:ed8c44e1b807c58f', 'ticker': '1303.TW', 'source': 'NPC official conference presentation', 'source_type': 'issuer_official', 'document_kind': 'presentation', 'projection_policy': 'npc-presentation-role-v1', 'url': 'https://www.npc.com.tw/npcfile/public/report/premat/20261012171625560.pdf', 'language': 'zh-TW', 'event_date': '2026-10-13', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': None, 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': None, 'presentation_cover_month': '2026-09', 'content_period': '2026H1', 'content_periods': ['2026H1 financials', 'historical company facts with original period qualifiers', 'issuer forward-looking plans at document time'], 'content_sha256': 'ed8c44e1b807c58fcb9102c6987093f88d916919cf97713a8faa6cf5b3abdf1d', 'page_count': 15, 'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [], 'role_page_allowlist': [1, 3, 13], 'excluded_native_text_pages': [2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15], 'native_editorial_caution': 'Pages2/4-12/14/15 are not role-qualified. Page14 column association and zero-base100% are unreconciled; solarKW is capacity, not energy, and planned completion is not actual completion. Full originals retained.', 'index_reuse_caution': 'October13 event links a September cover-month original; October12 in the file name is not verified first publication. Event occurrence is not independently verified.', 'forward_looking_caution': 'Page13 is management Q3 outlook as of the September document. Demand, utilization, copper prices and conflict statements are issuer claims, not independently verified current news or audited Q3 results.', 'period_scope_caution': 'Page3 market cap is an approximate September2026 issuer claim, not a current quote. Revenue2599億元 is2025 and excludes NanyaTechnology;99plants and28616employees include consolidated companies. Product ratios sum98%, preserve them without normalization.', 'unit_scope_caution': 'Keep TWD億元, headcount, plants and percentages distinct. Mixed scope and approximate market cap must retain qualifiers; no unqualified chart or table inference.', 'visual_semantics_caution': 'Only pages1/3/13 whole text role-qualified; all15 pages preserved. Other charts/table associations not asserted verified.', 'financial_scope_caution': 'Management presentation is not a five-year audited statement source. Do not overwrite annual,TTM,FCF or existing financial facts.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_npc_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete'or native['empty_pages']or native['garbled_pages']
            or native['page_count']!=PAGE_COUNT or len(native['pages'])!=PAGE_COUNT
            or [p['page_number']for p in native['pages']]!=list(range(1,PAGE_COUNT+1))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected!=QUALIFIED_SELECTED
            or sha256(json.dumps(native.get('symbol_mapping_evidence'),sort_keys=True,allow_nan=False).encode()).hexdigest()!=SYMBOL_EVIDENCE_SHA256):
        raise ValueError('complete original projection invalid')
    return native

def _context(selected,native,proof):
    doc=deepcopy(DOCUMENT_METADATA)
    doc.update(title=selected['title'],retrieved_at_epoch=proof['pdf']['retrieved_at'],pages=deepcopy(native['pages']),
               parser_version=native['parser_version'],symbol_mapping_evidence=deepcopy(native['symbol_mapping_evidence']))
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026H1','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'npc_conference_receipt':proof}

def role_pages(document):
    if not isinstance(document,dict):return []
    try:
        native={k:document[k]for k in ('pages','parser_version','symbol_mapping_evidence')}
        expected=_context(QUALIFIED_SELECTED,native,{'pdf':{'retrieved_at':document['retrieved_at_epoch']}})['documents'][0]
        if json.dumps(document,sort_keys=True,allow_nan=False)!=json.dumps(expected,sort_keys=True,allow_nan=False):return []
        if sha256(json.dumps(native['symbol_mapping_evidence'],sort_keys=True,allow_nan=False).encode()).hexdigest()!=SYMBOL_EVIDENCE_SHA256:return []
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
        if not supports_npc(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['npc_conference_receipt']
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


def fetch_npc_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_npc(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'npc_presentation_workflow':True}
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
        details.update(npc_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(npc_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','1303'),('official_name','南亞'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'npc', 'nan ya plastic', 'nan ya plastics corporation', '南亞塑膠工業股份有限公司', '南亞'}
    aliases = names | {'1303','1303.tw'}
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
    return isinstance(value,dict) and ('npc_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
