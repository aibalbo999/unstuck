"""Optional native PER original -> exact SDK rows -> PER quantiles only.

No EPS, bands, direct-exchange, period completeness or PIT certification.
Rejected proof never changes the native data, output, retries or cache policy.
"""
from dataclasses import dataclass
from datetime import date,datetime
from decimal import Decimal
from hashlib import sha256
import json,re,time
from urllib.parse import parse_qs,urlsplit,urlencode
from zoneinfo import ZoneInfo
from finmind_monthly_lineage import _digest,_number,_decimal_text,_unique

DATASET='TaiwanStockPER'
MAX_BYTES=2_000_000
IDS=('ticker','fetch_id','operation_id','attempt_id')
KEYS={'date','stock_id','dividend_yield','PER','PBR'}

def normalize_rows(rows,ticker,start,end):
 if not isinstance(rows,list) or not 0<len(rows)<=3000:raise ValueError('PER row count')
 result=[];seen=set()
 for row in rows:
  if not isinstance(row,dict) or set(row)!=KEYS:raise ValueError('PER row schema')
  if row['stock_id']!=ticker.split('.')[0] or not isinstance(row['date'],str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',row['date']):raise ValueError('PER issuer/date')
  when=date.fromisoformat(row['date'])
  if not start<=when<=end or when in seen:raise ValueError('PER period/duplicate')
  seen.add(when);normalized={'date':row['date'],'stock_id':row['stock_id']}
  for k in ('dividend_yield','PER','PBR'):
   if isinstance(row[k],bool) or not isinstance(row[k],(int,float,Decimal)):raise ValueError('PER numeric type')
   normalized[k]=_decimal_text(row[k])
  result.append(normalized)
 return sorted(result,key=lambda r:r['date'])

def body_rows(raw,ticker,start,end):
 if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('PER body size')
 p=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_unique,parse_float=Decimal,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('PER nonfinite')))
 if not isinstance(p,dict) or set(p)!={'msg','status','data'} or p['msg']!='success' or type(p['status'])is not int or p['status']!=200:raise ValueError('PER envelope')
 return normalize_rows(p['data'],ticker,start,end)

@dataclass(frozen=True)
class PerCapsule:
 ids:tuple
 receipt:dict
 digest:str
 row_count:int
 start:str
 end:str
 received:float
 dataset:str=DATASET

def capture_per_response(request,response,context):
 """Only the existing SDK Session observer calls this after native checks."""
 import requests
 from provider_correlation import current_source_identity
 if current_source_identity()!=('pe_river_chart','FinMind/default multiples'):return None
 if any(not isinstance(context.get(k),str) or not context[k] for k in IDS):return None
 ticker=context['ticker']
 if not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',ticker):return None
 p=urlsplit(request.url)
 if (request.method!='GET' or p.scheme!='https' or p.hostname!='api.finmindtrade.com' or p.port not in (None,443) or p.username or p.password or p.fragment
     or p.path not in ('/api/v3/data','/api/v4/data') or type(response)is not requests.Response or response.request is not request
     or getattr(response,'from_cache',False) or not response._content_consumed or response.history or response.status_code!=200):return None
 q=parse_qs(p.query,keep_blank_values=True)
 if q.get('dataset')!=[DATASET]:return None
 # Native SDK v4 emits stock_id='' alongside its nonempty data_id.
 # Only one exact nonempty identity is allowed; the other must be absent or
 # one explicit empty value, never a second issuer or repeated parameter.
 idkeys=[k for k in ('data_id','stock_id') if q.get(k)==[ticker.split('.')[0]]]
 if len(idkeys)!=1:return None
 idkey=idkeys[0];other='stock_id'if idkey=='data_id'else'data_id'
 if q.get(other)not in (None,['']) or len(q.get('start_date',[]))!=1:return None
 start=q['start_date'][0];ends=q.get('end_date',[''])
 if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',start) or len(ends)!=1 or ends[0]and not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',ends[0]):return None
 now=time.time();today=datetime.fromtimestamp(now,ZoneInfo('Asia/Taipei')).date();a=date.fromisoformat(start);b=date.fromisoformat(ends[0])if ends[0]else today
 if not a<=b<=today:return None
 public={'dataset':DATASET,idkey:q[idkey][0],'start_date':start}
 if ends[0]:public['end_date']=ends[0]
 secrets=[v for k,values in q.items()if k not in public for v in values if v]
 for k,v in request.headers.items():
  if any(s in k.lower()for s in ('authorization','cookie','token','api-key','api_key')):secrets.extend([v,*v.split()])
 raw=response.content
 if any(s.encode()in raw for s in secrets if s):return None
 rows=body_rows(raw,ticker,a,b)
 from official_response_evidence import archive_response
 proof=archive_response(raw,source_url=p._replace(query=urlencode(public),fragment='').geturl(),retrieved_at=now,max_bytes=MAX_BYTES)
 if proof.get('status')!='archived':return None
 proof.update(http_status_observed=True,response_complete=True,request_method='GET',cache_hit=False)
 return PerCapsule(tuple(context[k]for k in IDS),proof,_digest(rows),len(rows),a.isoformat(),b.isoformat(),now)

def bind_per_quantiles(loader,frame,result,ticker):
 import pandas as pd
 from provider_correlation import current_correlation,current_source_identity
 from official_response_evidence import read_response
 c=current_correlation()
 if type(frame)is not pd.DataFrame or current_source_identity()!=('pe_river_chart','FinMind/default multiples')or c.get('ticker')!=ticker:return None
 if not isinstance(result,dict) or result.get('valuation_basis')!='historical_quantiles' or result.get('historical_quantiles_available')is not True or result.get('source')!='FinMind 5-year PER quantiles':return None
 for capsule in reversed(getattr(loader,'_stock_per_transport_capsules',[])[:8]):
  if type(capsule)is not PerCapsule or capsule.ids!=tuple(c.get(k)for k in IDS)or not 0<=time.time()-capsule.received<=180:continue
  a,b=date.fromisoformat(capsule.start),date.fromisoformat(capsule.end)
  rows=normalize_rows(frame.to_dict(orient='records'),ticker,a,b);raw=read_response(capsule.receipt,max_bytes=MAX_BYTES);original=body_rows(raw,ticker,a,b)
  if _digest(rows)!=capsule.digest or _digest(original)!=capsule.digest or len(rows)!=capsule.row_count:continue
  # Reuse the current numeric selection and pandas quantile semantics exactly.
  values=[float(v)for v in frame.get('PER',[])if isinstance(v,(int,float))and 0<float(v)<100]
  if len(values)<20 or result.get('historical_sample_count')!=len(values):return None
  multiples=sorted({round(float(pd.Series(values).quantile(q)),1)for q in (.25,.5,.75,.9)})
  if result.get('multiples')!=multiples:return None
  return {'schema':'finmind-per-body-to-quantiles:v1','coverage':'historical_per_quantiles_only','ticker':ticker,'fetch_id':c['fetch_id'],'operation_id':c['operation_id'],'transport_attempt_id':c['attempt_id'],'native_response_sha256':sha256(raw).hexdigest(),'native_response_bytes':len(raw),'native_received_at_epoch':capsule.received,'sdk_rows_sha256':capsule.digest,'sdk_row_count':len(rows),'query_start_date':capsule.start,'query_end_date':capsule.end,'historical_sample_count':len(values),'multiples':multiples,'eps_and_bands_verified':False,'independent_primary_source_verified':False,'historical_pit_verified':False}
 return None

class PerResult(dict):
 """Transient proof sidecar; dictionary/JSON payload retains original fields."""
 def __init__(self,value,lineage):
  super().__init__(value);self.native_quantile_lineage=lineage

def audit_per_lineage(entry):
 """Only sanitized same-operation proof is admitted to public observations."""
 import math
 v=entry.get('sdk_per_quantile_lineage')
 if not isinstance(v,dict) or v.get('schema')!='finmind-per-body-to-quantiles:v1' or v.get('coverage')!='historical_per_quantiles_only':return None
 if (entry.get('source')!='pe_river_chart' or entry.get('provider')!='FinMind/default multiples' or entry.get('status')!='success'
     or entry.get('cache_hit')is not False or entry.get('stale')is not False):return None
 if any(v.get(k)!=entry.get(k)for k in ('ticker','fetch_id','operation_id')):return None
 if not any(a.get('attempt_id')==v.get('transport_attempt_id') and a.get('source')=='pe_river_chart' and a.get('provider')=='FinMind/default multiples' and a.get('status')=='success'for a in entry.get('provider_attempts',[])if isinstance(a,dict)):return None
 if any(not isinstance(v.get(k),str)or not re.fullmatch('[0-9a-f]{64}',v[k])for k in ('native_response_sha256','sdk_rows_sha256')):return None
 if any(not isinstance(v.get(k),str)or not 0<len(v[k])<=160 for k in ('ticker','fetch_id','operation_id','transport_attempt_id')):return None
 if not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',v['ticker']):return None
 for k in ('query_start_date','query_end_date'):
  if not isinstance(v.get(k),str)or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',v[k]):return None
  date.fromisoformat(v[k])
 if v['query_start_date']>v['query_end_date']:return None
 if any(type(v.get(k))is not int or not lo<=v[k]<=hi for k,lo,hi in (('native_response_bytes',1,MAX_BYTES),('sdk_row_count',20,3000),('historical_sample_count',20,3000))):return None
 if v['historical_sample_count']>v['sdk_row_count']:return None
 ts=v.get('native_received_at_epoch')
 if type(ts)not in (int,float)or not math.isfinite(ts)or not 0<ts<=time.time():return None
 multiples=v.get('multiples')
 if not isinstance(multiples,list)or not 1<=len(multiples)<=4 or any(type(x)not in (int,float)or not math.isfinite(x)or not 0<x<100 for x in multiples)or multiples!=sorted(set(multiples)):return None
 if any(v.get(k)is not False for k in ('eps_and_bands_verified','independent_primary_source_verified','historical_pit_verified')):return None
 allowed={'schema','coverage','ticker','fetch_id','operation_id','transport_attempt_id','native_response_sha256','native_response_bytes','native_received_at_epoch','sdk_rows_sha256','sdk_row_count','query_start_date','query_end_date','historical_sample_count','multiples','eps_and_bands_verified','independent_primary_source_verified','historical_pit_verified'}
 return {k:v[k]for k in allowed}

def attach_per_audit(result):
 """Preserve all normal values; retain optional proof only when fully bound."""
 value=result.get('value')
 if type(value)is not PerResult:return result
 proof=value.native_quantile_lineage
 if value.get('valuation_basis')!='historical_quantiles' or value.get('historical_quantiles_available')is not True or value.get('source')!='FinMind 5-year PER quantiles' or not isinstance(proof,dict):return result
 if value.get('multiples')!=proof.get('multiples')or value.get('historical_sample_count')!=proof.get('historical_sample_count'):return result
 public=audit_per_lineage({**result['audit'],'sdk_per_quantile_lineage':proof})
 if public is not None:result['audit']['sdk_per_quantile_lineage']=public
 return result

class _PerRequestAborted(BaseException):
 """Escape the vendor's catch-all retry loop before a second native send."""

class PerTransportError(RuntimeError):
 retryable=False

def bounded_per_frame(loader,*,stock_id,start_date):
 """Use the ordinary SDK method with a single-send, instance-local budget.

The SDK's shared helpers and requests classes remain unchanged. The existing
native observer still sees the original response. An unobserved custom loader
retains its original interface and cannot gain a native proof from this helper.
"""
 import requests
 session=getattr(loader,'_FinMindApi__session',None)
 if type(session)is not requests.Session or getattr(session,'_stock_transport_receipts_installed',False)is not True:
  return loader.taiwan_stock_per_pbr(stock_id=stock_id,start_date=start_date)
 original=session.send;attempted=False
 def send_once(request,*args,**kwargs):
  nonlocal attempted
  if attempted:raise _PerRequestAborted()
  attempted=True
  return original(request,*args,**kwargs)
 session.send=send_once
 try:
  from finmind_loader_limits import existing_per_socket_budget
  with existing_per_socket_budget():
   return loader.taiwan_stock_per_pbr(stock_id=stock_id,start_date=start_date,timeout=12)
 except _PerRequestAborted:
  raise PerTransportError('PER source single-send budget exhausted')from None
 except requests.RequestException as error:
  # The generic SDK adapter now exits after its first actual failure, before
  # the old second-send abort fires. Preserve this workflow's no-resend policy.
  error.retryable=False
  raise
 finally:
  if session.send is send_once:session.send=original
