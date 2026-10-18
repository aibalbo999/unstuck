"""Exact issuer/date trading-risk notices, backed by the complete official JSON.

These are exchange observations, not company results, sentiment or live quotes.
Absence remains unknown; dates have day precision and source failures survive.
"""
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from html import unescape
import json,math,re,time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from official_response_evidence import archive_response,read_response
from .trading_notice_transport import ENDPOINT,MAX_BYTES,TradingNoticeHttp,query_params

PROVIDER='TWSE official trading notices'
SOURCE='TWSE 官方注意交易公告'
SOURCE_TYPE='official_trading_risk_notice'
POLICY='twse-official-trading-notice.v1'
PAGE='https://www.twse.com.tw/zh/announcement/notice.html'
TAIPEI=ZoneInfo('Asia/Taipei')
FIELDS=['編號','證券代號','證券名稱','累計次數','注意交易資訊','日期','收盤價','本益比']
_CLAUSE_DECORATIONS={f"<font color='#FF0000'>﹝第{clause}款﹞</font>": f'﹝第{clause}款﹞'
                     for clause in ('九','十','十一','十二','十三')}


def _notice_text(value):
    # Complete official originals use these exact five decorative clause spans.
    # Keep its words; never generically strip, parse or render source HTML.
    if not isinstance(value,str) or not 10<=len(value)<=4000:
        raise ValueError('notice text unverified')
    text=value
    for decoration,words in _CLAUSE_DECORATIONS.items():
        text=text.replace(decoration,words)
    if len(text)<10:
        raise ValueError('notice text unverified')
    inspected=text
    for _ in range(8):
        decoded=unescape(inspected)
        if decoded==inspected:
            break
        inspected=decoded
    else:
        raise ValueError('notice text encoding unverified')
    if any(marker in inspected.lower() for marker in ('<','>','http://','https://')):
        raise ValueError('notice text markup unverified')
    return text


def source_url(ticker,now):
    return ENDPOINT+'?'+urlencode({'startDate':(now.date()-timedelta(days=30)).strftime('%Y%m%d'),
        'endDate':now.strftime('%Y%m%d'),'stockNo':ticker.split('.')[0],
        'querytype':'2','sortKind':'DATE','response':'json'})


def _json(raw):
    if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('notice response exceeds limit')
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('duplicate notice JSON key')
            out[key]=value
        return out
    def constant(value):raise ValueError('nonfinite notice JSON number')
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)


def _roc_day(value):
    match=re.fullmatch(r'(\d{3})\.(\d{2})\.(\d{2})',str(value))
    if not match:raise ValueError('unverified notice date')
    return date(int(match[1])+1911,int(match[2]),int(match[3]))


def parse_notice_rows(raw,url,ticker,observed):
    params=query_params(url)
    if ticker!=params['stockNo']+'.TW':raise ValueError('notice issuer mismatch')
    start,end=[datetime.strptime(params[k],'%Y%m%d').date() for k in ('startDate','endDate')]
    if end>observed.date():raise ValueError('future notice query')
    p=_json(raw)
    expected_title=f'公布注意有價證券資訊 ({start.year-1911}年{start:%m月%d日} 至 {end.year-1911}年{end:%m月%d日} 個股)'
    if not isinstance(p,dict) or p.get('stat')!='OK' or p.get('title')!=expected_title or p.get('fields')!=FIELDS:
        raise ValueError('notice envelope unverified')
    echoed=p.get('params')
    if not isinstance(echoed,dict) or any(echoed.get(k)!=v for k,v in params.items()):
        raise ValueError('notice query not echoed')
    if any(echoed.get(k)!=v for k,v in {'controller':'announcement','action':'notice','lang':'zh','selectType':''}.items()):
        raise ValueError('notice endpoint identity unverified')
    rows=p.get('data')
    if (not isinstance(rows,list) or len(rows)>31 or type(p.get('total')) is not int or p['total']!=len(rows)
            or type(p.get('count')) is not int or p['count']!=(1 if rows else 0)):
        raise ValueError('notice rows incomplete')
    result=[];seen=set();names=set()
    for index,row in enumerate(rows):
        if (not isinstance(row,list) or len(row)!=len(FIELDS) or type(row[0]) is not int or row[0]!=index+1
                or row[1]!=params['stockNo'] or not isinstance(row[2],str) or not 2<=len(row[2])<=80
                or row[2].strip()!=row[2] or not re.fullmatch(r'[1-9]\d{0,3}',str(row[3]))):
            raise ValueError('notice issuer row unverified')
        _notice_text(row[4])
        published=_roc_day(row[5])
        if not start<=published<=end or published in seen:raise ValueError('notice date outside query or duplicate')
        seen.add(published);names.add(row[2]);result.append((index,row,published))
    if len(names)>1:raise ValueError('notice issuer names conflict')
    return result


def _canonical_day(value):
    try:
        if isinstance(value,str) and re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value):return date.fromisoformat(value).isoformat()
        dt=datetime.fromisoformat(value)
        if dt.tzinfo and dt.utcoffset()==timedelta(0) and dt.time().replace(tzinfo=None)==datetime.min.time():return dt.date().isoformat()
    except (ValueError,TypeError):pass
    return None


def _digest(record):
    fields={k:record.get(k) for k in ('ticker','title','text','summary','link','source','source_type',
        'source_document_url','publication_date_precision','publication_date_original','source_role','event_assessment','content_truncated')}
    fields['date']=_canonical_day(record.get('date'))
    return sha256(json.dumps(fields,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def _record(ticker,row,published,url,receipt,index):
    day=published.isoformat();stock=ticker.split('.')[0]
    title=f'{row[2]}（{stock}）{day} 注意交易公告'
    summary=_notice_text(row[4])
    body=f'{title}\n{summary}'
    link=PAGE+'?'+urlencode({'startDate':published.strftime('%Y%m%d'),'endDate':published.strftime('%Y%m%d'),'stockNo':stock,'querytype':'2'})
    record={'ticker':ticker,'title':title,'text':body,'summary':summary,'date':day,'link':link,
        'source':SOURCE,'source_type':SOURCE_TYPE,'source_document_url':url,
        'publication_date_precision':'day','publication_date_original':{'twse_notice_date':row[5]},
        'source_role':'exchange_trading_risk_notice','event_assessment':'not_assessed',
        'content_coverage':'text_available','content_truncated':False}
    record['trading_notice_receipt']={'policy':POLICY,'row_index':index,'original':receipt,'parsed_content_sha256':_digest(record)}
    return record


def verified_notice_record(record,data):
    """Re-read the original, never trust a ticker/title or a copied receipt marker."""
    try:
        if (isinstance(record.get('trading_notice_receipt'), dict)
                and record['trading_notice_receipt'].get('policy') == 'twse-official-market-trading-notice.v1'):
            from .twse_market_trading_notices import verified_market_record
            return verified_market_record(record, data)
        ticker=str(data.get('ticker') or '').strip().upper();proof=record['trading_notice_receipt']
        if (not re.fullmatch(r'[1-9]\d{3}\.TW',ticker) or not isinstance(proof,dict) or proof.get('policy')!=POLICY
                or record.get('ticker')!=ticker or record.get('source')!=SOURCE or record.get('source_type')!=SOURCE_TYPE
                or record.get('content_truncated') is not False or record.get('publication_date_precision')!='day'
                or record.get('source_role')!='exchange_trading_risk_notice' or record.get('event_assessment')!='not_assessed'
                or proof.get('parsed_content_sha256')!=_digest(record)):
            return None
        receipt=proof['original'];stamp=receipt['retrieved_at']
        if (receipt.get('status')!='archived' or receipt.get('http_status')!=200 or type(stamp) not in (int,float)
                or not math.isfinite(stamp) or stamp<=0 or stamp>time.time()
                or receipt.get('evidence_kind')!='raw_http_response_bytes'
                or receipt.get('source_url')!=record.get('source_document_url')):return None
        observed=datetime.fromtimestamp(stamp,TAIPEI)
        rows=parse_notice_rows(read_response(receipt),receipt['source_url'],ticker,observed)
        index=proof['row_index']
        if type(index) is not int or not 0<=index<len(rows):return None
        _,row,day=rows[index];expected=_record(ticker,row,day,receipt['source_url'],receipt,index)
        if _digest(expected)!=_digest(record) or record.get('link')!=expected['link']:return None
        if 'published_date' in record and _canonical_day(record['published_date'])!=day.isoformat():return None
        return ticker.split('.')[0]
    except (KeyError,ValueError,TypeError,AttributeError,OSError,EOFError,OverflowError,RecursionError):return None


def fetch_trading_notices(ticker,*,now=None,get=None):
    ticker=str(ticker or '').strip().upper()
    audit={'source':'recent_catalysts','provider':PROVIDER,'selection_policy':POLICY,'status':'not_applicable',
        'record_count':0,'http_request_sent':False,'cache_hit':False,'stale':False,'window_complete':False}
    if not re.fullmatch(r'[1-9]\d{3}\.TW',ticker):return [],audit
    now=now or datetime.now(TAIPEI)
    if now.tzinfo is None:raise ValueError('notice cutoff must be timezone-aware')
    now=now.astimezone(TAIPEI);deadline=time.monotonic()+8
    http=TradingNoticeHttp(deadline);getter=get or http.get;url=source_url(ticker,now)
    audit.update(status='error',source_url=url)
    try:
        raw=getter(url)
        component=http.components[0] if http.components else {}
        stamp=component.get('fetched_at_epoch',time.time())
        receipt=archive_response(raw,source_url=url,retrieved_at=stamp,http_status=200)
        if receipt.get('status')!='archived' or read_response(receipt)!=raw:raise ValueError('notice original not preserved')
        audit['raw_response_receipt']=receipt
        rows=parse_notice_rows(raw,url,ticker,datetime.fromtimestamp(stamp,TAIPEI))
        records=[_record(ticker,row,published,url,receipt,index) for index,row,published in rows]
        if time.monotonic()>=deadline:raise TimeoutError('notice acquisition deadline exhausted')
        if not all(verified_notice_record(r,{'ticker':ticker}) for r in records):raise ValueError('notice saved evidence unverified')
        if time.monotonic()>=deadline:raise TimeoutError('notice original revalidation deadline exhausted')
        cached=bool(component.get('cache_hit'))
        audit.update(status='skipped_fresh_cache' if cached and records else 'success' if records else 'unavailable',
            record_count=len(records),coverage_status='issuer_query_complete' if records else 'empty_unknown',
            cache_hit=cached,http_request_sent=bool(http.http_request_count) if get is None else True,
            event_kind='cache_hit' if cached else 'aggregate',fetched_at_epoch=stamp,
            raw_response_receipt=receipt,quality_status='eligible_evidence' if records else 'no_eligible_evidence',
            message='官方注意交易資訊；影響未評估，未涵蓋其他公司事件。' if records else '官方查詢無公告；不推論無風險或無其他事件。')
        return records,audit
    except Exception as exc:
        component=http.components[0] if http.components else {}
        details=getattr(exc,'diagnostic',{})
        if isinstance(details,dict):audit.update(details)
        if component:audit.update(component_statuses={'official_notice':component},cache_hit=bool(component.get('cache_hit')),
            event_kind='cache_hit' if component.get('cache_hit') else 'aggregate',
            http_status=component.get('http_status'),fetched_at_epoch=component.get('fetched_at_epoch'))
        audit.update(status='error',error_kind=getattr(exc,'error_kind',type(exc).__name__),
            message='官方注意交易公告未取得完整可驗證原件。',http_request_sent=bool(http.http_request_count) if get is None else True)
        return [],audit
