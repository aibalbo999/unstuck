"""News-only report repair through the existing strict, bounded search gate."""
from copy import deepcopy
from datetime import datetime
import re
import time
from urllib.parse import urlsplit

from fastapi import HTTPException

PROVIDER = 'Alternative Search'
BUCKETS = ('recent_catalysts','additional_recent_catalysts','historical_catalysts',
           'unverified_catalysts','identity_rejected_catalysts')


def validate_recent_refresh_context(data,ticker):
    from source_applicability import instrument_type
    from source_content_selection import company_aliases
    identity=data.get('company_identity')if isinstance(data,dict)else None
    if isinstance(identity,dict):
        for key in ('official_name','legal_name','display_name'):
            if identity.get(key) is not None and not isinstance(identity[key],str):
                raise HTTPException(status_code=400,detail='原公司搜尋名稱格式無法安全核對')
        for key in ('allowed_aliases','english_names','forbidden_aliases'):
            values=identity.get(key)
            if values is not None and (not isinstance(values,list)or any(not isinstance(v,str)for v in values)):
                raise HTTPException(status_code=400,detail='原公司搜尋別名格式無法安全核對')
    if (not isinstance(data,dict) or data.get('ticker')!=ticker
            or not isinstance(ticker,str) or not re.fullmatch(r'[1-9]\d{3,5}\.TW(?:O)?',ticker)
            or instrument_type(data)!='EQUITY' or not isinstance(data.get('company_name'),str)
            or not data['company_name'].strip()
            or data.get('company_identity') is not None and not isinstance(data.get('company_identity'),dict)
            or not company_aliases(data)):
        raise HTTPException(status_code=400,detail='指定近期事件的股票身分或公司搜尋名稱無法核對')
    for key in (*BUCKETS,'source_record_archive'):
        if key in data and (not isinstance(data[key],list) or any(not isinstance(r,dict)for r in data[key])):
            raise HTTPException(status_code=400,detail='原近期事件或封存格式無法安全保留')


def valid_recent_receipt(value,audit,data,*,require_fetch_id=True):
    from config import CATALYST_LOOKBACK_DAYS,SEARCH_CATALYST_MAX_RESULTS
    from source_content_selection import select_company_records
    from company_news_queries import company_search_name
    from external_search_quality import search_quality_satisfied,required_unique_sources
    from external_search_types import SearchResult
    from news_record_utils import canonical_link
    from report_source_refresh import _timestamp
    from provider_correlation import current_correlation
    if (not isinstance(value,list) or len(value)!=SEARCH_CATALYST_MAX_RESULTS
            or any(not isinstance(r,dict)for r in value) or not isinstance(audit,dict)
            or audit.get('source')!='recent_catalysts' or audit.get('provider')!=PROVIDER
            or audit.get('status')!='success' or audit.get('quality_status')!='sufficient_candidates'
            or audit.get('selection_policy')!='company-time-v1'
            or type(audit.get('record_count'))is not int or audit['record_count']!=len(value)
            or audit.get('cache_hit')is not False or audit.get('stale')is not False
            or require_fetch_id and (not isinstance(audit.get('fetch_id'),str)or not audit['fetch_id'])):
        return False
    current=current_correlation()
    for key in ('ticker','fetch_id','job_id','operation_id','attempt_id'):
        if key in audit and audit[key] is not None:
            if not isinstance(audit[key],str)or not audit[key]:return False
            if key=='ticker'and audit[key]!=data['ticker']:return False
            if key=='fetch_id'and current.get(key)and audit[key]!=current[key]:return False
            if key=='job_id'and current.get('fetch_id')and audit[key]!=current.get(key):return False
    # A source operation owns a nested operation_id. Only the active fetch/job
    # IDs bind it to this acquisition; do not replace legitimate nested IDs.
    if ('http_request_sent'in audit and type(audit['http_request_sent'])is not bool
            or audit.get('http_request_sent')is False
            or 'http_request_count'in audit and (type(audit['http_request_count'])is not int
                                                 or audit['http_request_count']<=0)
            or 'event_kind'in audit and (not isinstance(audit['event_kind'],str)
                                          or audit['event_kind']not in ('aggregate','http_request'))):
        return False
    stamp=_timestamp(audit);now=time.time()
    if (stamp is None or not 0<stamp<=now or now-stamp>60
            or audit.get('http_status') is not None
               and (type(audit['http_status'])is not int or audit['http_status']!=200)):
        return False
    try:
        cutoff=datetime.fromisoformat(audit['selection_cutoff'])
        # ISO serializes microseconds; the original epoch may carry a fraction
        # of that unit. Publication-time admission remains unchanged.
        if cutoff.tzinfo is None or not -1e-6<=stamp-cutoff.timestamp()<=60:return False
        links=[]
        for row in value:
            if any(not isinstance(row.get(k),str)or not row[k].strip()for k in ('title','link','source')):return False
            url=urlsplit(row['link'])
            if url.scheme not in {'http','https'}or not url.hostname or url.username or url.password:return False
            links.append(canonical_link(row['link']))
        if len(set(links))!=len(value):return False
        selected,_=select_company_records(value,data,cutoff=now,lookback_days=CATALYST_LOOKBACK_DAYS)
        if len(selected)!=len(value):return False
        from news_freshness_policy import apply_news_freshness
        projection={k:deepcopy(data[k])for k in ('ticker','company_name','company_identity')if k in data}
        apply_news_freshness(projection,records=selected,cutoff=now,lookback_days=CATALYST_LOOKBACK_DAYS,
                             limit=SEARCH_CATALYST_MAX_RESULTS)
        selected=projection['recent_catalysts']
        if len(selected)!=len(value):return False
        if projection['news_selection']['publisher_count']<required_unique_sources(SEARCH_CATALYST_MAX_RESULTS):return False
        if any(not isinstance(r.get('summary')or r.get('text')or'',str)for r in selected):return False
        records=[SearchResult(r['title'],r.get('summary')or r.get('text')or'',r['link'],
                             r.get('publisher')or r['source'],r.get('date'))for r in selected]
        return search_quality_satisfied(records,max_results=SEARCH_CATALYST_MAX_RESULTS,
            query=company_search_name(data),require_recent=True,lookback_days=CATALYST_LOOKBACK_DAYS,cutoff=now)
    except (KeyError,TypeError,ValueError,OverflowError):return False


def guard_recent_source_result(result,data):
    """Reject a damaged successful receipt before canonical audit publication."""
    audit=result.audit if isinstance(result.audit,dict)else{}
    if ((result.status=='success' or audit.get('status')=='success')
            and (result.source!='recent_catalysts' or result.provider!=PROVIDER
                 or not valid_recent_receipt(result.value,audit,data,require_fetch_id=False))):
        result.status='degraded_enrichment'
        result.audit={**audit,'source':'recent_catalysts','provider':PROVIDER,
            'status':result.status,'record_count':0,'quality_status':'receipt_unverified',
            'unverified_returned_record_count':len(result.value)if isinstance(result.value,list)else None,
            'error_kind':'invalid_recent_news_receipt','message':'指定新聞憑據未通過公司、時間、數量與來源門檻；保留原快照。'}
    from provider_correlation import current_correlation
    current=current_correlation()
    audit=dict(result.audit)if isinstance(result.audit,dict)else{}
    rejected={key:audit[key]for key in ('ticker','fetch_id')
              if key in audit and current.get(key)and audit[key]!=current[key]}
    if current.get('fetch_id')and audit.get('job_id')is not None and audit['job_id']!=current.get('job_id'):
        rejected['job_id']=audit['job_id']
        if not current.get('job_id'):audit.pop('job_id')
    if rejected:
        # Record the rejected observation against this fetch, keeping the
        # contradictory supplied IDs as diagnostics rather than replaying them.
        for key in ('operation_id','attempt_id'):
            if key in audit:rejected[key]=audit.pop(key)
        audit['rejected_correlation']=rejected
    for key in ('ticker','fetch_id','job_id'):
        if current.get(key):audit[key]=current[key]
    result.audit=audit
    return result


def merge_recent_source(old_data,old_audits,value,audits,ticker):
    from news_freshness_policy import apply_news_freshness
    from news_record_utils import canonical_link
    from report_source_refresh import _reassess_original_freshness
    validate_recent_refresh_context(old_data,ticker)
    if (not isinstance(audits,list)or len(audits)!=1
            or not valid_recent_receipt(value,audits[0],old_data)):
        raise HTTPException(status_code=502,detail='指定近期事件未達原公司、日期、8筆與來源多樣性門檻；原快照保持')
    merged=deepcopy(old_data)
    previous=[row for key in BUCKETS for row in old_data.get(key,[])]
    context={key:deepcopy(old_data[key])for key in ('ticker','company_name','company_identity')if key in old_data}
    # The generic helper also reselects social samples; isolate news projection.
    apply_news_freshness(context,records=[*deepcopy(value),*deepcopy(previous)],cutoff=time.time())
    for key in (*BUCKETS,'news_selection'):merged[key]=deepcopy(context[key])
    archive=deepcopy(old_data.get('source_record_archive',[]))
    incoming={canonical_link(row['link'])for row in value}
    archive.extend({'source':'recent_catalysts','reason':'duplicate_recent_search_refresh','record':deepcopy(row)}
                   for row in previous if canonical_link(row.get('link')or row.get('url'))in incoming)
    archive.extend({'source':'recent_catalysts','reason':'superseded_recent_search_audit','audit':deepcopy(a)}
                   for a in old_audits if a.get('source')=='recent_catalysts'and a.get('provider')==PROVIDER)
    if archive:merged['source_record_archive']=archive
    merged['source_audit']=[deepcopy(a)for a in old_audits
        if not(a.get('source')=='recent_catalysts'and a.get('provider')==PROVIDER)]+deepcopy(audits)
    _reassess_original_freshness(merged,ticker,'recent_catalysts',audits)
    return merged
