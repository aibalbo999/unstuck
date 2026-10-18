"""Recompute cited institutional observations, without inventing primary provenance."""
import hashlib
import json
import math
from datetime import datetime, timezone


def institutional_claim_lineage(data, record):
    raw = data.get('institutional_trading') or {}
    raw = raw if isinstance(raw,dict) else {}
    rows = raw.get('daily_category_observations') or []
    receipt = {'status':'unavailable', 'independent_primary_source_verified':False,
               'scope':'saved normalized provider observations; not raw HTTP or historical PIT proof',
               'provider':record.get('provider'), 'population':record.get('population'),
               'window':record.get('window'), 'observed_at':record.get('observed_at'),
               'reported_value':record.get('value'), 'unit':record.get('unit')}
    def finish(status, reason):
        return dict(receipt, status=status, reason=reason)
    if not isinstance(rows, list) or not rows:
        return finish('unavailable','daily_observations_not_saved')
    window = record.get('window') or {}; population = record.get('population')
    if not isinstance(window,dict):
        return finish('unavailable','window_unknown')
    if population not in {'foreign','investment_trust','dealer','total'}:
        return finish('unavailable','population_unknown')
    categories = {'foreign','investment_trust','dealer'} if population=='total' else {population}
    dates = sorted({r.get('date') for r in rows if isinstance(r,dict) and isinstance(r.get('date'),str)})
    if window.get('kind')=='day':
        expected = [record.get('observed_at')]
    elif window.get('kind')=='trailing_trading_days':
        count = window.get('trading_days')
        if isinstance(count,bool) or not isinstance(count,(int,float)) or not math.isfinite(count) or count<=0 or int(count)!=count:
            return finish('unavailable','window_unknown')
        expected = dates[-int(count):]
        from data_fetch.institutional_provider import institutional_window_status
        if len(expected)!=int(count) or institutional_window_status(expected,str(data.get('ticker') or ''),int(count))!='complete':
            return finish('unavailable','exchange_session_window_incomplete')
    else:
        return finish('unavailable','window_unknown')
    if not expected or expected[-1]!=record.get('observed_at'):
        return finish('unavailable','observation_endpoint_mismatch')
    selected = [r for r in rows if isinstance(r,dict) and r.get('date') in expected and r.get('category') in categories]
    keys=[(r['date'],r['category']) for r in selected]
    wanted={(day,category) for day in expected for category in categories}
    if set(keys)!=wanted or len(keys)!=len(wanted):
        return finish('unavailable','missing_or_duplicate_category_observations')
    for row in selected:
        value=row.get('net_buy_shares')
        if (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)
                or int(value)!=value or row.get('unit')!='shares' or not isinstance(row.get('source'),str) or not row.get('source')):
            return finish('unavailable','invalid_observation_value_unit_or_source')
    if any(row['source'] not in str(record.get('provider') or '').split(' + ') for row in selected):
        return finish('unavailable','provider_dataset_mismatch')
    selected=sorted(selected,key=lambda r:(r['date'],r['category']))
    receipt.update(observation_dates=expected, row_count=len(selected),
                   normalized_observations_sha256=hashlib.sha256(json.dumps(selected,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
                   normalized_observations_path='data.institutional_trading.daily_category_observations',
                   source_datasets=sorted({r['source'] for r in selected}))
    shares=sum(r['net_buy_shares'] for r in selected)
    if record.get('unit')=='shares':
        value=shares; tolerance=0
    elif record.get('unit')=='thousand_shares':
        value=round(shares/1000,2); tolerance=1e-8
    else:
        return finish('unavailable','aggregate_unit_unknown')
    receipt.update(recomputed_shares=shares,recomputed_value=value,comparison_tolerance=tolerance,
                   formula='sum signed net_buy_shares for exact dates and population; thousand_shares round(sum/1000,2)')
    acquired=raw.get('fetched_at_epoch')
    if isinstance(acquired,(int,float)) and not isinstance(acquired,bool) and math.isfinite(acquired):
        try:receipt['provider_acquired_at']=datetime.fromtimestamp(acquired,timezone.utc).isoformat()
        except (ValueError,OverflowError,OSError):pass
    reported=record.get('value')
    if isinstance(reported,bool) or not isinstance(reported,(int,float)) or not math.isfinite(reported):
        return finish('unavailable','aggregate_value_unknown')
    if abs(reported-value)<=tolerance:
        from official_institutional_verification import evaluate_official_verification
        independent=evaluate_official_verification(raw.get('official_verification'),data,receipt)
        receipt['official_comparison']=independent
        receipt['independent_primary_source_verified']=independent['status']=='matched'
        if independent['status']=='mismatch':
            return finish('mismatch','official_daily_observations_contradict_provider')
        if raw.get('official_verification') and receipt['population']=='foreign' and independent['status'] in {'incomplete','unavailable'}:
            return finish('unavailable','official_comparison_incomplete')
    return finish('recomputed' if abs(reported-value)<=tolerance else 'mismatch',
                  'aggregate_matches_saved_observations' if abs(reported-value)<=tolerance else 'aggregate_contradicts_saved_observations')
