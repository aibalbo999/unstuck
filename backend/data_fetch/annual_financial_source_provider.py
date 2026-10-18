"""Only official annual statements, without quote/SDK/optional-source work."""
from copy import deepcopy
from datetime import date,datetime
from hashlib import sha256
import math
import re
import time
from urllib.parse import parse_qs,urlsplit
from zoneinfo import ZoneInfo

from source_applicability import instrument_type
from source_audit import audited_fetch
from provider_correlation import current_correlation
from .provider_base import DataProvider,provider_result_from_audited
from .market_sources.official_xbrl_financial import FIELDS,INDEX_URL,PROVIDER,assemble_annual_histories
from .market_sources.official_mopsfin_financial import PROVIDER as COMPARISON_PROVIDER,REPORT_URL,STATEMENT_FIELDS

SCHEMA='ordinary_consolidated_annual_history.v1'
HISTORY_FIELDS=('years','revenue_history','net_income_history','gross_profit_history','operating_income_history','fcf_history','total_assets_history','total_equity_history')


def validate_context(data,ticker):
    if (not isinstance(data,dict)or data.get('ticker')!=ticker
            or not re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?',ticker)
            or instrument_type(data)!='EQUITY' or data.get('financial_currency')!='TWD' or data.get('currency')!='TWD'):
        raise ValueError('annual_source_context_not_verified')
    from .market_sources.ordinary_individual_annual import supports_annual as supports_individual, validate_context as validate_individual_context
    if supports_individual(ticker):
        validate_individual_context(data,ticker)
    if ticker=='7750.TW':
        from .market_sources.syntec_annual_bridge import validate_bridge_context
        validate_bridge_context(data,ticker)
    if ticker=='5880.TW':
        from .market_sources.tcfhc_annual_financial import validate_annual_context
        validate_annual_context(data,ticker)
    if ticker=='2610.TW':
        from .market_sources.cal_annual_bridge import validate_bridge_context
        validate_bridge_context(data,ticker)


def _document_url(url,ticker,year):
    try:
        p=urlsplit(url);q=parse_qs(p.query,keep_blank_values=True)
        return (p.scheme=='https'and p.netloc=='mopsov.twse.com.tw'and p.path=='/server-java/FileDownLoad'and not p.fragment
                and set(q)=={'functionName','step','co_id','year','season','report_id'}
                and all(q[k]==[v]for k,v in {'functionName':'t164sb01','step':'9','co_id':ticker.split('.')[0],'year':str(year),'season':'4','report_id':'C'}.items()))
    except (TypeError,ValueError,KeyError):return False


def ordinary_projection(value,ticker):
    if not isinstance(value,dict):return None
    from .market_sources.cal_annual_bridge import SOURCE_URL as CAL_URL,project_bridge_history as project_cal_history
    if value.get('source_url')==CAL_URL:
        return project_cal_history(value,ticker)
    from .market_sources.syntec_annual_bridge import SOURCE_URL as BRIDGE_URL,project_bridge_history
    if value.get('source_url')==BRIDGE_URL:
        return project_bridge_history(value,ticker)
    from .market_sources.mops_public_annual import SOURCE_URL as PUBLIC_URL,project_public_history
    if value.get('source_url')==PUBLIC_URL:
        return project_public_history(value,ticker)
    try:
        years=value['years'];docs=value['documents'];rows=value['raw_twd_by_year']
        if (value.get('ticker',ticker)!=ticker or value.get('report_scope','consolidated')!='consolidated'
                or value.get('currency','TWD')!='TWD' or value.get('schema',SCHEMA)!=SCHEMA
                or value['source_url']!=INDEX_URL or not isinstance(years,list)or len(years)!=5
                or any(type(y)is not str or not re.fullmatch(r'20\d{2}',y)for y in years)
                or years!=[str(y)for y in range(int(years[0]),int(years[0])+5)]or int(years[-1])>=date.today().year
                or not isinstance(rows,dict)or set(rows)!=set(years)or not isinstance(docs,list)or len(docs)!=5
                or not isinstance(value.get('comparative_revisions'),list)):return None
        facts={}
        for year,document in zip(years,docs):
            if (not isinstance(document,dict)or type(document.get('year'))is not int or str(document['year'])!=year
                    or not isinstance(document.get('sha256'),str)or not re.fullmatch(r'[0-9a-f]{64}',document['sha256'])):return None
            if not _document_url(document.get('url'),ticker,year):
                parts=document.get('components')
                if (document.get('provider')!=COMPARISON_PROVIDER or not _document_url(document.get('requested_xbrl_url'),ticker,year)
                        or not isinstance(parts,list)or len(parts)!=3):return None
                statements=set()
                for part in parts:
                    statement=part.get('statement')if isinstance(part,dict)else None
                    if (statement not in STATEMENT_FIELDS or statement in statements or part.get('year')!=int(year)
                            or part.get('period_end')!=year+'-12-31'or part.get('provider')!=COMPARISON_PROVIDER or part.get('url')!=REPORT_URL
                            or part.get('request')!={'companyId':ticker.split('.')[0],'ys':year+'4','compareItem':statement}
                            or not isinstance(part.get('sha256'),str)or not re.fullmatch(r'[0-9a-f]{64}',part['sha256'])):return None
                    statements.add(statement)
                if document['sha256']!=sha256(';'.join(p['sha256']for p in parts).encode()).hexdigest():return None
            row=rows[year]
            if (not isinstance(row,dict)or set(row)!=set(FIELDS.values())|{'free_cash_flow'}
                    or any(type(v)is not int for v in row.values())or row['property_purchase']>0 or row['intangible_purchase']>0
                    or row['free_cash_flow']!=row['operating_cash_flow']+row['property_purchase']+row['intangible_purchase']):return None
            facts[int(year)]={tag:row[field]for tag,field in FIELDS.items()}
        projected=assemble_annual_histories(facts,expected_years=list(facts))
        if any(projected[k]!=value.get(k)for k in HISTORY_FIELDS):return None
        if any(not math.isfinite(v)for k in HISTORY_FIELDS if k!='years'for v in projected[k]):return None
        return {**deepcopy(value),'schema':SCHEMA,'ticker':ticker,'report_scope':'consolidated','currency':'TWD'}
    except (KeyError,ValueError,TypeError,OverflowError):return None


def project_source_value(value,ticker):
    if not isinstance(value,dict)or value.get('ticker')!=ticker:return None
    if value.get('schema')=='ordinary_individual.v1':
        from .market_sources.ordinary_individual_annual import project_individual_history
        return project_individual_history(value,ticker)
    # Legacy sector schemas may omit currency, but an explicit contradiction
    # must never be cast to TWD by their history projection.
    if 'currency'in value and value['currency']!='TWD':return None
    if value.get('schema')==SCHEMA:
        if value.get('report_scope')!='consolidated'or value.get('currency')!='TWD':return None
        return ordinary_projection(value,ticker)
    from .financial_history_basis import project_broker_histories,project_financial_institution_histories,project_insurer_standalone_histories
    projectors={'broker_consolidated.v1':project_broker_histories,'financial_institution_consolidated.v1':project_financial_institution_histories,'financial_holding_consolidated.v2':project_financial_institution_histories,'financial_holding_public_annual.v1':project_financial_institution_histories,'financial_holding_audited_annual.v1':project_financial_institution_histories,'bank_consolidated.v1':project_financial_institution_histories,'insurer_standalone.v1':project_insurer_standalone_histories}
    projector=projectors.get(value.get('schema'))
    projection=projector(value,ticker)if projector else None
    return {**projection,'sector_specific_financials':deepcopy(value)}if projection else None


def _valid_observation(audit,ticker,provider,latest_year):
    if (audit.get('source')!='financial_statements' or audit.get('provider')!=provider
            or type(audit.get('record_count'))is not int or audit['record_count']!=5
            or audit.get('cache_hit')is not False or audit.get('stale')is not False
            or audit.get('ticker')not in (None,ticker)
            or audit.get('fetch_id')not in (None,current_correlation().get('fetch_id'))):return False
    # Missing legacy transport diagnostics are unknown; explicit contradictory
    # diagnostics cannot establish a new successful acquisition.
    if ('http_status'in audit and audit['http_status']is not None
            and (type(audit['http_status'])is not int or audit['http_status']!=200)):
        return False
    if (audit.get('http_request_sent')is False
            or audit.get('event_kind')in {'cache_hit','local_block','deferred','cooldown'}):
        return False
    try:
        stamp=audit.get('fetched_at_epoch');iso=audit.get('fetched_at')
        if iso is not None:
            parsed=datetime.fromisoformat(iso)
            if parsed.tzinfo is None:return False
            original=parsed.timestamp()
            if stamp is None:stamp=original
            elif type(stamp)not in (int,float)or abs(original-stamp)>=1:return False
        period_close=datetime(int(latest_year)+1,1,1,tzinfo=ZoneInfo('Asia/Taipei')).timestamp()
        return type(stamp)in (int,float)and math.isfinite(stamp)and period_close<=stamp<=time.time()
    except (TypeError,ValueError,OverflowError):return False


class AnnualFinancialSourceProvider(DataProvider):
    source='financial_statements'
    name='Official annual financial statements'
    markets={'tw'}

    def fetch(self,request,context=None):
        data=(context or{}).get('data');validate_context(data,request.ticker)
        from .yfinance_extractors import _is_financial_industry
        from .financial_history_basis import INSTITUTION_SCHEMAS
        from mapping_fields import safe_mapping_dict
        typed_schema=(safe_mapping_dict(data.get('sector_specific_financials'))or{}).get('schema')or(safe_mapping_dict(data.get('financial_history_basis'))or{}).get('statement_schema')
        financial=(_is_financial_industry(' '.join(str(data.get(k)or'')for k in ['sector','industry']))
                   or typed_schema in {*INSTITUTION_SCHEMAS,'broker_consolidated.v1','insurer_individual.v1','insurer_standalone.v1'})
        from .market_sources.ordinary_individual_annual import supports_annual as supports_individual,fetch_annual_result as fetch_individual,PROVIDER as INDIVIDUAL_PROVIDER
        individual=supports_individual(request.ticker) and not financial
        if individual:
            expected_provider=INDIVIDUAL_PROVIDER
            result=fetch_individual(request.ticker);value=result.get('value');projected=project_source_value(value,request.ticker)
        elif financial:
            from .market_sources.financial_institution_xbrl import fetch_financial_institution_histories,PROVIDER as INSTITUTION_PROVIDER
            from .market_sources.mops_public_holding import supports_public_holding,fetch_public_holding_result,PROVIDER as HOLDING_PUBLIC_PROVIDER
            from .market_sources.tcfhc_annual_financial import supports_annual,fetch_annual_result,PROVIDER as AUDITED_HOLDING_PROVIDER
            if supports_annual(request.ticker):
                expected_provider=AUDITED_HOLDING_PROVIDER
                result=fetch_annual_result(request.ticker,force_refresh=True)
            elif supports_public_holding(request.ticker):
                expected_provider=HOLDING_PUBLIC_PROVIDER
                result=fetch_public_holding_result(request.ticker)
            else:
                expected_provider=INSTITUTION_PROVIDER
                result=audited_fetch(self.source,INSTITUTION_PROVIDER,fetch_financial_institution_histories,(request.ticker,),default=None,record_counter=lambda v:len(v.get('years',[]))if isinstance(v,dict)else 0)
            value=result['value'];projected=project_source_value(value,request.ticker)
        else:
            from .official_financial_gap_cache import fetch_official_financial_result
            from .market_sources.syntec_annual_bridge import supports_bridge,fetch_bridge_result,PROVIDER as BRIDGE_PROVIDER,SOURCE_URL as BRIDGE_URL
            from .market_sources.cal_annual_bridge import supports_bridge as supports_cal,fetch_bridge_result as fetch_cal,PROVIDER as CAL_PROVIDER,SOURCE_URL as CAL_URL
            result=(fetch_cal(request.ticker)if supports_cal(request.ticker)else
                    fetch_bridge_result(request.ticker)if supports_bridge(request.ticker)else fetch_official_financial_result(request.ticker))
            value=result.get('value');projected=ordinary_projection(value,request.ticker)if isinstance(value,dict)else None
            from .market_sources.mops_public_annual import SOURCE_URL as PUBLIC_URL,PROVIDER as PUBLIC_PROVIDER
            expected_provider=(CAL_PROVIDER if isinstance(value,dict)and value.get('source_url')==CAL_URL else
                               BRIDGE_PROVIDER if isinstance(value,dict)and value.get('source_url')==BRIDGE_URL else
                               PUBLIC_PROVIDER if isinstance(value,dict)and value.get('source_url')==PUBLIC_URL else PROVIDER)
        result=deepcopy(result);audit=result['audit']
        if audit.get('status')=='success'and (projected is None or not _valid_observation(audit,request.ticker,expected_provider,projected['years'][-1])):
            audit.update(ticker=request.ticker,status='degraded_enrichment',record_count=0,coverage_status='unverified_receipt',error_kind='invalid_annual_source_observation',message='年度來源的公司、期間、幣別、科目或原件憑據未通過核對。')
        if projected is not None and audit.get('status')=='success':
            result['value']=value if financial or individual else projected
            manifest=value['documents'];audit.update(coverage_status=('ordinary_individual_complete'if value.get('schema')=='ordinary_individual.v1'else('sector_specific_standalone_complete'if value.get('report_scope')=='standalone'else'sector_specific_complete')if financial else'complete'),source_url=value['source_url'],documents=deepcopy(manifest),comparative_revisions=deepcopy(value['comparative_revisions']),response_sha256=sha256(';'.join(f"{d['year']}:{d['sha256']}"for d in manifest).encode()).hexdigest(),report_scope=value.get('report_scope','consolidated'),statement_schema=value.get('schema',SCHEMA))
            if not financial:audit['inferred_zero_facts']=deepcopy(value.get('inferred_zero_facts',[]))
            if not financial:audit.update(raw_twd_by_year=deepcopy(value['raw_twd_by_year']),recovered_documents=deepcopy(value.get('recovered_documents',[])))
            if not financial and 'comparative_coverage'in projected:
                audit['comparative_coverage']=deepcopy(projected['comparative_coverage'])
        else:
            result['value']=None
            annual_failure=deepcopy(audit)
            # The quarterly CSV is a separate, explicitly partial fallback.
            # It never enters the five-year annual projection above.
            from .market_sources.official_quarterly_financials import (
                PROVIDER as QUARTERLY_PROVIDER, fetch_latest_quarter_result,
                project_latest_quarter,
            )
            quarterly=fetch_latest_quarter_result(request.ticker,data)
            quarterly_value=quarterly.get('value')
            quarterly_audit=quarterly.get('audit') if isinstance(quarterly,dict) else None
            if (project_latest_quarter(quarterly_value,request.ticker) is not None
                    and isinstance(quarterly_audit,dict)
                    and quarterly_audit.get('status') in {'success','skipped_fresh_cache'}
                    and quarterly_audit.get('record_count')==1):
                quarterly_audit['related_entries']=[annual_failure]
                quarterly_audit['annual_source_failure_preserved']=True
                return provider_result_from_audited(
                    {'value':quarterly_value,'audit':quarterly_audit},self.source,QUARTERLY_PROVIDER)
            related_failures=[annual_failure]
            if isinstance(quarterly_audit,dict):
                related_failures.append(deepcopy(quarterly_audit))
            from .market_sources import tpex_historical_quarterly_summary as tpex_summary
            if tpex_summary.supports_ticker(request.ticker):
                summary=tpex_summary.fetch_quarterly_summary_result(request.ticker)
                summary_value=summary.get('value') if isinstance(summary,dict) else None
                summary_audit=summary.get('audit') if isinstance(summary,dict) else None
                if (tpex_summary.project_summary(summary_value,request.ticker) is not None
                        and isinstance(summary_audit,dict)
                        and summary_audit.get('provider')==tpex_summary.PROVIDER
                        and summary_audit.get('status') in {'success','skipped_fresh_cache'}
                        and type(summary_audit.get('record_count')) is int
                        and summary_audit.get('record_count')==1):
                    summary_audit['related_entries']=deepcopy(related_failures)
                    summary_audit['annual_and_quarterly_source_failures_preserved']=True
                    return provider_result_from_audited(
                        {'value':summary_value,'audit':summary_audit},self.source,tpex_summary.PROVIDER)
                if isinstance(summary_audit,dict):
                    related_failures.append(deepcopy(summary_audit))
            audit['related_entries']=related_failures[1:] if len(related_failures)>1 else []
        return provider_result_from_audited(result,self.source,self.name)
