"""Complete corporate originals on Wiwynn's exchange-bound public site."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
import json,math,re,time,zlib
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

TICKER='6669.TW';MASTER=ROSTER_URL;INDEX='https://www.wiwynn.com/'
ARTICLE=re.compile(r'https://www\.wiwynn\.com/news/([a-z0-9]+(?:-[a-z0-9]+){0,80})\Z')
POLICY='wiwynn-public-corporate-originals-v1';LEGAL='緯穎科技服務股份有限公司';UBN='53687704'
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
MONTHS={name:i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')
class WiwynnHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)
def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _page(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('wiwynn_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')
def _date(value,*,short=False):
    pattern=r'([A-Z][a-z]{2}) (\d{1,2}), (20\d{2})'if short else r'([A-Z][a-z]+) (\d{1,2}), (20\d{2})'
    m=re.fullmatch(pattern,value)if isinstance(value,str)else None
    try:
        months={k[:3]:v for k,v in MONTHS.items()}if short else MONTHS
        return date(int(m[3]),months[m[1]],int(m[2]))if m else None
    except (ValueError,KeyError):return None

def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'緯穎',today=today)
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='6669']
    if not anchor or len(rows)!=1:raise ValueError('wiwynn_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN
            or row.get('英文簡稱')!='Wiwynn'or row.get('網址')!='https://www.wiwynn.com'
            or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('wiwynn_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'緯穎','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'Wiwynn',
            'website_host':'www.wiwynn.com','market':'TWSE','master_observed_on':published.isoformat(),
            'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def parse_index(raw):
    sections=_page(raw).select('#hs_cos_wrapper_widget_1687154120281 .hhs-blog-post-mod')
    if len(sections)!=1:raise ValueError('wiwynn_index_section_invalid')
    cards=sections[0].select(':scope > .container > .row > .col-repeat > .hhs-blog-post-card')
    if not 1<=len(cards)<=200:raise ValueError('wiwynn_index_count_invalid')
    rows,seen=[],{}
    for card in cards:
        links=card.select(':scope > .hhs-post-content > a[href]');stamps=card.select(':scope > .hhs-post-content > .hhs-post-meta > p')
        if len(links)!=1 or len(stamps)!=1:raise ValueError('wiwynn_index_fields_invalid')
        link=links[0];title=_clean(link);url=str(link['href']);stamp=_clean(stamps[0])
        if not ARTICLE.fullmatch(url)or not 1<=len(title)<=500 or _date(stamp,short=True)is None:raise ValueError('wiwynn_index_route_or_date_invalid')
        row={'title':title,'date_original':stamp,'url':url}
        if url in seen:
            if row!=seen[url]:raise ValueError('wiwynn_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows

def parse_article(raw,listed):
    from .issuer_news import TAIPEI
    soup=_page(raw);url=listed['url']
    if not ARTICLE.fullmatch(url):raise ValueError('wiwynn_article_route_invalid')
    headers=soup.select('main#main-content .post-page-full > .blog-header-full .blog-header__inner')
    bodies=soup.select('main#main-content .blog-post__body > span#hs_cos_wrapper_post_body')
    canonicals=soup.select('link[rel=canonical]')
    if len(headers)!=1 or len(bodies)!=1 or len(canonicals)!=1 or canonicals[0].get('href')!=url:raise ValueError('wiwynn_article_sections_invalid')
    h=headers[0];titles=h.select('h1.blog-post__title');stamps=h.select('.blog-post__meta .blog-post__timestamp');authors=h.select('.blog-post__meta .meta-author > a[href]');roles=h.select('.blog-post__tags > a.blog-post__tag-link')
    role_pairs=[(_clean(role),role.get('href'))for role in roles]
    allowed_roles={('Corporate','https://www.wiwynn.com/news/tag/corporate'),
                   ('Events','https://www.wiwynn.com/news/tag/events'),('OCP','https://www.wiwynn.com/news/tag/ocp')}
    if (len(titles)!=1 or len(stamps)!=1 or len(authors)!=1
            or not 1<=len(role_pairs)<=3 or len(set(role_pairs))!=len(role_pairs)
            or not set(role_pairs)<=allowed_roles
            or ('Corporate','https://www.wiwynn.com/news/tag/corporate')not in role_pairs
            or _clean(titles[0])!=listed['title']
            or _clean(authors[0])!='Wiwynn'or authors[0]['href']!='https://www.wiwynn.com/news/author/wiwynn'
            ):raise ValueError('wiwynn_index_article_or_role_mismatch')
    ld=[json.loads(s.get_text())for s in soup.select('script[type="application/ld+json"]')]
    if len(ld)!=1 or not isinstance(ld[0],dict):raise ValueError('wiwynn_publication_metadata_invalid')
    ld=ld[0];published=parse_news_datetime(ld.get('datePublished'))
    if (ld.get('@type')!='BlogPosting'or ld.get('@context')!='https://schema.org'
            or ld.get('mainEntityOfPage')!={'@type':'WebPage','@id':url}or ld.get('headline')!=listed['title']
            or ld.get('publisher',{}).get('name')!='Wiwynn Corporation'
            or ld.get('author')!={'name':'Wiwynn','url':'https://www.wiwynn.com/news/author/wiwynn','@type':'Person'}
            or not isinstance(ld.get('datePublished'),str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',ld['datePublished'])
            or published is None):raise ValueError('wiwynn_publication_metadata_invalid')
    visible=_clean(stamps[0]);index_day=_date(listed['date_original'],short=True)
    dates={'issuer_article_date':visible,'index_card_date':listed['date_original'],
           'jsonld_datePublished':ld['datePublished'],'date':published.isoformat()}
    if visible.startswith('Updated on '):
        # The new captured layout displays the revision date. Bind each day
        # to its own aware timestamp; never promote a revision to publication.
        modified=parse_news_datetime(ld.get('dateModified'))
        if (not isinstance(ld.get('dateModified'),str)
                or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z',ld['dateModified'])
                or modified is None or modified<published
                or published.astimezone(timezone.utc).date()!=index_day
                or _date(visible.removeprefix('Updated on '))!=modified.astimezone(timezone.utc).date()):
            raise ValueError('wiwynn_revision_metadata_invalid')
        dates.update(visible_date_kind='modified',jsonld_dateModified=ld['dateModified'],
                     index_date_comparison='UTC_calendar_date_of_datePublished',
                     visible_date_comparison='UTC_calendar_date_of_dateModified')
    elif (_date(visible)!=index_day or published.astimezone(TAIPEI).date()!=index_day):
        raise ValueError('wiwynn_publication_metadata_invalid')
    block=bodies[0]
    if block.find(['script','iframe','object','form']):raise ValueError('wiwynn_article_body_invalid')
    body=_clean(block)
    if not 100<=len(body)<=12_000 or not re.search(r'(?<!\w)Wiwynn(?!\w)',body)or re.search(r'(?<!\d)6669\.TWO(?!\w)',body):raise ValueError('wiwynn_article_issuer_or_market_unverified')
    return _clean(titles[0]),body,dates

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('wiwynn_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('wiwynn_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('wiwynn_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('wiwynn_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'緯穎官網','publisher':'Wiwynn','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'second','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':ARTICLE.fullmatch(listed['url'])[1],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','6669'),('official_name','緯穎'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if data.get('instrument_type')not in(None,'','EQUITY'):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'緯穎',LEGAL,'wiwynn'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
        proofs=record['issuer_news_receipt']['source_record_archive'];url=record['source_document_url']
        if not ARTICLE.fullmatch(str(url)):return None
        master=_read_original(proofs['master'],MASTER);index=_read_original(proofs['index'],INDEX);article=_read_original(proofs['article'],url)
        identity=_identity(master,today,proofs['master']['retrieved_at']);listed=[row for row in parse_index(index)if row['url']==url]
        if len(listed)!=1:return None
        title,body,dates=parse_article(article,listed[0]);published=parse_news_datetime(dates['date'])
        if any(proofs[k]['retrieved_at']<published.timestamp()for k in ('index','article')):return None
        if ('jsonld_dateModified'in dates
                and proofs['article']['retrieved_at']<parse_news_datetime(dates['jsonld_dateModified']).timestamp()):return None
        expected=_build_record(identity,listed[0],title,body,dates,proofs)
        if (parse_news_datetime(record.get('date'))!=published
                or 'published_date'in record and parse_news_datetime(record['published_date'])!=published
                or any(record.get(k)!=v for k,v in expected.items()if k!='date')):return None
        return 'Wiwynn'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or WiwynnHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
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
                    raise ValueError('wiwynn_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
                    raise ValueError('wiwynn_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('wiwynn_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_date(v['date_original'],short=True),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('wiwynn_saved_original_unverified')
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
