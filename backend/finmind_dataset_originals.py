"""Existing native FinMind body -> exact SDK input, never derived metric proof.

No HTTP or alternate parsing path lives here. Ambiguity drops optional evidence
without changing the provider result, cache, retry or report admission policy.
"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
import json
import math
import re
import time
from urllib.parse import parse_qs, urlsplit, urlencode
from zoneinfo import ZoneInfo

SCHEMA='finmind-native-body-to-sdk-input:v1'
MAX_BYTES=2_000_000
MAX_ROWS=20_000
IDS=('ticker','fetch_id','operation_id','attempt_id')
OWNERS={
    'TaiwanStockInstitutionalInvestorsBuySell':{('institutional_trading','FinMind')},
    'TaiwanStockFinancialStatements':{('twse_official','FinMind TWSE official')},
    'TaiwanStockBalanceSheet':{('twse_official','FinMind TWSE official')},
    'TaiwanStockCashFlowsStatement':{('twse_official','FinMind TWSE official')},
}

def _digest(rows):
    return sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()).hexdigest()

def _unique(pairs):
    out={}
    for k,v in pairs:
        if k in out:raise ValueError('duplicate JSON key')
        out[k]=v
    return out

def _rows(rows,ticker,dataset,start,end):
    if not isinstance(rows,list)or not 0<len(rows)<=MAX_ROWS:raise ValueError('input row limit')
    required={'date','stock_id','name','buy','sell'}if dataset=='TaiwanStockInstitutionalInvestorsBuySell'else{'date','stock_id','type','value'}
    allowed=required|({'origin_name'}if 'value'in required else set())
    columns=None;result=[]
    for row in rows:
        if not isinstance(row,dict)or not required<=row.keys()or not row.keys()<=allowed:raise ValueError('input schema')
        if columns is not None and set(row)!=columns:raise ValueError('nonuniform columns')
        columns=set(row)
        if row['stock_id']!=ticker.split('.')[0]or not isinstance(row['date'],str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',row['date']):raise ValueError('input issuer/date')
        if not start<=date.fromisoformat(row['date'])<=end:raise ValueError('input request period')
        normalized={}
        for k,v in row.items():
            if k in {'buy','sell','value'}:
                if isinstance(v,bool)or not isinstance(v,(int,float,Decimal))or len(str(v))>64:raise ValueError('input number')
                number=Decimal(str(v))
                if not number.is_finite()or len(number.as_tuple().digits)>32:raise ValueError('input nonfinite')
                if not number.is_zero()and not -20<=number.adjusted()<=30:raise ValueError('input numeric exponent')
                if number.is_zero():text='0'
                else:
                    text=format(number,'f');text=text.rstrip('0').rstrip('.')if '.'in text else text
                normalized[k]=['number',text]
            else:
                if not isinstance(v,str)or not v or len(v)>256:raise ValueError('input text')
                normalized[k]=['text',v]
        result.append(normalized)
    return sorted(result,key=lambda r:json.dumps(r,sort_keys=True,separators=(',',':')))

def _body(raw,ticker,dataset,start,end):
    if not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES:raise ValueError('input body limit')
    p=json.loads(raw.decode('utf8','strict'),object_pairs_hook=_unique,parse_float=Decimal,
        parse_constant=lambda _:(_ for _ in()).throw(ValueError('nonfinite JSON')))
    if not isinstance(p,dict)or set(p)!={'msg','status','data'}or p['msg']!='success'or type(p['status'])is not int or p['status']!=200:raise ValueError('input envelope')
    return _rows(p['data'],ticker,dataset,start,end)

@dataclass(frozen=True)
class DatasetCapsule:
    dataset:str
    ids:tuple
    receipt:dict
    row_digest:str
    row_count:int
    start:str
    end:str
    received:float

def capture_dataset_response(request,response,context):
    """Only the owned Session observer calls this after its native send checks."""
    import requests
    from provider_correlation import current_source_identity
    p=urlsplit(request.url);q=parse_qs(p.query,keep_blank_values=True);datasets=q.get('dataset',[])
    if len(datasets)!=1 or datasets[0]not in OWNERS or current_source_identity()not in OWNERS[datasets[0]]:return None
    dataset=datasets[0]
    if any(not isinstance(context.get(k),str)or not context[k]for k in IDS):return None
    ticker=context['ticker']
    if not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',ticker):return None
    if (request.method!='GET'or p.scheme!='https'or p.hostname!='api.finmindtrade.com'or p.port not in(None,443)
        or p.username or p.password or p.fragment or p.path not in('/api/v3/data','/api/v4/data')
        or type(response)is not requests.Response or response.request is not request or response.url!=request.url
        or type(response.status_code)is not int or response.status_code!=200 or response.history or getattr(response,'from_cache',False)
        or response._content_consumed is not True or response.headers.get('Content-Range')):return None
    idkeys=[k for k in('data_id','stock_id')if q.get(k)==[ticker.split('.')[0]]]
    if len(idkeys)!=1:return None
    key=idkeys[0];other='stock_id'if key=='data_id'else'data_id'
    if q.get(other)not in(None,[''])or len(q.get('start_date',[]))!=1:return None
    start=q['start_date'][0];ends=q.get('end_date',[''])
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',start)or len(ends)!=1 or ends[0]and not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',ends[0]):return None
    now=time.time();a=date.fromisoformat(start);b=date.fromisoformat(ends[0])if ends[0]else datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date()
    if not a<=b<=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date():return None
    public={'dataset':dataset,key:q[key][0],'start_date':start}
    if ends[0]:public['end_date']=ends[0]
    raw=response.content
    if not isinstance(raw,bytes)or not 0<len(raw)<=MAX_BYTES:return None
    if response.headers.get('Content-Encoding','identity').lower()in('','identity'):
        length=response.headers.get('Content-Length')
        if length is not None and(not length.isdecimal()or int(length)!=len(raw)):return None
    secrets=[v for k,values in q.items()if k not in public for v in values if v]
    for k,v in request.headers.items():
        if any(s in k.lower()for s in('authorization','cookie','token','api-key','api_key')):secrets.extend([v,*v.split()])
    if any(s.encode()in raw for s in secrets if s):return None
    rows=_body(raw,ticker,dataset,a,b)
    texts=[v[1]for row in rows for v in row.values()if v[0]=='text']
    if any(secret in text for secret in secrets for text in texts if secret):return None
    from official_response_evidence import archive_response
    receipt=archive_response(raw,source_url=p._replace(query=urlencode(public),fragment='').geturl(),retrieved_at=now,
        evidence_kind='decoded_complete_http_response_body',max_bytes=MAX_BYTES)
    if receipt.get('status')!='archived':return None
    receipt.update(http_status_observed=True,response_complete=True,request_method='GET',cache_hit=False)
    return DatasetCapsule(dataset,tuple(context[k]for k in IDS),receipt,_digest(rows),len(rows),a.isoformat(),b.isoformat(),now)

def bind_sdk_frame(loader,frame,ticker,dataset):
    import pandas as pd
    from provider_correlation import current_correlation,current_source_identity
    from official_response_evidence import read_response
    c=current_correlation()
    if type(frame)is not pd.DataFrame or dataset not in OWNERS or current_source_identity()not in OWNERS[dataset]or c.get('ticker')!=ticker:return None
    for capsule in reversed(getattr(loader,'_stock_dataset_transport_capsules',[])[:8]):
        if type(capsule)is not DatasetCapsule or capsule.dataset!=dataset or capsule.ids!=tuple(c.get(k)for k in IDS)or not 0<=time.time()-capsule.received<=180:continue
        a,b=date.fromisoformat(capsule.start),date.fromisoformat(capsule.end)
        try:
            rows=_rows(frame.to_dict(orient='records'),ticker,dataset,a,b);raw=read_response(capsule.receipt,max_bytes=MAX_BYTES)
            if _digest(rows)!=capsule.row_digest or _digest(_body(raw,ticker,dataset,a,b))!=capsule.row_digest or len(rows)!=capsule.row_count:continue
        except (OSError,ValueError,TypeError,KeyError,EOFError,OverflowError):
            continue
        return {'schema':SCHEMA,'dataset':dataset,'ticker':ticker,'fetch_id':c['fetch_id'],'operation_id':c['operation_id'],
            'transport_attempt_id':c['attempt_id'],'native_response_sha256':sha256(raw).hexdigest(),
            'native_source_url_sha256':sha256(capsule.receipt['source_url'].encode()).hexdigest(),'native_response_bytes':len(raw),
            'native_received_at_epoch':capsule.received,'sdk_rows_sha256':capsule.row_digest,'sdk_row_count':len(rows),
            'query_start_date':capsule.start,'query_end_date':capsule.end,'request_url_credentials_redacted':True,
            'native_http_status':200,'archived_original_available':True,'derived_metrics_verified':False,
            'independent_primary_source_verified':False,'historical_pit_verified':False}
    return None

def audit_input_lineages(entry):
    """Bounded public fingerprints; no paths, bodies, URLs or metric upgrade."""
    values=entry.get('sdk_input_lineages')
    if (not isinstance(values,list)or not 0<len(values)<=3 or entry.get('cache_hit')is not False
        or entry.get('status')not in {'success','degraded_enrichment'}
        or type(entry.get('record_count'))is not int or entry['record_count']<=0):return []
    out=[];seen=set()
    for value in values:
        if not isinstance(value,dict)or value.get('schema')!=SCHEMA:return []
        dataset=value.get('dataset')
        if not isinstance(dataset,str)or dataset not in OWNERS or(entry.get('source'),entry.get('provider'))not in OWNERS[dataset]or dataset in seen:return []
        if any(not isinstance(value.get(k),str)or not 0<len(value[k])<=160 for k in('ticker','fetch_id','operation_id','transport_attempt_id')):return []
        if not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',value['ticker'])or any(value[k]!=entry.get(k)for k in('ticker','fetch_id','operation_id')):return []
        if not any(isinstance(a,dict)and a.get('attempt_id')==value['transport_attempt_id']and a.get('status')=='success'
                   and a.get('source')==entry['source']and a.get('provider')==entry['provider']for a in entry.get('provider_attempts',[])):return []
        hashes=('native_response_sha256','native_source_url_sha256','sdk_rows_sha256')
        if any(not isinstance(value.get(k),str)or not re.fullmatch(r'[0-9a-f]{64}',value[k])for k in hashes):return []
        if any(type(value.get(k))is not int or not 0<value[k]<=limit for k,limit in(('native_response_bytes',MAX_BYTES),('sdk_row_count',MAX_ROWS))):return []
        if type(value.get('native_http_status'))is not int or value['native_http_status']!=200:return []
        stamp=value.get('native_received_at_epoch')
        if type(stamp)not in(int,float)or not math.isfinite(stamp)or not 0<stamp<=time.time()or time.time()-stamp>180:return []
        if any(value.get(k)is not True for k in('request_url_credentials_redacted','archived_original_available')):return []
        if any(value.get(k)is not False for k in('derived_metrics_verified','independent_primary_source_verified','historical_pit_verified')):return []
        dates=[]
        for k in('query_start_date','query_end_date'):
            if not isinstance(value.get(k),str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value[k]):return []
            try:dates.append(date.fromisoformat(value[k]))
            except ValueError:return []
        if not dates[0]<=dates[1]<=datetime.fromtimestamp(time.time(),ZoneInfo('Asia/Taipei')).date():return []
        fields={'schema','dataset','ticker','fetch_id','operation_id','transport_attempt_id',*hashes,'native_response_bytes','sdk_row_count','native_http_status','native_received_at_epoch','query_start_date','query_end_date','request_url_credentials_redacted','archived_original_available','derived_metrics_verified','independent_primary_source_verified','historical_pit_verified'}
        out.append({k:value[k]for k in fields});seen.add(dataset)
    return out

def attach_input_audit(result):
    value=result.get('value');audit=result.get('audit')
    if not isinstance(value,dict)or not isinstance(audit,dict):return result
    candidates=value.get('native_sdk_inputs')
    if audit.get('source')=='institutional_trading':
        provenance=value.get('source_provenance')
        candidate=provenance.get('native_sdk_input')if isinstance(provenance,dict)else None
        candidates=[candidate]if isinstance(candidate,dict)else None
    try:proof=audit_input_lineages({**audit,'sdk_input_lineages':candidates})
    except (TypeError,ValueError,OverflowError):proof=[]
    # Financial input metadata is an internal handoff, not another data field.
    clean={k:v for k,v in value.items()if k!='native_sdk_inputs'}if 'native_sdk_inputs'in value else value
    if proof:return {**result,'value':clean,'audit':{**audit,'sdk_input_lineages':proof}}
    return {**result,'value':clean}if clean is not value else result
