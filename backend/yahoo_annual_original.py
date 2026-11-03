"""Passive native annual Yahoo originals; no acquisition or financial certification."""
import json,re,time
from urllib.parse import urlsplit,parse_qs,parse_qsl,unquote,quote
from yahoo_public_original import _public_tree


def is_canonical_public_annual_url(url):
 """Bound only hash-only observation metadata, never source/data admission.

 A full145-field balance-sheet query exceeds the generic4096-character URL
 allowance. This finite profile accepts only the capture's exact anonymous
 canonical URL; no crumb, credentials, arbitrary query or raw URL is retained.
 """
 try:
  if not isinstance(url,str)or not 0<len(url)<=8192:return False
  parts=urlsplit(url)
  if(parts.scheme!='https'or parts.netloc not in{'query1.finance.yahoo.com','query2.finance.yahoo.com'}or parts.fragment):return False
  pairs=parse_qsl(parts.query,keep_blank_values=True,strict_parsing=True)
  if len(pairs)!=2 or [k for k,_ in pairs]!=['symbol','type']:return False
  symbol,series=pairs[0][1],pairs[1][1]
  if not re.fullmatch(r'[A-Z0-9][A-Z0-9.^=-]{0,39}',symbol):return False
  path='/ws/fundamentals-timeseries/v1/finance/timeseries/'+quote(symbol,safe='.^=-')
  types=series.split(',')
  if parts.path!=path or not 1<=len(types)<=300 or len(types)!=len(set(types)):return False
  from yfinance.const import fundamentals_keys
  allowed={'annual'+v for fields in fundamentals_keys.values()for v in fields}
  if any(t not in allowed for t in types):return False
  canonical='https://'+parts.netloc+path+'?symbol='+quote(symbol,safe='')+'&type='+quote(series,safe=',')
  return canonical==url
 except (ImportError,ValueError,TypeError,UnicodeError):return False


def _capture_annual_response(response,*,binding,selected_peer=None):
 try:
  from curl_cffi.requests import Response
  from provider_correlation import current_correlation
  from official_response_evidence import archive_response
  from yfinance.const import fundamentals_keys
  context=current_correlation()
  if not isinstance(binding,dict)or not all(isinstance(binding.get(k),str)and binding[k]and context.get(k)==binding[k]for k in('ticker','fetch_id','operation_id')):return None
  symbol=binding['ticker'] if selected_peer is None else selected_peer
  if selected_peer is not None:
   from provider_correlation import current_source_identity
   if symbol==binding['ticker']or current_source_identity()!=('dynamic_peer_metrics','FinMind/yfinance'):return None
  if not re.fullmatch(r'[A-Z0-9][A-Z0-9.^=-]{0,39}',symbol):return None
  if(type(response)is not Response or response.status_code!=200 or response.history or response.redirect_count or getattr(response,'from_cache',False)or response.queue is not None or response.stream_task is not None or response.astream_task is not None):return None
  request=response.request
  if request is None or request.method!='GET'or request.headers.get('Authorization'):return None
  actual,sent=urlsplit(response.url),urlsplit(request.url)
  path='/ws/fundamentals-timeseries/v1/finance/timeseries/'+quote(symbol,safe='.^=-')
  if any(p.scheme!='https'or p.hostname not in{'query1.finance.yahoo.com','query2.finance.yahoo.com'}or p.port not in(None,443)or p.username or p.password or p.fragment or unquote(p.path)!=unquote(path)for p in(actual,sent))or actual.hostname!=sent.hostname:return None
  aq,sq=parse_qs(actual.query),parse_qs(sent.query)
  if aq.get('symbol')!=[symbol]or sq.get('symbol')!=[symbol]or aq.get('type')!=sq.get('type')or len(aq.get('type',[]))!=1:return None
  types=aq['type'][0].split(',');allowed={'annual'+v for fields in fundamentals_keys.values()for v in fields}
  if not types or len(types)>300 or len(types)!=len(set(types))or any(t not in allowed for t in types):return None
  body=response.content
  if not isinstance(body,bytes)or not 0<len(body)<=2_000_000:return None
  payload=json.loads(body)
  if not isinstance(payload,dict)or set(payload)!={'timeseries'}or not _public_tree(payload):return None
  envelope=payload['timeseries']
  if not isinstance(envelope,dict)or envelope.get('error')is not None:return None
  rows=envelope.get('result')
  if not isinstance(rows,list)or not 0<len(rows)<=300:return None
  seen=set()
  for row in rows:
   if not isinstance(row,dict)or not isinstance(row.get('meta'),dict):return None
   meta=row['meta'];kind=meta.get('type')
   if meta.get('symbol')!=[symbol]or not isinstance(kind,list)or len(kind)!=1 or kind[0]not in types or kind[0]in seen:return None
   seen.add(kind[0])
   if set(row)-{'meta','timestamp',kind[0]}:return None
   if kind[0]in row and not isinstance(row[kind[0]],list):return None
  url='https://'+actual.hostname+path+'?symbol='+quote(symbol,safe='')+'&type='+quote(','.join(types),safe=',')
  proof=archive_response(body,source_url=url,retrieved_at=time.time(),evidence_kind='decoded_complete_http_response_body',max_bytes=2_000_000)
  if proof.get('status')!='archived':return None
  return {**proof,'http_status_observed':True,'response_complete':True,'cache_hit':False,'request_method':'GET','financial_semantics_verified':False}
 except Exception:return None


def capture_annual_response(response,*,binding):
 return _capture_annual_response(response,binding=binding)


def capture_peer_annual_response(response,*,binding,symbol):
 return _capture_annual_response(response,binding=binding,selected_peer=symbol)
