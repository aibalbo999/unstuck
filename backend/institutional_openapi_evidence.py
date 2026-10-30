"""Qualify OpenAPI-labelled snapshot rows against exact archived issuer/day bytes.

This establishes source binding only, never historical point-in-time or finality.
"""
from datetime import date,datetime
import re
import time


def openapi_rows_bound(raw, ticker):
    from tpex_openapi_institutional import SOURCE,URL,parse_latest_report
    from official_response_evidence import read_response
    from market_evidence_policy import acquisition_phase
    if (not isinstance(ticker,str) or not re.fullmatch(r'\d{4,6}\.TWO',ticker)
            or not isinstance(raw,dict)):
        return False
    rows=raw.get('daily_category_observations')
    if not isinstance(rows,list) or not 0<len(rows)<=300:
        return False
    if any(not isinstance(r,dict) or not isinstance(r.get('category'),str)
           or r['category']not in {'foreign','investment_trust','dealer'}
           or r.get('unit')!='shares' or type(r.get('net_buy_shares'))is not int
           or abs(r['net_buy_shares'])>=10**20 or not isinstance(r.get('date'),str) for r in rows):
        return False
    observation_dates=raw.get('observation_dates')
    if not isinstance(observation_dates,list) or any(not isinstance(d,str)for d in observation_dates):
        return False
    dates_all=sorted({r['date']for r in rows})
    try:
        if any(date.fromisoformat(d).isoformat()!=d for d in dates_all):
            return False
    except ValueError:
        return False
    if (len({(r['date'],r['category'])for r in rows})!=len(rows)
            or len(set(observation_dates))!=len(observation_dates)
            or set(observation_dates)!=set(dates_all)
            or raw.get('latest_date')!=dates_all[-1]
            or raw.get('observed_date_count')!=len(dates_all)
            or raw.get('lookback_trading_days')!=len(dates_all)):
        return False
    totals={cat:sum(r['net_buy_shares']for r in rows if r['category']==cat)
            for cat in ('foreign','investment_trust','dealer')}
    if (raw.get('net_buy_shares_by_category')!=totals
            or raw.get('net_buy_thousand_shares_by_category')!={k:round(v/1000,2)for k,v in totals.items()}
            or raw.get('total_net_buy_shares')!=sum(totals.values())
            or raw.get('total_net_buy_thousand_shares')!=round(sum(totals.values())/1000,2)):
        return False
    daily={day:sum(r['net_buy_shares']for r in rows if r['date']==day)for day in dates_all}
    from data_fetch.institutional_provider import institutional_window_status
    five_status=institutional_window_status(dates_all,ticker,5)
    expected_five=round(sum(daily[d]for d in dates_all[-5:])/1000,2) if five_status=='complete' else None
    if (raw.get('last_5_window_status')!=five_status
            or raw.get('last_5_trading_days_net_buy_thousand_shares')!=expected_five):
        return False
    expected_daily=[{'date':day,'net_buy_thousand_shares':round(daily[day]/1000,2)}for day in dates_all[-10:]]
    if raw.get('daily_total_net_buy_last_10')!=expected_daily:
        return False
    selected=[r for r in rows if isinstance(r,dict) and r.get('source')==SOURCE]
    if not selected:
        return False
    official=raw.get('latest_official_observation')or{}
    if not isinstance(official,dict) or official.get('ticker')!=ticker or official.get('market')!='TPEX':
        return False
    proofs=[]
    if isinstance(official.get('raw_evidence'),dict):
        proofs.append({'date':official.get('date'),'raw_evidence':official['raw_evidence']})
    recovery=raw.get('official_recovery')or{}
    if isinstance(recovery,dict) and isinstance(recovery.get('reports'),list):
        proofs.extend(r for r in recovery['reports'][:100]if isinstance(r,dict))
    try:
        dates={r['date']for r in selected}
        if not 0<len(dates)<=100:
            return False
        for day in dates:
            group=[r for r in selected if r['date']==day]
            if (len(group)!=3 or {r.get('category')for r in group}!={'foreign','investment_trust','dealer'}
                    or any(r.get('unit')!='shares' or type(r.get('net_buy_shares'))is not int for r in group)):
                return False
            candidates={}
            for r in proofs:
                proof=r.get('raw_evidence')or{}
                if r.get('date')==day and isinstance(proof,dict) and proof.get('source_url')==URL:
                    key=(proof.get('raw_response_sha256'),proof.get('raw_response_path'),proof.get('retrieved_at'))
                    candidates[key]=proof
            if len(candidates)!=1:
                return False
            proof=next(iter(candidates.values()))
            acquired=datetime.fromisoformat(proof['retrieved_at'])
            if (proof.get('status')!='archived' or proof.get('evidence_kind')!='raw_http_response_bytes'
                    or proof.get('http_status')!=200 or acquired.tzinfo is None
                    or not 0<acquired.timestamp()<=time.time()
                    or acquisition_phase(day,acquired)!='post_cutoff'):
                return False
            parsed=parse_latest_report(read_response(proof),day)['rows'].get(ticker.split('.')[0])
            if parsed is None or any(parsed[r['category']]!=r['net_buy_shares']for r in group):
                return False
    except (OSError,ValueError,TypeError,KeyError,AttributeError,EOFError,OverflowError):
        return False
    return True
