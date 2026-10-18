"""A bounded, cached official-session observation for report price comparisons."""
from datetime import datetime, timezone
import hashlib
import re
from external_http_client import sync_get
from shared_provider_cache import shared_fetch
from screener_twse_daily import DATED_URL, observed_date, numeric

CACHE_VERSION = 'report-official-session-ohlcv:v4:'


def official_quote_code(code):
    # Preserve official stock and zero-leading fund identifiers verbatim.
    # A matched quote is not an instrument or strategy eligibility decision.
    return isinstance(code, str) and re.fullmatch(
        r'(?:[1-9][0-9]{3}|0[0-9]{3,5}|0[0-9]{4}[A-Z])', code) is not None


FIELDS = {'open':'開盤價','high':'最高價','low':'最低價','close':'收盤價','volume':'成交股數'}


def parse_session(payload, day):
    if not isinstance(payload,dict) or payload.get('stat')!='OK' or observed_date(payload.get('date'))!=day:
        raise ValueError('Official session date/status not verified')
    for table in payload.get('tables') or []:
        fields=table.get('fields') or []
        if not {'證券代號',*FIELDS.values()}.issubset(fields):continue
        notes=table.get('notes') or []
        scope_note=next((str(note) for note in notes if '本統計資訊含一般、零股、盤後定價、鉅額交易，不含拍賣、標購' in str(note)),None)
        rows={}
        for values in table.get('data') or []:
            if not isinstance(values,list) or len(values)!=len(fields):continue
            row=dict(zip(fields,values));code=str(row['證券代號']).strip()
            if not official_quote_code(code):continue
            rows[code]={'date':day,**{key:numeric(row[field]) for key,field in FIELDS.items()},'source_fields':{field:row[field] for field in FIELDS.values()},'volume_scope':'twse_general_odd_fixed_block_excluding_auction_tender' if scope_note else None,'volume_scope_note':scope_note,'volume_scope_verified':bool(scope_note)}
        if rows:return rows
    raise ValueError('Official OHLC/share-volume table missing')


def official_observation(ticker, day):
    """No approximate ticker mapping, previous-day fallback or fake acquisition time."""
    code,sep,market=str(ticker).partition('.')
    if sep!='.' or market!='TW' or not official_quote_code(code):
        return {'status':'not_applicable','ticker':ticker}
    from market_evidence_policy import acquisition_phase
    phase=acquisition_phase(day)
    url=DATED_URL+'?date='+day.replace('-','')+'&type=ALL&response=json'
    def fetch():
        response=sync_get(DATED_URL,params={'date':day.replace('-',''),'type':'ALL','response':'json'},timeout=15,headers={'User-Agent':'stock-agent/1.0 Mozilla/5.0'},provider='TWSE Free API')
        payload=response.json()
        from official_response_evidence import archive_response
        acquired=datetime.now(timezone.utc).isoformat()
        proof=archive_response(getattr(response,'content',None),source_url=url,retrieved_at=acquired,http_status=getattr(response,'status_code',None))
        return {'raw_evidence':proof,'acquisition_phase':phase,'date':day,'rows':parse_session(payload,day),'retrieved_at':datetime.now(timezone.utc).isoformat(),'response_sha256':hashlib.sha256(response.content).hexdigest(),'response_hash_kind':'raw HTTP response bytes;full response not archived in report'}
    value,meta=shared_fetch(CACHE_VERSION+day+':'+phase,fetch,freshness_seconds=300 if phase!='post_cutoff' else 21600,retention_seconds=21600,error_retry_seconds=60,lock_wait_seconds=1)
    if not isinstance(value,dict) or meta.get('stale') or meta.get('error_kind'):
        return {'status':'unavailable','ticker':ticker,'date':day,'source_url':url,'error_kind':meta.get('error_kind'),'cache_hit':meta.get('cache_hit',False),'retrieved_at':None}
    row=value.get('rows',{}).get(code)
    if row is None:return {'status':'symbol_missing','ticker':ticker,'date':day,'source_url':url,'retrieved_at':value.get('retrieved_at'),'cache_hit':meta.get('cache_hit',False)}
    return {**row,'raw_evidence':value.get('raw_evidence'),'acquisition_phase':value.get('acquisition_phase'),'usable_for_completed_session':phase=='post_cutoff' and (value.get('raw_evidence') or {}).get('status')=='archived','cache_key':CACHE_VERSION+day+':'+phase,'status':'observed','ticker':ticker,'source':'TWSE MI_INDEX daily closing table','source_url':url,'volume_unit':'shares','price_basis':'unadjusted_exchange_ohlc','retrieved_at':value.get('retrieved_at'),'response_sha256':value.get('response_sha256'),'response_hash_kind':value.get('response_hash_kind'),'cache_hit':meta.get('cache_hit',False),'historical_point_in_time_verified':False}
