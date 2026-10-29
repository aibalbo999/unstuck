"""Bounded official exchange backup for missing institutional observations.

Per-date all-market snapshots are shared. An absent security row remains absence,
not a zero trade or proof of a suspension. Only explicitly dated source rows can
advance observation age. Partial windows remain partial after recovery.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

TWSE_SOURCE = 'TWSE T86'
TPEX_SOURCE = 'TPEx dailyTrade'
MAX_REPORTS = 5
TOTAL_BUDGET_SECONDS = 12
PARSER_VERSION = 'official-institutional-v1'
TWSE_FIELDS = ['證券代號', '證券名稱', '外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)',
               '外陸資買賣超股數(不含外資自營商)', '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數',
               '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數', '自營商買進股數(自行買賣)',
               '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)', '自營商買進股數(避險)', '自營商賣出股數(避險)',
               '自營商買賣超股數(避險)', '三大法人買賣超股數']
TPEX_FIELDS = ['代號', '名稱'] + ['買進股數', '賣出股數', '買賣超股數'] * 7 + ['三大法人買賣超股數合計']


def expected_sessions(ticker, now_epoch, count=MAX_REPORTS):
    """Select only sessions inside the existing conservative publication window."""
    from data_freshness_market import market_calendar
    current = datetime.fromtimestamp(now_epoch, ZoneInfo('Asia/Taipei'))
    day = current.date() if (current.hour, current.minute) >= (22, 30) else current.date()-timedelta(days=1)
    result, calendars = [], {}
    for _ in range(max(45, count*3)):
        if day.year not in calendars:
            calendars[day.year] = market_calendar(ticker, current=datetime.combine(day, datetime.min.time()))
        calendar = calendars[day.year]
        if calendar.get('coverage_status') != 'available':
            return []
        if day.weekday()<5 and day not in calendar['holidays']:
            result.append(day.isoformat())
            if len(result)==count:
                return result
        day -= timedelta(days=1)
    return result


def _number(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Missing institutional share quantity')
    try:
        number=Decimal(str(value).strip().replace(',',''))
    except InvalidOperation as exc:
        raise ValueError('Invalid institutional share quantity') from exc
    if not number.is_finite() or number!=number.to_integral_value():
        raise ValueError('Invalid institutional share quantity')
    return int(number)


def _parse_report(payload, market, requested_day):
    from source_observation_freshness import parse_observation_date
    if not isinstance(payload, dict):
        raise ValueError('Invalid institutional report')
    stat=str(payload.get('stat') or '')
    if stat in {'很抱歉，沒有符合條件的資料!', '很抱歉，沒有符合條件的資料！'}:
        return {'date':requested_day, 'rows':{}, 'report_status':'valid_empty', 'market':market}
    if stat.lower()!='ok':
        raise ValueError('Institutional report not successful')
    observed=parse_observation_date(payload.get('date'))
    if observed is None or observed.isoformat()!=requested_day:
        raise ValueError('Institutional report date does not match query')
    if market=='TWSE':
        if payload.get('fields')!=TWSE_FIELDS or '股' not in str(payload.get('hints','')):
            raise ValueError('Unknown TWSE institutional schema or unit')
        rows=payload.get('data'); width=19
    else:
        tables=payload.get('tables')
        matches=[t for t in tables or [] if isinstance(t,dict) and t.get('fields')==TPEX_FIELDS]
        if len(matches)!=1:
            raise ValueError('Unknown TPEx institutional schema')
        rows=matches[0].get('data'); width=24
    if not isinstance(rows,list):
        raise ValueError('Missing institutional rows')
    parsed={}
    for row in rows:
        if not isinstance(row,list) or len(row)!=width:
            raise ValueError('Malformed institutional row')
        code=str(row[0]).strip()
        if not code or code in parsed:
            raise ValueError('Ambiguous institutional identity')
        if market=='TWSE':
            foreign=_number(row[4])+_number(row[7]); trust=_number(row[10]); dealer=_number(row[11]); total=_number(row[18])
            if dealer!=_number(row[14])+_number(row[17]):
                raise ValueError('Conflicting TWSE dealer totals')
        else:
            foreign=_number(row[10]); trust=_number(row[13]); dealer=_number(row[22]); total=_number(row[23])
            if foreign!=_number(row[4])+_number(row[7]) or dealer!=_number(row[16])+_number(row[19]):
                raise ValueError('Conflicting TPEx category totals')
        if foreign+trust+dealer!=total:
            raise ValueError('Conflicting institutional totals')
        parsed[code]={'company_name':str(row[1]).strip(), 'foreign':foreign, 'investment_trust':trust, 'dealer':dealer}
    return {'date':requested_day, 'rows':parsed, 'report_status':'available' if parsed else 'valid_empty', 'market':market}


def _url(market, day):
    if market=='TWSE':
        return 'https://www.twse.com.tw/rwd/zh/fund/T86?'+urlencode({'response':'json','date':day.replace('-',''),'selectType':'ALLBUT0999'})
    return 'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?'+urlencode({'date':day.replace('-','/'),'type':'Daily','sect':'EW','response':'json'})


def _fetch_report(market, day, timeout, *, openapi=False):
    from external_http_client import sync_get
    from search_provider_runtime import (SourceResponseError, cooldown_state, observe_http_response,
                                         record_observation, remember_failure, scope_key, error_details)
    if openapi and market!='TPEX':
        raise ValueError('TPEx OpenAPI is only valid for the OTC market')
    if openapi:
        from tpex_openapi_institutional import SOURCE as source, URL as url, parse_latest_report
    else:
        source=TWSE_SOURCE if market=='TWSE' else TPEX_SOURCE
        url=_url(market,day)
    key=scope_key(source, endpoint='institutional_daily'); started=time.monotonic()
    from search_admission import endpoint_admission
    timeout = max(0.001, min(float(timeout), 8 if market == 'TWSE' else 5))
    with endpoint_admission(key, timeout_seconds=timeout) as owns:
        if owns is None:
            record_observation(source, started, outcome='busy', source='institutional_trading',
                               details={'error_kind': 'single_flight_busy'}, sent=False)
            raise SourceResponseError('single_flight_busy')
        blocked=cooldown_state(key)
        if blocked:
            record_observation(source,started,outcome='cooldown',source='institutional_trading',details=blocked,sent=False)
            raise SourceResponseError(blocked.get('error_kind','cooldown'),status_code=blocked.get('http_status'))
        from official_source_runtime import failure_state_snapshot, reset_failure_history_after_success
        observed_failure_state = failure_state_snapshot(key)
        if observed_failure_state is None:
            record_observation(source, started, outcome='unavailable', source='institutional_trading',
                               details={'error_kind': 'guard_storage_unavailable'}, sent=False)
            raise SourceResponseError('guard_storage_unavailable')
        observe_http_response(None)
        deadline = time.monotonic() + timeout
        attempt_started = started
        fallback_reason = ''
        try:
            try:
                response=sync_get(url,timeout=min(5, max(0.001, deadline-time.monotonic())),provider=source)
            except Exception as primary_exc:
                primary_details = error_details(primary_exc)
                remaining = deadline-time.monotonic()
                if (market != 'TWSE' or openapi or not owns() or remaining <= 0.5
                        or primary_details['error_kind'] not in {'timeout', 'transport_error', 'server_error'}):
                    raise
                record_observation(source,started,outcome='failure',source='institutional_trading',
                                   details={**primary_details,'parser_version':PARSER_VERSION,
                                            'requested_date':day,'source_url':url,'attempt_role':'primary_before_mirror'})
                fallback_reason = primary_details['error_kind']
                url = url.replace('https://www.twse.com.tw/', 'https://wwwc.twse.com.tw/', 1)
                attempt_started = time.monotonic()
                observe_http_response(None)
                response=sync_get(url,timeout=min(3, max(0.001, deadline-time.monotonic())),provider=source)
            observe_http_response(response)
            report=parse_latest_report(response.content,day) if openapi else _parse_report(response.json(),market,day)
            from official_response_evidence import archive_response
            report['raw_evidence']=archive_response(getattr(response,'content',None),source_url=url,retrieved_at=datetime.now(timezone.utc).isoformat(),http_status=getattr(response,'status_code',None))
            report['source']=source
            report['source_url']=url
            if fallback_reason:
                report['fallback_reason']=fallback_reason
        except Exception as exc:
            details={**(remember_failure(key,exc) if owns() else {**error_details(exc), 'state_write_skipped': 'lease_lost'}),
                     'parser_version':PARSER_VERSION,'requested_date':day,'source_url':url}
            if fallback_reason:
                details['fallback_reason']=fallback_reason
                details['attempt_role']='official_mirror'
            record_observation(source,attempt_started,outcome='failure',source='institutional_trading',details=details)
            raise
        reset_failure_history_after_success(key, observed_failure_state, owns=owns)
        record_observation(source,attempt_started,outcome='results' if report['rows'] else 'valid_empty',count=len(report['rows']),
                           source='institutional_trading',details={'http_status':getattr(response,'status_code',None),
                           'parser_version':PARSER_VERSION,'observation_date':day,'source_url':url,
                           'fallback_reason':fallback_reason})
        return report


def recover_institutional_observations(ticker, primary, *, now_epoch, limit, force_refresh=False):
    """Merge exact day/category once; keep conflicts and acquisition diagnostics."""
    from data_freshness_market import is_taiwan_ticker
    from shared_provider_cache import shared_fetch
    from institutional_observations import summarize_observations
    if not is_taiwan_ticker(ticker):
        return primary, {}
    dates=expected_sessions(ticker,now_epoch)
    if not dates:
        return primary, {'status':'calendar_unknown','checked_dates':[],'added_observation_count':0}
    market='TPEX' if str(ticker).upper().endswith('.TWO') else 'TWSE'
    source=TWSE_SOURCE if market=='TWSE' else TPEX_SOURCE
    code=str(ticker).split('.')[0]
    old_records=primary.get('daily_category_observations') or []
    merged={(row['date'],row['category']):dict(row) for row in old_records}
    required_dates = expected_sessions(ticker, now_epoch, limit)
    categories = ('foreign', 'investment_trust', 'dealer')
    missing_dates = [day for day in required_dates
                     if any((day, category) not in merged for category in categories)]
    # Always acquire/bind the latest session first. Spend the remaining fixed
    # five-report budget on actual window gaps before rechecking present rows.
    # A complete primary window keeps the original latest-five plan.
    dates = list(dict.fromkeys([dates[0], *missing_dates, *dates[1:]]))[:MAX_REPORTS]
    diagnostics={'status':'unavailable','provider':source,'checked_dates':[], 'reports':[],
                 'added_observation_count':0,'conflicts':[],
                 'required_window_dates': required_dates, 'missing_expected_dates': missing_dates,
                 'selected_recovery_dates': dates,
                 'coverage_scope': 'latest session and selected gaps; not full official window verification',
                 'absence_policy':'Missing security rows are not zero trades or evidence of suspension.'}
    started=time.monotonic()
    for day in dates:
        remaining=TOTAL_BUDGET_SECONDS-(time.monotonic()-started)
        if remaining<=0:
            diagnostics['budget_exhausted']=True
            break
        def fetch_before_deadline(day=day):
            remaining_http = TOTAL_BUDGET_SECONDS - (time.monotonic() - started)
            if remaining_http <= 0:
                diagnostics['budget_exhausted'] = True
                raise TimeoutError('Official acquisition budget exhausted before HTTP')
            if market=='TPEX' and day==dates[0] and phase=='post_cutoff':
                try:
                    return _fetch_report(market, day, min(5, remaining_http), openapi=True)
                except Exception as exc:
                    diagnostics['latest_openapi_fallback_reason']=type(exc).__name__
                    remaining_http = TOTAL_BUDGET_SECONDS - (time.monotonic() - started)
                    if remaining_http <= 0:
                        diagnostics['budget_exhausted'] = True
                        raise
            return _fetch_report(market, day, min(8 if market=='TWSE' else 5, remaining_http))

        from market_evidence_policy import acquisition_phase
        phase=acquisition_phase(day,datetime.fromtimestamp(now_epoch,ZoneInfo('Asia/Taipei')))
        report,meta=shared_fetch(f'official-institutional:{market}:{day}:v2:{phase}',
                                fetch_before_deadline,
                                freshness_seconds=6*3600 if phase=='post_cutoff' else 300,retention_seconds=6*3600,error_retry_seconds=60,lock_wait_seconds=0,
                                result_ttl=lambda row:6*3600 if row.get('rows') and phase=='post_cutoff' else 300,
                                use_cache=True, force_refresh=force_refresh, preserve_cache_on_force_error=True)
        receipt={'date':day,'source':source,'source_url':_url(market,day),'acquisition_phase':phase,'cache_key':f'official-institutional:{market}:{day}:v2:{phase}',**meta}
        if isinstance(report,dict):
            receipt['raw_evidence']=report.get('raw_evidence')
            receipt['source']=report.get('source') or source
            receipt['source_url']=report.get('source_url') or _url(market,day)
        if not isinstance(report,dict) or meta.get('error_kind'):
            diagnostics['reports'].append({**receipt,'status':'unavailable'})
            break  # One failure opens the endpoint's cooldown; do not issue more days.
        diagnostics['checked_dates'].append(day)
        row=report['rows'].get(code)
        diagnostics['reports'].append({**receipt,'status':'available' if row else
                                       'valid_empty' if not report['rows'] else 'security_absent'})
        if row is None:
            continue
        report_source=report.get('source') or source
        report_url=report.get('source_url') or _url(market,day)
        if day==dates[0]:
            diagnostics['latest_official_observation']={'date':day,'market':market,'ticker':ticker,'categories':{key:row[key] for key in ('foreign','investment_trust','dealer')},'unit':'shares','acquisition_phase':phase,'raw_evidence':report.get('raw_evidence'),'source_url':report_url}
        for category in ('foreign','investment_trust','dealer'):
            key=(day,category)
            observed={'date':day,'category':category,'net_buy_shares':row[category],'source':report_source,
                      'source_url':report_url,'unit':'shares'}
            if key in merged:
                if merged[key]['net_buy_shares']!=row[category]:
                    diagnostics['conflicts'].append({'date':day,'category':category,'primary':merged[key],
                                                     'official':observed,'selected':'primary'})
                continue
            merged[key]=observed; diagnostics['added_observation_count']+=1
    if diagnostics['added_observation_count']:
        recovered=summarize_observations(list(merged.values()),ticker,limit=limit,
                                        rejected_count=primary.get('rejected_record_count',0))
        if primary.get('source_provenance'):
            recovered['_source_record_archive'] = {
                'primary_sdk': deepcopy(primary['source_provenance']),
                'primary_observation_dates': sorted({row['date'] for row in old_records}),
            }
        # Legacy aggregate-only caches cannot be merged without day/category evidence.
        if primary and not old_records:
            recovered['prior_summary_not_merged']={key:primary.get(key) for key in
                                                 ('source','latest_date','lookback_trading_days','total_net_buy_shares')}
        diagnostics['status']='partial_recovery'
        if diagnostics.get('latest_official_observation'):recovered['latest_official_observation']=diagnostics['latest_official_observation']
        return recovered, diagnostics
    statuses={row['status'] for row in diagnostics['reports']}
    diagnostics['status']=('conflict' if diagnostics['conflicts'] else 'security_absent' if statuses=={'security_absent'}
                           else 'valid_empty' if statuses and statuses<={'valid_empty','security_absent'} else 'unavailable')
    primary=dict(primary)
    if diagnostics.get('latest_official_observation'):primary['latest_official_observation']=diagnostics['latest_official_observation']
    return primary,diagnostics
