"""Merge a complete annual series while retaining the original quote basis."""
from copy import deepcopy
from datetime import datetime,timezone
import math
import time

from fastapi import HTTPException
from data_fetch.annual_financial_source_provider import HISTORY_FIELDS,SCHEMA,project_source_value,validate_context
from data_fetch.yfinance_derived import calculate_margin_histories,calculate_revenue_cagr


def validate_annual_refresh_context(data,ticker,audits=None):
    try:validate_context(data,ticker)
    except ValueError as exc:raise HTTPException(status_code=400,detail='指定財報刷新須有台股EQUITY身分及TWD財報幣別；原快照保持')from exc
    if audits is not None and any(a.get('source')=='market_data'and a.get('ticker')not in (None,ticker,ticker.split('.')[0])for a in audits):
        raise HTTPException(status_code=400,detail='保留的股價來源與股票身分不一致；原快照保持')


def _growth(values):
    if len(values)>=2 and type(values[-2])in(int,float)and type(values[-1])in(int,float)and values[-2]>0:
        growth=(values[-1]/values[-2]-1)*100
        if math.isfinite(growth):return f'{growth:.1f}%'
    return 'N/A'


def _finite_number(value):
    if type(value)not in (int,float):return None
    try:
        number=float(value)
        return number if math.isfinite(number)else None
    except (OverflowError,ValueError,TypeError):return None


def _retained_scalar_note(data,archive):
    from report_source_refresh import _timestamp
    # Include earlier saved annual refreshes so repeated repairs cannot renew
    # the age of quote/TTM scalars which were never acquired by this provider.
    origins=[row['audit']for row in archive
             if row.get('source')=='financial_statements'
             and row.get('reason')=='superseded_by_annual_source_refresh'
             and isinstance(row.get('audit'),dict)]
    saved_freshness=data.get('source_freshness')
    freshness=saved_freshness.get('financial_statements')if isinstance(saved_freshness,dict)else None
    if isinstance(freshness,dict):origins.append(freshness)
    dated=[]
    for row in origins:
        try:stamp=_timestamp(row)
        except (OverflowError,ValueError,TypeError):stamp=None
        if stamp is not None:dated.append((stamp,row))
    if dated:
        stamp,row=min(dated,key=lambda pair:pair[0])
        iso=row.get('fetched_at')or datetime.fromtimestamp(stamp,timezone.utc).isoformat()
        age=max(0,(time.time()-stamp)/3600)
        origin=f'原財務來源最早可核對觀測 {iso}（距今 {age:.1f} 小時，原狀態 {row.get("status","unknown")}，原過期標記 {row.get("stale","unknown")}）'
    else:origin='原財務來源取得時間未確認'
    return f'保留的即時／TTM 財務純量未重新取得；{origin}；此觀測不證明各純量的完整來源，本次年度取得時間不適用於保留純量。'


def apply_annual_history_values(merged,projected,value,scalar_data,*,basis_label='本次官方'):
    """Apply one verified annual series; current quote/TTM inputs stay separate."""
    for key in HISTORY_FIELDS:merged[key]=deepcopy(projected[key])
    for key in ('financial_history_basis','sector_specific_financials','net_revenue_history'):merged[key]=deepcopy(projected.get(key))
    merged.update(calculate_margin_histories(merged['revenue_history'],merged['gross_profit_history'],merged['operating_income_history'],merged['net_income_history'],merged['total_equity_history']))
    revenues=merged['revenue_history'];income=merged['net_income_history']
    merged['revenue_cagr_5yr']=calculate_revenue_cagr(revenues)if revenues[0]is not None and revenues[-1]is not None and revenues[0]>0 and revenues[-1]>0 else'N/A'
    merged['latest_annual_revenue_growth']=_growth(revenues);merged['latest_annual_net_income_growth']=_growth(income)
    merged['revenue_growth']=merged['latest_annual_revenue_growth']+'（最新年度 YoY）'if merged['latest_annual_revenue_growth']!='N/A'else'N/A'
    merged['earnings_growth']=merged['latest_annual_net_income_growth']+'（最新年度 YoY）'if merged['latest_annual_net_income_growth']!='N/A'else'N/A'
    latest_rev=revenues[-1];ttm=_finite_number(scalar_data.get('revenue_ttm_raw'))
    change=(ttm/(latest_rev*1e9)-1)*100 if ttm is not None and latest_rev is not None and latest_rev>0 else None
    merged['ttm_vs_latest_annual_revenue_change']=f'{change:.1f}%'if change is not None and math.isfinite(change)else'N/A'
    if value.get('schema')=='ordinary_individual.v1':merged['ttm_vs_latest_annual_revenue_change']='N/A'
    assets=merged['total_assets_history'][-1];equity=merged['total_equity_history'][-1];ni=income[-1];year=merged['years'][-1]
    merged.update(equity_multiplier='N/A',equity_multiplier_note='',dupont_identity_note='')
    if assets>0 and equity>0:
        merged['equity_multiplier']=f'{assets/equity:.3f}x';scope=value.get('report_scope','consolidated')
        from data_fetch.financial_history_basis import INSTITUTION_SCHEMAS
        institution=(merged.get('financial_history_basis')or{}).get('statement_schema')in INSTITUTION_SCHEMAS
        label='金融業合併淨收益'if institution else'該年度營業收入'
        merged['equity_multiplier_note']=f'{year}年度期末資產／權益，採{basis_label}{scope}年度科目；非即時估值。'
        revenue=latest_rev if latest_rev is not None else(projected.get('net_revenue_history')or[None])[-1]
        if revenue is not None and revenue>0:
            merged['dupont_identity_note']=(f'{year}同期間年度杜邦恒等式（{label}）：淨利／收入 {ni/revenue*100:.1f}% × 收入／資產 {revenue/assets:.3f}x × 資產／權益 {assets/equity:.3f}x = ROE {ni/equity*100:.1f}%（等同該年度淨利／期末權益）')


def merge_annual_financial_source(old_data,old_audits,value,audits,ticker):
    if isinstance(value,dict) and value.get('coverage_status') in {
            'latest_quarter_only','period_comparison_summary_only'}:
        return merge_latest_quarter_financial_source(old_data,old_audits,value,audits,ticker)
    from report_source_refresh import _timestamp,_reassess_original_freshness
    validate_annual_refresh_context(old_data,ticker,old_audits)
    projected=project_source_value(value,ticker)
    if (projected is None or not isinstance(audits,list)or len(audits)!=1
            or audits[0].get('source')!='financial_statements'or audits[0].get('status')!='success'
            or type(audits[0].get('record_count'))is not int or audits[0]['record_count']!=5
            or not audits[0].get('fetch_id')or audits[0].get('cache_hit')is True or audits[0].get('stale')is True
            or _timestamp(audits[0])is None or audits[0].get('documents')!=value.get('documents')
            or audits[0].get('source_url')!=value.get('source_url')):
        raise HTTPException(status_code=502,detail='指定年度財報未取得完整、同口徑的五年憑據；原快照保持')
    merged=deepcopy(old_data)
    prior_retention=merged.pop('annual_history_retention',None)
    apply_annual_history_values(merged,projected,value,old_data)
    notes=merged.get('data_source_notes',[])
    if not isinstance(notes,list)or any(not isinstance(n,str)for n in notes):raise HTTPException(status_code=400,detail='原來源說明格式無法安全保留')
    if prior_retention is not None:
        notes=[n for n in notes if not n.startswith('年度財報沿用此報告已核對原件：')]
    note='僅補齊官方年度財報序列；股價、即時／TTM欄位與其他來源沿原快照及原取得時間，分析本文需重新執行。'
    if note not in notes:notes.append(note)
    from data_fetch.market_sources.mops_public_annual import first_comparative_origin_note
    origin_note=first_comparative_origin_note(projected)
    from data_fetch.market_sources.syntec_annual_bridge import bridge_origin_note
    origin_note=bridge_origin_note(projected)or origin_note
    from data_fetch.market_sources.cal_annual_bridge import bridge_origin_note as cal_origin_note
    origin_note=cal_origin_note(projected)or origin_note
    from data_fetch.market_sources.tcfhc_annual_financial import origin_note as tcfhc_origin_note
    origin_note=tcfhc_origin_note(value)or origin_note
    if origin_note:notes=[origin_note,*[n for n in notes if n!=origin_note]]
    merged['data_source_notes']=notes
    # Retain every superseded observation internally, without treating an old
    # four-year failure as the active assessment of the new complete series.
    archive=merged.get('source_record_archive',[])
    if not isinstance(archive,list)or any(not isinstance(r,dict)for r in archive):raise HTTPException(status_code=400,detail='原來源封存格式無法安全保留')
    if prior_retention is not None:
        archive.append({'source':'financial_statements','reason':'superseded_saved_annual_retention','retention':prior_retention})
    archive.extend({'source':'financial_statements','reason':'superseded_by_annual_source_refresh','audit':deepcopy(row)}for row in old_audits if row.get('source')=='financial_statements')
    merged['source_record_archive']=archive
    # The note is first so both full and compact prompts expose the old basis.
    scalar_note=_retained_scalar_note(old_data,archive)
    merged['data_source_notes']=[scalar_note,*[n for n in notes if not n.startswith('保留的即時／TTM 財務純量未重新取得；')]]
    merged['source_audit']=[deepcopy(a)for a in old_audits if a.get('source')!='financial_statements']+deepcopy(audits)
    _reassess_original_freshness(merged,ticker,'financial_statements',audits)
    return merged


def _merge_tpex_quarterly_financial_summary(old_data,old_audits,value,audits,ticker):
    from data_fetch.market_sources.tpex_historical_quarterly_summary import (
        PROVIDER,project_summary,
    )
    from report_source_refresh import _timestamp
    validate_annual_refresh_context(old_data,ticker,old_audits)
    projected=project_summary(value,ticker)
    related=(audits[0].get('related_entries')if isinstance(audits,list)and audits
             and isinstance(audits[0],dict)else None)
    failure_keys=('source','provider','status','record_count','fetch_id')
    preserves_failures=(isinstance(related,list)and len(related)==2
        and isinstance(audits,list)and len(audits)==3
        and all(isinstance(row,dict)for row in related+audits[1:])
        and all(all(related[index].get(key)==audits[index+1].get(key)for key in failure_keys)
                and related[index].get('source')=='financial_statements'
                and related[index].get('status')not in{'success','skipped_fresh_cache','not_applicable'}
                and type(related[index].get('record_count'))is int
                and related[index].get('record_count')==0
                and related[index].get('fetch_id')==audits[0].get('fetch_id')
                for index in range(2)))
    valid_audit=(isinstance(audits,list)and len(audits)==3
        and isinstance(audits[0],dict)and audits[0].get('source')=='financial_statements'
        and audits[0].get('provider')==PROVIDER
        and audits[0].get('status')in{'success','skipped_fresh_cache'}
        and audits[0].get('coverage_status')=='period_comparison_summary_only'
        and type(audits[0].get('record_count'))is int and audits[0].get('record_count')==1
        and bool(audits[0].get('fetch_id')) and _timestamp(audits[0])is not None
        and preserves_failures)
    if projected is None or not valid_audit:
        raise HTTPException(status_code=502,detail='指定TPEx同期摘要或前序來源失敗憑據未通過核對；原快照保持')
    prior=old_data.get('latest_quarter_financial_summary')
    if (isinstance(prior,dict)and prior.get('schema')=='tpex_quarterly_summary.v1'
            and prior.get('ticker')==ticker):
        valid_prior=project_summary(prior,ticker)
        if valid_prior is not None:
            old_period=valid_prior.get('period',{});new_period=projected.get('period',{})
            if (old_period.get('year'),old_period.get('quarter'))>(new_period.get('year'),new_period.get('quarter')):
                raise HTTPException(status_code=502,detail='新摘要早於已保存的有效摘要；原快照保持')
    merged=deepcopy(old_data)
    merged['latest_quarter_financial_summary']=deepcopy(projected)
    notes=merged.get('data_source_notes',[])
    if not isinstance(notes,list)or any(not isinstance(note,str)for note in notes):
        raise HTTPException(status_code=400,detail='原來源說明格式無法安全保留')
    notes=[note for note in notes if not note.startswith('TPEx 同期摘要補充；')]
    year=projected['period']['year'];quarter=projected['period']['quarter']
    notes.insert(0,(f'TPEx 同期摘要補充；{year}年第{quarter}季損益數字為年初至季末累計，與去年同期比較；'
                    '金額單位為新臺幣仟元。不是完整三表、年度序列或 TTM，且未提供現金流量表。'))
    merged['data_source_notes']=notes
    merged['source_audit']=deepcopy(old_audits)+deepcopy(audits)
    # A quarterly summary does not establish a new annual-series observation.
    return merged


def merge_latest_quarter_financial_source(old_data,old_audits,value,audits,ticker):
    """Store a verified quarterly supplement without refreshing annual freshness."""
    if isinstance(value,dict)and value.get('coverage_status')=='period_comparison_summary_only':
        return _merge_tpex_quarterly_financial_summary(old_data,old_audits,value,audits,ticker)
    from data_fetch.market_sources.official_quarterly_financials import (
        PROVIDER, project_latest_quarter,
    )
    from report_source_refresh import _timestamp
    validate_annual_refresh_context(old_data,ticker,old_audits)
    projected=project_latest_quarter(value,ticker)
    related=(audits[0].get('related_entries')if isinstance(audits,list)and audits and isinstance(audits[0],dict)else None)
    preserves_failure=(isinstance(related,list)and len(related)==1 and isinstance(related[0],dict)
        and isinstance(audits,list)and len(audits)==2 and isinstance(audits[1],dict)
        and all(related[0].get(key)==audits[1].get(key)for key in ('source','provider','status','record_count','message')))
    if (projected is None or not isinstance(audits,list)or len(audits)!=2
            or not isinstance(audits[0],dict)or audits[0].get('source')!='financial_statements'
            or audits[0].get('provider')!=PROVIDER
            or audits[0].get('status')not in{'success','skipped_fresh_cache'}
            or audits[0].get('coverage_status')!='latest_quarter_only'
            or type(audits[0].get('record_count'))is not int or audits[0]['record_count']!=1
            or not audits[0].get('fetch_id')or _timestamp(audits[0])is None
            or not isinstance(audits[1],dict)or audits[1].get('source')!='financial_statements'
            or audits[1].get('status')in{'success','skipped_fresh_cache','not_applicable'}
            or type(audits[1].get('record_count'))is not int or audits[1]['record_count']!=0
            or audits[1].get('fetch_id')!=audits[0].get('fetch_id')
            or not preserves_failure):
        raise HTTPException(status_code=502,detail='指定最新季報或年度失敗憑據未通過核對；原快照保持')
    prior=old_data.get('latest_quarter_financials')
    if (isinstance(prior,dict)and prior.get('schema')=='mops_latest_quarter_financials.v1'
            and prior.get('ticker')==ticker and isinstance(prior.get('period'),dict)
            and type(prior['period'].get('year'))is int and type(prior['period'].get('quarter'))is int):
        old_period=prior['period']
        new_period=projected.get('period',{})
        if (old_period.get('year'),old_period.get('quarter'))>(new_period.get('year'),new_period.get('quarter')):
            raise HTTPException(status_code=502,detail='新季報早於已保存的有效季報；原快照保持')
    merged=deepcopy(old_data)
    merged['latest_quarter_financials']=deepcopy(projected)
    notes=merged.get('data_source_notes',[])
    if not isinstance(notes,list)or any(not isinstance(note,str)for note in notes):
        raise HTTPException(status_code=400,detail='原來源說明格式無法安全保留')
    notes=[note for note in notes if not note.startswith('官方最新季報補充；')]
    year=projected['period']['year'];quarter=projected['period']['quarter']
    notes.insert(0,(f'官方最新季報補充；{year}年第{quarter}季資產負債表為季末時點，損益表為年初至季末累計；'
                    '來源未提供現金流量表，本資料不代表五年年度序列、TTM、營業現金流或自由現金流。'))
    merged['data_source_notes']=notes
    merged['source_audit']=deepcopy(old_audits)+deepcopy(audits)
    # Do not replace financial_statements source_freshness: the annual-series
    # observation and its age remain unchanged by a latest-quarter supplement.
    return merged
