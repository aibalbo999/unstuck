"""PCSC dynamic official event selection; exact qualified partial role evidence."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import math
import re
import time
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from pcsc_presentation_pdf_reader import extract_pcsc_presentation_pages, ORIGINAL_SHA256, PAGE_TEXT_SHA256, xref_evidence
from .pcsc_conference_transport import PcscConferenceHttp, MASTER_URL, INDEX_URL, PROFILE_URL, PROVIDER, pdf_url, original_bytes, valid_expiry
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at

TICKER='2912.TW'
LEGAL='統一超商股份有限公司'
UBN='22555003'
POLICY='pcsc-dynamic-presentation-v1'
PROJECTION_POLICY='pcsc-presentation-role-v2'
ROLE_PAGES=(1,2,6,7,9,10,18,21,22)
EXCLUDED_PAGES=tuple(i for i in range(1,23) if i not in ROLE_PAGES)
NOTE=('統一超商官方準備簡報，非逐字稿或問答；原件22頁完整保存，原生文字仍為partial，'
      '第3、4頁各有2個未資格化私用字元，圖表、圖片及位置關係未完整抽取。'
      '角色僅使用已核第1、2、6、7、9、10、18、21、22頁，其他頁整頁排除；'
      '第19頁新市2025已啟用物流效益在原生順序可能錯接台中港2026／2029計畫，禁止重排或推定歸屬。'
      '內容混合2026H1與2021–2025歷年資料及未來目標，不能當完整年度查核財報。'
      '第7頁個體與合併ROE／ROA百分比須分別保留；第18頁全門市導入與導入ING不同；'
      '第21頁2025 ESG評等為公司自述，不能與未來IFRS S1／S2關注重點混同。'
      '場次日期不是首次發布或實際舉行的獨立證明，發布日期未知；未驗證商業重製授權。')


def _canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,allow_nan=False,separators=(',',':'))
def supports_pcsc(ticker):return str(ticker).strip().upper()==TICKER
def _today(epoch):return datetime.fromtimestamp(epoch,ZoneInfo('Asia/Taipei')).date()
def _check(deadline):
    if time.monotonic()>=deadline:raise SourceResponseError('timeout')


def parse_master(raw,epoch,source_url=MASTER_URL,*,as_of_epoch=None):
    observed=reference_epoch(epoch,as_of_epoch=as_of_epoch)
    rows=[r for r in master_rows(raw,epoch,source_url) if r.get('公司代號')=='2912']
    if len(rows)!=1:raise ValueError('PCSC master issuer not unique')
    r=rows[0]
    if (r.get('公司名稱')!=LEGAL or r.get('公司簡稱')!='統一超' or r.get('營利事業統一編號')!=UBN
            or r.get('英文簡稱','').strip()!='PCSC' or r.get('網址') not in {'http://www.7-11.com.tw','https://www.7-11.com.tw','http://www.7-11.com.tw/','https://www.7-11.com.tw/'}
            or not re.fullmatch(r'\d{7}',r.get('出表日期',''))):raise ValueError('PCSC master identity invalid')
    s=r['出表日期'];day=date(int(s[:3])+1911,int(s[3:5]),int(s[5:]))
    if not 0<=(_today(observed)-day).days<=14 or day>_today(epoch):raise ValueError('PCSC master date invalid')
    return {'ticker':TICKER,'legal_name':LEGAL,'official_ubn':UBN,'as_of':day.isoformat()}


def _html(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=1_048_576:raise ValueError('invalid issuer HTML size')
    text=raw.decode('utf-8-sig','strict');soup=BeautifulSoup(text,'html.parser')
    if (text.count('</html>')!=1 or text.count('</body>')!=1 or not soup.title
            or soup.title.get_text(' ',strip=True)!='7-ELEVEN 投資人關係'
            or not soup.select('a[href="https://www.7-11.com.tw/"]')
            or 'President Chain Store Corporation' not in text):raise ValueError('complete issuer HTML required')
    return soup


def parse_profile(raw):
    soup=_html(raw);rows={}
    for tr in soup.select('table tr'):
        th=tr.find('th');td=tr.find('td')
        if th is None or td is None:continue
        key=th.get_text(' ',strip=True)
        if key in rows:raise ValueError('duplicate profile field')
        rows[key]=td.get_text(' ',strip=True)
    if any(rows.get(k)!=v for k,v in {'公司名稱':LEGAL,'股票代號':'2912','營利事業統一編號':UBN}.items()):
        raise ValueError('issuer profile identity invalid')
    return {'ticker':TICKER,'legal_name':LEGAL,'official_ubn':UBN}


def select_presentation(raw,epoch,*,as_of_epoch=None):
    today=min(_today(reference_epoch(epoch,as_of_epoch=as_of_epoch)),_today(epoch))
    soup=_html(raw)
    if not soup.select('a[href="companyprofile.php"]'):raise ValueError('published issuer profile link required')
    years={};active=[]
    for li in soup.select('ul.tabs li[role="tab"]'):
        links=li.find_all('a',href=True)
        if len(links)!=1:raise ValueError('ambiguous year link')
        a=links[0];m=re.fullmatch(r'event\.php\?year=(20\d{2})',a['href'])
        if not m or a.get_text(strip=True)!=m[1]:raise ValueError('year href mismatch')
        year=int(m[1])
        if year in years:raise ValueError('duplicate published year')
        years[year]=urljoin(INDEX_URL,a['href'])
        if li.get('aria-selected')=='true':active.append(year)
        elif li.get('aria-selected')!='false':raise ValueError('ambiguous selected year')
    past_years=[y for y in years if y<=today.year]
    if not past_years or active!=[max(past_years)]:raise ValueError('default index not latest published current year')
    selected_year=active[0]
    tables=[]
    for t in soup.find_all('table'):
        if 'd-none' in t.get('class',[]):continue
        if [c.get_text(' ',strip=True) for c in t.find('tr').find_all('td')]==['日期','時間','說明','相關檔案']:tables.append(t)
    if len(tables)!=1:raise ValueError('unique event table required')
    events=[];seen=set()
    for tr in tables[0].find_all('tr')[1:]:
        cells=tr.find_all('td',recursive=False)
        if len(cells)!=4:raise ValueError('event row malformed')
        stamp=cells[0].get_text(strip=True);clock=cells[1].get_text(strip=True);title=cells[2].get_text(' ',strip=True)
        if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',stamp) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',clock):raise ValueError('event date or time invalid')
        day=date.fromisoformat(stamp)
        if day.year!=selected_year or not 1<=len(title)<=500 or not title.startswith('本公司') or '法人說明會' not in title:
            raise ValueError('event year or issuer subject invalid')
        if stamp in seen:raise ValueError('same-day event ambiguous')
        seen.add(stamp)
        pdfs=[]
        for a in cells[3].find_all('a',href=True):
            url=urljoin(INDEX_URL,a['href'])
            if a.select('i.fa-file-pdf'):
                if not pdf_url(url):raise ValueError('published PDF route invalid')
                pdfs.append(url)
        events.append((day,clock,title,pdfs))
    past=[r for r in events if r[0]<=today]
    if not past:raise ValueError('no current past event')
    day,clock,title,pdfs=max(past,key=lambda r:r[0])
    if (today-day).days>370 or len(pdfs)!=1:raise ValueError('latest event requires unique same-row PDF')
    return {'event_date':day.isoformat(),'event_end_date':day.isoformat(),'event_time':clock,'event_timezone':None,
            'event_title':title,'index_year':selected_year,'published_year_url':years[selected_year],
            'pdf_url':pdfs[0],'selection_policy':'latest_past_event_in_latest_published_active_year_same_row_attachment'}


def native_presentation(raw,selected,deadline):
    _check(deadline)
    budget=min(10.,deadline-time.monotonic())
    if sha256(raw).hexdigest()!=ORIGINAL_SHA256:
        # A clean generic extraction does not qualify unknown page semantics.
        # Its unknown warnings are fatal; no copied page numbers or false success.
        extract_pdf_pages(raw,timeout_seconds=budget)
        _check(deadline)
        raise SourceResponseError('unqualified_revision')
    native=extract_pcsc_presentation_pages(raw,timeout_seconds=budget)
    event=date.fromisoformat(selected['event_date'])
    if not date(2026,7,1)<=event<=date(2026,12,31):raise ValueError('known body period incompatible with event year')
    _check(deadline)
    return native


def _document(selected,native,stamp):
    return {'document_id':'2912:'+selected['event_date']+':'+native['content_sha256'][:16],
        'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
        'title':selected['event_title'],'url':selected['pdf_url'],'event_date':selected['event_date'],
        'event_end_date':selected['event_end_date'],'event_time':selected['event_time'],'event_timezone':None,
        'event_date_basis':'issuer_published_active_year_same_row_attachment','event_status':'announced_past_date_not_independently_occurrence_verified',
        'published_at':None,'content_period':'','content_periods':['2026H1','2021–2025 historical comparisons','2026 targets and 2029 expected milestones'],
        'retrieved_at_epoch':stamp,'content_sha256':native['content_sha256'],'page_count':native['page_count'],'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':False,'native_text_coverage':'partial','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
        'xref_validation_evidence':native['xref_validation_evidence'],'projection_policy':PROJECTION_POLICY,
        'role_page_allowlist':list(ROLE_PAGES),'projection_excluded_pages':list(EXCLUDED_PAGES),
        'known_native_text_omission_pages':list(EXCLUDED_PAGES),'source_selection':selected,
        'financial_scope_caution':NOTE,'period_scope_caution':'2026H1、2021–2025歷年與未來目標混合，非完整年度財報。',
        'visual_semantics_caution':'原生文字不保證圖表及空間歸屬完整；第19頁整頁排除，不重排或猜綁。',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'always_native_no_success_cache'}


def _context(selected,native,proof):
    stamp=proof['pdf']['retrieved_at']
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['event_title'],
        'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
        'materials':[{'url':selected['pdf_url'],'kind':'presentation','language':'zh-TW'}],
        'documents':[_document(selected,native,stamp)],'coverage_status':'partial','coverage_notes':[NOTE],
        'fetched_at_epoch':stamp,'pcsc_conference_receipt':proof}


def _fresh(proof,max_age):
    observed=time.time()
    stamps=[proof[k]['retrieved_at'] for k in ('identity','index','profile','pdf')]
    ordered=all(type(v) in (int,float) and math.isfinite(v) for v in stamps) and stamps==sorted(stamps) and stamps[-1]<=observed
    return (ordered and current_at(proof['identity'],max_age,observed) and all(
        valid_expiry(proof[k],observed) and 0<=observed-proof[k]['retrieved_at']<max_age for k in ('index','profile','pdf')))


def verify_context(value,ticker,*,deadline=None,max_age=1800):
    deadline=time.monotonic()+10 if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_pcsc(ticker) or not isinstance(value,dict) or value.get('ticker')!=TICKER:return False
        p=value['pcsc_conference_receipt']
        if set(p)!={'policy','identity','index','profile','pdf','selected'} or p['policy']!=POLICY or not is_shared(p['identity']):return False
        identity=p['identity'];url=identity['source_url']
        parse_master(original_bytes(identity,url,max_age=max_age),identity['retrieved_at'],url)
        selected=select_presentation(original_bytes(p['index'],INDEX_URL,max_age=max_age),p['index']['retrieved_at'])
        parse_profile(original_bytes(p['profile'],PROFILE_URL,max_age=max_age))
        if _canonical(selected)!=_canonical(p['selected']) or date.fromisoformat(selected['event_date'])>_today(p['pdf']['retrieved_at']):return False
        native=native_presentation(original_bytes(p['pdf'],selected['pdf_url'],max_age=max_age),selected,deadline)
        expected=_context(selected,native,p)
        if _canonical(value)!=_canonical(expected):return False
        _check(deadline);valid=_fresh(p,max_age);_check(deadline)
        return valid
    except SourceResponseError as exc:
        if exc.error_kind=='timeout':raise
        return False
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OSError,OverflowError,SourcePdfError):return False


def fetch_pcsc_context(ticker,*,diagnostics=None,force_refresh=False,use_cache=True):
    if not supports_pcsc(ticker):return {}
    deadline=time.monotonic()+20.
    http=PcscConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details={'actual_provider':PROVIDER,'pcsc_presentation_workflow':True}
    try:
        raw,identity=http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url'])
        raw,index=http.get_receipt(INDEX_URL);selected=http.authorize_index_links(index)
        raw,profile=http.get_receipt(PROFILE_URL);parse_profile(raw)
        raw,pdf=http.get_receipt(selected['pdf_url']);native=native_presentation(raw,selected,deadline)
        p={'policy':POLICY,'identity':identity,'index':index,'profile':profile,'pdf':pdf,'selected':selected}
        value=_context(selected,native,p)
        if not verify_context(value,ticker,deadline=deadline):raise SourceResponseError('original_unverified')
        details.update(pcsc_originals_verified=True,coverage_status='qualified_partial_presentation',
            cache_hit=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE,
            component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
        if diagnostics is not None:diagnostics.update(details)
        _check(deadline)
        if not _fresh(p,1800):raise SourceResponseError('original_expired')
        _check(deadline)
        return value
    except Exception as original:
        kind='timeout' if time.monotonic()>=deadline else getattr(original,'error_kind','parse_error')
        exc=original if isinstance(original,SourceResponseError) and original.error_kind==kind else SourceResponseError(kind)
        for target in (details,diagnostics,exc.diagnostic):
            if target is not None:
                for key in ('cache_hit','coverage_status','fetched_at_epoch','message'):target.pop(key,None)
        details.update(pcsc_originals_verified=False,status='error',error_kind=kind,
            component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original


def validate_context(data,ticker):
    from source_applicability import instrument_type
    from news_record_utils import clean_text
    if (ticker!=TICKER or not isinstance(data,dict) or data.get('ticker')!=ticker or data.get('stock_id') not in (None,'','2912') or instrument_type(data)!='EQUITY'
        or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity=data.get('company_identity')
    if identity is None:identity={}
    if not isinstance(identity,dict) or any(identity.get(k) not in (None,'','EQUITY') for k in ('quote_type','quoteType')):return False
    for key,expected in [('ticker',TICKER),('stock_id','2912'),('official_name','統一超'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
    names={'統一超','統一超商',LEGAL,'president chain store corporation','president chain store corp','president chain store corp.','pcsc'}
    name=data.get('company_name')
    if name is not None and (not isinstance(name,str) or any(clean_text(s).casefold() not in names for s in name.split(' / '))):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows=identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
    return not names.intersection(clean_text(s).casefold().strip('* ').strip() for s in identity.get('forbidden_aliases',[]))


def is_marked(value):
    if not isinstance(value,dict):return False
    def marker(d):return isinstance(d,dict) and (d.get('source')==PROVIDER or d.get('projection_policy')==PROJECTION_POLICY or pdf_url(d.get('url')))
    return ('pcsc_conference_receipt' in value or value.get('source_url')==INDEX_URL or marker(value)
        or any(marker(d) for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    try:
        native={k:deepcopy(document[k]) for k in ('pages','parser_version','page_count','content_sha256','garbled_pages','xref_validation_evidence')}
        native.update(empty_pages=document['missing_text_pages'])
        if (document['content_sha256']!=ORIGINAL_SHA256 or type(document['page_count']) is not int or document['page_count']!=22
                or len(document['pages'])!=22 or any(type(p.get('page_number')) is not int or p['page_number']!=i for i,p in enumerate(document['pages'],1))
                or tuple(sha256(p['text'].encode()).hexdigest() for p in document['pages'])!=PAGE_TEXT_SHA256
                or _canonical(document['xref_validation_evidence'])!=_canonical(xref_evidence())
                or _canonical(document)!=_canonical(_document(document['source_selection'],native,document['retrieved_at_epoch']))):return []
        return [deepcopy(p) for p in document['pages'] if p['page_number'] in ROLE_PAGES]
    except (ValueError,TypeError,KeyError,AttributeError):return []
