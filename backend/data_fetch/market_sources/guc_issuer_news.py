"""Complete, dated GUC press releases on its exchange-bound public website."""
from __future__ import annotations

from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
import json,math,re,time,zlib
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

TICKER='3443.TW';MASTER=ROSTER_URL;INDEX='https://www.guc-asic.com/tw'
LEGAL='創意電子股份有限公司';UBN='16299879';POLICY='guc-public-press-originals-v1'
ROLE_INDEX='https://www.guc-asic.com/tw/news/PressReleases'
ARTICLE=re.compile(r'https://www\.guc-asic\.com/tw/news/PressReleases/([A-Za-z0-9_]{1,80})\Z')
MONTHS={name:i for i,name in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')

class GucHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)

def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()

def _page(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('guc_response_size_invalid')
    return BeautifulSoup(raw.decode('utf-8',errors='strict'),'html.parser')

def _date(value):
    match=re.fullmatch(r'(\d{2}) ([A-Za-z]{3}) (20\d{2})',value)if isinstance(value,str)else None
    try:return date(int(match[3]),MONTHS[match[2].title()],int(match[1]))if match else None
    except (ValueError,KeyError):return None

def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'創意',today=today)
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='3443']
    if not anchor or len(rows)!=1:raise ValueError('guc_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN
            or row.get('英文簡稱')!='GUC'or row.get('網址')!='www.guc-asic.com'
            or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('guc_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'創意','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'GUC',
            'website_host':'www.guc-asic.com','market':'TWSE','master_observed_on':published.isoformat(),
            'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def parse_index(raw):
    soup=_page(raw);sections=soup.select('main section.news')
    urls=soup.select('meta[property="og:url"]')
    if len(sections)!=1 or len(urls)!=1 or urls[0].get('content')!=INDEX:raise ValueError('guc_index_section_invalid')
    cards=sections[0].select('.news-swiper > .swiper-wrapper > .swiper-slide > .item-wrapper > a.news-item[href]')
    if not 1<=len(cards)<=200:raise ValueError('guc_index_count_invalid')
    rows,seen=[],{}
    for card in cards:
        titles=card.select(':scope > .item-content > .item-title-xs > p.des')
        days=card.select(':scope > .item-header > .date > p');months=card.select(':scope > .item-header > .info > .month-year > p.month')
        years=card.select(':scope > .item-header > .info > .month-year > p.year');roles=card.select(':scope > .item-header > .info > span.category')
        if not all(len(x)==1 for x in (titles,days,months,years,roles)):raise ValueError('guc_index_fields_invalid')
        title=_clean(titles[0]);url=card['href'];stamp=' '.join(_clean(v[0])for v in (days,months,years));match=ARTICLE.fullmatch(url)
        if not match or _date(stamp)is None or not 1<=len(title)<=500 or _clean(roles[0])!='新聞稿':raise ValueError('guc_index_route_date_or_role_invalid')
        row={'title':title,'date_original':stamp,'url':url,'category':'新聞稿','original_id':match[1]}
        if url in seen:
            if row!=seen[url]:raise ValueError('guc_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows

def parse_article(raw,listed):
    soup=_page(raw);url=listed['url']
    if not ARTICLE.fullmatch(url):raise ValueError('guc_article_route_invalid')
    articles=soup.select('main section.content .blk[type=article]');og=soup.select('meta[property="og:url"]')
    locales=soup.select('meta[property="og:locale"]');sites=soup.select('meta[property="og:site_name"]')
    if (len(articles)!=1 or len(og)!=1 or og[0].get('content')!=url
            or len(locales)!=1 or locales[0].get('content')!='zh_TW'
            or len(sites)!=1 or sites[0].get('content')!='guc'
            or any(n.get('href')!=url for n in soup.select('link[rel=canonical]'))):raise ValueError('guc_article_sections_invalid')
    article=articles[0];titles=article.select(':scope > .title-wrap > .title > h2.article-title')
    days=article.select(':scope > .title-wrap > .info-content > .date-circle > p.date-text')
    monthyears=article.select(':scope > .title-wrap > .info-content > .group > .year > p.date-text')
    roles=article.select(':scope > .title-wrap > .info-content > .group > .tag-list a.category[href]')
    bodies=article.select(':scope > ._articleBlock')
    if not all(len(v)==1 for v in (titles,days,monthyears,roles,bodies)):raise ValueError('guc_article_fields_invalid')
    stamp=_clean(days[0])+' '+_clean(monthyears[0])
    if (_clean(titles[0])!=listed['title']or _date(stamp)!=_date(listed['date_original'])
            or listed['category']!='新聞稿'or _clean(roles[0])!='新聞稿'or roles[0]['href']!=ROLE_INDEX):raise ValueError('guc_index_article_or_role_mismatch')
    block=bodies[0]
    if block.find(['script','iframe','object','form','video']):raise ValueError('guc_article_body_invalid')
    # Download buttons point to separate attachments, never additional body text.
    for button in block.select('._buttonCover'):button.decompose()
    body=_clean(block)
    if not 100<=len(body)<=12_000 or '創意電子'not in body or re.search(r'(?<!\d)3443\.TWO(?!\w)',body):raise ValueError('guc_article_issuer_or_market_unverified')
    return listed['title'],body,{'issuer_article_date':stamp,'index_card_date':listed['date_original'],'date':_date(stamp).isoformat()}

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('guc_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('guc_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('guc_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('guc_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'創意電子官網','publisher':'GUC','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':listed['original_id'],'article_category':listed['category'],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','3443'),('official_name','創意'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'創意','創意電子',LEGAL,'guc'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
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
        return 'GUC'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or GucHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(rows);candidates=[]
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
                        or component.get('cache_source')!='official-company-roster:v2:.TW' or component.get('source_url')!=url
                        or component.get('source_payload_sha256')!=sha256(raw).hexdigest()
                        or type(component.get('source_payload_bytes'))is not int or component['source_payload_bytes']!=len(raw)):
                    raise ValueError('guc_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('guc_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('guc_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_date(v['date_original']),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('guc_saved_original_unverified')
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
