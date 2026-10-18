"""Keep reused annual-source time separate from a newly fetched quote."""
from datetime import datetime,timezone
import math
import re
import json
from hashlib import sha256


def valid_cached_histories(stored):
    if not isinstance(stored,dict) or not isinstance(stored.get('histories'),dict):return False
    row=stored['histories'];years=row.get('years')
    if (not isinstance(years,list) or any(not isinstance(y,str) for y in years)
            or not isinstance(stored.get('notes'),list) or any(not isinstance(x,str) for x in stored['notes'])):return False
    try:
        for key in ('revenue_history','net_income_history','gross_profit_history','operating_income_history',
                    'fcf_history','total_assets_history','total_equity_history'):
            values=row.get(key)
            if not isinstance(values,list) or len(values)!=len(years):return False
            if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v)) for v in values):return False
        return True
    except (TypeError,ValueError,OverflowError):return False


def balance_inputs_digest(row):
    return sha256(json.dumps({k:row[k] for k in ('schema','ticker','period','assets','equity','data_fingerprint')},
                            sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def original_stamp(audit, now):
    stamp=audit.get('fetched_at_epoch');iso=None
    if audit.get('fetched_at') is not None:
        try:
            parsed=datetime.fromisoformat(audit['fetched_at'].replace('Z','+00:00'))
            if parsed.tzinfo is None:return None
            iso=parsed.timestamp()
        except (TypeError,ValueError,OverflowError,AttributeError):return None
    if stamp is None:stamp=iso
    try:
        if (type(stamp) not in (int,float) or not math.isfinite(stamp) or not 0<stamp<=now
                or iso is not None and abs(stamp-iso)>=1):return None
    except (TypeError,ValueError,OverflowError):return None
    return stamp


def preserve_reused_annual_freshness(data,ticker,audits,now):
    entries=[a for a in audits if isinstance(a,dict)]
    if not any(a.get('cache_hit') is True for a in entries):return
    from data_freshness import build_source_freshness_entry
    stamps=[original_stamp(a,now) for a in entries]
    # An undated cached observation cannot become current with the quote.
    stamp=min(stamps) if stamps and all(s is not None for s in stamps) else None
    data.setdefault('source_freshness',{})['financial_statements']=build_source_freshness_entry(
        'financial_statements',ticker,stamp,cache_hit=True,now_epoch=now,
        source_data={'stale':True} if any(a.get('stale') is True for a in entries) else None)


def primary_balance_frame(data,now):
    """Reuse the same unrounded SDK values only when aligned with these histories."""
    if not isinstance(data,dict):return None
    row=data.get('primary_balance_snapshot');audit=data.get('primary_financial_audit')
    if not isinstance(row,dict) or not isinstance(audit,dict):return None
    try:
        period=datetime.strptime(row['period'],'%Y-%m-%d').date()
        if (row.get('schema')!='yahoo-annual-balance-inputs.v1' or row.get('ticker')!=data.get('ticker')
                or period>datetime.fromtimestamp(now,timezone.utc).date()
                or audit.get('source')!='financial_statements' or audit.get('provider')!='Yahoo annual financial statements'
                or audit.get('ticker')!=data.get('ticker')
                or audit.get('status') not in {'success','degraded_enrichment','skipped_fresh_cache'}
                or audit.get('component_statuses',{}).get('balance_sheet',{}).get('status')!='complete'
                or original_stamp(audit,now) is None
                or not re.fullmatch(r'[0-9a-f]{64}',str(row.get('data_fingerprint')or''))
                or row['data_fingerprint']!=audit.get('data_fingerprint')
                or balance_inputs_digest(row)!=audit.get('balance_inputs_sha256')
                or data['years'][-1]!=str(period.year)):
            return None
        for name,history in [('assets','total_assets_history'),('equity','total_equity_history')]:
            value=row[name]
            if (type(value) not in (int,float) or not math.isfinite(value) or value<=0
                    or type(data[history][-1]) not in (int,float)
                    or round(value/1e9,2)!=data[history][-1]):return None
        import pandas as pd
        return pd.DataFrame({'original':[row['assets'],row['equity']]},
                            index=['Total Assets','Stockholders Equity'])
    except (KeyError,ValueError,TypeError,AttributeError,IndexError,OverflowError):return None
