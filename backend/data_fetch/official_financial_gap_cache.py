"""Short reuse of a confirmed issuer validation gap, never a successful report.

The original provider observation and all quality gates are preserved. This
does not cache transport, authorization, quota or unrecognized parsing errors.
Successful data and existing raw/radar cache lifetimes are unchanged.
"""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import math,re,time
from pathlib import Path
from zoneinfo import ZoneInfo

from cache_store import get_cache_json,set_cache_json
from source_audit import audited_fetch
from provider_correlation import current_audit_correlation,source_operation,correlation_metadata
from .market_sources.official_xbrl_financial import PROVIDER,FilingError,fetch_official_annual_histories,confirmed_annual_gap
from .market_sources.annual_filing_index_gap import (
    SCHEMA as SHORT_INDEX_SCHEMA, MESSAGE as SHORT_INDEX_MESSAGE, validate_short_annual_index_proof,
)

SCHEMA='official-financial-validation-gap.v3'
GAP_RETRY_SECONDS=300
CORRELATION_KEYS={'job_id','fetch_id','operation_id','attempt_id','provider_attempts',
                  'provider_attempt_count','provider_sla_event_id','ticker','data_fingerprint','event_kind'}


def _parser_fingerprint():
    directory=Path(__file__).resolve().parent
    paths=[Path(__file__).resolve(),directory/'market_sources/official_xbrl_financial.py',
           directory/'market_sources/official_mopsfin_financial.py',
           directory/'market_sources/annual_filing_index_gap.py']
    return sha256(b''.join(p.read_bytes() for p in paths)).hexdigest()


def _gap_reason(message):
    if message==SHORT_INDEX_MESSAGE:return True
    match=re.fullmatch(r'(?:annual XBRL facts are incomplete|conflicting incomplete comparative statement) for (20\d{2})',str(message))
    return bool(match and 2013<=int(match[1])<=datetime.now(ZoneInfo('Asia/Taipei')).year)


def _validated_proof(proof,ticker,message):
    try:
        if not isinstance(proof,dict) or proof.get('issuer')!=ticker.split('.')[0] or proof.get('message')!=message:
            return False
        if proof.get('schema')==SHORT_INDEX_SCHEMA:
            return validate_short_annual_index_proof(proof,proof['issuer'],message)
        rows={int(y):values for y,values in proof['raw_twd_by_year'].items()}
        expected=confirmed_annual_gap(message,proof['issuer'],rows,
            {proof['year']:proof['comparative_raw_twd']},proof['documents'])
        return expected is not None and expected==proof
    except (KeyError,ValueError,TypeError,AttributeError):return False


def _valid(stored,ticker,fingerprint):
    if not isinstance(stored,dict) or stored.get('schema')!=SCHEMA or stored.get('ticker')!=ticker or stored.get('parser_fingerprint')!=fingerprint:
        return False
    audit=stored.get('audit')
    if (not isinstance(audit,dict) or audit.get('source')!='financial_statements' or audit.get('provider')!=PROVIDER
            or audit.get('status')!='error' or audit.get('error_kind')!='FilingError'
            or type(audit.get('record_count')) is not int or audit['record_count']!=0
            or not _gap_reason(audit.get('message'))
            or not _validated_proof(stored.get('validation_gap'),ticker,audit.get('message'))):return False
    proof=stored['validation_gap']
    if proof.get('schema')==SHORT_INDEX_SCHEMA and (
            audit.get('coverage_status')!='insufficient_annual_history'
            or audit.get('available_consolidated_annual_years')!=proof['available_consolidated_annual_years']):return False
    stamp=audit.get('fetched_at_epoch')
    try:
        original=datetime.fromisoformat(audit['fetched_at'])
        return (original.tzinfo is not None and type(stamp) in (int,float) and math.isfinite(stamp)
                and abs(original.timestamp()-stamp)<.000001 and 0<=time.time()-stamp<GAP_RETRY_SECONDS)
    except (KeyError,ValueError,TypeError,OverflowError):return False


def fetch_official_financial_result(ticker,*,fetcher=None):
    """Keep one actual failure; repeat reads have new identity and no attempt."""
    if fetcher is None:
        # The new public protocol owns its receipts and provider identity.
        # Preserve the legacy iXBRL gap namespace for explicit legacy callers.
        from .market_sources.mops_public_annual import fetch_public_financial_result
        return fetch_public_financial_result(ticker)
    fetcher=fetcher or fetch_official_annual_histories
    started=time.monotonic()
    ticker=str(ticker).strip().upper()
    key=None;stored=None;fingerprint=None;cache_read_failed=False
    if re.fullmatch(r'[1-9]\d{3}\.TW(?:O)?',ticker):
        try:
            fingerprint=_parser_fingerprint()
            key=f'official-financial-validation-gap:{fingerprint}:{datetime.now(ZoneInfo("Asia/Taipei")).year}:{ticker}'
            stored=get_cache_json(key)
        except Exception:
            stored=None;cache_read_failed=True
    if key and _valid(stored,ticker,fingerprint):
        with source_operation('financial_statements',PROVIDER):
            old_keys=CORRELATION_KEYS | set(correlation_metadata(stored['audit']))
            audit={k:deepcopy(v) for k,v in stored['audit'].items() if k not in old_keys}
            original_message=audit['message']
            audit.update(current_audit_correlation(),ticker=ticker,cache_hit=True,stale=False,
                event_kind='cache_hit',http_request_sent=False,original_status='error',
                provider_attempts=[],provider_attempt_count=0,
                duration_ms=max(0,round((time.monotonic()-started)*1000)),
                retry_at=audit['fetched_at_epoch']+GAP_RETRY_SECONDS,
                message=original_message+'；沿用已確認的同股票年度財報缺口，暫不重複下載。')
            return {'value':None,'audit':audit}
    validated=[]
    def capture_gap(*args):
        validated.clear()
        try:return fetcher(*args)
        except FilingError as exc:
            proof=getattr(exc,'validation_gap',None)
            if _validated_proof(proof,ticker,str(exc)):validated.append(deepcopy(proof))
            raise
    result=audited_fetch('financial_statements',PROVIDER,capture_gap,(ticker,),default=None,
        record_counter=lambda value:len(value.get('years',[]))if isinstance(value,dict)else 0,
        unavailable_message='MOPS 未回傳五年完整合併年報。')
    audit=result.get('audit') or {}
    if validated and validated[0].get('schema')==SHORT_INDEX_SCHEMA:
        audit.update(coverage_status='insufficient_annual_history',
            available_consolidated_annual_years=list(validated[0]['available_consolidated_annual_years']))
    if key and audit.get('status')=='success' and (stored is not None or cache_read_failed):
        try:set_cache_json(key,None,1)
        except Exception:pass
    if key and validated and result.get('value') is None and audit.get('status')=='error' and audit.get('error_kind')=='FilingError' and _gap_reason(audit.get('message')):
        try:
            original=deepcopy(audit)
            stamp=datetime.fromisoformat(original['fetched_at'])
            if stamp.tzinfo is None:raise ValueError('Unverified original gap timestamp')
            original['fetched_at_epoch']=stamp.timestamp()
            receipt={'schema':SCHEMA,'ticker':ticker,'parser_fingerprint':fingerprint,'audit':original,'validation_gap':validated[0]}
            if _valid(receipt,ticker,fingerprint):set_cache_json(key,receipt,GAP_RETRY_SECONDS)
        except Exception:
            pass
    return result
