"""Complete corporate originals on Chroma's exchange-bound public site."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
import json,math,re,time,zlib
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

TICKER='2360.TW';MASTER=ROSTER_URL;INDEX='https://www.chromaate.com/en/newsroom/news_list'
ARTICLE=re.compile(r'https://www\.chromaate\.com/en/newsroom/news([1-9][0-9]{0,7})\Z')
POLICY='chroma-public-corporate-originals-v1';LEGAL='致茂電子股份有限公司';UBN='09461025'
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
MONTHS={name:i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')
class ChromaHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)
def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _page(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('chroma_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')
def _date(value,*,short=False):
    match=re.fullmatch(r'(\d{2}) ([A-Z][a-z]{2}) (20\d{2})',value)if isinstance(value,str)else None
    try:return date(int(match[3]),{k[:3]:v for k,v in MONTHS.items()}[match[2]],int(match[1]))if match else None
    except (ValueError,KeyError):return None

def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'致茂',today=today)
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='2360']
    if not anchor or len(rows)!=1:raise ValueError('chroma_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN
            or row.get('英文簡稱')!='CHROMA'or row.get('網址')!='http://www.chromaate.com'
            or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('chroma_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'致茂','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'CHROMA',
            'website_host':'www.chromaate.com','market':'TWSE','master_observed_on':published.isoformat(),
            'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def parse_index(raw):
    roots=_page(raw).select('div#news_list_box')
    if len(roots)!=1:raise ValueError('chroma_index_section_invalid')
    cards=roots[0].select(':scope > section.news-list')
    if not 1<=len(cards)<=200:raise ValueError('chroma_index_count_invalid')
    rows,seen=[],{}
    for card in cards:
        links=card.select(':scope > a.w-100[href]')
        if len(links)!=1:raise ValueError('chroma_index_link_invalid')
        link=links[0];titles=link.select(':scope > div.infor > h3.title');stamps=link.select(':scope > p.date')
        if len(titles)!=1 or len(stamps)!=1:raise ValueError('chroma_index_fields_invalid')
        url=str(link['href']);title=_clean(titles[0]);stamp=_clean(stamps[0])
        if not ARTICLE.fullmatch(url)or not 1<=len(title)<=500 or _date(stamp)is None:raise ValueError('chroma_index_route_or_date_invalid')
        row={'title':title,'date_original':stamp,'url':url}
        if url in seen:
            if row!=seen[url]:raise ValueError('chroma_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows


def parse_article(raw,listed):
    soup=_page(raw);url=listed['url']
    if not ARTICLE.fullmatch(url):raise ValueError('chroma_article_route_invalid')
    headers=soup.select('article.wrapper > div.container > section.page-title')
    bodies=soup.select('article.wrapper > div.container > section.page-content > div.txt01')
    canonicals=soup.select('link[rel=canonical]');og_urls=soup.select('meta[property="og:url"]');og_titles=soup.select('meta[property="og:title"]')
    if (len(headers)!=1 or len(bodies)!=1 or len(canonicals)!=1 or canonicals[0].get('href')!=url
            or len(og_urls)!=1 or og_urls[0].get('content')!=url or len(og_titles)!=1 or og_titles[0].get('content')!=listed['title']):raise ValueError('chroma_article_sections_invalid')
    titles=headers[0].select(':scope > h1');stamps=headers[0].select(':scope > p.inner_date > span.day')
    if (len(titles)!=1 or len(stamps)!=1 or _clean(titles[0])!=listed['title']
            or _date(_clean(stamps[0]))!=_date(listed['date_original'])):raise ValueError('chroma_index_article_date_or_title_mismatch')
    ld=[json.loads(s.get_text())for s in soup.select('script[type="application/ld+json"]')]
    if len(ld)!=1 or not isinstance(ld[0],dict):raise ValueError('chroma_publication_metadata_invalid')
    ld=ld[0];day=_date(listed['date_original'])
    if (ld.get('@type')!='Article'or ld.get('@context')!='http://schema.org'or ld.get('URL')!=url
            or ld.get('headline')!=listed['title']or ld.get('author')!={'@type':'Organization','name':'Chroma ATE Inc. | Global'}
            or ld.get('datePublished')!=day.isoformat()or not isinstance(ld.get('articleBody'),str)):
        raise ValueError('chroma_publication_metadata_invalid')
    block=bodies[0]
    if block.find(['script','iframe','object','form']):raise ValueError('chroma_article_body_invalid')
    body=_clean(block)
    if (not 100<=len(body)<=12000 or not re.search(r'(?<!\w)Chroma(?!\w)',body)
            or not 100<=len(_clean(ld['articleBody']))<=500 or not body.startswith(_clean(ld['articleBody']))):raise ValueError('chroma_complete_body_or_issuer_unverified')
    # The visible and structured dates are day precision. Future exhibition
    # dates in the complete body stay future; no completed-event claim is added.
    return _clean(titles[0]),body,{'issuer_article_date':_clean(stamps[0]),'index_card_date':listed['date_original'],
                                'jsonld_datePublished':ld['datePublished'],'date':day.isoformat()}

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('chroma_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('chroma_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('chroma_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('chroma_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'致茂官網','publisher':'Chroma','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':ARTICLE.fullmatch(listed['url'])[1],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','2360'),('official_name','致茂'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'致茂',LEGAL,'chroma'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
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
        return 'Chroma'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or ChromaHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(rows);candidates=[]
        for row in rows:
            day=_date(row['date_original'],short=True);stamp=parse_news_datetime(day.isoformat())
            if day>today:excluded['future']+=1
            elif day<(now-timedelta(days=30)).astimezone(TAIPEI).date():excluded['historical']+=1
            else:candidates.append(row)
        def archive(raw,url):
            component=[c for c in http.components if c.get('url')==url][-1];epoch=component['fetched_at_epoch']
            shared_master=component.get('evidence_kind')==CACHED_MASTER_KIND
            if shared_master:
                if (url!=MASTER or component.get('http_request_sent')is not False or component.get('cache_hit')is not True
                        or component.get('stale')is not False or component.get('http_status_observed')is not False or component.get('http_status')is not None
                        or component.get('cache_source')!='official-company-roster:v2:.TW' or component.get('source_url')!=url
                        or component.get('source_payload_sha256')!=sha256(raw).hexdigest()
                        or type(component.get('source_payload_bytes'))is not int or component['source_payload_bytes']!=len(raw)):
                    raise ValueError('chroma_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
                    raise ValueError('chroma_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('chroma_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_date(v['date_original'],short=True),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('chroma_saved_original_unverified')
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
