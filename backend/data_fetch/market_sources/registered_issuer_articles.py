"""Complete dated originals on the registered Mirle and Mega public sites."""
from collections import Counter
from copy import deepcopy
from datetime import date,datetime,timedelta
from hashlib import sha256
import csv,io,json,math,re,time,zlib
from urllib.parse import urlsplit,parse_qs,urljoin
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

POLICY='registered-issuer-original-articles-v1'
SHARED_MASTER_POLICY='registered-issuer-original-articles-shared-master-v2'
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
CSV_MASTER_URL='https://mopsfin.twse.com.tw/opendata/t187ap03_L.csv'
MASTER_ORIGINAL_TTL=1800

def _master_original_key():return 'registered_issuer_master_original:v1:'+sha256(CSV_MASTER_URL.encode()).hexdigest()

def _qualified_master_original(receipt):
 raw=_read_original(receipt,CSV_MASTER_URL);stamp=receipt['retrieved_at']
 if not 0<=time.time()-stamp<MASTER_ORIGINAL_TTL:raise ValueError('registered_master_original_expired')
 from .issuer_news import TAIPEI
 for ticker in PROFILES:_identity(raw,ticker,datetime.now(TAIPEI).date(),stamp,CSV_MASTER_URL)
 if time.time()>=stamp+MASTER_ORIGINAL_TTL:raise ValueError('registered_master_original_expired')
 return raw

def retain_qualified_master_original(receipt):
 """Explicit archived original adoption; never an HTTP result/cache seed."""
 from cache_store import get_cache_json,set_cache_json
 _qualified_master_original(receipt);remaining=int(receipt['retrieved_at']+MASTER_ORIGINAL_TTL-time.time())
 if remaining<=0:raise ValueError('registered_master_original_expired')
 row={'policy':POLICY,'original_receipt':deepcopy(receipt),'fresh_until_epoch':receipt['retrieved_at']+MASTER_ORIGINAL_TTL};key=_master_original_key();set_cache_json(key,row,ttl_seconds=remaining)
 if get_cache_json(key)!=row:raise ValueError('registered_master_original_retention_unverified')
 _qualified_master_original(receipt)
 return {'cache_key':key,'original_receipt':deepcopy(receipt),'fresh_until_epoch':row['fresh_until_epoch'],'new_HTTP_or_acquisition_successes':0}

def _retained_master_original(http):
 from cache_store import get_cache_json
 try:row=get_cache_json(_master_original_key())
 except Exception:return None
 if row is None:return None
 if not isinstance(row,dict)or row.get('policy')!=POLICY:raise ValueError('registered_master_original_policy_invalid')
 receipt=row['original_receipt'];raw=_qualified_master_original(receipt)
 if row.get('fresh_until_epoch')!=receipt['retrieved_at']+MASTER_ORIGINAL_TTL or time.monotonic()>=http.deadline:raise SourceResponseError('timeout')
 http.components.append({'url':CSV_MASTER_URL,'cache_hit':True,'http_request_sent':False,'fetched_at_epoch':receipt['retrieved_at'],'http_status':200,'original_reused':True,'original_receipt':deepcopy(receipt)})
 return raw
from .yulon_group_articles import PROFILE as YULON_PROFILE
PROFILES={
 '2201.TW':YULON_PROFILE,
 '2464.TW':dict(short_name='盟立',legal_name='盟立自動化股份有限公司',english_name='Mirle Automation Corporation',ubn='22099478',english_alias='Mirle',website='http://www.mirle.com.tw',host='www.mirle.com.tw',publisher='Mirle',index='https://www.mirle.com.tw/news/?index_m_year=2026'),
 '2886.TW':dict(short_name='兆豐金',legal_name='兆豐金融控股股份有限公司',english_name='Mega Financial Holding Co., Ltd.',ubn='70796754',english_alias='MEGA FHC',website='www.megaholdings.com.tw',host='www.megaholdings.com.tw',publisher='Mega FHC',index='https://www.megaholdings.com.tw/tc/news.aspx'),
}

def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _page(raw):
 if not isinstance(raw,bytes)or not 0<len(raw)<=500000:raise ValueError('registered_original_size_invalid')
 text=raw.decode('utf8',errors='strict')
 if '\ufffd'in text:raise ValueError('registered_original_encoding_invalid')
 return BeautifulSoup(text,'html.parser')
def _day(value):
 if not isinstance(value,str)or not re.fullmatch(r'20\d{2}[-.]\d{2}[-.]\d{2}',value):raise ValueError('registered_day_invalid')
 return date.fromisoformat(value.replace('.','-'))
def _article_id(url,ticker):
 if ticker=='2201.TW':
  from .yulon_group_articles import article_id
  return article_id(url)
 if ticker=='2464.TW':
  m=re.fullmatch(r'https://www\.mirle\.com\.tw/news-detail/([1-9]\d{0,7})/',str(url))
  return m[1]if m else None
 if ticker!='2886.TW':return None
 try:
  u=urlsplit(url);q=parse_qs(u.query,strict_parsing=True)
  if (u.scheme!='https'or u.netloc!='www.megaholdings.com.tw'or u.path!='/tc/news_in.aspx'or u.fragment
      or set(q)!={'id','cid','chk','param'}or any(len(v)!=1 for v in q.values())or q['cid']!=['0']or q['param']!=['pn=1']
      or not re.fullmatch(r'[1-9]\d{0,7}',q['id'][0])or not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',q['chk'][0])):return None
  return q['id'][0]
 except (ValueError,TypeError):return None
def url_contract(url):
 if url==CSV_MASTER_URL:return 2500000,{'text/csv','application/csv'}
 if url==ROSTER_URL:return 2500000,{'application/json','text/json'}
 if any(url in (p['index'],p.get('identity_url'))for p in PROFILES.values()):return 500000,{'text/html','application/xhtml+xml'}
 if any(_article_id(url,t)for t in PROFILES):return 300000,{'text/html','application/xhtml+xml'}
 raise SourceResponseError('transport_url_invalid')
class ArticlesHttp(IssuerNewsHttp):
 route_contract=staticmethod(url_contract)
 def get(self,url):
  if url==CSV_MASTER_URL:
   from .registered_issuer_master import request_master
   raw,_=request_master(self)
   return raw
  from .yulon_group_articles import YulonNewsHttp, DIRECTORY, INDEX, article_id
  if url not in {DIRECTORY,INDEX} and not article_id(url):return super().get(url)
  native=YulonNewsHttp(self.deadline)
  try:
   raw,_=native.get_receipt(url)
   return raw
  finally:
   self.components.extend(native.components)
   self.http_request_count+=native.http_request_count

def _master_rows(raw,url):
 if url==ROSTER_URL:return json.loads(raw)
 if url!=CSV_MASTER_URL:raise ValueError('registered_master_url_invalid')
 text=raw.decode('utf-8-sig',errors='strict')
 if '\ufffd'in text:raise ValueError('registered_master_encoding_invalid')
 reader=csv.DictReader(io.StringIO(text,newline=''),strict=True);fields=reader.fieldnames;rows=list(reader)
 if (not fields or len(fields)!=len(set(fields))or not {'出表日期','公司代號','公司名稱','公司簡稱','營利事業統一編號','英文簡稱','網址'}<=set(fields)
     or not 500<=len(rows)<=5000 or any(None in r or any(v is None for v in r.values())for r in rows)):raise ValueError('registered_master_CSV_shape_invalid')
 return rows

def _identity(raw,ticker,today,epoch,master_url=ROSTER_URL):
 from .official_company_legal_name import parse_roster,select_legal_name
 from .issuer_news import TAIPEI
 p=PROFILES[ticker];all_rows=_master_rows(raw,master_url);derived=json.dumps(all_rows,ensure_ascii=False).encode()if master_url==CSV_MASTER_URL else raw;anchor=select_legal_name(parse_roster(derived,'.TW'),ticker,p['short_name'],today=today)
 rows=[r for r in all_rows if r.get('公司代號')==ticker.split('.')[0]]
 if (not anchor or len(rows)!=1 or anchor['legal_name']!=p['legal_name']or rows[0].get('營利事業統一編號')!=p['ubn']
     or rows[0].get('網址')!=p['website']or rows[0].get('英文簡稱')!=p['english_alias']
     or date.fromisoformat(anchor['as_of'])>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('registered_issuer_identity_unverified')
 return {'ticker':ticker,'short_name':p['short_name'],'legal_name':p['legal_name'],'official_ubn':p['ubn'],'english_alias':p['english_alias'],'website_host':p['host'],'market':'TWSE','master_observed_on':anchor['as_of'],'master_source_url':master_url,'master_response_sha256':sha256(raw).hexdigest()}

def _owner(soup,ticker):
 if ticker=='2201.TW':
  from .yulon_group_articles import owner
  return owner(soup)
 if ticker=='2464.TW':
  nodes=soup.select('div.copyright');og=soup.select('meta[property="og:site_name"]')
  if len(nodes)!=1 or _clean(nodes[0])!='Copyright © 盟立集團. All rights reserved.'or len(og)!=1 or og[0].get('content')!='盟立自動化':raise ValueError('mirle_registered_brand_unverified')
 else:
  nodes=soup.select('div#footer > p');authors=soup.select('meta[name="author"]')
  if not any(_clean(n).startswith(PROFILES[ticker]['legal_name']+' 地址：')for n in nodes)or len(authors)!=1 or authors[0].get('content')!='兆豐金控':raise ValueError('mega_registered_legal_owner_unverified')

def parse_index(raw,ticker):
 p=PROFILES[ticker];soup=_page(raw);_owner(soup,ticker);rows=[];seen={}
 if ticker=='2201.TW':
  from .yulon_group_articles import parse_index as parse_group_index
  rows=parse_group_index(soup)
 elif ticker=='2464.TW':
  roots=soup.select('div.mainArea > div.wrap > div.contentBox > div.newsList')
  if len(roots)!=1:raise ValueError('mirle_index_section_invalid')
  cards=roots[0].select(':scope > div.newsItem > div.item > div.Txt')
  if not 1<=len(cards)<=100:raise ValueError('mirle_index_count_invalid')
  for c in cards:
   links=c.select(':scope > h3.title > a[href]');days=c.select(':scope > div.newsDate > strong');roles=c.select(':scope > div.newsDate > div.classTitle')
   if len(roles)==1 and _clean(roles[0])!='重大公告':continue
   if len(links)!=1 or len(days)!=1 or len(roles)!=1:raise ValueError('mirle_index_fields_invalid')
   a=links[0];url=a['href']
   if not _article_id(url,ticker):continue
   if _clean(roles[0])!='重大公告':continue
   rows.append({'url':url,'title':_clean(a),'date_original':_clean(days[0])})
 else:
  cards=soup.select('a.item[href][id^="ctl00_ContentPlaceHolder1_rptList_"]')
  if not 1<=len(cards)<=100:raise ValueError('mega_index_count_invalid')
  for a in cards:
   titles=a.select(':scope > b');days=a.select(':scope > i');url=urljoin(p['index'],a['href'])
   if len(titles)!=1 or len(days)!=1 or not _article_id(url,ticker):raise ValueError('mega_native_index_route_invalid')
   title=_clean(titles[0])
   if _clean(a.get('title',''))!=title:raise ValueError('mega_native_index_title_conflict')
   # Subsidiary releases are retained in the original index, never relabelled.
   if '兆豐金控'not in title:continue
   rows.append({'url':url,'title':title,'date_original':_clean(days[0])})
 for row in rows:
  _day(row['date_original'])
  if not 1<=len(row['title'])<=500:raise ValueError('registered_index_title_invalid')
  if row['url']in seen and row!=seen[row['url']]:raise ValueError('registered_index_duplicate_conflict')
  seen[row['url']]=row
 return list(seen.values())

def parse_article(raw,listed,ticker):
 soup=_page(raw);_owner(soup,ticker);p=PROFILES[ticker];url=listed['url']
 if not _article_id(url,ticker):raise ValueError('registered_article_route_invalid')
 if ticker=='2201.TW':
  from .yulon_group_articles import parse_article as parse_group_article
  return parse_group_article(soup,listed)
 if ticker=='2464.TW':
  tops=[n for n in soup.select('div.topBox')if n.select_one('h1.articleTitle')]
  if len(tops)!=2:raise ValueError('mirle_responsive_sections_invalid')
  copies=[]
  for top in tops:
   titles=top.select(':scope > div.head > h1.articleTitle');days=top.select(':scope > div.newsDate > strong');roles=top.select(':scope > div.newsDate > div.classTitle');links=top.select('input#copyLink');blocks=top.parent.select(':scope > div.textEditor')
   if len(titles)!=1 or len(days)!=1 or len(roles)!=1 or len(blocks)!=1 or len(links)!=1:raise ValueError('mirle_article_sections_invalid')
   title=_clean(titles[0]);stamp=_clean(days[0]);block=blocks[0]
   if links[0].get('value')!=url.rstrip('/')or _clean(roles[0])!='重大公告':raise ValueError('mirle_copylink_or_role_invalid')
   if block.find(['script','iframe','object','form','audio','video','table']):raise ValueError('mirle_text_scope_unverified')
   copies.append((title,stamp,_clean(block),len(block.find_all('img'))))
  if copies[0]!=copies[1]:raise ValueError('mirle_responsive_content_conflict')
  title,stamp,body,images=copies[0]
  page_titles=soup.select('title');og=soup.select('meta[property="og:title"]')
  if len(page_titles)!=1 or _clean(page_titles[0])!=title or len(og)!=1 or og[0].get('content')!=title or '盟立集團（2464）'not in body:raise ValueError('mirle_native_owner_title_unverified')
 else:
  roots=soup.select('#printcontext > #in_right')
  if len(roots)!=1:raise ValueError('mega_native_root_invalid')
  titles=roots[0].select(':scope > div.in_title');blocks=roots[0].select(':scope > div#editing_area > div.font_s')
  if len(titles)!=1 or len(blocks)!=1:raise ValueError('mega_native_sections_invalid')
  block=blocks[0];title=_clean(titles[0]);body=_clean(block)
  native_day=re.match(r'^([1-9]\d{1,2}年(?:[1-9]|1[0-2])月(?:[1-9]|[12]\d|3[01])日)(?:\s|$)',body)
  stamp=native_day[1]if native_day else ''
  m=re.fullmatch(r'([1-9]\d{1,2})年([1-9]|1[0-2])月([1-9]|[12]\d|3[01])日',stamp)
  if not m or date(int(m[1])+1911,int(m[2]),int(m[3]))!=_day(listed['date_original']):raise ValueError('mega_native_roc_date_invalid')
  if block.find(['script','iframe','object','form','audio','video','table'])or'兆豐金控'not in body:raise ValueError('mega_native_parent_body_unverified')
  images=len(block.find_all('img'))
 if title!=listed['title']or ticker=='2464.TW'and stamp!=listed['date_original']or not 100<=len(body)<=12000:raise ValueError('registered_title_date_or_body_invalid')
 return title,body,{'date':_day(listed['date_original']).isoformat(),'issuer_article_date':stamp,'index_card_date':listed['date_original'],'image_count':images,'images_independently_verified':False,'responsive_text_copies_agree':ticker=='2464.TW'}

def validate_context(data,ticker):
 from source_applicability import instrument_type
 p=PROFILES.get(ticker);context=data.get('company_identity')if isinstance(data,dict)else None
 if context is None:context={}
 if not p or not isinstance(data,dict)or data.get('ticker')!=ticker or instrument_type(data)!='EQUITY'or not isinstance(context,dict)or any(data.get(k)not in(None,'','EQUITY')for k in ('instrument_type','quote_type','quoteType')):return False
 if data.get('company_name')not in(None,'')and _clean(data['company_name']).casefold()not in{s.casefold()for s in (p['short_name'],p['legal_name'],p['english_name'],p['short_name']+' / '+p['english_name'])}:return False
 for key,expected in [('ticker',ticker),('stock_id',ticker.split('.')[0]),('official_name',p['short_name']),('legal_name',p['legal_name']),('official_ubn',p['ubn']),('instrument_type','EQUITY')]:
  if context.get(key)not in(None,'',expected):return False
 forbidden=context.get('forbidden_aliases',[])
 return isinstance(forbidden,(list,tuple))and all(isinstance(v,str)for v in forbidden)and not {p['short_name'].casefold(),p['legal_name'].casefold(),p['english_alias'].casefold()}&{_clean(v).strip('* ').casefold()for v in forbidden}

def _read_original(proof,url):
 from .conference_issuer_master import is_shared
 if is_shared(proof):
  from .official_issuer_master import original_bytes
  if url not in {CSV_MASTER_URL,ROSTER_URL}or proof.get('source_url')!=url:raise ValueError('registered_shared_master_url_invalid')
  stamp=proof.get('retrieved_at')
  if type(stamp)not in(int,float)or not math.isfinite(stamp)or not 0<stamp<=time.time():raise ValueError('registered_shared_master_epoch_invalid')
  # Historical selection retains the old date policy. Live acquisition checks
  # the original physical/declared expiry separately, before handing off data.
  return original_bytes(proof,max_age=max(86400,time.time()-stamp+1))
 limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
 cached=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
 from .official_issuer_master import ARCHIVE_FIELDS
 legacy_fields=ARCHIVE_FIELDS|({'http_status_observed','cache_source','source_payload_sha256','source_payload_bytes'}if cached else set())
 if not isinstance(proof,dict)or set(proof)!=legacy_fields:raise ValueError('registered_legacy_receipt_shape_invalid')
 # Historical JSON came from the independently retained complete roster,
 # with unknown HTTP status. Newly decoded JSON requires its typed wire proof.
 if url==ROSTER_URL and not cached:raise ValueError('registered_legacy_JSON_provenance_invalid')
 if cached:
  if url!=ROSTER_URL or proof.get('http_status')is not None or proof.get('http_status_observed')is not False or proof.get('cache_source')!='official-company-roster:v2:.TW'or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes'):raise ValueError('registered_cached_master_invalid')
 elif not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'or proof.get('http_status_observed',True)is not True or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes')):raise ValueError('registered_native_receipt_invalid')
 if proof.get('status')!='archived'or proof.get('source_url')!=url or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time():raise ValueError('registered_original_receipt_invalid')
 raw=read_response(proof)
 if len(raw)!=proof['raw_response_bytes']:raise ValueError('registered_original_length_invalid')
 return raw

def _build_record(ticker,identity,listed,title,body,dates,proofs):
 from .conference_issuer_master import is_shared
 p=PROFILES[ticker]
 extra={}
 if ticker=='2201.TW':
  from .yulon_group_articles import record_fields
  extra=record_fields()
 return {'ticker':ticker,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],'source':p['short_name']+'官網','publisher':p['publisher'],'source_type':'first_party_issuer_news','publication_date_original':dates,'publication_date_precision':'day','publication_date_basis':'issuer_page_displayed_day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed','financial_assurance':'not_verified_as_audited','issuer_news_receipt':{**identity,'policy':SHARED_MASTER_POLICY if is_shared(proofs['master'])else POLICY,'original_id':_article_id(listed['url'],ticker),'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs},**extra}

def verified_record(record,data,*,today):
 try:
  ticker=data.get('ticker');p=PROFILES.get(ticker)
  if not p or not validate_context(data,ticker):return None
  proofs=record['issuer_news_receipt']['source_record_archive'];url=record['source_document_url']
  if not _article_id(url,ticker):return None
  master_url=proofs['master']['source_url']
  if master_url not in {ROSTER_URL,CSV_MASTER_URL}:return None
  master=_read_original(proofs['master'],master_url);index=_read_original(proofs['index'],p['index']);article=_read_original(proofs['article'],url);identity=_identity(master,ticker,today,proofs['master']['retrieved_at'],master_url)
  if ticker=='2201.TW':
   from .yulon_group_articles import validate_directory
   validate_directory(_read_original(proofs['directory'],p['identity_url']))
  listed=[r for r in parse_index(index,ticker)if r['url']==url]
  if len(listed)!=1:return None
  title,body,dates=parse_article(article,listed[0],ticker);published=parse_news_datetime(dates['date']);expected=_build_record(ticker,identity,listed[0],title,body,dates,proofs)
  if any(proofs[k]['retrieved_at']<published.timestamp()for k in ('index','article'))or parse_news_datetime(record.get('date'))!=published or 'published_date'in record and parse_news_datetime(record['published_date'])!=published or any(record.get(k)!=v for k,v in expected.items()if k!='date'):return None
  return p['publisher']
 except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,UnicodeError,zlib.error,csv.Error,AssertionError,SourceResponseError):return None

def fetch_recent_news(ticker,*,now,http=None):
 from .issuer_news import TAIPEI
 p=PROFILES[ticker];deadline=time.monotonic()+20;http=http or ArticlesHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter();audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
 try:
  master=_retained_master_original(http)
  if master is None:master=http.get(CSV_MASTER_URL)
  component=[c for c in http.components if c.get('url')in {CSV_MASTER_URL,ROSTER_URL}and c.get('fetched_at_epoch')is not None][-1]
  master_url=component['url'];master_epoch=component['fetched_at_epoch'];identity=_identity(master,ticker,today,master_epoch,master_url)
  directory=None
  if ticker=='2201.TW':
   from .yulon_group_articles import validate_directory
   directory=http.get(p['identity_url']);validate_directory(directory)
  index=http.get(p['index']);rows=parse_index(index,ticker);audit['raw_count']=len(rows);candidates=[]
  for row in rows:
   day=_day(row['date_original'])
   if day>today:excluded['future']+=1
   elif day<(now-timedelta(days=30)).astimezone(TAIPEI).date():excluded['historical']+=1
   else:candidates.append(row)
  def archive(raw,url):
   component=[c for c in http.components if c.get('url')==url][-1];epoch=component['fetched_at_epoch'];cached=component.get('evidence_kind')==CACHED_MASTER_KIND
   from .conference_issuer_master import is_shared
   if is_shared(component.get('original_receipt')):
    from .official_issuer_master import original_bytes
    receipt=component['original_receipt']
    if url!=master_url or receipt['source_url']!=url or original_bytes(receipt,max_age=MASTER_ORIGINAL_TTL)!=raw:raise ValueError('registered_shared_master_original_changed')
    return deepcopy(receipt)
   if component.get('original_reused')is True:
    receipt=component['original_receipt']
    if url!=CSV_MASTER_URL or epoch!=receipt['retrieved_at']or _qualified_master_original(receipt)!=raw:raise ValueError('registered_master_original_changed')
    return deepcopy(receipt)
   if cached:
    if url!=ROSTER_URL or component.get('http_request_sent')is not False or component.get('cache_hit')is not True or component.get('stale')is not False or component.get('http_status_observed')is not False or component.get('http_status')is not None or component.get('cache_source')!='official-company-roster:v2:.TW'or component.get('source_url')!=url or component.get('source_payload_sha256')!=sha256(raw).hexdigest()or type(component.get('source_payload_bytes'))is not int or component['source_payload_bytes']!=len(raw):raise ValueError('registered_cached_master_metadata_invalid')
    receipt=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND);receipt.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
   else:
    if component.get('http_status_observed',True)is not True or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes')):raise ValueError('registered_native_metadata_conflict')
    receipt=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
   if _read_original(receipt,url)!=raw:raise ValueError('registered_original_archive_unverified')
   return receipt
  shared=None
  for row in sorted(candidates,key=lambda r:_day(r['date_original']),reverse=True)[:3]:
   if time.monotonic()>=deadline:raise SourceResponseError('timeout')
   raw=http.get(row['url']);title,body,dates=parse_article(raw,row,ticker);published=parse_news_datetime(dates['date'])
   if not now-timedelta(days=30)<=published<=now:excluded['outside_window']+=1;continue
   if shared is None:
    shared={'master':archive(master,master_url),'index':archive(index,p['index'])}
    if directory is not None:shared['directory']=archive(directory,p['identity_url'])
   record=_build_record(ticker,identity,row,title,body,dates,{**shared,'article':archive(raw,row['url'])})
   if not verified_record(record,{'ticker':ticker,'instrument_type':'EQUITY'},today=today):raise ValueError('registered_saved_original_unverified')
   if time.monotonic()>=deadline:raise SourceResponseError('timeout')
   records.append(record)
  if time.monotonic()>=deadline:raise SourceResponseError('timeout')
  try:
   for c in http.components:
    if c.get('original_reused'):_qualified_master_original(c['original_receipt'])
   if time.monotonic()>=deadline:raise SourceResponseError('timeout')
  except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,UnicodeError,zlib.error,csv.Error,AssertionError,SourceResponseError):
   records=[];raise
  audit['status']='success'if records else'unavailable'
 except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,UnicodeError,zlib.error,csv.Error,AssertionError,SourceResponseError)as exc:
  if any(c.get('original_reused')for c in http.components)and(str(exc)=='registered_master_original_expired'or time.monotonic()>=deadline):records=[]
  audit.update(status='degraded_enrichment'if records else'error',error_kind=getattr(exc,'error_kind','parse_error'),error_message=str(exc)[:150])
 components=getattr(http,'components',[]);sent=getattr(http,'http_request_count',0);cached=bool(components)and all(c.get('cache_hit')for c in components)
 if audit['status']=='success'and cached and not sent:audit['status']='skipped_fresh_cache'
 epochs=[c['fetched_at_epoch']for c in components if type(c.get('fetched_at_epoch'))in(int,float)]
 audit.update(http_request_sent=bool(sent),http_request_count=sent,event_kind='http_request'if sent else'cache_hit'if cached else'local_block',cache_hit=cached,stale=False,record_count=len(records),usable_count=len(records),fetched_at_epoch=min(epochs)if epochs else None,parser_version=POLICY,excluded_reason_counts=dict(excluded),component_receipts=[{k:v for k,v in c.items()if k!='original_receipt'}for c in components])
 if records:
  # Saved news remains usable as dated evidence, but a new acquisition may
  # only hand off the originals that were current throughout this collection.
  try:
   from .conference_issuer_master import is_shared,current_at
   from .official_issuer_master import original_bytes
   proof=records[0]['issuer_news_receipt']['source_record_archive']['master']
   if is_shared(proof):original_bytes(proof,max_age=MASTER_ORIGINAL_TTL)
   observed=time.time()
   if is_shared(proof)and not current_at(proof,MASTER_ORIGINAL_TTL,observed):raise SourceResponseError('original_expired')
   for record in records:
    for proof in record['issuer_news_receipt']['source_record_archive'].values():
     stamp=proof['retrieved_at']
     if ticker=='2201.TW'and(type(stamp)not in(int,float)or not math.isfinite(stamp)or not 0<=observed-stamp<1800):raise SourceResponseError('original_expired')
   if time.monotonic()>=deadline:raise SourceResponseError('timeout')
  except (OSError,EOFError,KeyError,TypeError,ValueError,OverflowError,UnicodeError,zlib.error,csv.Error,SourceResponseError)as exc:
   records=[];audit.update(status='error',error_kind=getattr(exc,'error_kind','original_unverified'),record_count=0,usable_count=0)
 return records,audit
