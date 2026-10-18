"""Exact dated TPEX stock rows from its official monthly single-stock endpoint.

The monthly payload's date is the month, never the observation date. Raw volume
is in lots as published, excluding block trades; it is not TWSE share volume.
"""
from datetime import date, datetime, timezone
import math
import re
from urllib.parse import urlencode
from external_http_client import sync_get
from shared_provider_cache import shared_fetch

DATED_URL='https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock'
FIELDS={'open':'開盤','high':'最高','low':'最低','close':'收盤','volume':'成交張數'}
SCOPE_NOTE='以上資料不含上櫃股票鉅額交易'

def query_params(ticker,day):
    code,sep,market=str(ticker).partition('.')
    if sep!='.' or market!='TWO' or not re.fullmatch(r'[1-9][0-9]{3}',code):
        raise ValueError('Exact supported TPEX ticker required;no instrument inference')
    d=date.fromisoformat(day)
    return {'code':code,'date':d.strftime('%Y/%m/01'),'response':'json'}

def source_url(ticker,day):
    return DATED_URL+'?'+urlencode(query_params(ticker,day))

def number(value):
    if isinstance(value,bool):raise ValueError('Invalid official numeric field')
    result=float(str(value).replace(',',''))
    if not math.isfinite(result) or result<0:raise ValueError('Invalid official numeric field')
    return result

def parse_observation(payload,ticker,day):
    params=query_params(ticker,day);expected=date.fromisoformat(day)
    if not isinstance(payload,dict) or payload.get('stat')!='ok' or payload.get('code')!=params['code'] or payload.get('date')!=expected.strftime('%Y%m01') or payload.get('flagField')!='張數':
        raise ValueError('TPEX symbol/month/status/volume unit not verified')
    matches=[]
    for table in payload.get('tables') or []:
        if not isinstance(table,dict) or table.get('title')!='個股日成交資訊' or table.get('date')!=expected.strftime('%Y%m01'):continue
        fields=table.get('fields') or []
        if len(fields)!=len(set(fields)) or not {'日 期',*FIELDS.values()}.issubset(fields):continue
        for values in table.get('data') or []:
            if not isinstance(values,list) or len(values)!=len(fields):continue
            row=dict(zip(fields,values));m=re.fullmatch(r'([0-9]{3})/([0-9]{2})/([0-9]{2})',str(row.get('日 期')))
            if not m:continue
            observed=date(int(m[1])+1911,int(m[2]),int(m[3])).isoformat()
            if observed!=day:continue
            numbers={key:number(row[field]) for key,field in FIELDS.items()}
            if any(numbers[k]<=0 for k in ('open','high','low','close')) or numbers['high']<max(numbers['open'],numbers['low'],numbers['close']) or numbers['low']>min(numbers['open'],numbers['close']):
                raise ValueError('TPEX OHLC inconsistent or missing')
            notes=table.get('notes') or [];scope_note=SCOPE_NOTE if SCOPE_NOTE in notes else None
            matches.append({'date':day,**numbers,'source_fields':{field:row[field] for field in FIELDS.values()},'volume_unit':'lots','volume_scope':'tpex_stock_monthly_excluding_block_trades' if scope_note else None,'volume_scope_note':scope_note,'volume_scope_verified':bool(scope_note)})
    if len(matches)!=1:raise ValueError('Unique exact TPEX daily row unavailable')
    return matches[0]

def official_observation(ticker,day):
    try:params=query_params(ticker,day);url=source_url(ticker,day)
    except (TypeError,ValueError):return {'status':'not_applicable','ticker':ticker}
    from market_evidence_policy import acquisition_phase
    phase=acquisition_phase(day)
    def fetch():
        response=sync_get(DATED_URL,params=params,timeout=15,headers={'User-Agent':'stock-agent/1.0 Mozilla/5.0'},provider='TPEX official stock history')
        payload=response.json();row=parse_observation(payload,ticker,day)
        from official_response_evidence import archive_response
        acquired=datetime.now(timezone.utc).isoformat()
        proof=archive_response(getattr(response,'content',None),source_url=url,retrieved_at=acquired,http_status=getattr(response,'status_code',None))
        return {'row':row,'raw_evidence':proof,'retrieved_at':acquired,'acquisition_phase':acquisition_phase(day,datetime.fromisoformat(acquired))}
    key='tpex-report-official-stock-session:v1:'+str(ticker)+':'+day+':'+phase
    value,meta=shared_fetch(key,fetch,freshness_seconds=300 if phase!='post_cutoff' else 21600,retention_seconds=21600,error_retry_seconds=60,lock_wait_seconds=1)
    if not isinstance(value,dict) or meta.get('stale') or meta.get('error_kind'):
        return {'status':'unavailable','ticker':ticker,'date':day,'source_url':url,'error_kind':meta.get('error_kind'),'retrieved_at':None}
    proof=value.get('raw_evidence') or {}
    return {**value['row'],'status':'observed','ticker':ticker,'source':'TPEX monthly stock history;exact daily row','source_url':url,'raw_evidence':proof,'retrieved_at':value.get('retrieved_at'),'acquisition_phase':value.get('acquisition_phase'),'usable_for_completed_session':value.get('acquisition_phase')=='post_cutoff' and proof.get('status')=='archived','price_basis':'unadjusted_exchange_ohlc','historical_point_in_time_verified':False,'finality_verified':False,'cache_hit':meta.get('cache_hit',False)}
