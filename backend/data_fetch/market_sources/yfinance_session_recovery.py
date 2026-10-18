"""Recover one missing completed-session bar from the same provider, never impute."""
from datetime import datetime, date, timedelta, timezone
import pandas as pd
from shared_provider_cache import shared_fetch
from short_term_market_data import daily_market_data_from_frame
from market_price_reconciliation import number

COLUMNS=('Open','High','Low','Close','Adj Close','Volume')


def recover_session(stock, raw, expected, *, as_of):
    result={'attempted':False,'adopted':False}
    if not expected or raw is None or raw.empty:return raw,result
    normalized=daily_market_data_from_frame(raw,as_of=as_of,volume_unit='shares')
    matching=raw[[index.date().isoformat()==expected for index in raw.index]]
    latest=matching.iloc[-1] if not matching.empty else None
    closes=[number(latest.get(key)) if latest is not None else None for key in ('Close','Adj Close')]
    if normalized['as_of']==expected and all(x is not None and x>0 for x in closes):return raw,result
    query={'start':expected,'end':(date.fromisoformat(expected)+timedelta(days=1)).isoformat(),'auto_adjust':False}
    result={'attempted':True,'adopted':False,'query':query,'date':expected}
    def fetch():
        frame=stock.history(**query)
        if frame is None or frame.empty:raise ValueError('Provider session unavailable')
        rows=frame[[index.date().isoformat()==expected for index in frame.index]]
        if rows.empty:raise ValueError('Provider session date mismatch')
        row=rows.iloc[-1];values={key:number(row.get(key)) for key in COLUMNS}
        valid=daily_market_data_from_frame(rows.tail(1),as_of=as_of,volume_unit='shares')
        if not valid['bars'] or any(values[key] is None or values[key]<=0 for key in ('Open','High','Low','Close','Adj Close')) or values['Volume'] is None or values['Volume']<0:
            raise ValueError('Provider OHLC/adjustment/volume incomplete')
        return {'date':expected,'values':values,'retrieved_at':datetime.now(timezone.utc).isoformat()}
    ticker=str(getattr(stock,'ticker','') or '')
    value,meta=shared_fetch('yahoo-completed-session-recovery:v1:'+ticker+':'+expected,fetch,freshness_seconds=21600,retention_seconds=21600,error_retry_seconds=60,lock_wait_seconds=1)
    result.update(cache_hit=meta.get('cache_hit',False),retrieved_at=(value or {}).get('retrieved_at'))
    if not value or meta.get('stale') or meta.get('error_kind'):
        result['reason']='session_recovery_unavailable';return raw,result
    values=value.get('values') or {}
    # Known values must agree before supplementing the provider's missing cells.
    if latest is not None:
        conflicts=[]
        for key in COLUMNS:
            before,after=number(latest.get(key)),number(values.get(key))
            tolerance=0.0 if key=='Volume' else max(.0001,abs(after or 0)*1e-7)
            if before is not None and after is not None and abs(before-after)>tolerance:conflicts.append(key)
        if conflicts:
            result.update(reason='overlapping_provider_fields_conflict',conflicting_fields=conflicts);return raw,result
    frame=raw.copy();indices=[index for index in frame.index if index.date().isoformat()==expected]
    index=indices[-1] if indices else pd.Timestamp(expected,tz=frame.index.tz)
    # Use the independently returned complete row, including its actual Adj Close.
    for key,value_number in values.items():frame.loc[index,key]=value_number
    result.update(adopted=True,reason='same_provider_exact_session_observation')
    return frame,result
