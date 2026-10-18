"""Complete E.SUN parent press originals; native malformed metadata stays untrusted."""
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

TICKER='2884.TW';MASTER=ROSTER_URL;INDEX='https://www.esunfhc.com/zh-tw/news-center/news-center/news'
LEGAL='玉山金融控股股份有限公司';UBN='70796305';POLICY='esun-public-parent-published-news-originals-v1'
ARTICLE=re.compile(r'https://www\.esunfhc\.com/zh-tw/news-center/news-center/news/detail\?id=([A-F0-9]{32})&p=148DB1EBDC2B47629ED09DC9820A2155\Z')
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX:return 600_000,{'text/html','application/xhtml+xml'}
    if ARTICLE.fullmatch(str(url)):return 400_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')
class EsunHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)
def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _day(value):
    if not isinstance(value,str)or not re.fullmatch(r'20\d{2}/\d{2}/\d{2}',value):return None
    try:return date.fromisoformat(value.replace('/','-'))
    except ValueError:return None
def _page(raw,url):
    limit,_=url_contract(url)
    if not isinstance(raw,bytes)or not 0<len(raw)<=limit:raise ValueError('esun_response_size_invalid')
    s=BeautifulSoup(raw.decode('utf8',errors='strict'),'html.parser');canon=s.select('link[rel=canonical]');ogurl=s.select('meta[property="og:url"]');ogtitle=s.select('meta[property="og:title"]')
    index=url==INDEX;expected=url.removeprefix('https://www.esunfhc.com') if index else 'https://'+url
    title='新聞中心 - 玉山金控' if index else '- E.SUN FHC';ogname='媒體新聞' if index else '- E.SUN FHC'
    if (not s.html or s.html.get('lang')!='zh-Hant-TW' or not s.title or _clean(s.title)!=title
            or len(canon)!=1 or canon[0].get('href')!=expected or len(ogurl)!=1 or ogurl[0].get('content')!=expected
            or len(ogtitle)!=1 or ogtitle[0].get('content')!=ogname or list(s.stripped_strings).count('©E.SUN FHC')!=1):
        raise ValueError('esun_site_identity_or_native_metadata_changed')
    # The publisher emits "https://https://..." in article canonical/OG.
    # Keep and fingerprint it; never repair, follow, or use it as article identity.
    return s
def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'玉山金',today=today);rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='2884']
    if not anchor or len(rows)!=1:raise ValueError('esun_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN or _clean(row.get('英文簡稱'))!='E.S.F.H'
            or row.get('網址')!='https://www.esunfhc.com' or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('esun_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'玉山金','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'E.S.F.H',
            'website_host':'www.esunfhc.com','market':'TWSE','master_observed_on':published.isoformat(),'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}
def parse_index(raw):
    s=_page(raw,INDEX);heads=s.select('h1');cards=s.select('div.newsList');rows=[];seen={}
    if len(heads)!=1 or _clean(heads[0])!='新聞中心' or not 1<=len(cards)<=200:raise ValueError('esun_index_role_or_count_invalid')
    for c in cards:
        links=c.select('.contentBox > a[href]');pics=c.select(':scope > a.picBox[href]');titles=c.select('h3.title');dates=c.select('p.catalog > span');desc=c.select('p.descript')
        if not len(links)==len(pics)==len(titles)==len(dates)==len(desc)==1:raise ValueError('esun_index_fields_invalid')
        url=urljoin(INDEX,links[0]['href']);m=ARTICLE.fullmatch(url);title=_clean(titles[0]);stamp=_clean(dates[0]);body=_clean(desc[0])
        if not m or urljoin(INDEX,pics[0]['href'])!=url or _day(stamp)is None or len(title)>500 or not 80<=len(body)<=12000:raise ValueError('esun_index_route_date_or_body_invalid')
        row={'title':title,'date_original':stamp,'url':url,'category':'新聞稿','original_id':m[1],'index_body':body,'parent_body_lead':body.startswith('玉山金控')}
        if url in seen:
            if row!=seen[url]:raise ValueError('esun_index_duplicate_conflict')
            continue
        rows.append(row);seen[url]=row
    return rows
def parse_article(raw,listed):
    s=_page(raw,listed['url']);roots=s.select('section.l-news[data-type="comp"][data-comp-name="_news"]')
    if len(roots)!=1:raise ValueError('esun_article_section_invalid')
    root=roots[0];titles=root.select('h1#news-title');dates=root.select('.l-news__headRight > p.p3.mt-4');blocks=root.select(':scope > div.l-news__content');backs=root.select(':scope > a[news-gobak][href]')
    if not len(titles)==len(dates)==len(blocks)==len(backs)==1:raise ValueError('esun_article_fields_invalid')
    stamp=_clean(dates[0]);body=_clean(blocks[0])
    if (_clean(titles[0])!=listed['title'] or not listed['title'] or stamp!=listed['date_original'] or _day(stamp)is None
            or urljoin(listed['url'],backs[0]['href'])!=INDEX or _clean(backs[0])!='返回列表' or listed['category']!='新聞稿'):
        raise ValueError('esun_index_article_title_date_role_mismatch')
    if (blocks[0].find(['script','iframe','object','form','video']) or not 80<=len(body)<=12000 or not listed['parent_body_lead']
            or not body.startswith('玉山金控') or body!=listed['index_body']):raise ValueError('esun_full_parent_article_body_unverified')
    return listed['title'],body,{'issuer_article_date':stamp,'index_card_date':listed['date_original'],'date':_day(stamp).isoformat()}
def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('esun_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('esun_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('esun_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('esun_original_size_mismatch')
    return raw


def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'玉山金控官方新聞','publisher':'E.SUN FHC','source_type':'first_party_issuer_news','publication_date_original':dates,
            'publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':listed['original_id'],'article_category':listed['category'],
                'article_identity_basis':'actual_published_index_URL_title_date_and_complete_parent_issuer_body',
                'known_duplicate_scheme_canonical_OG_not_used_as_article_identity':True,
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}
def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','2884'),('official_name','玉山金'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'玉山金','玉山金控',LEGAL,'e.s.f.h'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
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
        return 'E.SUN FHC'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or EsunHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
    audit={'selection_policy':POLICY,'coverage_status':'partial','window_complete':False}
    try:
        master_raw=http.get(MASTER);master_epoch=[c for c in http.components if c.get('url')==MASTER][-1]['fetched_at_epoch'];identity=_identity(master_raw,today,master_epoch)
        index_raw=http.get(INDEX);rows=parse_index(index_raw);audit['raw_count']=len(rows);candidates=[]
        for row in rows:
            day=_day(row['date_original'])
            if not row['title']:excluded['missing_original_title']+=1
            elif not row['parent_body_lead']:excluded['not_explicit_parent_body_lead']+=1
            elif day>today:excluded['future']+=1
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
                    raise ValueError('esun_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):raise ValueError('esun_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('esun_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_day(v['date_original']),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('esun_saved_original_unverified')
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
