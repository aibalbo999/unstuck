"""NanyaPCB official presentation with distinct event and document dates."""
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
from .nanyapcb_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '8046.TW'
LEGAL = '南亞電路板股份有限公司'
UBN = '16096804'
POLICY = 'nanyapcb-original-presentation-v1'
PROJECTION_POLICY = 'nanyapcb-presentation-role-v1'
KNOWN_SHA = '41e3540db0a50da875542163b6f9495b5d5c3cb6e5c5927f4fa5f8a36add03f8'
PAGE_TEXT_SHA256 = ('4437951c1a228d60cc84a1bbe7aeac83b2c66b1be631758b5214408eb989308f', '41b48c554fa3cd2c9e373a227cfac5e534f865e3619ac442e945bcfb8f05800b', 'ef88e20a0e5db338fca2f820090f0df56d5fa7e27183c0f1a26defac59c5adb0', '5d92f4c0bf81cc8c7edfcbca91cbf90212c3e3fb0d00461904db8a1316d4959d', '595cc224c58e7490f11345dc4e5101e19520d4f4359b0ff8ff15522f29ff4649', '3283012e6c734228c6484df005ed9d06252bac0a90352e016a0d65cd9f8f65d8', '4158c086b08d54ae89a21147eef66ae859855c5512567ffd03ce1618c7152d22', 'be133f4ff296ab863d5da27e96f8e388f32bda45121d9b8b47e92dcdd87a02d2', 'a355ea1ebbfc7769c9056271fb872ae9c18e4a07502c239ac5315c1e01710cf1', '72244c568faafcac17a830db6310869fa16b92b10a1b5e336943777bcb0012eb', '0e35699b67f31e55c9297b7450d1de354b63a28a1623626adba9c36584a7b0dc', '966dfa4d0098ecf1f546a1f2e89e2f0cebd12bfd02152b5eb8a9266925b58976', '7af94f5d7212cab2918f41b7aed395622b092366daeb57d39a6783bf61786c32', 'c8fe4929912a6b732615735bc058c094ac1b8128c8a656ff68ccb38658ad6c8c')
ROLE_PAGES = (1, 2, 4, 12, 13)
NOTE = '南電官方14頁完整簡報，活動與封面均8/27，檔名20260506不作日期。原生文字complete但整體partial，角色限1/2/4/12/13完整頁；保留免責聲明、H1合併營收及6/30歷史市值。未核金融圖表不進角色，產品與轉型為計畫，非完工、逐字稿或五年查核財報。'

def supports_nanyapcb(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'8046', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_nanyapcb_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('NanyaPCB master size invalid')
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
        raise ValueError('NanyaPCB complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '8046']
    if len(matched) != 1:
        raise ValueError('NanyaPCB master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': '南亞電路板股份有限公司', '公司簡稱': '南電', '營利事業統一編號': '16096804', '網址': 'https://www.nanyapcb.com.tw/nypcb/Chinese/index'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'N.P.C'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('NanyaPCB master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('NanyaPCB master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '南電', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}




QUALIFIED_SELECTED = {'title': '南電2026年第二季營運概況（8/27台新金證券投資論壇）', 'pdf_url': 'https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260506.pdf', 'event_date': '2026-08-27', 'document_date': '2026-08-27', 'cover_month': '2026-08', 'period_label': '2026H1', 'index_record_count': 3, 'selection_policy': 'latest_exact_published_event_in_complete_current_year_table', 'history_scope': '3 visible2026 rows; earlier history retained but not qualified complete; new publication requires qualification'}
CURRENT_ROWS = [{'cells': ['台新金證券2026年第三季投資論壇', '台北晶華酒店', '2026/08/27', '下載', ''], 'links': ['https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260506.pdf']}, {'cells': ['永豐金證券2026年第二季投資論壇', '台北寒舍艾美酒店', '2026/06/12', '下載', '影片連結'], 'links': ['https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260612.pdf', 'https://www.youtube.com/watch?v=kzWc1gGeZTI']}, {'cells': ['群益證券2026 第一季投資論壇', '台北茹曦酒店', '2026/03/17', '下載', '影片連結'], 'links': ['https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260316.pdf', 'https://www.youtube.com/watch?v=kaxvrmlz-e0']}]
SYMBOL_EVIDENCE_SHA256 = '52c8659f3c418e354080f175c224cbd3e9e5fe930515359b267a2e73ff44383f'
HEAD_TITLE = '財務資訊'
OWNER = 'Copyright © Nan Ya PCB Co., Ltd. All right reserved.'
HEADERS = ['參與法說會訊息', '地點', '日期', '簡報下載', '影片']
ROW_COUNT = 36
DATE_COLUMN = 2

def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import urljoin
    if not isinstance(raw,bytes)or not 0<len(raw)<=1_048_576:raise ValueError('index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if (not closing or trailer.strip()or text.count('<html>')!=3 or text.count('</html>')!=3
            or text.count('<body>')!=3 or text.count('</body>')!=3):raise ValueError('complete index required')
    soup=BeautifulSoup(text,'html.parser')
    # Native ASP.NET page embeds a complete header and footer document. They
    # are publisher includes, not extra events; require their exact containers.
    roots=soup.find_all('html')
    if (len(roots)!=3 or roots[0].parent.name!='[document]'
            or [(h.parent.name,h.parent.get('id'))for h in roots[1:]]!=[('div','includedContent'),('div','includedFooter')]
            or len(soup.select('form#form1[action="./FinancialReports"]'))!=1):raise ValueError('index include structure changed')
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

PAGE_COUNT = 14
DOCUMENT_METADATA = {'document_id': '8046:2026-08-27:41e3540db0a50da8', 'ticker': '8046.TW', 'source': 'NanyaPCB official conference presentation', 'source_type': 'issuer_official', 'document_kind': 'presentation', 'projection_policy': 'nanyapcb-presentation-role-v1', 'url': 'https://www.nanyapcb.com.tw/nypcb/images/InvestorRelations/FinancialReport/NYPCBCH20260506.pdf', 'language': 'zh-TW', 'event_date': '2026-08-27', 'event_date_basis': 'exact_published_issuer_index_row; PDF cover recorded separately', 'event_status': 'published_past_material_not_independently_occurrence_verified', 'event_time': None, 'event_timezone': 'Asia/Taipei', 'published_at': None, 'material_file_date': '2026-08-27', 'presentation_cover_month': '2026-08', 'content_period': '2026H1', 'content_periods': ['2026H1 financials', 'historical company facts with original period qualifiers', 'issuer forward-looking plans at document time'], 'content_sha256': '41e3540db0a50da875542163b6f9495b5d5c3cb6e5c5927f4fa5f8a36add03f8', 'page_count': 14, 'binary_complete': True, 'text_extraction_complete': True, 'native_text_coverage': 'complete', 'coverage_status': 'partial', 'full_content_coverage_verified': False, 'full_visual_content_verified': False, 'financial_statement_complete': False, 'missing_text_pages': [], 'garbled_pages': [], 'role_page_allowlist': [1, 2, 4, 12, 13], 'excluded_native_text_pages': [3, 5, 6, 7, 8, 9, 10, 11, 14], 'native_editorial_caution': 'Pages3/5-11/14 are not role-qualified. Full originals retained; unqualified financial chart associations excluded.', 'index_reuse_caution': 'Published August27 index row and PDF cover agree. File name NYPCBCH20260506 is not document date or verified first publication; event occurrence not independently verified.', 'forward_looking_caution': 'Pages12/13 high-value product development, future mass production and four transformations are management plans, not completed investment or guaranteed results. Preserve page2 historical/unaudited and forward-looking disclaimer.', 'period_scope_caution': 'Page4 revenue247.5億元 is2026H1 consolidated; market cap7657.1億元 is historical2026-06-30, not a current quote. Cover/eventAugust27 and financialH1/Q2 are distinct.', 'unit_scope_caution': 'Keep TWD億元 and period qualifiers. Unqualified chart numbers, growth percentages and ratios are excluded from roles; no conversion into audited annual/TTM/FCF facts.', 'visual_semantics_caution': 'Only pages1/2/4/12/13 whole text role-qualified; all14 pages preserved. Other charts and table associations not asserted verified.', 'financial_scope_caution': 'Management presentation is not a five-year audited statement source. Do not overwrite annual,TTM,FCF or existing financial facts.', 'q_and_a_transcript_available': False, 'commercial_reuse_permission_verified': False, 'response_reuse_policy': 'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse'}

def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('original revision is not qualified')
    try:native=extract_nanyapcb_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
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
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'nanyapcb_conference_receipt':proof}

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
        if not supports_nanyapcb(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['nanyapcb_conference_receipt']
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


def fetch_nanyapcb_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_nanyapcb(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'nanyapcb_presentation_workflow':True}
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
        details.update(nanyapcb_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(nanyapcb_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','8046'),('official_name','南電'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'南電', '南亞電路板股份有限公司', 'nan ya printed circuit board co', 'n.p.c', 'nan ya printed circuit board corporation'}
    aliases = names | {'8046','8046.tw'}
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
    return isinstance(value,dict) and ('nanyapcb_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
