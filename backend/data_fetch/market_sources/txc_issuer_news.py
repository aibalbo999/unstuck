"""Complete corporate originals on Txc's exchange-bound public site."""
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

TICKER='3042.TW';MASTER=ROSTER_URL;INDEX='https://www.txccorp.com/news/'
ARTICLE=re.compile(r'https://www\.txccorp\.com/news-detail/((?:consolidated-revenue|73)(?:__[1-9][0-9]{0,5})?)/\Z')
POLICY='txc-public-corporate-originals-v1';LEGAL='台灣晶技股份有限公司';UBN='21204867'
CACHED_MASTER_KIND='cached_complete_source_payload_verified_by_digest'
MONTHS={name:i for i,name in enumerate(('January','February','March','April','May','June','July','August','September','October','November','December'),1)}

def url_contract(url):
    if url==MASTER:return 2_500_000,{'application/json','text/json'}
    if url==INDEX or ARTICLE.fullmatch(str(url)):return 600_000,{'text/html','application/xhtml+xml'}
    raise SourceResponseError('transport_url_invalid')
class TxcHttp(IssuerNewsHttp):
    route_contract=staticmethod(url_contract)
def _clean(value):return re.sub(r'\s+',' ',clean_text(value)).strip()
def _page(raw):
    if not isinstance(raw,bytes)or not 0<len(raw)<=600_000:raise ValueError('txc_response_size_invalid')
    # Preserve a truncated metadata byte as a surrogate; never replace or repair
    # it. Every adopted title/date/body cell is independently strict UTF-8.
    return BeautifulSoup(raw.decode('utf-8',errors='surrogateescape'),'html.parser')
def _strict(value):
    value.encode('utf-8',errors='strict')
    if '\ufffd'in value:raise ValueError('txc_text_replacement_invalid')
    return value
def _date(value,*,short=False):
    match=re.fullmatch(r'(\d{2}) ([A-Z][a-z]{2}) (20\d{2})',value)if isinstance(value,str)else None
    try:return date(int(match[3]),{k[:3]:v for k,v in MONTHS.items()}[match[2]],int(match[1]))if match else None
    except (ValueError,KeyError):return None

def _identity(raw,today,epoch):
    from .official_company_legal_name import parse_roster,select_legal_name
    from .issuer_news import TAIPEI
    anchor=select_legal_name(parse_roster(raw,'.TW'),TICKER,'晶技',today=today)
    rows=[r for r in json.loads(raw)if str(r.get('公司代號'))=='3042']
    if not anchor or len(rows)!=1:raise ValueError('txc_issuer_not_unique')
    row=rows[0];published=date.fromisoformat(anchor['as_of'])
    if (anchor['legal_name']!=LEGAL or row.get('營利事業統一編號')!=UBN
            or row.get('英文簡稱')!='TXC'or row.get('網址')!='www.txccorp.com'
            or published>datetime.fromtimestamp(epoch,TAIPEI).date()):raise ValueError('txc_issuer_domain_unverified')
    return {'ticker':TICKER,'short_name':'晶技','legal_name':LEGAL,'official_ubn':UBN,'english_alias':'TXC',
            'website_host':'www.txccorp.com','market':'TWSE','master_observed_on':published.isoformat(),
            'master_source_url':MASTER,'master_response_sha256':sha256(raw).hexdigest()}

def _card_date(node):
    days=node.select(':scope > div.day');months=node.select(':scope > span.yearMonth')
    if len(days)!=1 or len(months)!=1:raise ValueError('txc_visible_date_invalid')
    value=_strict(_clean(days[0])+' '+_clean(months[0]).removeprefix('/ ').strip())
    if _date(value)is None:raise ValueError('txc_visible_date_invalid')
    return value

def parse_index(raw):
    roots=_page(raw).select('div.mainArea > div.wrap > div.contentBox > div.newsList')
    if len(roots)!=1:raise ValueError('txc_index_section_invalid')
    cards=roots[0].select(':scope > div.newsItem > div.item > a[href]')
    if not 1<=len(cards)<=400:raise ValueError('txc_index_count_invalid')
    rows,seen=[],{}
    for link in cards:
        url=str(link['href'])
        if not ARTICLE.fullmatch(url):continue
        titles=link.select(':scope > div.Txt > h2.title');stamps=link.select(':scope > div.Txt > div.newsInfoBox > div.dateBox > div.date');roles=link.select(':scope > div.Txt > div.newsInfoBox > div.classTitle')
        if len(titles)!=1 or len(stamps)!=1 or len(roles)!=1 or _strict(_clean(roles[0]))!='財務訊息':raise ValueError('txc_index_fields_invalid')
        title=_strict(_clean(titles[0]));stamp=_card_date(stamps[0])
        if not 1<=len(title)<=200:raise ValueError('txc_index_title_invalid')
        row={'title':title,'date_original':stamp,'url':url}
        if url in seen:
            if row!=seen[url]:raise ValueError('txc_index_duplicate_conflict')
            continue
        seen[url]=row;rows.append(row)
    return rows

def parse_article(raw,listed):
    soup=_page(raw);url=listed['url']
    if not ARTICLE.fullmatch(url):raise ValueError('txc_article_route_invalid')
    roots=soup.select('div.mainArea.ins > div.wrap > div.contentBox')
    if len(roots)!=1:raise ValueError('txc_article_section_invalid')
    root=roots[0];titles=root.select(':scope > div.topBox > h1.articleTitle');stamps=root.select(':scope > div.topBox > div.newsInfoBox > div.dateBox > div.date');roles=root.select(':scope > div.topBox > div.newsInfoBox > div.classTitle');bodies=root.select(':scope > div.textEditor')
    if len(titles)!=1 or len(stamps)!=1 or len(roles)!=1 or len(bodies)!=1:raise ValueError('txc_article_sections_invalid')
    title=_strict(_clean(titles[0]));day=_date(listed['date_original'])
    if title!=listed['title']or _card_date(stamps[0])!=listed['date_original']or _strict(_clean(roles[0]))!='財務訊息':raise ValueError('txc_index_article_date_or_title_mismatch')
    full_title=title+'-台灣晶技股份有限公司 TXC Corporation.'
    og=soup.select('meta[property="og:title"]');copies=root.select(':scope > div.sideShare input#copyLink');page_titles=soup.select('title')
    if (len(page_titles)!=1 or _strict(_clean(page_titles[0]))!=full_title or len(og)!=1 or _strict(og[0].get('content',''))!=full_title
            or len(copies)!=1 or copies[0].get('value')!=url.removesuffix('/')):raise ValueError('txc_native_article_identity_invalid')
    # The source has no canonical/OG URL. Its explicit copyLink is a slashless
    # article identity; preserve it, never follow it or turn it into another URL.
    block=bodies[0]
    if block.find(['script','iframe','object','form','img','video','audio']):raise ValueError('txc_complete_body_unverified')
    body=_strict(_clean(block))
    match=re.fullmatch(r'本公司(20\d{2})年([1-9]|1[0-2])月(合併營收|自結損益)公告',title)
    if not match or (int(match[1]),int(match[2]))>=(day.year,day.month):raise ValueError('txc_content_period_invalid')
    year,month=int(match[1]),int(match[2]);tables=block.find_all('table')
    if match[3]=='合併營收':
        if tables or not 100<=len(body)<=1000 or not re.search(r'股票代碼\s*3042(?:\s|$)',body)or f'{year} 年 {month:02d} 月份'not in body:raise ValueError('txc_revenue_body_unverified')
    else:
        if len(tables)!=1:raise ValueError('txc_income_table_invalid')
        table=tables[0];headers=table.select(':scope > thead > tr');rows=table.select(':scope > tbody > tr')
        if len(headers)!=2 or len(rows)!=8:raise ValueError('txc_income_table_shape_invalid')
        head1=headers[0].find_all('th',recursive=False);head2=headers[1].find_all('th',recursive=False)
        if ([_strict(_clean(c))for c in head1]!=['項目(新台幣仟元)','當月數','累計數']or [c.get('rowspan')for c in head1]!=['2',None,None]
                or [c.get('colspan')for c in head1]!=[None,'2','2']or [_strict(_clean(c))for c in head2]!=[f'{year-1911}年{month:02d}月','差異比率(YoY)',f'{year-1911}年','差異比率(YoY)']):raise ValueError('txc_income_table_period_or_units_invalid')
        labels=['合併營業收入','合併營業利益','合併稅前損益','歸屬於母公司','非控制權益','稅前每股盈餘(新台幣元)','歸屬於母公司','非控制權益'];lines=[]
        for row,expected in zip(rows,labels):
            cells=row.find_all('td',recursive=False)
            if len(cells)!=5 or any(c.has_attr('rowspan')or c.has_attr('colspan')for c in cells):raise ValueError('txc_income_table_cell_invalid')
            values=[_strict(_clean(c))for c in cells]
            if values[0]!=expected or any(v and not re.fullmatch(r'-?(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?%?',v)for v in values[1:]):raise ValueError('txc_income_table_value_invalid')
            if not values[1]or not values[3]:raise ValueError('txc_income_table_value_missing')
            lines.append(' | '.join(values))
        # Keep both original header rows, blank YoY cells and all original notes.
        # No numeric extraction, arithmetic or insertion into annual/TTM data.
        rendered='\n'.join([' | '.join(_strict(_clean(c))for c in head1),' | '.join(_strict(_clean(c))for c in head2),*lines])
        copy=BeautifulSoup(str(block),'html.parser');copy.find('table').replace_with(rendered);body=_strict(copy.get_text(' ',strip=True))
        if not 200<=len(body)<=5000:raise ValueError('txc_complete_income_body_invalid')
    return title,body,{'issuer_article_date':_card_date(stamps[0]),'index_card_date':listed['date_original'],'native_copyLink_original':copies[0]['value'],'date':day.isoformat()}

def _read_original(proof,url):
    limit,_=url_contract(url);epoch=proof.get('retrieved_at')if isinstance(proof,dict)else None
    cached_master=isinstance(proof,dict)and proof.get('evidence_kind')==CACHED_MASTER_KIND
    if cached_master:
        if (url!=MASTER or proof.get('http_status')is not None or proof.get('http_status_observed')is not False
                or proof.get('cache_source')!='official-company-roster:v2:.TW'
                or proof.get('source_payload_sha256')!=proof.get('raw_response_sha256')
                or type(proof.get('source_payload_bytes'))is not int or proof['source_payload_bytes']!=proof.get('raw_response_bytes')):
            raise ValueError('txc_cached_master_receipt_invalid')
    elif (not isinstance(proof,dict)or type(proof.get('http_status'))is not int or proof['http_status']!=200 or proof.get('evidence_kind')!='raw_http_response_bytes'
            or 'http_status_observed'in proof and proof['http_status_observed']is not True
            or any(k in proof for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
        raise ValueError('txc_native_receipt_invalid')
    if (not isinstance(proof,dict)or proof.get('status')!='archived'or proof.get('source_url')!=url
            or type(proof.get('raw_response_bytes'))is not int or not 0<proof['raw_response_bytes']<=limit
            or type(epoch)not in(int,float)or not math.isfinite(epoch)or not 0<epoch<=time.time()):raise ValueError('txc_original_receipt_invalid')
    raw=read_response(proof)
    if len(raw)!=proof['raw_response_bytes']:raise ValueError('txc_original_size_mismatch')
    return raw

def _build_record(identity,listed,title,body,dates,proofs):
    return {'ticker':TICKER,'title':title,'text':body,'summary':body[:280],'date':dates['date'],'link':listed['url'],'source_document_url':listed['url'],
            'source':'晶技官網','publisher':'TXC','source_type':'first_party_issuer_news','publication_date_original':dates,
            'financial_assurance':'not_verified_as_audited','publication_date_precision':'day','content_coverage':'text_available','content_truncated':False,'source_role':'issuer_statement','event_assessment':'not_assessed',
            'issuer_news_receipt':{**identity,'policy':POLICY,'original_id':ARTICLE.fullmatch(listed['url'])[1],
                'index_response_sha256':proofs['index']['raw_response_sha256'],'article_response_sha256':proofs['article']['raw_response_sha256'],'source_record_archive':proofs}}

def verified_record(record,data,*,today):
    try:
        context=data.get('company_identity')
        if context is None:context={}
        if data.get('ticker')!=TICKER or not isinstance(context,dict):return None
        for key,expected in [('ticker',TICKER),('stock_id','3042'),('official_name','晶技'),('legal_name',LEGAL),('official_ubn',UBN),('instrument_type','EQUITY')]:
            if context.get(key)not in(None,'',expected):return None
        if any(data.get(key)not in(None,'','EQUITY')for key in ('instrument_type','quote_type','quoteType')):return None
        forbidden=context.get('forbidden_aliases',[])
        if not isinstance(forbidden,(list,tuple))or any(not isinstance(v,str)for v in forbidden)or {'晶技',LEGAL,'txc'}&{_clean(v).casefold().strip('*').strip()for v in forbidden}:return None
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
        return 'TXC'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,UnicodeError,zlib.error,SourceResponseError):return None

def fetch_recent_news(*,now,http=None):
    from .issuer_news import TAIPEI
    deadline=time.monotonic()+20;http=http or TxcHttp(deadline);today=now.astimezone(TAIPEI).date();records=[];excluded=Counter()
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
                    raise ValueError('txc_cached_master_metadata_invalid')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=None,evidence_kind=CACHED_MASTER_KIND)
                proof.update({k:component[k]for k in ('http_status_observed','cache_source','source_payload_sha256','source_payload_bytes')})
            else:
                if ('http_status_observed'in component and component['http_status_observed']is not True
                        or any(k in component for k in ('cache_source','source_payload_sha256','source_payload_bytes'))):
                    raise ValueError('txc_native_metadata_conflict')
                proof=archive_response(raw,source_url=url,retrieved_at=epoch,http_status=200)
            if _read_original(proof,url)!=raw:raise ValueError('txc_original_archive_unverified')
            return proof
        shared=None
        for row in sorted(candidates,key=lambda v:_date(v['date_original'],short=True),reverse=True)[:5]:
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            article=http.get(row['url']);title,body,dates=parse_article(article,row);published=parse_news_datetime(dates['date'])
            if not now-timedelta(days=30)<=published<=now:
                excluded['future'if published>now else'historical']+=1;continue
            if shared is None:shared={'master':archive(master_raw,MASTER),'index':archive(index_raw,INDEX)}
            proofs={**shared,'article':archive(article,row['url'])};record=_build_record(identity,row,title,body,dates,proofs)
            if not verified_record(record,{'ticker':TICKER},today=today):raise ValueError('txc_saved_original_unverified')
            if time.monotonic()>=deadline:raise SourceResponseError('timeout')
            records.append(record)
        if time.monotonic()>=deadline:raise SourceResponseError('timeout')
        audit['status']='success'if records else'unavailable'
    except (OSError,EOFError,ValueError,TypeError,KeyError,AttributeError,OverflowError,UnicodeError,zlib.error,SourceResponseError)as exc:
        audit.update(status='degraded_enrichment'if records else'error',error_kind=getattr(exc,'error_kind','parse_error'),error_message=str(exc)[:150])
    components=getattr(http,'components',[]);sent=getattr(http,'http_request_count',0);cached=bool(components)and all(c.get('cache_hit')for c in components)
    if audit['status']=='success'and cached and not sent:audit['status']='skipped_fresh_cache'
    epochs=[c['fetched_at_epoch']for c in components if type(c.get('fetched_at_epoch'))in(int,float)]
    audit.update(http_request_sent=bool(sent),http_request_count=sent,event_kind='http_request'if sent else'cache_hit'if cached else'local_block',cache_hit=cached,stale=False,
        record_count=len(records),usable_count=len(records),fetched_at_epoch=min(epochs)if epochs else None,parser_version=POLICY,excluded_reason_counts=dict(excluded),component_receipts=components)
    return records,audit
