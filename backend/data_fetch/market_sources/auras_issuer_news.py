"""Complete Auras public CMS news with independent issuer and article-date replay."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
import json,math,re,time,zlib
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp
from .auras_monthly_history import _json,_master_anchor
TICKER='3324.TWO';LEGAL='雙鴻科技股份有限公司';UBN='16619628'
MASTER='https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O'
INDEX='https://www.auras.com.tw/CmsApi/api/Announcement/getAnnouncementListAsync?Keyword=&IsFront=true&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=announcementStartDate&IsDesc=true'
ARTICLE_BASE='https://www.auras.com.tw/CmsApi/api/Announcement/getAnnouncementAsync?AnnouncementId='
ARTICLE_TAIL='&Keyword=&IsFront=true&IsPage=false&CurrentPage=1&PageSize=10&OrderBy=&IsDesc=true'
ARTICLE=re.compile(re.escape(ARTICLE_BASE)+r'([1-9]\d{0,7})'+re.escape(ARTICLE_TAIL)+r'\Z')
POLICY='auras-public-news-originals-v1'
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 1_000_000,{'application/json','text/json'}
    raise SourceResponseError('transport_url_invalid')

class AurasNewsHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)

def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()

def _date(value):
    try:return date.fromisoformat(value.replace('/','-')) if isinstance(value,str)and re.fullmatch(r'20\d{2}/\d{2}/\d{2}',value)else None
    except ValueError:return None

def _identity(raw,today,epoch):
    from .issuer_news import TAIPEI
    anchor=_master_anchor(raw,today=today)
    if date.fromisoformat(anchor['as_of'])>datetime.fromtimestamp(epoch,TAIPEI).date():raise ValueError('auras_news_master_future')
    return {'ticker':TICKER,'short_name':'雙鴻','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'Auras',
        'website_host':'www.auras.com.tw','market':'TPEx','master_observed_on':anchor['as_of'],
        'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def _rows(raw):
    root=_json(raw)
    if (not isinstance(root,dict)or root.get('status')is not True or root.get('errorMessage')not in(None,'')
        or not isinstance(root.get('infos'),list)or type(root.get('totalCount'))is not int
        or root['totalCount']!=len(root['infos'])or not 1<=len(root['infos'])<=100):raise ValueError('auras_news_response_invalid')
    return root['infos']

def parse_index(raw):
    out=[];seen=set()
    for row in _rows(raw):
        number=row.get('announcementId');title=(row.get('eng')or{}).get('title');day=_date(row.get('announcementStartDate'));created=_date(row.get('createDate'))
        if type(number)is not int or not 0<number<100000000 or number in seen or not isinstance(title,str)or not title.strip()or day is None or created is None:raise ValueError('auras_news_index_identity_invalid')
        seen.add(number)
        # CMS probe labels are not public business news. Do not request or count them.
        if re.search(r'(?i)SSTI|RCE_|Probe_',title):continue
        out.append({'original_id':number,'url':ARTICLE_BASE+str(number)+ARTICLE_TAIL,'title':title,
                    'date_original':row['announcementStartDate'],'create_date_original':row['createDate'],'category':'issuer_statement'})
    return out

def parse_article(raw,listed):
    rows=_rows(raw)
    if len(rows)!=1:raise ValueError('auras_news_article_not_unique')
    row=rows[0];eng=row.get('eng')or{}
    if (type(row.get('announcementId'))is not int or row.get('announcementId')!=listed['original_id']or row.get('announcementStartDate')!=listed['date_original']
        or row.get('createDate')!=listed['create_date_original']or eng.get('title')!=listed['title']
        or not isinstance(eng.get('content'),str)):raise ValueError('auras_news_article_binding_invalid')
    soup=BeautifulSoup(eng['content'],'html.parser')
    if soup.find(['script','iframe','form']):raise ValueError('auras_news_article_active_content')
    body=_clean(soup.get_text(' ',strip=True))
    if not 500<=len(body)<=50000 or LEGAL not in body or not re.search(r'Auras\s*\(3324\)',body,re.I):raise ValueError('auras_news_article_issuer_or_body_invalid')
    datelines=re.findall(r'\bDate:\s*(20\d{2}/\d{2}/\d{2})\b',body)
    if len(datelines)!=1 or _date(datelines[0])is None:raise ValueError('auras_news_article_date_unverified')
    published=_date(datelines[0])
    if published<max(_date(listed['date_original']),_date(listed['create_date_original'])):raise ValueError('auras_news_article_date_conflict')
    cn=(row.get('tcn')or{}).get('content')
    if isinstance(cn,str)and cn:
        dates=re.findall(r'日期[：:]\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',_clean(BeautifulSoup(cn,'html.parser').get_text(' ',strip=True)))
        if len(dates)!=1 or date(*map(int,dates[0]))!=published:raise ValueError('auras_news_article_language_date_conflict')
    dates={'date':published.isoformat()+'T00:00:00+08:00','article_dateline':datelines[0],
        'index_display_start':listed['date_original'],'cms_create_date':listed['create_date_original'],
        'publication_date_basis':'issuer_article_dateline','first_available_time_verified':False,
        'event_occurrence_verified':False}
    return listed['title'],body,dates

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TWO'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('auras_news_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('auras_news_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('auras_news_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('auras_news_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'雙鴻科技官網','publisher':'Auras','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':listed['original_id'],'article_category':listed['category'],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','3324'),('official_name','雙鴻'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'雙鴻','雙鴻科技',LEGAL,'auras'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
        proofs=record['issuer_news_receipt']['source_record_archive'];url=record['source_document_url']
        if not ARTICLE.fullmatch(str(url)):return None
        master=_read_original(proofs['master'],MASTER);index=_read_original(proofs['index'],INDEX);article=_read_original(proofs['article'],url)
        identity=_identity(master,today,proofs['master']['retrieved_at']);listed=[row for row in parse_index(index)if row['url']==url]
        if len(listed)!=1:return None
        title,body,dates=parse_article(article,listed[0]);published=parse_news_datetime(dates['date'])
        if any(proofs[k]['retrieved_at']<published.timestamp()for k in ('index','article')):return None
        expected=_build_record(identity,listed[0],title,body,dates,proofs)
        if (parse_news_datetime(record.get('date'))!=published
                or 'published_date'in record and parse_news_datetime(record['published_date'])!=published
                or any(record.get(k)!=v for k,v in expected.items()if k!='date')):return None
        return 'Auras'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or AurasNewsHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(_rows(index_raw));excluded['non_business_probe_index']=audit['raw_count']-len(rows);candidates=[]
        for row in rows:
            day=_date(row['date_original'])
            if day>today:excluded['future']+=1
            elif day<(now-timedelta(days=30)).astimezone(TAIPEI).date():excluded['historical']+=1
            else:candidates.append(row)
        def archive(raw,url):
            component=[c for c in http.components if c.get('url')==url][-1];epoch=component['fetched_at_epoch'];shared_master=component.get('evidence_kind')==CACHED_MASTER_KIND
            if shared_master:
                if (url!=MASTER or component.get('http_request_sent')is not False or component.get('cache_hit')is not True
                        or component.get('stale')is not False or component.get('http_status_observed')is not False or component.get('http_status')is not None
                        or component.get('cache_source')!='official-company-roster:v2:.TWO' or component.get('source_url')!=url
                        or component.get('source_payload_sha256')!=sha256(raw).hexdigest()
                        or type(component.get('source_payload_bytes'))is not int or component['source_payload_bytes']!=len(raw)):
                    raise ValueError('auras_news_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('auras_news_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('auras_news_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_date(v['date_original']),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('auras_news_saved_original_unverified')
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            records.append(record)
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        audit['status']='success'if records else'unavailable'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError)as exc:
        audit.update(status='degraded_enrichment'if records else'error',error_kind=getattr(exc,'error_kind','parse_error'),error_message=str(exc)[:150])
    components=getattr(http,'components',[]);sent=getattr(http,'http_request_count',0);cached=bool(components)and all(c.get('cache_hit')for c in components)
    if audit['status']=='success'and cached and not sent:audit['status']='skipped_fresh_cache'
    epochs=[c['fetched_at_epoch']for c in components if type(c.get('fetched_at_epoch'))in(int,float)]
    audit.update(http_request_sent=bool(sent),http_request_count=sent,event_kind='http_request'if sent else'cache_hit'if cached else'local_block',cache_hit=cached,stale=False,
        record_count=len(records),usable_count=len(records),fetched_at_epoch=min(epochs)if epochs else None,parser_version=POLICY,excluded_reason_counts=dict(excluded),component_receipts=components)
    return records,audit
