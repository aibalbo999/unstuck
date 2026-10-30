"""Read qualified cached report gaps without fetching or renewing observations."""
from datetime import datetime
import json
import time


def reuse_cached_window(ticker, dates, merged, *, now_epoch, calendar_token, deadline):
    from shared_provider_cache import peek_fresh_shared
    from official_response_evidence import read_response
    from official_institutional_source import _parse_report, _url, TWSE_SOURCE, TPEX_SOURCE
    from tpex_openapi_institutional import URL, SOURCE, parse_latest_report
    from market_evidence_policy import acquisition_phase
    from zoneinfo import ZoneInfo
    market='TPEX' if ticker.endswith('.TWO') else 'TWSE'
    code=ticker.split('.')[0]
    moment=datetime.fromtimestamp(now_epoch,ZoneInfo('Asia/Taipei'))
    reports=[];added=0
    for day in dates[1:]:  # Latest admission stays in the existing bounded planner.
        if time.monotonic()>=deadline:
            break
        if all((day,cat)in merged for cat in ('foreign','investment_trust','dealer')):
            continue
        phase=acquisition_phase(day,moment)
        key=f'official-institutional:{market}:{day}:v3:{calendar_token}:{phase}'
        report,meta=peek_fresh_shared(key)
        if not isinstance(report,dict):
            continue
        try:
            proof=report['raw_evidence'];url=proof['source_url']
            allowed={_url(market,day)}
            if market=='TPEX':allowed.add(URL)
            else:allowed.add(_url(market,day).replace('https://www.twse.com.tw/','https://wwwc.twse.com.tw/',1))
            acquired=datetime.fromisoformat(proof['retrieved_at'])
            if (report.get('date')!=day or proof.get('status')!='archived'
                    or proof.get('evidence_kind')!='raw_http_response_bytes'
                    or proof.get('http_status')!=200 or url not in allowed
                    or acquired.tzinfo is None or not 0<acquired.timestamp()<=now_epoch
                    or acquisition_phase(day,acquired)!='post_cutoff'):
                continue
            raw=read_response(proof)
            parsed=parse_latest_report(raw,day) if url==URL else _parse_report(json.loads(raw),market,day)
            if parsed['rows']!=report.get('rows'):
                continue
            row=parsed['rows'].get(code)
            if row is None:
                continue
            source=SOURCE if url==URL else TWSE_SOURCE if market=='TWSE' else TPEX_SOURCE
            if any((day,cat)in merged and merged[(day,cat)]['net_buy_shares']!=row[cat]
                   for cat in ('foreign','investment_trust','dealer')):
                continue  # Existing acquisition path retains explicit conflict handling.
            for cat in ('foreign','investment_trust','dealer'):
                if (day,cat) not in merged:
                    merged[(day,cat)]={'date':day,'category':cat,'net_buy_shares':row[cat],
                                      'source':source,'source_url':url,'unit':'shares'}
                    added+=1
            reports.append({'date':day,'source':source,'source_url':url,'raw_evidence':proof,
                            'acquisition_phase':phase,'cache_key':key,'status':'available',
                            'cached_window_readback':True,**meta})
        except (OSError,ValueError,KeyError,TypeError,AttributeError,EOFError,OverflowError):
            continue
    return reports,added
