"""CHB issuer QA with complete cross-page answers and immutable originals."""
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
from .chb_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, replay_expiry_valid

TICKER = '2801.TW'
LEGAL = '彰化商業銀行股份有限公司'
UBN = '51811609'
POLICY = 'chb-original-qa-v1'
PROJECTION_POLICY = 'chb-qa-role-v1'
KNOWN_SHA = '627f86419bc4de265260e65263c5e11e39aacb698605b6705d929b61f17003f9'
PAGE_TEXT_SHA256 = ('3914d654b6e357e3fccc00d1e810b039f641c2b7a5b35c823dcf8c2f765c682f', '1a021c174dc2ef217a81448b844d021555666a151fa59623545c7cf648000c95', 'a90f355d598be7a66a5b6e97edd8d3af485c80c18588e7658b596824039f720d', '78bd5115c91a8ed7ea42846b64a237b309d53c6c116a4d64e7ea9b75b81627b4', '94be04aef7ed84539ad4d04192f22eb9b5ae8f9fae8772933e8d917e08053129', 'f44968b2e7bab53f2129557b3762cd4693bfd27de9f8979e2a98f8d735e1f240', '77740e80a4e738497082e129597a071a4d517fd4369e638fdb6d13fa1ebc7ae8')
ROLE_PAGES = (1,2,3,4,5,6,7)
NOTE = ('彰銀2026年第2季法說的官方投資人提問重點彙整，7頁原生文字完整、12題及跨頁回答保持。'
 '整體覆蓋仍partial：不是影音逐字稿、全部問答或完整財報，沒有驗證全部圖像。'
 '原文是2026/8/25場次的公司說法；H1實績、H2展望、海外據點籌設、整併評估及人才計畫須分開，不代表現在已完成。')


def supports_chb(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'2801', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def extract_chb_presentation_pages(raw, *, timeout_seconds):
    from source_pdf_reader import extract_pdf_pages
    return extract_pdf_pages(raw, timeout_seconds=timeout_seconds)


def parse_master(raw, epoch, source_url=MASTER_URL, *, as_of_epoch=None):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('CHB master size invalid')
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
        raise ValueError('CHB complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '2801']
    if len(matched) != 1:
        raise ValueError('CHB master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '彰銀', '營利事業統一編號': UBN, '網址': 'www.bankchb.com'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'CHANG HWA BANK'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('CHB master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today(as_of_epoch) - day).days <= 14 or day > _today(epoch):
        raise ValueError('CHB master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '彰銀', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}



def select_presentation(raw, epoch, *, as_of_epoch=None):
    from urllib.parse import quote, urljoin
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('CHB index size invalid')
    text=raw.decode('utf-8-sig','strict');body,closing,trailer=text.rpartition('</html>')
    if not closing or '</html>'in body or trailer.strip():raise ValueError('CHB index incomplete')
    soup=BeautifulSoup(body+closing,'html.parser')
    if not soup.title or soup.title.get_text(' ',strip=True)!='彰化銀行-法人說明會':raise ValueError('CHB publisher changed')
    if '© 彰化銀行' not in soup.get_text(' ',strip=True):raise ValueError('CHB owner absent')
    tables=soup.select('table[summary="法人說明會"]')
    if len(tables)!=1 or tables[0].parent.get('class')!=['chb-comp-23']:raise ValueError('CHB index ambiguous')
    table=tables[0]
    if [t.get_text(' ',strip=True)for t in table.select('th')]!=['','日期','地點','簡報資料']:raise ValueError('CHB headers changed')
    rows=table.select('tbody > tr')
    if len(rows)!=35:raise ValueError('CHB visible history changed')
    parsed=[]
    for row in rows:
        cols=row.find_all('td',recursive=False)
        if len(cols)!=4:raise ValueError('CHB row shape changed')
        date_text=cols[1].get_text(' ',strip=True)
        if not re.fullmatch(r'20\d{2}/\d{2}/\d{2}',date_text):raise ValueError('CHB date invalid')
        day=datetime.strptime(date_text,'%Y/%m/%d').date()
        parsed.append((day,row,cols))
    dates=[v[0]for v in parsed]
    if len(set(dates))!=35 or dates!=sorted(dates,reverse=True):raise ValueError('CHB event order ambiguous')
    day,row,cols=parsed[0]
    if (row.get('data-id')!='40' or day!=date(2026,8,25)
            or cols[0].get_text(' ',strip=True)!='2026年第2季法人說明會'
            or cols[2].get_text(' ',strip=True)!='線上法人說明會'
            or not day<=_today(epoch)<=_today(as_of_epoch) or (_today(as_of_epoch)-day).days>370):raise ValueError('CHB newest event unqualified')
    links=cols[3].select('a[href]')
    if [a.get_text(' ',strip=True)for a in links]!=['中文版簡報','法說會錄影檔','投資人提問重點彙整']:raise ValueError('CHB materials changed')
    urls=[quote(urljoin(INDEX_URL,a['href']),safe=':/?=&%()_-.')for a in links]
    if (any(a.has_attr('onclick')for a in links) or urls!=[
            'https://www.bankchb.com/chb_2a_resource/leap_do/gallery/1787203413541/2026Q2_InvestorConference_Chinese.pdf',
            'https://www.zucast.com/event/Y57Z7X3S/subscribe/create?openExternalBrowser=1',PDF_URL]):raise ValueError('CHB attachment identity changed')
    return {'title':'彰銀2026年第2季法人說明會投資人提問重點彙整','period_label':'2026Q2','pdf_url':PDF_URL,
        'event_date':'2026-08-25','event_time':None,'event_timezone':'Asia/Taipei','index_record_count':35,
        'selection_policy':'newest_dated_row_and_exact_published_QA_original',
        'history_scope':'35 rows visible on issuer table; not asserted complete off-site history','event_url':INDEX_URL}



def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('CHB QA revision unqualified')
    try:native=extract_chb_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
        raise
    _check(deadline)
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=7 or len(native['pages'])!=7
            or [p['page_number']for p in native['pages']]!=list(ROLE_PAGES)
            or tuple(sha256(p['text'].encode()).hexdigest()for p in native['pages'])!=PAGE_TEXT_SHA256
            or native['content_sha256']!=KNOWN_SHA or selected['period_label']!='2026Q2'
            or selected['event_date']!='2026-08-25'):raise ValueError('CHB native QA unverified')
    return native


def _context(selected,native,proof):
    doc={'document_id':'2801:2026-08-25:'+KNOWN_SHA[:16],'ticker':TICKER,'source':PROVIDER,
        'source_type':'issuer_official','document_kind':'issuer_qa_summary','projection_policy':PROJECTION_POLICY,
        'title':selected['title'],'url':PDF_URL,'language':'zh-TW','event_date':selected['event_date'],
        'event_date_basis':'issuer_table_exact_QA_and_document_period','event_status':'published_past_material_not_independently_occurrence_verified',
        'event_time':None,'event_timezone':'Asia/Taipei','published_at':None,'material_file_date':None,
        'content_period':'2026Q2','content_periods':['2026H1 results','2026H2 outlook and later plans'],
        'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':KNOWN_SHA,'page_count':7,'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':[],'garbled_pages':[],'parser_version':native['parser_version'],'role_page_allowlist':list(ROLE_PAGES),
        'question_count':12,'cross_page_questions':{'2':[1,2],'4':[2,3],'6':[3,4],'12':[6,7]},
        'qa_scope_caution':'Issuer-edited question-and-answer compilation; not a recording transcript, all audience questions or independent verification.',
        'forward_looking_caution':'All statements are issuer claims as of the2026-08-25 event. Overseas permits, planned openings, hiring targets and M&A assessments are not completed operations or transactions.',
        'period_scope_caution':'Q2 conference includes H1 results, July/August developments and H2 forecasts. No current verification or publication date inferred from the URL timestamp.',
        'financial_scope_caution':'Bank business figures and consolidated profit differ in scope. Preserve NIM/Spread and percentage/percentage-point distinctions; do not override audited annual statements or TTM.',
        'visual_semantics_caution':'Complete native text; only pages1/6 visually sampled. Fontconfig warning retained; full visual verification is not claimed.',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'Always native issuer index/QA acquisition; immutable private audit originals, no success-cache reuse'}
    return {'ticker':TICKER,'date':selected['event_date'],'time':None,'period':'2026Q2','title':selected['title'],
        'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
        'materials':[{'url':PDF_URL,'kind':'issuer_qa_summary','language':'zh-TW'}],'documents':[doc],
        'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
        'fetched_at_epoch':proof['pdf']['retrieved_at'],'chb_qa_receipt':proof}


def role_pages(document):
    # All seven pages fit the existing6000-character/1000-per-page budget.
    # Preserve complete questions and their cross-page answers in original order.
    expected={'source':PROVIDER,'ticker':TICKER,'projection_policy':PROJECTION_POLICY,'content_sha256':KNOWN_SHA,
        'document_kind':'issuer_qa_summary','event_date':'2026-08-25','content_period':'2026Q2','page_count':7,
        'native_text_coverage':'complete','text_extraction_complete':True,'binary_complete':True,
        'q_and_a_transcript_available':False,'financial_statement_complete':False,'full_visual_content_verified':False,
        'question_count':12,'role_page_allowlist':list(ROLE_PAGES),'cross_page_questions':{'2':[1,2],'4':[2,3],'6':[3,4],'12':[6,7]}}
    if any(document.get(k)!=v or type(document.get(k))is not type(v)for k,v in expected.items()):return []
    pages=document.get('pages')
    if not isinstance(pages,list)or len(pages)!=7:return []
    for n,p in enumerate(pages,1):
        if (not isinstance(p,dict)or type(p.get('page_number'))is not int or p['page_number']!=n
                or not isinstance(p.get('text'),str)or len(p['text'])>1000
                or sha256(p['text'].encode()).hexdigest()!=PAGE_TEXT_SHA256[n-1]):return []
    if sum(len(p['text'])for p in pages)>6000:return []
    return deepcopy(pages)


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and replay_expiry_valid(proof[k],max_age,observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_chb(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['chb_qa_receipt']
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


def fetch_chb_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_chb(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'chb_qa_workflow':True}
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
        details.update(chb_originals_verified=True,coverage_status='native_qa_text_complete',
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
        details.update(chb_originals_verified=False,error_kind=exc.error_kind,status='error',
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
    for key,expected in [('ticker',TICKER),('stock_id','2801'),('official_name','彰銀'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'彰銀','彰化銀行',LEGAL.casefold(),'chang hwa bank','chang hwa commercial bank, ltd.','chang hwa commercial bank ltd'}
    aliases = names | {'2801','2801.tw'}
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
    return isinstance(value,dict) and ('chb_qa_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL
            or d.get('projection_policy') == PROJECTION_POLICY)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
