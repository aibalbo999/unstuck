"""Jentech dynamic official event selection; exact qualified partial role evidence."""
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
import math
import re
import time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import SourcePdfError, extract_pdf_pages
from .jentech_conference_transport import JentechConferenceHttp, MASTER_URL, INDEX_URL, PROVIDER, SITE_ID, pdf_url, official_url, original_bytes, valid_expiry
from .conference_issuer_master import master_rows, reference_epoch, is_shared, current_at

TICKER='3653.TW'
LEGAL='健策精密工業股份有限公司'
UBN='22415854'
POLICY='jentech-dynamic-presentation-v1'
PROJECTION_POLICY='jentech-presentation-role-v1'
ROLE_PAGES=(1,2,5,6,7,8,11,21)
EXCLUDED_PAGES=tuple(i for i in range(1,25) if i not in ROLE_PAGES)
NOTE=('健策2025年11月28日官方準備簡報，非逐字稿或問答；原件24頁完整保存，原生文字仍為partial。'
      '角色僅使用已核第1、2、5、6、7、8、11、21頁；第3、4、14–17頁亂碼，其他圖表及空間關係不完整。'
      '第13頁期間定義不明，第20頁日期欄順序錯位，第22、23頁圖例與季度未完整綁定，皆整頁排除，不重排或推定。'
      '第5、6頁是歷史廠房面積，不是產能；第7頁2026Q1及第8頁2027Q1均為2025當時預計，不能稱已完工。'
      '第8頁土地9,340坪與一期樓地板11,340+坪不同，保留加號及原文16,075坪，不自行修正或推算。'
      '第11頁應用描述不證明客戶、合約或市占。第21頁為2024Q1至2025Q3合併單季，金額新台幣仟元，EPS為元，括號負值；非完整年度財報。'
      '第2頁財務未完全經會計師查核或核閱與前瞻免責必須保留。場次日期非首次發布或獨立舉行證明。'
      '僅私人分析；原頁Confidential及禁止未經許可重製散布之註記保留，未驗證商業重製授權。')
ORIGINAL_SHA256='7f50e2245ee2b065df51026c3f37f6e73c8759631c556b7a44c58f36eeb54629'
PAGE_TEXT_SHA256=('f571051735fe34e676e22e7326da33d6a3c09e2ff6cf444e741ab51ee8149e2d', '57e31d5267579bfb7e25fa1deb3dc09c925658a3a1f54860d45ab035a4f76ca4', 'bdf4788ca9efd3d5e7eb513c7fd244c6d8f90bf0b01bd2469a36e28b68ee41c3', 'ff34ac6f70211118ba69b383be8c2fe2b843df99b5b668f1063a1ef1b0558cb0', '52f219f7e0fac3a58f8a556bbe27b07a8f3386bb227465698427f0f71a48313f', '5859dc3d1b1894e7d03b4cdb35552db5c9906859b34dc10424f1a3abfcba1c94', '1071432bae5ebc2f6f0d126fd8ff8ff6684a2c693d682e6004e7e823582ff820', 'faf3ba27e5a566a86ba4c89f11e0ecd4bb59a496e46dc0f769327201d78f6249', 'ef5dbbd8e939863c8d243546f5edf55517d83e6b91a0f4b3c4a173c063a9b1bc', '3cf38278bd8393f0e612dd4c94dc40f3f57ec7348e93a643c1afd4a707338a5e', 'a038a9d10f2650b3c775f6ee8833bbe49e3ef389318cd33e9647fe7347b8cd24', '26a4a68f580d447e0f06e0ac9889165235d54cdd597a9562282b1a2870aaf49d', '696b5ebf7498e9f346ac2b95c164773b8b6a8b19c5c6645919871930603b5c02', '78b884cc2baf82e1055c37f127537106bcabd15716614e6323673565283509e7', '462417d7177a743580c88fe664a3d7c17de40ef37ee8a161c975883d3a3ede25', 'ee7bc513f1b66b848cfe86ee2e6d50718a8836d7e3c3d1feda778a19d65d6991', 'fbd47b31c9683c45592713966808a4624f9350f82112585750468fe84475dc26', '6413b67e2d1ac88ddedef0837cae0c43ee9ba5ef96f75aeb5dccd58f41801187', 'ddabe45a728d0bedd85d023bc6d7d7b99b650dd71f414e9214ba8c4d350eefcb', 'c58665bf6cbf6120a2131c74eacd9889da81aaf3bb2b86d0f463cc865cc7e617', '28a2d242e8a6e8a75c233abfddb7a1740772a8904deadb2454c1bc3476bcd5ec', 'dca61f5ba0e9c76e4d001fbd1a884cd7d6150f009776384f2d37d0ade1958b8a', '9715dfe1515cfabbf3fb7e851ae0638157a5b16a3ba4ac146df3e527bc926dd5', 'a3a85ed2a7c810519d13cb1c012c1d2fb5b03f3e88b3f3b7541fa58d68b3ed86')


def _canonical(value):return json.dumps(value,ensure_ascii=True,sort_keys=True,allow_nan=False,separators=(',',':'))
def supports_jentech(ticker):return str(ticker).strip().upper()==TICKER
def _today(epoch):return datetime.fromtimestamp(epoch,ZoneInfo('Asia/Taipei')).date()
def _check(deadline):
    if time.monotonic()>=deadline:raise SourceResponseError('timeout')


def parse_master(raw,epoch,source_url=MASTER_URL,*,as_of_epoch=None):
    observed=reference_epoch(epoch,as_of_epoch=as_of_epoch)
    rows=[r for r in master_rows(raw,epoch,source_url) if r.get('公司代號')=='3653']
    if len(rows)!=1:raise ValueError('Jentech master issuer not unique')
    r=rows[0]
    if (r.get('公司名稱')!=LEGAL or r.get('公司簡稱')!='健策' or r.get('營利事業統一編號')!=UBN
            or r.get('英文簡稱','').strip()!='JENTECH' or r.get('網址') not in {'https://www.jentech.com.tw/zh','https://www.jentech.com.tw/zh/'}
            or not re.fullmatch(r'\d{7}',r.get('出表日期',''))):raise ValueError('Jentech master identity invalid')
    s=r['出表日期'];day=date(int(s[:3])+1911,int(s[3:5]),int(s[5:]))
    if not 0<=(_today(observed)-day).days<=14 or day>_today(epoch):raise ValueError('Jentech master date invalid')
    return {'ticker':TICKER,'legal_name':LEGAL,'official_ubn':UBN,'as_of':day.isoformat()}


def select_presentation(raw,epoch,*,as_of_epoch=None):
    today=min(_today(reference_epoch(epoch,as_of_epoch=as_of_epoch)),_today(epoch))
    if not isinstance(raw,bytes) or not 0<len(raw)<=2*1024*1024:raise ValueError('invalid issuer index size')
    text=raw.decode('utf-8-sig','strict');soup=BeautifulSoup(text,'html.parser')
    if (text.count('</html>')!=1 or text.count('</body>')!=1 or not soup.title
            or soup.title.get_text(' ',strip=True)!='法人說明會資訊 | Jentech Precision Industrial CO., LTD'):
        raise ValueError('complete issuer index required')
    metas=soup.find_all('meta',attrs={'http-equiv':'X-Wix-Meta-Site-Id'})
    models=soup.find_all('script',id='wix-viewer-model')
    if len(metas)!=1 or metas[0].get('content')!=SITE_ID or len(models)!=1:raise ValueError('site identity ambiguous')
    model=json.loads(models[0].string)
    if (model['site']['metaSiteId']!=SITE_ID or model['siteFeaturesConfigs']['tpaCommons']['userFileDomainUrl']!='filesusr.com'):
        raise ValueError('index CDN publication chain invalid')
    headings=[h for h in soup.find_all(['h1','h2','h3']) if '年度法人說明會' in h.get_text()]
    events=[];seen=set()
    for h in headings:
        title=h.get_text(' ',strip=True)
        m=re.fullmatch(r'(\d{3})年度法人說明會 \((\d{3})年(\d{1,2})月(\d{1,2})日\)',title)
        if not m or m[1]!=m[2]:raise ValueError('event year or date invalid')
        day=date(int(m[2])+1911,int(m[3]),int(m[4]))
        if day in seen:raise ValueError('ambiguous duplicate event')
        seen.add(day)
        # The nearest attachment-bearing container must contain this one
        # conference heading, never a sibling's attachment or global PDF.
        container=next((a for a in h.parents if a.find('a',href=True)),None)
        if container is None:links=[]
        else:
            if sum('年度法人說明會' in x.get_text() for x in container.find_all(['h1','h2','h3']))!=1:
                links=[]
            else:links=container.find_all('a',href=True)
        chinese=[]
        for a in links:
            label=a.get('title','')
            if re.fullmatch(m[1]+r'年(?:度)?法(?:人說明|說)會簡報檔\.pdf',label):
                url=a['href']
                if not official_url(url):raise ValueError('same-event official PDF route invalid')
                chinese.append(url)
        events.append((day,title,chinese))
    past=[e for e in events if e[0]<=today]
    if not past:raise ValueError('no past published event')
    day,title,links=max(past,key=lambda e:e[0])
    if (today-day).days>370 or len(links)!=1:raise ValueError('latest event requires unique same-container Chinese PDF')
    url=links[0]
    return {'event_date':day.isoformat(),'event_end_date':day.isoformat(),'event_time':None,'event_timezone':None,
        'event_title':title,'official_pdf_url':url,'pdf_url':'https://'+SITE_ID+'.filesusr.com'+url.split('/zh/_files',1)[1],
        'site_uuid':SITE_ID,'selection_policy':'latest_past_event_same_container_chinese_attachment_index_bound_cdn'}


def native_presentation(raw,selected,deadline):
    _check(deadline)
    native=extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
    _check(deadline)
    if native['content_sha256']!=ORIGINAL_SHA256:raise SourceResponseError('unqualified_revision')
    if selected['event_date']!='2025-11-28':raise ValueError('known body date incompatible with event')
    if (native['page_count']!=24 or native['coverage_status']!='partial' or native['empty_pages']!=[]
            or native['garbled_pages']!=[3,4,14,15,16,17]
            or tuple(sha256(x['text'].encode()).hexdigest() for x in native['pages'])!=PAGE_TEXT_SHA256):
        raise ValueError('native page qualification changed')
    return native


def _document(selected,native,stamp):
    return {'document_id':'3653:'+selected['event_date']+':'+native['content_sha256'][:16],
        'ticker':TICKER,'source':PROVIDER,'source_type':'issuer_official','document_kind':'presentation',
        'title':selected['event_title'],'url':selected['pdf_url'],'event_date':selected['event_date'],
        'event_end_date':selected['event_end_date'],'event_time':selected['event_time'],'event_timezone':None,
        'event_date_basis':'issuer_published_same_container_attachment_verified_redirect','event_status':'announced_past_date_not_independently_occurrence_verified',
        'published_at':None,'content_period':'','content_periods':['2024Q1–2025Q3 consolidated single quarters','2025 plant and application descriptions','2026Q1 and 2027Q1 plans stated in 2025'],
        'retrieved_at_epoch':stamp,'content_sha256':native['content_sha256'],'page_count':native['page_count'],'pages':native['pages'],
        'binary_complete':True,'text_extraction_complete':False,'native_text_coverage':'partial','coverage_status':'partial',
        'full_content_coverage_verified':False,'full_visual_content_verified':False,'financial_statement_complete':False,
        'missing_text_pages':native['empty_pages'],'garbled_pages':native['garbled_pages'],'parser_version':native['parser_version'],
        'projection_policy':PROJECTION_POLICY,
        'role_page_allowlist':list(ROLE_PAGES),'projection_excluded_pages':list(EXCLUDED_PAGES),
        'known_native_text_omission_pages':list(EXCLUDED_PAGES),'source_selection':selected,
        'financial_scope_caution':NOTE,'period_scope_caution':'2024Q1–2025Q3合併單季、2025歷史廠房與未來計畫混合，非2026新場次或完整年度財報。',
        'visual_semantics_caution':'第13、20、22、23頁期間或圖表歸屬未核，整頁排除；不重排、猜綁或轉成數值claims。',
        'q_and_a_transcript_available':False,'commercial_reuse_permission_verified':False,
        'response_reuse_policy':'always_native_no_success_cache'}


def _context(selected,native,proof):
    stamp=proof['pdf']['retrieved_at']
    return {'ticker':TICKER,'date':selected['event_date'],'period':'','title':selected['event_title'],
        'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':False,
        'materials':[{'url':selected['pdf_url'],'kind':'presentation','language':'zh-TW'}],
        'documents':[_document(selected,native,stamp)],'coverage_status':'partial','coverage_notes':[NOTE],
        'fetched_at_epoch':stamp,'jentech_conference_receipt':proof}


def _fresh(proof,max_age):
    observed=time.time()
    stamps=[proof[k]['retrieved_at'] for k in ('identity','index','redirect','pdf')]
    ordered=all(type(v) in (int,float) and math.isfinite(v) for v in stamps) and stamps==sorted(stamps) and stamps[-1]<=observed
    return (ordered and current_at(proof['identity'],max_age,observed) and all(
        valid_expiry(proof[k],observed) and 0<=observed-proof[k]['retrieved_at']<max_age for k in ('index','redirect','pdf')))


def verify_context(value,ticker,*,deadline=None,max_age=1800):
    deadline=time.monotonic()+10 if deadline is None else deadline
    try:
        _check(deadline)
        if not supports_jentech(ticker) or not isinstance(value,dict) or value.get('ticker')!=TICKER:return False
        p=value['jentech_conference_receipt']
        if set(p)!={'policy','identity','index','redirect','pdf','selected'} or p['policy']!=POLICY or not is_shared(p['identity']):return False
        identity=p['identity'];url=identity['source_url']
        parse_master(original_bytes(identity,url,max_age=max_age),identity['retrieved_at'],url)
        selected=select_presentation(original_bytes(p['index'],INDEX_URL,max_age=max_age),p['index']['retrieved_at'])
        original_bytes(p['redirect'],selected['official_pdf_url'],max_age=max_age)
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


def fetch_jentech_context(ticker,*,diagnostics=None,force_refresh=False,use_cache=True):
    if not supports_jentech(ticker):return {}
    deadline=time.monotonic()+20.
    http=JentechConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache)
    details={'actual_provider':PROVIDER,'jentech_presentation_workflow':True}
    try:
        raw,identity=http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url'])
        raw,index=http.get_receipt(INDEX_URL);selected=http.authorize_index_links(index)
        raw,redirect=http.get_receipt(selected['official_pdf_url']);http.authorize_redirect(redirect,selected)
        raw,pdf=http.get_receipt(selected['pdf_url']);native=native_presentation(raw,selected,deadline)
        p={'policy':POLICY,'identity':identity,'index':index,'redirect':redirect,'pdf':pdf,'selected':selected}
        value=_context(selected,native,p)
        if not verify_context(value,ticker,deadline=deadline):raise SourceResponseError('original_unverified')
        details.update(jentech_originals_verified=True,coverage_status='qualified_partial_presentation',
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
        details.update(jentech_originals_verified=False,status='error',error_kind=kind,
            component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
        exc.diagnostic.update(details)
        if diagnostics is not None:diagnostics.update(details)
        if exc is original:raise
        raise exc from original


def validate_context(data,ticker):
    from source_applicability import instrument_type
    from news_record_utils import clean_text
    if (ticker!=TICKER or not isinstance(data,dict) or data.get('ticker')!=ticker or data.get('stock_id') not in (None,'','3653') or instrument_type(data)!='EQUITY'
        or any(data.get(k) not in (None,'','EQUITY') for k in ('instrument_type','quote_type','quoteType'))):return False
    identity=data.get('company_identity')
    if identity is None:identity={}
    if not isinstance(identity,dict) or any(identity.get(k) not in (None,'','EQUITY') for k in ('quote_type','quoteType')):return False
    for key,expected in [('ticker',TICKER),('stock_id','3653'),('official_name','健策'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
        if identity.get(key) not in (None,'',expected):return False
    names={'健策','健策精密',LEGAL,'jentech precision industrial co., ltd','jentech precision industrial co., ltd.','jentech precision industrial co ltd','jentech'}
    name=data.get('company_name')
    if name is not None and (not isinstance(name,str) or any(clean_text(s).casefold() not in names for s in name.split(' / '))):return False
    for key in ('allowed_aliases','english_names','forbidden_aliases'):
        rows=identity.get(key,[])
        if not isinstance(rows,(list,tuple)) or any(not isinstance(s,str) for s in rows):return False
    return not names.intersection(clean_text(s).casefold().strip('* ').strip() for s in identity.get('forbidden_aliases',[]))


def is_marked(value):
    if not isinstance(value,dict):return False
    def marker(d):return isinstance(d,dict) and (d.get('source')==PROVIDER or d.get('projection_policy')==PROJECTION_POLICY or pdf_url(d.get('url')))
    return ('jentech_conference_receipt' in value or value.get('source_url')==INDEX_URL or marker(value)
        or any(marker(d) for key in ('documents','materials') for d in (value.get(key) if isinstance(value.get(key),list) else [])))


def role_pages(document):
    try:
        native={k:deepcopy(document[k]) for k in ('pages','parser_version','page_count','content_sha256','garbled_pages')}
        native.update(empty_pages=document['missing_text_pages'])
        if (document['content_sha256']!=ORIGINAL_SHA256 or type(document['page_count']) is not int or document['page_count']!=24
                or len(document['pages'])!=24 or any(type(p.get('page_number')) is not int or p['page_number']!=i for i,p in enumerate(document['pages'],1))
                or tuple(sha256(p['text'].encode()).hexdigest() for p in document['pages'])!=PAGE_TEXT_SHA256
                or _canonical(document)!=_canonical(_document(document['source_selection'],native,document['retrieved_at_epoch']))):return []
        return [deepcopy(p) for p in document['pages'] if p['page_number'] in ROLE_PAGES]
    except (ValueError,TypeError,KeyError,AttributeError):return []
