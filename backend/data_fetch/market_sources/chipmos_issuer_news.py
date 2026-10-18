"""Full public ChipMOS press originals with exchange and published-index identity."""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta
from hashlib import sha256
from urllib.parse import urljoin
import json,math,re,time,zlib
from bs4 import BeautifulSoup
from news_record_utils import clean_text,parse_news_datetime
from official_response_evidence import archive_response,read_response
from search_provider_runtime import SourceResponseError
from .issuer_news_transport import IssuerNewsHttp,ROSTER_URL

TICKER='8150.TW';MASTER=ROSTER_URL;INDEX='https://www.chipmos.com/chinese/news/news-list.aspx?MID=1'
LEGAL='南茂科技股份有限公司';UBN='16130042';POLICY='chipmos-public-published-news-originals-v1'
ARTICLE=re.compile(r'https://www\.chipmos\.com/chinese/news/news-detail\.aspx\?NID=([1-9]\d{0,7})\Z')
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
MONTHS={name:i for i,name in enumerate(('Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'),1)}

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')
class ChipmosHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)
def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _day(value):
    if not isinstance(value,str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value):return None
    try:return date.fromisoformat(value)
    except ValueError:return None
def _page(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('chipmos_response_size_invalid')
    soup=BeautifulSoup(raw.decode('utf8',errors='strict'),'html.parser');canon=soup.select('link[rel=canonical]');types=soup.select('meta[property="og:type"]')
    if (not soup.html or soup.html.get('lang')!='zh-TW'or not soup.title or not _clean(soup.title).startswith(LEGAL)
            or len(canon)!=1 or canon[0].get('href')!='https://www.chipmos.com/'
            or len(types)!=1 or types[0].get('content')!='website'):raise ValueError('chipmos_site_identity_invalid')
    roots=soup.select('div.page div.wrap-fs.inpage > div.wrap1140.page-content')
    if len(roots)!=1:raise ValueError('chipmos_content_section_invalid')
    # This legacy site's homepage canonical and social OG URL describe its
    # shared header. Article identity is the actual URL published by the index.
    return roots[0]
def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'南茂',today=today);rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='8150']
    if not anchor or len(rows)!=1:raise ValueError('chipmos_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN or _clean(row.get('英文簡稱'))!='ChipMOS'
            or row.get('網址')!='www.chipmos.com'or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('chipmos_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'南茂','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'ChipMOS',
            'website_host':'www.chipmos.com','market':'TWSE','master_observed_on':published.isoformat(),'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}
def parse_index(raw):
    root=_page(raw);titles=root.select(':scope > div.iryearbox > h4');cards=root.select(':scope > div.editbox > div.ir-table-wrap > ul.ir-table2.csr-news:not(.table2-header)')
    headers=root.select(':scope > div.editbox > div.ir-table-wrap > ul.ir-table2.table2-header.csr-news')
    if len(headers)!=1 or [_clean(n)for n in headers[0].select(':scope > li')]!=['日期','新聞標題']:raise ValueError('chipmos_index_header_invalid')
    if len(titles)!=1 or _clean(titles[0])!='新聞訊息'or not 1<=len(cards)<=200:raise ValueError('chipmos_index_role_or_count_invalid')
    rows,seen=[],{}
    for card in cards:
        cells=card.select(':scope > li')
        if len(cells)!=2:raise ValueError('chipmos_index_fields_invalid')
        links=cells[1].select(':scope > a[href]');stamp=_clean(cells[0])
        if len(links)!=1 or _day(stamp)is None:raise ValueError('chipmos_index_date_or_link_invalid')
        title=_clean(links[0]);url=urljoin(INDEX,links[0]['href']);match=ARTICLE.fullmatch(url)
        if not match or not 1<=len(title)<=500 or '南茂科技'not in title:raise ValueError('chipmos_index_route_or_title_invalid')
        row={'title':title,'date_original':stamp,'url':url,'category':'新聞訊息','original_id':match[1]}
        if url in seen:
            if row!=seen[url]:raise ValueError('chipmos_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows
def parse_article(raw,listed):
    if not ARTICLE.fullmatch(listed['url']):raise ValueError('chipmos_article_route_invalid')
    root=_page(raw);titles=root.select(':scope > h4');dates=root.select(':scope > p.fc-main');blocks=root.select(':scope > div.editbox');backs=root.select(':scope > p.textC > a.btn[href]')
    if not len(titles)==len(dates)==len(blocks)==len(backs)==1:raise ValueError('chipmos_article_fields_invalid')
    stamp=_clean(dates[0]);body=_clean(blocks[0]);press=re.search(r'HSINCHU, (?:Taiwan, )?([A-Z][a-z]{2})\. ([1-9]\d?), (20\d{2})',body)
    try:body_date=date(int(press[3]),MONTHS[press[1]],int(press[2]))if press else None
    except (ValueError,KeyError):body_date=None
    if (_clean(titles[0])!=listed['title']or stamp!=listed['date_original']or _day(stamp)is None or body_date!=_day(stamp)
            or urljoin(listed['url'],backs[0]['href'])!=INDEX or _clean(backs[0])!='回列表頁'or listed['category']!='新聞訊息'):
        raise ValueError('chipmos_index_article_date_or_role_mismatch')
    if blocks[0].find(['script','iframe','object','form','video']):raise ValueError('chipmos_article_body_invalid')
    if (not 100<=len(body)<=12_000 or 'ChipMOS TECHNOLOGIES INC.'not in body
            or not re.search(r'Taiwan Stock Exchange: *8150\b',body)
            or re.search(r'(?<!\d)8150\.TWO(?!\w)',body)):raise ValueError('chipmos_article_issuer_or_market_unverified')
    return listed['title'],body,{'issuer_article_date':stamp,'index_card_date':listed['date_original'],'body_press_date':body_date.isoformat(),'date':stamp}
def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('chipmos_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('chipmos_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('chipmos_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('chipmos_original_size_mismatch')
    return raw


def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'南茂官方新聞','publisher':'ChipMOS','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':listed['original_id'],'article_category':listed['category'],
                'article_identity_basis':'actual_request_URL_and_full_published_index_title_date_and_body_exchange_identity',
                'sitewide_canonical_OG_not_used_as_article_identity':True,
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}
def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','8150'),('official_name','南茂'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'南茂','南茂科技',LEGAL,'chipmos'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
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
        return 'ChipMOS'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or ChipmosHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(rows);candidates=[]
        for row in rows:
            day=_day(row['date_original'])
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
                    raise ValueError('chipmos_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('chipmos_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('chipmos_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_day(v['date_original']),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('chipmos_saved_original_unverified')
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
