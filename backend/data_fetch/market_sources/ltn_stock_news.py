"""Bounded public LTN search and original articles; publication evidence stays separate."""
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from hashlib import sha256
from copy import deepcopy
from types import SimpleNamespace
from urllib.parse import urlencode,urlsplit,parse_qs
import base64,json,re,time,os,math
from bs4 import BeautifulSoup
from bounded_curl_process import collect_capped_process
from news_record_utils import clean_text,parse_news_datetime

PROVIDER='自由財經'
POLICY='ltn-stock-original-v1'
BASIS='verified_ltn_publisher_original'
MAX_BYTES=1_000_000
MAX_CANDIDATES=5
MAX_RECORDS=3
MAX_SECONDS=10
ARTICLE=re.compile(r'https://ec\.ltn\.com\.tw/article/breakingnews/[0-9]{6,10}\Z')
TAIPEI=ZoneInfo('Asia/Taipei')


def _finite_number(value):
    try:return type(value) in (int,float) and math.isfinite(value)
    except (OverflowError,TypeError,ValueError):return False


def _basic_identity(data):
    identity=data.get('company_identity')
    ticker=data.get('ticker')
    if not isinstance(identity,dict) or not isinstance(ticker,str) or not re.fullmatch(r'[0-9]{4}\.(TW|TWO)',ticker):
        return None
    code=ticker.split('.')[0]
    if (identity.get('ticker')!=ticker or identity.get('stock_id')!=code or identity.get('instrument_type')!='EQUITY'
            or not isinstance(identity.get('official_name'),str) or not identity['official_name'].strip()
            or identity.get('legal_name') is not None and not isinstance(identity.get('legal_name'),str)):
        return None
    return ticker,code


def _today():
    return datetime.now(TAIPEI).date()


def _identity(data,anchor=None):
    identity=_basic_identity(data)
    if not identity:return None
    company=data['company_identity'];legal=company.get('legal_name')
    if anchor is None:return identity if isinstance(legal,str) and legal.strip() else None
    from .official_company_legal_name import verified_legal_name_from_evidence
    try:
        epoch=anchor.get('fetched_at_epoch') if isinstance(anchor,dict) else None
        if not _finite_number(epoch) or not 0<epoch<=time.time():return None
        verified=verified_legal_name_from_evidence(anchor,identity[0],company['official_name'])
        observed=datetime.fromisoformat(anchor.get('as_of')).date()
        if (not verified or not 0<=(_today()-observed).days<=14
                or legal and legal.strip()!=verified):return None
        return identity
    except (TypeError,ValueError,AttributeError,OverflowError):return None


def _load_anchor(data,*,deadline,now,diagnostics):
    """Read an exact official issuer row within the existing publisher budget."""
    from .official_company_legal_name import URLS,parse_roster,select_legal_name
    from .issuer_news_transport import IssuerNewsHttp
    from official_response_evidence import archive_response
    class CompanyRosterHttp(IssuerNewsHttp):
        @staticmethod
        def route_contract(url):
            if url in URLS.values():return 2_500_000,{'application/json','text/json'}
            raise ValueError('Unknown official issuer roster URL')
    ticker=data['ticker'];suffix='.TWO' if ticker.endswith('.TWO') else '.TW'
    http=CompanyRosterHttp(deadline);diag={'transport_attempts':0,'components':http.components}
    diagnostics['official_issuer_anchor']=diag
    try:
        raw=http.get(URLS[suffix])
        anchor=select_legal_name(parse_roster(raw,suffix),ticker,data['company_identity']['official_name'],today=now.astimezone(TAIPEI).date())
        if not anchor:return None
        anchor={**anchor,'fetched_at_epoch':http.components[-1].get('fetched_at_epoch'),'stale':False}
        if not _identity(data,anchor):return None
        receipt=archive_response(raw,source_url=URLS[suffix],retrieved_at=anchor['fetched_at_epoch'],http_status=200)
        if receipt.get('status')!='archived':return None
        diag.update(response_sha256=anchor['response_sha256'],as_of=anchor['as_of'])
        return anchor
    finally:diag['transport_attempts']=http.http_request_count


def _digest(record):
    fields={k:record.get(k) for k in ('title','summary','text','date','source','link','source_type','publication_date_original','response_sha256','response_bytes','issuer_evidence_basis','content_truncated','impact_status')}
    fields['index_response_sha256']=(record.get('ltn_original_receipt') or {}).get('index_response_sha256')
    for key in ('official_issuer_anchor','index_publication_hint'):
        if key in (record.get('ltn_original_receipt') or {}):fields[key]=record['ltn_original_receipt'][key]
    stamp=parse_news_datetime(fields['date']);fields['date']=stamp.isoformat() if stamp else None
    return sha256(json.dumps(fields,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def verified_ltn_record(record,data):
    try:
        receipt=record.get('ltn_original_receipt')
        identity=_identity(data,receipt.get('official_issuer_anchor') if isinstance(receipt,dict) else None)
        if not identity or not isinstance(receipt,dict):return None
        ticker,code=identity
        hint=receipt.get('index_publication_hint')
        if hint is not None and (not isinstance(hint,dict) or hint.get('precision')!='relative_discovery_only'
                                 or not re.fullmatch(r'[12]天前',str(hint.get('value') or ''))):return None
        stamp=parse_news_datetime(record.get('date'))
        if (receipt.get('policy')!=POLICY or receipt.get('ticker')!=ticker
                or record.get('source_type')!='publisher_original_news' or record.get('source')!=PROVIDER
                or record.get('issuer_evidence_basis')!=BASIS or record.get('content_truncated') is not False
                or record.get('impact_status')!='not_assessed'
                or not ARTICLE.fullmatch(str(record.get('link') or ''))
                or type(record.get('response_bytes')) is not int or not 0<record['response_bytes']<=MAX_BYTES
                or not re.fullmatch(r'[0-9a-f]{64}',str(record.get('response_sha256') or ''))
                or receipt.get('article_response_sha256')!=record['response_sha256']
                or not re.fullmatch(r'[0-9a-f]{64}',str(receipt.get('index_response_sha256') or ''))
                or not isinstance(record.get('title'),str) or not 1<=len(record['title'])<=300
                or not isinstance(record.get('text'),str) or not 40<=len(record['text'])<=6000
                or not isinstance(record.get('summary'),str) or record['summary']!=record['text'][:400]
                or stamp is None or receipt.get('parsed_content_sha256')!=_digest(record)
                or not re.search(r'[（(]\s*'+code+r'\s*[)）]',record['text'])):return None
        from source_content_selection import issuer_match
        plain={k:v for k,v in record.items() if k not in {'ltn_original_receipt','issuer_evidence_basis'}}
        plain['source_type']='publisher_record_verification'
        return issuer_match(plain,data)
    except (TypeError,ValueError,KeyError,AttributeError,OverflowError):return None


def parse_listing(raw,code,*,now):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:return []
    soup=BeautifulSoup(raw,'html.parser')
    title=soup.title.get_text(' ',strip=True) if soup.title else ''
    if title!=f'{code} - 全域查詢 - 自由時報電子報':return []
    lists=soup.select('section.Searchnews ul.list.boxTitle')
    if len(lists)!=1:return []
    rows=[];seen=set()
    for li in lists[0].find_all('li',recursive=False):
        links=li.select(':scope > div.cont > a.tit[href]');dates=li.select(':scope > div.cont > span.time')
        if len(links)!=1 or len(dates)!=1:continue
        url=links[0].get('href');day=dates[0].get_text(' ',strip=True);heading=links[0].get_text(' ',strip=True)
        if not isinstance(url,str) or not ARTICLE.fullmatch(url) or url in seen or not 1<=len(heading)<=300:continue
        if re.fullmatch(r'[12]天前',day):
            candidate={'url':url,'title':heading,'day':None,'relative_date_hint':day}
        else:
            try:published=datetime.strptime(day,'%Y/%m/%d').date()
            except ValueError:continue
            if not (now.astimezone(TAIPEI)-timedelta(days=30)).date()<=published<=now.astimezone(TAIPEI).date():continue
            candidate={'url':url,'title':heading,'day':day}
        seen.add(url);rows.append(candidate)
        if len(rows)>=MAX_CANDIDATES:break
    return rows


def parse_article(raw,candidate,data,*,now,index_hash,issuer_anchor=None):
    identity=_identity(data,issuer_anchor)
    if not identity or not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:return None
    ticker,code=identity;url=candidate['url']
    if not ARTICLE.fullmatch(url):return None
    soup=BeautifulSoup(raw,'html.parser')
    def meta(name):
        nodes=soup.head.find_all('meta',attrs={'property':name},recursive=False) if soup.head else []
        values=[v.get('content') for v in nodes]
        return values[0] if values and all(isinstance(v,str) and v==values[0] for v in values) else None
    if meta('og:url')!=url:return None
    containers=[v for v in soup.select('div.whitecon.boxText') if 'template' not in v.get('class',[])]
    if len(containers)!=1:return None
    box=containers[0];titles=box.select(':scope > h1');clocks=box.select(':scope > div.function > span.time');bodies=box.select(':scope > div.text')
    if len(titles)!=1 or len(clocks)!=1 or len(bodies)!=1:return None
    title=titles[0].get_text(' ',strip=True);original=meta('article:published_time');stamp=parse_news_datetime(original)
    try:
        if not isinstance(original,str) or datetime.fromisoformat(original).tzinfo is None:return None
    except ValueError:return None
    if (title!=candidate['title'] or meta('og:title')!=title+' - 自由財經' or stamp is None
            or not isinstance(original,str) or stamp.tzinfo is None
            or not timedelta(0)<=now-stamp<=timedelta(days=30)
            or clocks[0].get_text(' ',strip=True)!=stamp.astimezone(TAIPEI).strftime('%Y/%m/%d %H:%M')):return None
    if candidate.get('day') is not None:
        if stamp.astimezone(TAIPEI).strftime('%Y/%m/%d')!=candidate['day']:return None
    elif not re.fullmatch(r'[12]天前',str(candidate.get('relative_date_hint') or '')):return None
    paragraphs=[]
    for p in bodies[0].find_all('p',recursive=False):
        if set(p.get('class') or [])&{'before_ir','after_ir','appE1121'}:continue
        clone=deepcopy(p)
        for node in clone.select('.ph_b,img,script,style'):node.decompose()
        text=clean_text(clone.get_text(' ',strip=True))
        if text and not text.startswith('一手掌握經濟脈動'):paragraphs.append(text)
    body='\n'.join(paragraphs)
    if not 40<=len(body)<=6000 or not re.search(r'[（(]\s*'+code+r'\s*[)）]',body):return None
    record={'title':title,'summary':body[:400],'text':body,'date':stamp.isoformat(),'source':PROVIDER,'link':url,
            'source_type':'publisher_original_news','publication_date_original':{'article:published_time':original},
            'response_sha256':sha256(raw).hexdigest(),'response_bytes':len(raw),'content_truncated':False,
            'impact_status':'not_assessed','issuer_evidence_basis':BASIS}
    record['ltn_original_receipt']={'policy':POLICY,'ticker':ticker,'index_response_sha256':index_hash,
                                  'article_response_sha256':record['response_sha256']}
    if issuer_anchor is not None:record['ltn_original_receipt']['official_issuer_anchor']=deepcopy(issuer_anchor)
    if candidate.get('relative_date_hint'):
        record['ltn_original_receipt']['index_publication_hint']={'value':candidate['relative_date_hint'],'precision':'relative_discovery_only'}
    record['ltn_original_receipt']['parsed_content_sha256']=_digest(record)
    return record if verified_ltn_record(record,data) else None


def _read(url,*,deadline,diagnostics):
    if not _url_allowed(url):raise ValueError('Unknown publisher URL')
    if os.getenv('STOCK_AGENT_TEST_NO_NETWORK')=='1':
        raise RuntimeError('Isolated tests cannot contact the original publisher')
    from shared_provider_cache import shared_fetch
    from search_provider_runtime import SourceResponseError,cooldown_state,remember_failure,scope_key
    key=scope_key('LTN public originals',endpoint='public_html')
    def download():
        blocked=cooldown_state(key)
        if blocked:raise SourceResponseError('cooldown')
        remaining=min(3.0,deadline-time.monotonic())
        if remaining<.1:raise TimeoutError('Original publisher acquisition deadline exhausted')
        argv=['/usr/bin/curl','--disable','--silent','--show-error','--fail-with-body','--max-time',str(remaining),'--connect-timeout',str(min(1.5,remaining)),'--max-filesize',str(MAX_BYTES),'--proto','=https','--max-redirs','0','--retry','0','--dump-header','/dev/fd/{HEADER_FD}',url]
        parts,rc,error=collect_capped_process(argv,min(deadline,time.monotonic()+remaining+.1),body_limit=MAX_BYTES,headers=True)
        codes=re.findall(rb'(?m)^HTTP/[^ ]+ ([0-9]{3})',parts['headers']);status=int(codes[-1]) if codes else None
        started=parts.get('process_started') is True
        if not started:status=None
        diagnostics['transport_attempts']=diagnostics.get('transport_attempts',0)+int(started)
        diagnostics['http_requests']+=int(started and status is not None)
        if not started or error or rc!=0 or status!=200 or not parts['body']:
            kind={401:'authentication',402:'payment_required',403:'access_denied',429:'rate_limited'}.get(status,'server_error' if status and status>=500 else 'timeout' if error=='timeout' else 'transport_error')
            diagnostics['transport_failures'].append({'url':url,'http_status':status,'error_kind':kind,'http_request_sent':True if started and status is not None else None if started else False})
            exc=SourceResponseError(kind,status_code=status,response_text=parts['body'].decode(errors='replace')[:2000])
            retry=re.findall(rb'(?im)^Retry-After:\s*([^\r\n]+)',parts['headers'])
            exc.response=SimpleNamespace(status_code=status,headers={'Retry-After':retry[-1].decode('ascii',errors='replace').strip()} if retry else {})
            remember_failure(key,exc);raise exc
        from official_response_evidence import archive_response
        receipt=archive_response(parts['body'],source_url=url,retrieved_at=time.time(),http_status=status)
        return {'body_b64':base64.b64encode(parts['body']).decode(),'sha256':sha256(parts['body']).hexdigest(),'raw_receipt':receipt}
    value,meta=shared_fetch('ltn-public-raw:v1:'+url,download,freshness_seconds=1800,retention_seconds=1800,lock_wait_seconds=.1,error_retry_seconds=120)
    if not isinstance(value,dict) or meta.get('stale') or meta.get('error_kind'):raise SourceResponseError(str(meta.get('error_kind') or 'parse_error'))
    epoch=meta.get('fetched_at_epoch')
    if not _finite_number(epoch) or epoch<=0 or not 0<=time.time()-epoch<=1800:
        raise SourceResponseError('parse_error')
    raw=base64.b64decode(value['body_b64'],validate=True)
    if not 0<len(raw)<=MAX_BYTES or sha256(raw).hexdigest()!=value['sha256']:raise SourceResponseError('parse_error')
    diagnostics['raw_reads'].append({'url':url,'cache_hit':bool(meta.get('cache_hit')),'fetched_at_epoch':meta.get('fetched_at_epoch'),'response_sha256':value['sha256'],'response_bytes':len(raw)})
    return raw


def _url_allowed(url):
    if not isinstance(url,str):return False
    if ARTICLE.fullmatch(url):return True
    try:
        p=urlsplit(url);q=parse_qs(p.query,strict_parsing=True)
        if (p.scheme!='https' or p.netloc!='search.ltn.com.tw' or p.path!='/list' or p.fragment
                or set(q)!={'keyword','type','sort','start_time','end_time'}
                or any(len(v)!=1 for v in q.values()) or q['type']!=['business'] or q['sort']!=['date']
                or not re.fullmatch(r'[0-9]{4}',q['keyword'][0])):return False
        start=datetime.strptime(q['start_time'][0],'%Y%m%d');end=datetime.strptime(q['end_time'][0],'%Y%m%d')
        return timedelta(0)<=end-start<=timedelta(days=30)
    except (ValueError,KeyError,TypeError):return False


def fetch_ltn_stock_news(data,*,deadline,diagnostics=None,now=None,max_records=MAX_RECORDS):
    from search_admission import endpoint_admission
    from search_provider_runtime import scope_key
    diag=diagnostics if diagnostics is not None else {}
    if type(max_records) is not int or not 1<=max_records<=MAX_RECORDS:
        diag['status']='invalid_record_limit';return []
    if not _finite_number(deadline):
        diag['status']='invalid_deadline';return []
    if not _basic_identity(data):diag['status']='issuer_identity_unverified';return []
    seconds=min(MAX_SECONDS,deadline-time.monotonic())
    if seconds<.1:diag['status']='deadline_exhausted';return []
    with endpoint_admission(scope_key('LTN public originals',endpoint='public_html'),timeout_seconds=seconds) as owns:
        if owns is None:diag['status']='single_flight_busy';return []
        return _acquire(data,deadline=deadline,diagnostics=diag,now=now,owns=owns,max_records=max_records)


def _acquire(data,*,deadline,diagnostics=None,now=None,owns=lambda:True,max_records=MAX_RECORDS):
    diag=diagnostics if diagnostics is not None else {};diag.update(policy=POLICY,http_requests=0,raw_reads=[],transport_failures=[],rejected_count=0)
    identity=_basic_identity(data)
    if not identity:diag['status']='issuer_identity_unverified';return []
    now=now or datetime.now(timezone.utc);deadline=min(deadline,time.monotonic()+MAX_SECONDS)
    if deadline-time.monotonic()<.1:diag['status']='deadline_exhausted';return []
    ticker,code=identity;upper=now.astimezone(TAIPEI).date();lower=(now-timedelta(days=30)).astimezone(TAIPEI).date()
    url='https://search.ltn.com.tw/list?'+urlencode({'keyword':code,'type':'business','sort':'date','start_time':lower.strftime('%Y%m%d'),'end_time':upper.strftime('%Y%m%d')})
    records=[]
    try:
        if not owns():diag['status']='lease_lost';return []
        anchor=None
        if not _identity(data):
            anchor=_load_anchor(data,deadline=deadline,now=now,diagnostics=diag)
            if not anchor:diag['status']='issuer_identity_unverified';return []
            if not owns():diag['status']='lease_lost';return []
            if time.monotonic()>=deadline:diag['status']='deadline_exhausted';return []
        raw=_read(url,deadline=deadline,diagnostics=diag);candidates=parse_listing(raw,code,now=now);diag['candidate_count']=len(candidates)
        for candidate in candidates:
            if not owns():diag['status']='lease_lost';break
            if deadline-time.monotonic()<.1:diag['status']='deadline_exhausted';break
            article=_read(candidate['url'],deadline=deadline,diagnostics=diag)
            record=parse_article(article,candidate,data,now=now,index_hash=sha256(raw).hexdigest(),issuer_anchor=anchor)
            if not owns():diag['status']='lease_lost';break
            if time.monotonic()>=deadline:diag['status']='deadline_exhausted';break
            if record:records.append(record)
            else:diag['rejected_count']+=1
            if len(records)>=max_records:break
        diag.setdefault('status','records_received' if records else 'no_eligible_records')
    except (ValueError,KeyError,TypeError,RuntimeError,TimeoutError) as exc:
        diag.update(status='partial' if records else 'unavailable',error_kind=getattr(exc,'error_kind',type(exc).__name__))
    diag['record_count']=len(records)
    return records
