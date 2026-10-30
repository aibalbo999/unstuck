"""Exact official 2Q26 transcript; no future-event or independent-fact upgrade."""
from . import conference_issuer_master as master_identity
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json,re,time,zlib
from urllib.parse import urljoin,unquote
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from search_provider_runtime import SourceResponseError
from source_pdf_reader import extract_pdf_pages, SourcePdfError
from .taiwanmobile_conference_transport import ConferenceHttp,MASTER_URL,INDEX_URL,PDF_URL,PROVIDER,RAW_TTL,original_bytes,valid_expiry,is_legacy_master
TICKER='3045.TW'
LEGAL='台灣大哥大股份有限公司'
UBN='97176270'
LEGACY_POLICY='taiwanmobile-original-transcript-v1'
POLICY='taiwanmobile-original-transcript-v2'
PROJECTION_POLICY='taiwanmobile-transcript-role-v1'
INDEX_TITLE='Results Conference Call - Taiwan Mobile: Open Possible | Internet Services |Prepaid Cards|Monthly Plans|Cell Phones'
NOTE='台灣大哥大官網2026Q2法說逐字稿12頁原生文字；會議日2026-08-14依官網與稿件，實際會議及逐字稿準確性未由影音獨立核對。11月12日Q3仍是未來場次。保留Q2與H1、幣別、每股及non-GAAP界線；展望、訂單、資料中心容量與市場排名是公司說法，不是已驗證實績；官網04:00 p.m.未明示時區，台北時刻保持未知。首次發布日、商業再利用授權未知。'
KNOWN_SHA = 'd81cb943e4aed5ca3d0ebde20234e39389aa8610a82c0fd570d46f912baaf28b'
PAGE_TEXT_SHA256 = ('50f22ee17960137de029ef506c65fedd94fe177d8e6a29c10c94b243d3f3bed2', 'b7100136cf786d094de81e053c9d95ff763dab2cfad4bd4f6a630c11747509e7', '5e25166fa5c6d7048878fbddceaaf80536de521273043f6aee9da7b917941eda', '4130c2d56fab74f0134317ae9c2f986d1e5a472a3800bad56f1042e96029c633', '0573379a5f6782ba28742fc9230fe46969702f6fb8eae277eb6f7a26ef335813', '001ef1f60f21966ef9aff2278dfb0349c07014a038154fdda1e4811b44d6b4e8', '6dae8591b03430fd75b3889a3947f8f3dab4e630c8a274bba6cdfce0e606e1c5', 'a11deeffc5beba4bcd313da4f7385a028fecd0d6c8225194c9b4c02f2863cbdc', 'b5e0a8b2176becf30cbbabca95c8abdc61724df440187e248455616a23083070', 'c6087c185c0fe2b9693cfe3c39c5251e71196684c1d33edfed6145c8fc8a853c', '094e1fc862ae5fa3eb81c53fab33090845c8c9ac39b510a6584ec6cc8989b772', '4bb387d1e5c63f39215cd9aa8d324d2c8c7abd240944f7a77e4405ff84dab1b8')

def supports(ticker):return isinstance(ticker,str)and ticker.strip().upper()in {'3045',TICKER}
def _today(epoch=None):return datetime.fromtimestamp(time.time()if epoch is None else epoch,ZoneInfo('Asia/Taipei')).date()
def _check(deadline):
 if time.monotonic()>=deadline:raise SourceResponseError('timeout')

def _master_policy_valid(policy, receipt):
 if policy==LEGACY_POLICY:return is_legacy_master(receipt)
 return (policy==POLICY and not is_legacy_master(receipt) and master_identity.is_shared(receipt)
         and receipt.get('source_url') in (MASTER_URL,master_identity.JSON_URL))

def parse_master(raw,epoch,source_url=MASTER_URL):
 rows=master_identity.master_rows(raw,epoch,source_url)
 matches=[r for r in rows if r.get('公司代號')=='3045']
 if len(matches)!=1:raise ValueError('issuer not unique')
 row=matches[0]
 if any(row.get(k)!=v for k,v in {'公司名稱':LEGAL,'公司簡稱':'台灣大','營利事業統一編號':UBN,'網址':'www.taiwanmobile.com','英文簡稱':'TWM'}.items()):raise ValueError('master issuer mismatch')
 stamp=row.get('出表日期','')
 if not re.fullmatch(r'\d{7}',stamp):raise ValueError('master date')
 day=date(int(stamp[:3])+1911,int(stamp[3:5]),int(stamp[5:]))
 if not 0<=(_today()-day).days<=14 or day>_today(epoch):raise ValueError('master stale or future')
 return True

def select_transcript(raw,epoch):
 if not isinstance(raw,bytes)or not 0<len(raw)<=1048576:raise ValueError('index size')
 text=raw.decode('utf-8','strict');soup=BeautifulSoup(text,'html.parser')
 if text.lower().count('</html>')!=1 or text.lower().count('</body>')!=1 or not soup.title or soup.title.get_text(' ',strip=True)!=INDEX_TITLE or not any(h.get_text(' ',strip=True)=='Results Conference Call'for h in soup.select('h1')):raise ValueError('complete publisher index required')
 events=[]
 pattern=r'The ([1-4]Q\d{2}) results webcast (was held|will be held) at 04:00 p\.m\. on ([A-Za-z]+, [A-Za-z]+ \d{1,2}, 20\d{2})\.'
 for card in soup.select('article.modal .modal-body'):
  p=card.select(':scope > p.p')
  if len(p)!=1:continue
  match=re.match(pattern,p[0].get_text(' ',strip=True))
  if not match:continue
  day=datetime.strptime(match[3],'%A, %B %d, %Y').date()
  if match[3].split(',')[0]!=day.strftime('%A'):raise ValueError('weekday conflict')
  if day.year!=2026:continue
  events.append((day.isoformat(),match[1],match[2],card))
 expected={('2026-11-12','3Q26','will be held'),('2026-08-14','2Q26','was held'),('2026-05-13','1Q26','was held'),('2026-03-13','4Q25','was held')}
 if len(events)!=4 or {(a,b,c)for a,b,c,_ in events}!=expected:raise ValueError('current event coverage changed')
 today=min(_today(),_today(epoch))
 if _today()>=date(2026,11,12)or today<date(2026,8,14):raise ValueError('qualified call no longer current or still future')
 past=[e for e in events if date.fromisoformat(e[0])<=today]
 selected=max(past,key=lambda e:e[0])
 if selected[:3]!=('2026-08-14','2Q26','was held'):raise ValueError('latest past event changed')
 links=[unquote(urljoin(INDEX_URL,a['href']))for a in selected[3].select('a[href]')if a.get_text(' ',strip=True)=='Conference Call Transcript']
 if links!=[PDF_URL]:raise ValueError('same-card transcript not unique')
 return {'event_date':'2026-08-14','content_period':'2026Q2','pdf_url':PDF_URL,'title':'台灣大哥大2026Q2官方法說逐字稿','upcoming_event':{'date':'2026-11-12','period':'2026Q3','status':'future_event_not_current_evidence'},'selection_policy':'complete_current_year_index_latest_past_call_same_card_transcript'}

def native_transcript(raw,selected,deadline):
 _check(deadline)
 if not isinstance(raw,bytes)or sha256(raw).hexdigest()!=KNOWN_SHA:raise ValueError('unqualified original revision')
 try:native=extract_pdf_pages(raw,timeout_seconds=min(10.,deadline-time.monotonic()))
 except SourcePdfError as exc:
  if exc.error_kind=='timeout':raise SourceResponseError('timeout')from exc
  raise
 _check(deadline)
 pages=native['pages']
 if native['coverage_status']!='complete'or native['page_count']!=12 or native['empty_pages']or native['garbled_pages']or len(pages)!=12 or [p['page_number']for p in pages]!=list(range(1,13))or tuple(sha256(p['text'].encode()).hexdigest()for p in pages)!=PAGE_TEXT_SHA256:raise ValueError('complete native text unverified')
 cover=' '.join(pages[0]['text'].split())
 if not cover.startswith('1 Taiwan Mobile 2Q26 Results Conference Call August 14, 2026')or selected['event_date']!='2026-08-14'or selected['content_period']!='2026Q2':raise ValueError('cover issuer or period mismatch')
 return native

def _context(selected,native,proof):
 doc={'document_id':'3045:2026-08-14:'+KNOWN_SHA[:16],'ticker':TICKER,'title':selected['title'],'url':PDF_URL,'source':PROVIDER,'source_type':'issuer_official','document_kind':'transcript','projection_policy':PROJECTION_POLICY,'event_date':selected['event_date'],'event_date_basis':'official_index_and_transcript_cover_declared_date','event_time_Taipei':None,'event_timezone':None,'source_declared_time_label':'04:00 p.m.','published_at':None,'material_file_date':None,'content_period':'2026Q2','source_page_displayed_date':None,'language':'en','translation_accuracy_verified':False,'transcript_accuracy_independently_verified':False,'retrieved_at_epoch':proof['pdf']['retrieved_at'],'content_sha256':KNOWN_SHA,'binary_complete':True,'page_count':12,'pages':deepcopy(native['pages']),'missing_text_pages':[],'garbled_pages':[],'text_extraction_complete':True,'native_text_coverage':'complete','coverage_status':'partial','full_content_coverage_verified':False,'parser_version':native['parser_version'],'commercial_reuse_permission_verified':False,'financial_scope_caution':NOTE}
 return {'ticker':TICKER,'date':selected['event_date'],'period':'2026Q2','title':selected['title'],'source':PROVIDER,'source_url':INDEX_URL,'summary':'','transcript_excerpt':'','transcript_available':True,'materials':[{'url':PDF_URL,'kind':'transcript','language':'en'}],'documents':[doc],'coverage_status':'partial','coverage_notes':[NOTE],'selection_policy':selected['selection_policy'],'upcoming_event':deepcopy(selected['upcoming_event']),'fetched_at_epoch':proof['pdf']['retrieved_at'],'taiwanmobile_conference_receipt':deepcopy(proof)}

def verify_context(value,ticker,*,deadline=None,max_age=RAW_TTL):
 deadline=time.monotonic()+10. if deadline is None else deadline
 try:
  _check(deadline)
  if not supports(ticker)or not isinstance(value,dict)or value.get('ticker')!=TICKER:return False
  proof=value['taiwanmobile_conference_receipt']
  if set(proof)!={'policy','identity','index','pdf','selected'}or not _master_policy_valid(proof['policy'],proof['identity']):return False
  parse_master(original_bytes(proof['identity'],proof['identity']['source_url'],max_age=max_age),proof['identity']['retrieved_at'],proof['identity']['source_url'])
  selected=select_transcript(original_bytes(proof['index'],INDEX_URL,max_age=max_age),proof['index']['retrieved_at'])
  if selected!=proof['selected']:return False
  native=native_transcript(original_bytes(proof['pdf'],PDF_URL,max_age=max_age),selected,deadline)
  expected=_context(selected,native,proof);_check(deadline)
  return json.dumps(value,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False)and all(valid_expiry(proof[k])for k in ('identity','index','pdf'))
 except SourceResponseError as exc:
  if exc.error_kind=='timeout':raise
  return False
 except (ValueError,TypeError,KeyError,AttributeError,IndexError,OSError,EOFError,SourcePdfError,zlib.error):return False

def fetch_context(ticker,*,diagnostics=None,force_refresh=False,use_cache=True):
 if not supports(ticker):return {}
 deadline=time.monotonic()+25.;http=ConferenceHttp(deadline,force_refresh=force_refresh,use_cache=use_cache);details={'actual_provider':PROVIDER,'taiwanmobile_transcript_workflow':True}
 try:
  raw,identity=http.get_receipt(MASTER_URL);parse_master(raw,identity['retrieved_at'],identity['source_url'])
  raw,index=http.get_receipt(INDEX_URL);selected=select_transcript(raw,index['retrieved_at'])
  raw,pdf=http.get_receipt(PDF_URL);native=native_transcript(raw,selected,deadline)
  proof={'policy':LEGACY_POLICY if is_legacy_master(identity) else POLICY,'identity':identity,'index':index,'pdf':pdf,'selected':selected};value=_context(selected,native,proof)
  if not verify_context(value,TICKER,deadline=deadline):raise SourceResponseError('original_unverified')
  if not all(valid_expiry(proof[k])for k in ('identity','index','pdf')):raise SourceResponseError('original_expired')
  value=deepcopy(value)
  details.update(taiwanmobile_originals_verified=True,coverage_status='native_text_complete',cache_hit=pdf['cache_hit'],stale=False,fetched_at_epoch=pdf['retrieved_at'],message=NOTE)
  _check(deadline)
 except Exception as original:
  exc=original if isinstance(original,SourceResponseError)else SourceResponseError('parse_error')
  details.update(taiwanmobile_originals_verified=False,error_kind=exc.error_kind)
  details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
  exc.diagnostic.update(details)
  if diagnostics is not None:diagnostics.update(details)
  if exc is original:raise
  raise exc from original
 details.update(component_statuses=deepcopy(http.components),http_request_sent=bool(http.http_request_count),http_request_count=http.http_request_count)
 if diagnostics is not None:diagnostics.update(details)
 _check(deadline)
 if not all(valid_expiry(proof[k])for k in ('identity','index','pdf')):
  exc=SourceResponseError('original_expired');exc.diagnostic.update(details,taiwanmobile_originals_verified=False)
  if diagnostics is not None:diagnostics.update(taiwanmobile_originals_verified=False)
  raise exc
 return value

def validate_context(data,ticker):
 if ticker!=TICKER or not isinstance(data,dict)or data.get('ticker')!=ticker:return False
 if any(data.get(k)not in (None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType')):return False
 identity=data.get('company_identity',{})
 if not isinstance(identity,dict):return False
 for k,v in {'ticker':TICKER,'stock_id':'3045','official_name':'台灣大','legal_name':LEGAL,'official_ubn':UBN,'instrument_type':'EQUITY'}.items():
  if identity.get(k)not in (None,'',v):return False
 names={'台灣大',LEGAL,'Taiwan Mobile Co., Ltd.','Taiwan Mobile Co. Ltd.','Taiwan Mobile','TWM','TAIWAN MOBILE CO LTD','TAIWAN MOBILE CO'};names={n.casefold()for n in names};aliases=names|{'3045','3045.tw'}
 def good(value,allowed):return isinstance(value,str)and all(n.strip().casefold()in allowed for n in value.split(' / '))
 for k in ('company_name','raw_company_name'):
  if data.get(k)is not None and not good(data[k],names):return False
 for k in ('allowed_aliases','english_names','forbidden_aliases'):
  rows=identity.get(k,[])
  if not isinstance(rows,list)or any(not good(v,aliases)for v in rows)and k!='forbidden_aliases':return False
  if k=='forbidden_aliases'and any(good(v,aliases)for v in rows):return False
 return True
