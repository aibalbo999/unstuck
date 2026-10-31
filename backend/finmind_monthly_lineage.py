"""Passive native FinMind monthly body -> SDK rows -> existing formatter proof.

This never supplies data, changes cache status or certifies direct official/PIT
truth. Ambiguity drops only this optional proof, preserving original behavior.
"""
from dataclasses import dataclass
from datetime import date,datetime
from decimal import Decimal
from hashlib import sha256
import json,math,re,time
from urllib.parse import parse_qs,urlsplit,urlencode
from zoneinfo import ZoneInfo

SCHEMA='finmind-monthly-body-to-result:v1'
DATASET='TaiwanStockMonthRevenue'
PROVIDER='FinMind TaiwanStockMonthRevenue'
MAX_BYTES=2_000_000
_KEYS={'date','stock_id','country','revenue','revenue_month','revenue_year','create_time'}
_REQUIRED=_KEYS-{'country','create_time'}
_IDS=('ticker','fetch_id','operation_id','attempt_id')

def _digest(value):
 return sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def _number(value):
 if isinstance(value,bool) or len(str(value))>64:raise ValueError('invalid monetary number')
 number=Decimal(str(value))
 if not number.is_finite() or len(number.as_tuple().digits)>32:raise ValueError('invalid monetary number')
 if number.is_zero():return Decimal(0)
 if not -20<=number.adjusted()<=30:raise ValueError('monetary exponent limit')
 return number

def _decimal_text(value):
 text=format(_number(value),'f')
 return text.rstrip('0').rstrip('.') if '.' in text else text

def _rows(rows,ticker,start,end):
 if not isinstance(rows,list) or not 0<len(rows)<=120:raise ValueError('monthly row limit')
 normalized=[];columns=None
 for row in rows:
  if not isinstance(row,dict) or not _REQUIRED<=row.keys() or not row.keys()<=_KEYS:raise ValueError('monthly row schema')
  if columns is not None and set(row)!=columns:raise ValueError('nonuniform monthly columns')
  columns=set(row)
  if row['stock_id']!=ticker.split('.')[0] or not isinstance(row['date'],str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',row['date']):raise ValueError('monthly issuer/date')
  observed=date.fromisoformat(row['date'])
  year,month=(_number(row[k]) for k in ('revenue_year','revenue_month'))
  if year!=year.to_integral_value() or month!=month.to_integral_value() or not 1990<=year<=end.year or not 1<=month<=12:raise ValueError('monthly period')
  if not start<=observed<=end or date(int(year),int(month),1)>observed:raise ValueError('monthly request period')
  if 'country' in row and (not isinstance(row['country'],str) or len(row['country'])>64):raise ValueError('monthly country')
  if 'create_time' in row:
   created=row['create_time']
   today=datetime.fromtimestamp(time.time(),ZoneInfo('Asia/Taipei')).date()
   if not isinstance(created,str) or created and (not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',created) or not date(2026,4,21)<=date.fromisoformat(created)<=today):raise ValueError('monthly provider ingestion date')
  normalized.append({k:('number',_decimal_text(v)) if k in {'revenue','revenue_month','revenue_year'} else ('text',v) for k,v in row.items()})
 return sorted(normalized,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':')))

def _unique(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('duplicate JSON key')
  result[key]=value
 return result

def _body(raw,ticker,start,end):
 if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_BYTES:raise ValueError('monthly body limit')
 payload=json.loads(raw.decode('utf-8','strict'),object_pairs_hook=_unique,parse_float=Decimal,parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite JSON')))
 if not isinstance(payload,dict) or set(payload)!={'msg','status','data'} or payload['msg']!='success' or type(payload['status']) is not int or payload['status']!=200:raise ValueError('monthly envelope')
 return _rows(payload['data'],ticker,start,end)

@dataclass(frozen=True)
class _Capsule:
 ids:tuple
 receipt:dict
 row_digest:str
 row_count:int
 start:str
 end:str
 received:float

def capture_monthly_response(request,response,context):
 """Called only after native Session/adapter/send checks, never independently."""
 if any(not isinstance(context.get(k),str) or not context[k] for k in _IDS):return None
 ticker=context['ticker']
 if not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',ticker):return None
 parts=urlsplit(request.url)
 if (request.method!='GET' or parts.scheme!='https' or parts.hostname!='api.finmindtrade.com'
     or parts.port not in (None,443) or parts.username or parts.password
     or parts.path not in ('/api/v3/data','/api/v4/data')
     or response.request is not request or getattr(response,'from_cache',False)
     or not response._content_consumed or response.history):return None
 query=parse_qs(parts.query,keep_blank_values=True)
 if query.get('dataset')!=[DATASET] or response.status_code!=200:return None
 identity_key='data_id' if 'data_id' in query else 'stock_id'
 if query.get(identity_key)!=[ticker.split('.')[0]] or len(query.get('start_date',[]))!=1:return None
 start_literal=query['start_date'][0]
 if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',start_literal):return None
 received=time.time();today=datetime.fromtimestamp(received,ZoneInfo('Asia/Taipei')).date();start=date.fromisoformat(start_literal)
 values=query.get('end_date',['']);end_literal=values[0] if len(values)==1 else None
 if end_literal is None or end_literal and not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',end_literal):return None
 end=date.fromisoformat(end_literal) if end_literal else today
 if start>end or end>today:return None
 public={'dataset':DATASET,identity_key:query[identity_key][0],'start_date':start_literal}
 if end_literal:public['end_date']=end_literal
 raw=response.content
 # No credential value may enter the public original. Unknown query arguments
 # are treated as private rather than copied into the source URL.
 secrets=[v for k,values in query.items() if k not in public for v in values if v]
 for key,value in request.headers.items():
  if any(word in key.lower() for word in ('authorization','cookie','token','api-key','api_key')):secrets.extend([value,*value.split()])
 if any(secret.encode('utf-8') in raw for secret in secrets if secret):return None
 rows=_body(raw,ticker,start,end)
 texts=[v[1] for row in rows for v in row.values() if v[0]=='text']
 if any(secret in text for secret in secrets for text in texts if secret):return None
 from official_response_evidence import archive_response
 receipt=archive_response(raw,source_url=parts._replace(query=urlencode(public),fragment='').geturl(),retrieved_at=received,max_bytes=MAX_BYTES)
 if receipt.get('status')!='archived':return None
 receipt.update(http_status_observed=True,response_complete=True,request_method='GET',cache_hit=False)
 return _Capsule(tuple(context[k] for k in _IDS),receipt,_digest(rows),len(rows),start.isoformat(),end.isoformat(),received)

def bind_monthly_result(loader,frame,formatted,ticker):
 from provider_correlation import current_correlation,current_source_identity
 from data_fetch.market_sources.monthly_revenue_rows import format_monthly_revenue_rows
 from official_response_evidence import read_response
 import pandas as pd
 context=current_correlation()
 if type(frame) is not pd.DataFrame or current_source_identity()!=('monthly_revenue',PROVIDER):return None
 if ticker!=context.get('ticker') or formatted!=format_monthly_revenue_rows(frame) or not formatted:return None
 for capsule in reversed(getattr(loader,'_stock_monthly_transport_capsules',[])[:8]):
  if type(capsule) is not _Capsule or capsule.ids!=tuple(context.get(k) for k in _IDS) or not 0<=time.time()-capsule.received<=180:continue
  rows=_rows(frame.to_dict(orient='records'),ticker,date.fromisoformat(capsule.start),date.fromisoformat(capsule.end))
  raw=read_response(capsule.receipt,max_bytes=MAX_BYTES)
  replay=_body(raw,ticker,date.fromisoformat(capsule.start),date.fromisoformat(capsule.end))
  if _digest(rows)!=capsule.row_digest or _digest(replay)!=capsule.row_digest or len(rows)!=capsule.row_count:continue
  return {'schema':SCHEMA,'dataset':DATASET,'ticker':ticker,'fetch_id':context['fetch_id'],'operation_id':context['operation_id'],'transport_attempt_id':context['attempt_id'],
   'native_response_sha256':capsule.receipt['raw_response_sha256'],'native_source_url_sha256':sha256(capsule.receipt['source_url'].encode()).hexdigest(),'native_response_bytes':len(raw),'native_received_at_epoch':capsule.received,
   'sdk_rows_sha256':capsule.row_digest,'sdk_row_count':len(rows),'formatted_rows_sha256':_digest(formatted),'formatted_row_count':len(formatted),
   'query_start_date':capsule.start,'query_end_date':capsule.end,'request_url_credentials_redacted':True,'native_http_status':200,'archived_original_available':True,'independent_primary_source_verified':False,'historical_pit_verified':False}
 return None

def audit_lineage(entry):
 """Keep only a fully bound, secret-free public fingerprint on a success row."""
 value=entry.get('sdk_payload_lineage')
 if not isinstance(value,dict) or value.get('schema')!=SCHEMA or value.get('dataset')!=DATASET:return None
 if entry.get('source')!='monthly_revenue' or entry.get('provider')!=PROVIDER or entry.get('status')!='success' or entry.get('cache_hit') is not False:return None
 if any(value.get(k)!=entry.get(k) for k in ('ticker','fetch_id','operation_id')):return None
 if not any(a.get('attempt_id')==value.get('transport_attempt_id') and a.get('status')=='success' for a in entry.get('provider_attempts',[]) if isinstance(a,dict)):return None
 hashes=('native_response_sha256','native_source_url_sha256','sdk_rows_sha256','formatted_rows_sha256')
 if any(not isinstance(value.get(k),str) or not re.fullmatch('[0-9a-f]{64}',value[k]) for k in hashes):return None
 if any(type(value.get(k)) is not int or not 0<value[k]<=limit for k,limit in (('native_response_bytes',MAX_BYTES),('sdk_row_count',120),('formatted_row_count',6))):return None
 if (type(entry.get('record_count')) is not int or value['formatted_row_count']!=entry['record_count']
     or value['formatted_row_count']>value['sdk_row_count']
     or type(value.get('native_http_status')) is not int or value['native_http_status']!=200):return None
 if value.get('request_url_credentials_redacted') is not True:return None
 if value.get('archived_original_available') is not True or value.get('independent_primary_source_verified') is not False or value.get('historical_pit_verified') is not False:return None
 if type(value.get('native_received_at_epoch')) not in (int,float) or not math.isfinite(value['native_received_at_epoch']) or not 0<value['native_received_at_epoch']<=time.time():return None
 if any(not isinstance(value.get(k),str) or len(value[k])>160 for k in ('ticker','fetch_id','operation_id','transport_attempt_id')):return None
 for key in ('query_start_date','query_end_date'):
  if not isinstance(value.get(key),str) or not re.fullmatch(r'20\d{2}-\d{2}-\d{2}',value[key]):return None
  date.fromisoformat(value[key])
 if value['query_start_date']>value['query_end_date'] or not re.fullmatch(r'[0-9]{4,6}\.(TW|TWO)',value['ticker']):return None
 allowed={'schema','dataset','ticker','fetch_id','operation_id','transport_attempt_id',*hashes,'native_response_bytes','native_received_at_epoch','sdk_row_count','formatted_row_count','query_start_date','query_end_date','request_url_credentials_redacted','native_http_status','archived_original_available','independent_primary_source_verified','historical_pit_verified'}
 return {k:value[k] for k in allowed}


def bind_audited_result(audit,value,lineage):
 if not isinstance(lineage,dict) or _digest(value)!=lineage.get('formatted_rows_sha256'):return None
 return audit_lineage({**audit,'sdk_payload_lineage':lineage})
