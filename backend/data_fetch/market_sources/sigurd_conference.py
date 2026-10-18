"""Published Sigurd presentation with explicit native visual and financial scope limits."""
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
from sigurd_presentation_pdf_reader import extract_sigurd_presentation_pages
from .sigurd_conference_transport import ConferenceHttp, MASTER_URL, INDEX_URL, PDF_URL, PROVIDER, RAW_TTL, original_bytes, valid_expiry

TICKER = '6257.TW'
LEGAL = '矽格股份有限公司'
UBN = '23218022'
POLICY = 'sigurd-original-presentation-v1'
PROJECTION_POLICY = 'sigurd-presentation-role-v1'
KNOWN_SHA = '2e90848f7ad58715bf828870749eed8bf9f14ebcf47a9914e022324f56812aee'
CONTENT_PERIODS = ['2026Q2','2026H1','2026Jan-Aug','2026Jan-Sep']
NOTE = ('矽格官方英文法說簡報，並非逐字稿；第23頁僅Q&A／Thank You，不含實際問答或影音核對。'
        '23頁原生文字取得不等於圖表語意完整；第12頁月營收柱高、第14–15頁圓餅圖關聯及第16–22頁圖片、流程與布局未完整核對。'
        '內容含2026Q2、上半年、1–8月及1–9月不同口徑，不因10月6日場次推定Q4財報。'
        '合併財務數、歸屬母公司淨利與Sigurd UTC子公司資本支出須分開，不能將簡報數字覆寫正式年度財報或TTM。'
        '第2頁聲明展望基於當時資訊、存在風險與不確定性，實際可能有重大差異且無更新義務；4Q26完工與1Q27量產仍為展望。'
        '檔案首次發布日、實際會議舉行及公司營運陳述未獨立驗證；不由檔名或HTTP取得時間推定發布時間。')


def supports_sigurd(ticker):
    return isinstance(ticker, str) and ticker.strip().upper() in {'6257', TICKER}


def _today(epoch=None):
    return datetime.fromtimestamp(time.time() if epoch is None else epoch, ZoneInfo('Asia/Taipei')).date()


def _check(deadline):
    if time.monotonic() >= deadline:
        raise SourceResponseError('timeout')


def parse_master(raw, epoch):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_500_000:
        raise ValueError('Sigurd master size invalid')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', 'strict')), strict=True)
    rows = list(reader); fields = reader.fieldnames
    if (not fields or len(fields) != len(set(fields)) or not 500 <= len(rows) <= 2000
            or any(None in r or any(v is None for v in r.values()) for r in rows)):
        raise ValueError('Sigurd complete master shape invalid')
    matched = [r for r in rows if r.get('公司代號') == '6257']
    if len(matched) != 1:
        raise ValueError('Sigurd master issuer not unique')
    row = matched[0]
    expected = {'公司名稱': LEGAL, '公司簡稱': '矽格', '營利事業統一編號': UBN, '網址': 'www.sigurd.com.tw'}
    # The native CSV publishes literal escaped ideographic padding here.
    english = row.get('英文簡稱', '').replace('\\u3000', '\u3000').strip()
    if (any(row.get(k) != v for k, v in expected.items()) or english != 'SIGURD'
            or not re.fullmatch(r'\d{7}', row.get('出表日期', ''))):
        raise ValueError('Sigurd master identity invalid')
    s = row['出表日期']; day = date(int(s[:3]) + 1911, int(s[3:5]), int(s[5:]))
    if not 0 <= (_today() - day).days <= 14 or day > _today(epoch):
        raise ValueError('Sigurd master date invalid')
    return {'ticker': TICKER, 'legal_name': LEGAL, 'official_name': '矽格', 'official_ubn': UBN,
            'registered_website': expected['網址'], 'as_of': day.isoformat(), 'complete_master_sha256': sha256(raw).hexdigest()}


def _one(root, selector):
    values = root.select(selector)
    if len(values) != 1:
        raise ValueError('Sigurd index section ambiguous')
    return values[0]


def select_presentation(raw, epoch):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('Sigurd index size invalid')
    soup=BeautifulSoup(raw.decode('utf-8','strict'),'html.parser')
    if not soup.title or soup.title.get_text(strip=True)!='公開資訊觀測站':raise ValueError('MOPS index title invalid')
    form=_one(soup,'form#fm_fileDownload')
    if form.get('method','').lower()!='post' or form.get('action')!='/server-java/FileDownLoad':raise ValueError('MOPS download form invalid')
    for name,value in [('step','9'),('filePath','/home/html/nas/STR/'),('fileName',''),('functionName','t100sb02_1')]:
        if _one(form,'input[name="'+name+'"]').get('value')!=value:raise ValueError('MOPS download route invalid')
    table=_one(soup,'#myTable');rows=table.find_all('tr',recursive=False)
    if not 1<=len(rows)<=100:raise ValueError('MOPS event rows invalid')
    eligible=[];seen=set()
    for row in rows:
        cells=row.find_all('td',recursive=False)
        if len(cells)!=12 or cells[0].get_text(strip=True)!='6257' or cells[1].get_text(strip=True)!='矽格':
            raise ValueError('MOPS event identity or shape invalid')
        text=cells[2].get_text(strip=True)
        if not re.fullmatch(r'115/\d{2}/\d{2}',text):raise ValueError('MOPS event date invalid')
        _,month,day=text.split('/');day=date(2026,int(month),int(day));clock=cells[3].get_text(strip=True)
        if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('MOPS event clock invalid')
        stamp=datetime.combine(day,datetime.strptime(clock,'%H:%M').time(),ZoneInfo('Asia/Taipei')).timestamp()
        if stamp in seen:raise ValueError('MOPS event identity ambiguous')
        seen.add(stamp)
        website=cells[8].find_all('a')
        if len(website)!=1 or website[0].get('href')!='https://www.sigurd.com.tw':raise ValueError('MOPS issuer website invalid')
        if stamp<=epoch and 0<=(_today()-day).days<=370:
            eligible.append((stamp,day,clock,cells))
    if not eligible:raise ValueError('Sigurd current event absent')
    _,day,clock,cells=max(eligible,key=lambda v:v[0])
    # Choose latest metadata first; missing or changed attachments cannot select an old event.
    if day.isoformat()!='2026-10-06' or clock!='14:30':raise ValueError('Sigurd latest event not qualified')
    for position,filename in [(6,'625720261006M001.pdf'),(7,'625720261006E001.pdf')]:
        links=cells[position].find_all('a')
        expected='document.fm_fileDownload.fileName.value="'+filename+'";document.fm_fileDownload.submit();'
        if len(links)!=1 or links[0].get('href')!='#' or links[0].get('onclick')!=expected or links[0].get_text(strip=True)!=filename:
            raise ValueError('Sigurd exact published attachment invalid')
    location=cells[4].get_text(' ',strip=True);summary=cells[5].get_text(' ',strip=True)
    if not location or not summary:raise ValueError('Sigurd event metadata empty')
    return {'event_date':day.isoformat(),'event_time':clock,'event_timezone':'Asia/Taipei','event_location':location,
            'period':'2026Q2 / 2026Jan-Sep','title':'矽格2026年10月6日官方英文法說簡報','pdf_url':PDF_URL,
            'selection_policy':'latest_eligible_MOPS_row_including_attachment_free_events_exact_published_download_form_and_filename'}


def native_presentation(raw, selected, deadline):
    _check(deadline)
    if sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('Sigurd original revision not qualified')
    try:native=extract_sigurd_presentation_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    except SourcePdfError as exc:
        if exc.error_kind=='timeout':raise SourceResponseError('timeout') from exc
        raise
    _check(deadline)
    pages=native['pages'];cover=re.sub(r'\s+','',pages[0]['text']);disclaimer=re.sub(r'\s+',' ',pages[1]['text'])
    if (native['coverage_status']!='complete' or native['empty_pages'] or native['garbled_pages']
            or native['page_count']!=23 or len(pages)!=23 or native['content_sha256']!=KNOWN_SHA
            or any(v not in cover for v in ['矽格股份有限公司','SIGURDMICROELECTRONICSCORP.','www.sigurd.com.tw','Oct.06.2026'])
            or selected['event_date']!='2026-10-06'
            or any(v not in disclaimer for v in ['Disclaimer','forward- looking statements','risks and uncertainties','differ materially','no obligation to update or revise'])
            or 'January-September 2026 Revenue Report' not in pages[11]['text']
            or 'subsidiary Sigurd UTC' not in pages[18]['text']
            or 'Q & A' not in pages[22]['text'] or 'Thank You' not in pages[22]['text']):
        raise ValueError('Sigurd native issuer period or limitations unverified')
    return native


def _context(selected,native,proof):
    doc={'document_id':'6257:'+selected['event_date']+':'+native['content_sha256'][:16],
         'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
         'projection_policy':PROJECTION_POLICY,'title':selected['title'],'url':PDF_URL,'language':'en',
         'event_date':selected['event_date'],'event_date_basis':'MOPS_issuer_event_row_and_PDF_cover',
         'event_time':selected['event_time'],'event_time_Taipei':selected['event_time'],'event_timezone':'Asia/Taipei','event_location':selected['event_location'],
         'event_status':'published_past_event_not_independently_occurrence_verified',
         'content_periods':CONTENT_PERIODS[:],'published_at':None,'material_file_date':None,
         'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':native['content_sha256'],
         'page_count':23,'pages':native['pages'],'binary_complete':True,'text_extraction_complete':True,
         'native_text_coverage':'complete','coverage_status':'partial','full_content_coverage_verified':False,
         'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
         'sigurd_glyph_evidence':native['sigurd_glyph_evidence'],
         'known_native_text_omissions':[{'page_number':p,'issue':'visual_content_not_fully_represented_in_native_text'} for p in (12,14,15,16,17,18,19,20,21,22)],
         'subsidiary_scope_caution':'合併財務數、歸屬母公司淨利與第19頁Sigurd UTC子公司資本支出必須分開。',
         'financial_scope_caution':'包含Q2、上半年、1–8月及1–9月不同期間；法說簡報不是完整經核對年度財報，不推定Q4財報或覆寫TTM。',
         'forward_looking_caution':'第2頁展望聲明及第19、22頁4Q26完工／1Q27量產計畫不是已實現事實，公司不保證更新。',
         'q_and_a_transcript_available':False,'disclaimer_pages':[2],'commercial_reuse_permission_verified':False}
    return {'ticker':TICKER,'date':selected['event_date'],'period':selected['period'],'title':selected['title'],
            'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
            'materials':[{'url':PDF_URL,'kind':'presentation','language':'en'}],'documents':[doc],
            'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],
            'fetched_at_epoch':proof['pdf']['retrieved_at'],'sigurd_conference_receipt':proof}


def _originals_fresh(proof, max_age):
    observed = time.time()
    return all(type(proof[k]['retrieved_at']) in (int,float) and 0 <= observed-proof[k]['retrieved_at'] < max_age and valid_expiry(proof[k],observed)
               for k in ('identity','index','pdf'))


def verify_context(value, ticker, *, deadline=None, max_age=86400):
    deadline = deadline if deadline is not None else time.monotonic()+10.
    try:
        _check(deadline)
        if not supports_sigurd(ticker) or not isinstance(value,dict) or value.get('ticker') != TICKER:
            return False
        proof = value['sigurd_conference_receipt']
        if set(proof) != {'policy','identity','index','pdf','selected'} or proof['policy'] != POLICY:
            return False
        parse_master(original_bytes(proof['identity'],MASTER_URL,max_age=max_age),proof['identity']['retrieved_at'])
        selected = select_presentation(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
        if selected != proof['selected'] or date.fromisoformat(selected['event_date']) > _today(proof['pdf']['retrieved_at']):
            return False
        raw = original_bytes(proof['pdf'],PDF_URL,max_age=max_age)
        expected = _context(selected,native_presentation(raw,selected,deadline),proof)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=max_age)
        matches = value == expected and json.dumps(value,sort_keys=True,allow_nan=False) == json.dumps(expected,sort_keys=True,allow_nan=False)
        _check(deadline)
        return matches and _originals_fresh(proof,max_age)
    except SourceResponseError as exc:
        if exc.error_kind == 'timeout': raise
        return False
    except (ValueError,TypeError,KeyError,AttributeError,IndexError,OverflowError,OSError,EOFError,zlib.error,SourcePdfError):
        return False


def fetch_sigurd_context(ticker, *, diagnostics=None, force_refresh=False, use_cache=True):
    if not supports_sigurd(ticker):return {}
    deadline = time.monotonic()+25.
    http = ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details = {'actual_provider':PROVIDER,'sigurd_presentation_workflow':True}
    try:
        raw,identity = http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at']);_check(deadline)
        selected,index = http.get_receipt(INDEX_URL,parser=lambda raw,r:select_presentation(raw,r['retrieved_at']));_check(deadline)
        native,pdf = http.get_receipt(PDF_URL,parser=lambda raw,r:native_presentation(raw,selected,deadline))
        proof = {'policy':POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected}
        value = _context(selected,native,proof)
        if not verify_context(value,TICKER,deadline=deadline,max_age=RAW_TTL):
            raise SourceResponseError('original_unverified')
        value = deepcopy(value)
        details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        for key,url in [('identity',MASTER_URL),('index',INDEX_URL),('pdf',PDF_URL)]:
            original_bytes(proof[key],url,max_age=RAW_TTL)
        _check(deadline)
        if not _originals_fresh(proof,RAW_TTL):raise SourceResponseError('original_expired')
        details.update(sigurd_originals_verified=True,coverage_status='native_presentation_text_complete',
                       cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
    except Exception as original:
        if time.monotonic() >= deadline:
            exc = SourceResponseError('timeout')
        else:
            exc = original if isinstance(original,SourceResponseError) else SourceResponseError('parse_error')
        details.update(sigurd_originals_verified=False,error_kind=exc.error_kind,status='error',
                       component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),
                       http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original
    if diagnostics is not None:diagnostics.update(details)
    return value


def validate_context(data, ticker):
    from source_applicability import instrument_type
    if (ticker != TICKER or not isinstance(data,dict) or data.get('ticker') != ticker or instrument_type(data) != 'EQUITY'
            or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity = data.get('company_identity')
    if identity is None:identity = {}
    if not isinstance(identity,dict):return False
    for key,expected in [('ticker',TICKER),('stock_id','6257'),('official_name','矽格'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
        if key != 'instrument_type' and data.get(key) not in (None,'',expected):return False
    names = {'矽格',LEGAL,'sigurd','sigurd microelectronics corporation','sigurd microelectronics corp','sigurd microelectronics corp.'}
    aliases = names | {'6257','6257.tw'}
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
    return isinstance(value,dict) and ('sigurd_conference_receipt' in value or value.get('source') == PROVIDER
        or value.get('source_url') == INDEX_URL or any(isinstance(d,dict) and (d.get('source') == PROVIDER or d.get('url') == PDF_URL)
            for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))
