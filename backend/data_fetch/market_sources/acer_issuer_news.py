"""Full dated Acer newsroom stories bound to its exchange-listed company."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
import json,math,re,time,zlib
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

TICKER='2353.TW';MASTER=ROSTER_URL;INDEX='https://news.acer.com/zh'
LEGAL='宏碁股份有限公司';UBN='20828393';POLICY='acer-public-newsroom-originals-v1'
ARTICLE=re.compile(r'https://news\.acer\.com/(hong-qi[a-z0-9-]{1,240})\Z')
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')

class AcerHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)

def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()

def _stamp(value):
    if not isinstance(value,str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)',value):raise ValueError('acer_publication_time_invalid')
    return datetime.fromisoformat(value.replace('Z','+00:00'))

def _page(raw,url):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('acer_response_size_invalid')
    soup=BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')
    if not soup.html or soup.html.get('lang')!='zh-Hant':raise ValueError('acer_language_invalid')
    for selector,attr,expected in [('link[rel=canonical]','href',url),('meta[property="og:site_name"]','content','Acer'),('meta[property="og:locale"]','content','zh_Hant')]:
        nodes=soup.select(selector)
        if len(nodes)!=1 or nodes[0].get(attr)!=expected:raise ValueError('acer_page_metadata_invalid')
    og_urls=soup.select('meta[property="og:url"]')
    if (url!=INDEX and len(og_urls)!=1 or len(og_urls)>1
            or any(n.get('content')!=url for n in og_urls)):raise ValueError('acer_page_url_invalid')
    objects=[json.loads(n.get_text())for n in soup.select('script[type="application/ld+json"]')]
    if any(not isinstance(n,dict)for n in objects):raise ValueError('acer_structured_metadata_invalid')
    owners=[n for n in objects if n.get('@type')=='Organization']
    if len(owners)!=1 or owners[0].get('name')!='宏碁公司'or owners[0].get('url')!='https://news.acer.com/':raise ValueError('acer_newsroom_owner_invalid')
    # The exact listed website and the fixed newsroom share the acer.com domain.
    if not any(a.get('href')in ('https://www.acer.com','https://www.acer.com/')and _clean(a)=='www.acer.com'for a in soup.select('a[href]')):raise ValueError('acer_registered_website_link_missing')
    return soup,objects

def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'宏碁',today=today)
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='2353']
    if not anchor or len(rows)!=1:raise ValueError('acer_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN
            or row.get('英文簡稱')!='ACER'or row.get('網址')!='http://www.acer.com'
            or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('acer_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'宏碁','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'ACER',
            'website_host':'www.acer.com','newsroom_host':'news.acer.com','market':'TWSE','master_observed_on':published.isoformat(),
            'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def parse_index(raw):
    soup,_=_page(raw,INDEX);cards=soup.select('main div.StoryCard_container__MsB7x')
    if not 1<=len(cards)<=200:raise ValueError('acer_index_count_invalid')
    rows,seen=[],{}
    for card in cards:
        titles=card.select('h2.StoryCard_title__6k9Zr');dates=card.select('time[datetime]');links=card.select('a.StoryCard_linkOverlay__9ats1[href]')
        if not len(titles)==len(dates)==len(links)==1:raise ValueError('acer_index_fields_invalid')
        title=_clean(titles[0]);url=urljoin(INDEX,links[0]['href']);match=ARTICLE.fullmatch(url);stamp=dates[0]['datetime'];published=_stamp(stamp)
        if (not match or not 1<=len(title)<=500 or '宏碁'not in title or _clean(links[0].get('aria-label'))!=title
                or _clean(dates[0])!=published.strftime('%m/%d/%Y')):raise ValueError('acer_index_route_date_or_title_invalid')
        row={'title':title,'date_original':stamp,'visible_date':_clean(dates[0]),'url':url,'category':'newsroom_story','original_id':match[1]}
        if url in seen:
            if row!=seen[url]:raise ValueError('acer_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows

def parse_article(raw,listed):
    url=listed['url']
    if not ARTICLE.fullmatch(url):raise ValueError('acer_article_route_invalid')
    soup,objects=_page(raw,url);articles=soup.select('main > div.Story_container__mieav > article');metas=[n for n in objects if n.get('@type')=='NewsArticle']
    if len(articles)!=1 or len(metas)!=1:raise ValueError('acer_article_sections_invalid')
    article=articles[0];meta=metas[0];titles=article.select('h1');dates=article.select('time[datetime]');bodies=article.select(':scope > div.ContentRenderer_renderer__IBbst')
    if not len(titles)==len(dates)==len(bodies)==1:raise ValueError('acer_article_fields_invalid')
    stamp=dates[0]['datetime'];published=_stamp(stamp);modified=_stamp(meta.get('dateModified'));publisher=meta.get('publisher')
    if (_clean(titles[0])!=listed['title']or _clean(meta.get('headline'))!=listed['title']or _stamp(listed['date_original'])!=published
            or _stamp(meta.get('datePublished'))!=published or modified<published or _clean(dates[0])!=listed['visible_date']
            or meta.get('url')!=url or meta.get('mainEntityOfPage')!={'@type':'WebPage','@id':url}
            or meta.get('inLanguage')!='zh-Hant'or not isinstance(publisher,dict)
            or publisher.get('@type')!='Organization'or publisher.get('name')!='宏碁公司'or publisher.get('url')!='https://news.acer.com/'
            or listed['category']!='newsroom_story'):raise ValueError('acer_index_article_metadata_mismatch')
    block=bodies[0]
    if block.find(['script','iframe','object','form','video']):raise ValueError('acer_article_body_invalid')
    body=_clean(block)
    if not 100<=len(body)<=12_000 or '宏碁'not in body or re.search(r'(?<!\d)2353\.TWO(?!\w)',body):raise ValueError('acer_article_issuer_or_market_unverified')
    return listed['title'],body,{'issuer_article_time':stamp,'index_card_time':listed['date_original'],'visible_date':listed['visible_date'],
                                'published':published.isoformat(),'modified':modified.isoformat()}

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('acer_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('acer_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('acer_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('acer_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['published'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'宏碁官方新聞室','publisher':'ACER','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'second','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':listed['original_id'],'article_category':listed['category'],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','2353'),('official_name','宏碁'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'宏碁','宏碁公司',LEGAL,'acer'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
        proofs=record['issuer_news_receipt']['source_record_archive'];url=record['source_document_url']
        if not ARTICLE.fullmatch(str(url)):return None
        master=_read_original(proofs['master'],MASTER);index=_read_original(proofs['index'],INDEX);article=_read_original(proofs['article'],url)
        identity=_identity(master,today,proofs['master']['retrieved_at']);listed=[row for row in parse_index(index)if row['url']==url]
        if len(listed)!=1:return None
        title,body,dates=parse_article(article,listed[0]);published=_stamp(dates['published'])
        if any(proofs[k]['retrieved_at']<published.timestamp()for k in ('index','article'))or proofs['article']['retrieved_at']<_stamp(dates['modified']).timestamp():return None
        expected=_build_record(identity,listed[0],title,body,dates,proofs)
        if (parse_news_datetime(record.get('date'))!=published
                or 'published_date'in record and parse_news_datetime(record['published_date'])!=published
                or any(record.get(k)!=v for k,v in expected.items()if k!='date')):return None
        return 'ACER'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or AcerHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(rows);candidates=[]
        for row in rows:
            published=_stamp(row['date_original'])
            if published>now:excluded['future']+=1
            elif published<now-timedelta(days=30):excluded['historical']+=1
            else:candidates.append(row)
        def archive(raw,url):
            component=[c for c in http.components if c.get('url')==url][-1];epoch=component['fetched_at_epoch'];shared_master=component.get('evidence_kind')==CACHED_MASTER_KIND
            if shared_master:
                if (url!=MASTER or component.get('http_request_sent')is not False or component.get('cache_hit')is not True
                        or component.get('stale')is not False or component.get('http_status_observed')is not False or component.get('http_status')is not None
                        or component.get('cache_source')!='official-company-roster:v2:.TW' or component.get('source_url')!=url
                        or component.get('source_payload_sha256')!=sha256(raw).hexdigest()
                        or type(component.get('source_payload_bytes'))is not int or component['source_payload_bytes']!=len(raw)):
                    raise ValueError('acer_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('acer_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('acer_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_stamp(v['date_original']),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=_stamp(dates['published'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('acer_saved_original_unverified')
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
