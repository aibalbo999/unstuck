"""Chroma official presentation with distinct event and document dates."""
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
from .chroma_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2360.TW'
LEGAL = '致茂電子股份有限公司'
UBN = '09461025'
POLICY = 'chroma-original-presentation-v1'
PROJECTION_POLICY = 'chroma-presentation-role-v1'
KNOWN_SHA = 'ef87118ee759f32c241d6a7549b0da7a7cb2f98f92e2e2ddd52712cba3639c23'
PAGE_TEXT_SHA256 = ('0f0e62c6b0422be20b80709be1eedb761994c888d11bf9346410b35bbe8e5de3', '29150dfcf46bdeba1380361f750a21d03f37b683fa7bdd20f5a275e4c34b0aaf', '4c2e652a14d73658eb492b256666f49fd9ccce7c8721052f88c1d9e9b5af1e57', '62e99a743c877df0198e0adc9673d9d673d9ed5bc12123018d5ec5d30aad897a', 'ba32210c278f23a007a2c7344b79e8de4d584f5e78a67ece305f4f6f86a494b5', '9414c9a0117497041aff4b3b5ded9399bd32ece229058cd65309db3493ff68c9', 'c6e90539bf359730849c1aa601a98fd93bf5fa7a79c1f37d92079613a7cdb12d', '57e0de11a03e273d0520f057e6f4aacb97bdaa870b99b0bcc1ba8f758b4f107e', 'b96e5ccb8f6e8c260068cc33f714f6b84e73d3ada5814e38dca8b632e241557c', 'cb5f355f91dc49df4c3b528ff04f136366edb503ec89407bcd6e9c4881283843', '9e10625c664b6dc5ee8978fd11ba9c9fa061555408b3078191a236d5d44d4163', 'd36d3f5706735a191af73c8d31aa5708276f094845f6bb23dba676e358cb7f05', '42e84d4c9530080512181b1c7fcc7a2595351fd6342d1f1f6488d5862321df02', '85adb236a08588f781a31a205390c2adca9496795c36eabec07cb1c2b898fb68', '0346404c38d6ca25f2bc5579634aa069bf15ac75ad3bc2cc381f86350d4df4fb', '187c84da2346529c7dbd0a2986b63962ec005bed8bab12c337c9db3167cb4e30', 'f492930e2faff1500f926a6b903fe5571f0eddb2dd2c2d0358dfa26550719676', 'd8c7f742d5969c9f7956dc2ea72fc5a19b02249d247cf3bf6128eb6ea3e4e2aa')
ROLE_PAGES = (1,5,6,7,10)
NOTE = '致茂官方18頁Q2簡報完整，9/15論壇沿用7/30原件；活動日、文件日與H1/Q2內容期分開，首次發布日未知。原生文字complete但整體partial，不是逐字稿或完整查核財報。角色僅使用1/5/6/7/10完整原文頁。p9H1比例與p6不一致，整頁排除，不改原數；產品圖表與未核關聯頁亦不送角色。p7ROE/ROA已年化，自由現金流是營業加全部投資現金流，不等於營業減資本支出。財務單位百萬新台幣，EPS為元；母公司、部門與合併口徑不可混用。H2展望是7/30公司主張，不是今日已實現事實。'

def supports_chroma(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2360', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_chroma_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Chroma master size invalid')
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
        raise ValueError('Chroma complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2360']
    if len(matched) != 1:
        raise ValueError('Chroma master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '致茂', '營利事業統一編號': UBN, '網址': 'http://www.chromaate.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'CHROMA'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Chroma master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('Chroma master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '致茂', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}



INDEX_ROW_TEXTS = ('2026 第二季 2026.09.15 第一金證券論壇', '2026 第二季 2026.07.30 法人說明會', '2026 第一季 2026.04.30 法人說明會 (English Only)', '2025 第四季 2025.03.06 KGI 投資論壇', '2025 第四季 2026.02.25 法人說明會', '2025 第三季 2025.10.30 法人說明會 (Audio: English Only)', '2025 第二季 2025.07.31 法人說明會', '2025 第一季 2025.04.30 法人說明會 (Audio: English Only)')

def select_presentation(raw, epoch, *, as_of_epoch=None):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('Chroma index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>' in body or trailer.strip():raise ValueError('Chroma complete index required')
    soup=BeautifulSoup(text,'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='每季營運報告 | 致茂電子 Chroma ATE Inc. | Traditional Chinese':raise ValueError('Chroma publisher changed')
    canon=soup.select('link[rel="canonical"]')
    if len(canon)!=1 or canon[0].get('href')!=INDEX_URL or '© 致茂電子股份有限公司'not in soup.get_text(' ',strip=True):raise ValueError('Chroma canonical/owner changed')
    rows=soup.select('section.page-content > .operation_item')
    if len(rows)!=8 or tuple(r.get_text(' ',strip=True)for r in rows)!=INDEX_ROW_TEXTS:raise ValueError('Chroma current/visible history changed')
    for row in rows:
        cells=[c for c in row.find_all(recursive=False)if c.name]
        if len(cells)!=5 or any(c.name!='div'for c in cells):raise ValueError('Chroma row malformed')
    for row in rows[:2]:
        links=row.select('.file_right a')
        if len(links)!=1 or links[0].get('href')!=PDF_URL or links[0].has_attr('onclick'):raise ValueError('Chroma published current PDF changed')
    audio=rows[0].select('.va a')
    if len(audio)!=1 or audio[0].get('href')!='https://www.chromaate.com/downloads/investors/mp3/2026/Chroma_20260915_firstsec_tc.mp3':raise ValueError('Chroma event association changed')
    day=date(2026,9,15)
    if not day<=_today(epoch)<=_today(as_of_epoch) or not 0<=(_today(as_of_epoch)-day).days<=370:raise ValueError('Chroma event date invalid')
    return {'title':'致茂2026年第2季業績說明會簡報（9/15論壇沿用）','pdf_url':PDF_URL,'event_date':'2026-09-15',
        'document_date':'2026-07-30','period_label':'2026Q2','index_record_count':8,
        'selection_policy':'latest_exact_visible_issuer_event_with_explicit_prior_document_date',
        'history_scope':'eight visible rows; historical2025Q4/2025.03.06 inconsistency retained, not repaired'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('Chroma original revision is not qualified')
    try:native=extract_chroma_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=18 or len(native['pages'])!=18
            or [p['page_number']for p in native['pages']]!=list(range(1,19))
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected['period_label']!='2026Q2'
            or selected['event_date']!='2026-09-15' or selected['document_date']!='2026-07-30'):
        raise ValueError('Chroma complete original projection invalid')
    return native


def _context(selected,native,proof):
    doc={'document_id':'2360:2026-09-15:'+KNOWN_SHA[:16],'ticker':TICKER,'source':PROVIDER,
        'source_type':'issuer_official','document_kind':'presentation','projection_policy':PROJECTION_POLICY,
        'title':selected['title'],'url':PDF_URL,'language':'zh-TW','event_date':selected['event_date'],
        'event_date_basis':'exact_issuer_September_event_links_July_original_with_cover_date',
        'event_status':'published_past_material_not_independently_occurrence_verified',
        'event_time':None,'event_timezone':'Asia/Taipei','published_at':None,'material_file_date':selected['document_date'],
        'content_period':'2026Q2','content_periods':['2026Q2 and Q1/Q2 comparisons','2026H1','2026H2 outlook as of July30'],
        'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':KNOWN_SHA,'page_count':18,'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':[],'garbled_pages':[],'parser_version':native['parser_version'],'role_page_allowlist':list(ROLE_PAGES),
        'excluded_native_text_pages':[n for n in range(1,19)if n not in ROLE_PAGES],
        'native_editorial_caution':'Page9 H1 business percentages conflict with page6; exclude page9 from roles without changing either original.',
        'index_reuse_caution':'September15 event links July30 presentation. Neither event occurrence nor audio/transcript is independently verified. Historical index date mismatch retained.',
        'forward_looking_caution':'All outlook statements are issuer claims as of July30,2026, not current verification or completed H2 results. No independent update or guarantee.',
        'period_scope_caution':'Separate September15 event, July30 cover, Q2 and H1 comparisons. First publication date unknown; do not infer from URL or footer.',
        'financial_scope_caution':'Management presentation, not audited statements or five-year history. Parent, business-unit and consolidated scopes differ; no TTM or annual overrides.',
        'unit_scope_caution':'Amounts in TWD millions except EPS in TWD. ROE/ROA on page7 annualized. FCF defined as operating plus all investing cash flow, not operating minus capital purchases. Dashes are not zero.',
        'visual_semantics_caution':'Only pages1/5/6/7/10 selected for roles after visual check; all18 original pages preserved. Other diagrams and associations not fully verified.',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'Always native issuer index/PDF acquisition; immutable private originals, no success-cache reuse'}
    return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,
        'summary':'','transcript_excerpt':'','transcript_available':False,'materials':[{'url':PDF_URL,'kind':'presentation','language':'zh-TW'}],
        'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'chroma_conference_receipt':proof}


def role_pages(document):
    expected={'source':PROVIDER,'ticker':TICKER,'projection_policy':PROJECTION_POLICY,'content_sha256':KNOWN_SHA,
        'document_kind':'presentation','event_date':'2026-09-15','material_file_date':'2026-07-30','content_period':'2026Q2','page_count':18,
        'native_text_coverage':'complete','text_extraction_complete':True,'binary_complete':True,'coverage_status':'partial',
        'q_and_a_transcript_available':False,'financial_statement_complete':False,'full_visual_content_verified':False,
        'role_page_allowlist':list(ROLE_PAGES),'excluded_native_text_pages':[n for n in range(1,19)if n not in ROLE_PAGES]}
    if any(document.get(k)!=v or type(document.get(k))is not type(v)for k,v in expected.items()):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=18:return []
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
        if not supports_chroma(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['chroma_conference_receipt']
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


def fetch_chroma_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_chroma(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'chroma_presentation_workflow':True}
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
        details.update(chroma_originals_verified=True,coverage_status='native_text_complete',
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
        details.update(chroma_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2360'),('official_name','致茂'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'致茂',LEGAL.casefold(),'chroma','chroma ate inc.','chroma ate inc'}
    aliases = names | {'2360','2360.tw'}
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
    return isinstance(value,dict) and ('chroma_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
