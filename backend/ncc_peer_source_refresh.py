"""NCC-only peer refresh: exact issuer scope, live originals and dated metrics."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import time
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from data_fetch.market_sources.ncc_mobile_peer_cohort import IDENTITIES,supports_context,verified_candidates
from data_fetch.market_sources.peer_recovery import industry_comparability
from thermal_peer_source_refresh import _usable_metrics


def validate_ncc_refresh_context(data,ticker):
 from source_applicability import instrument_type
 if (not isinstance(data,dict)or data.get('ticker')!=ticker
     or not supports_context(ticker,data.get('industry'),data.get('company_identity'))
     or instrument_type(data)!='EQUITY'
     or any(data.get(k)not in(None,'','EQUITY')for k in('quote_type','quoteType','instrument_type'))
     or not isinstance(data.get('dynamic_peer_metrics'),list)):
  raise HTTPException(status_code=400,detail='NCC 同業刷新須有一致的電信股票身分、業務分類與原指標清單')
 short,legal,_=IDENTITIES[ticker];name=data.get('company_name');identity=data['company_identity'];english=identity.get('english_names',[])
 if (not isinstance(name,str)or not name.strip()or not isinstance(english,list)
     or any(not isinstance(v,str)for v in english)):
  raise HTTPException(status_code=400,detail='NCC 同業刷新公司名稱未通過核對')
 parts=name.split(' / ')
 if (parts[0].strip()not in{short,legal}or any(not v.strip()or v.strip()not in english for v in parts[1:])):
  raise HTTPException(status_code=400,detail='NCC 同業刷新公司名稱與原身分不一致')


def validate_ncc_payload(data,value,audits,ticker):
 from report_source_refresh import _timestamp
 validate_ncc_refresh_context(data,ticker)
 today=datetime.now(ZoneInfo('Asia/Taipei')).date()
 if not isinstance(value,list)or not value or not verified_candidates(value,ticker,today=today):
  raise ValueError('ncc_membership_originals_unverified')
 for row in value:
  if (row.get('comparison_status')!='business_industry_matched'
      or industry_comparability(data['industry'],row.get('reported_industry'))!='business_industry_matched'):
   raise ValueError('ncc_quote_industry_unverified')
 usable=sum(_usable_metrics(row,today)for row in value)
 if not usable or not isinstance(audits,list)or len(audits)!=1:raise ValueError('ncc_metric_evidence_missing')
 audit=audits[0]
 if (not isinstance(audit,dict)or audit.get('source')!='dynamic_peer_metrics'
     or audit.get('provider')!='FinMind/yfinance' or audit.get('ticker')!=ticker
     or not isinstance(audit.get('fetch_id'),str)or not audit['fetch_id']
     or not isinstance(audit.get('operation_id'),str)or not audit['operation_id']
     or audit.get('status')not in{'success','degraded_enrichment'}
     or type(audit.get('record_count'))is not int or audit['record_count']!=usable
     or type(audit.get('usable_count'))is not int or audit['usable_count']!=usable
     or audit.get('stale')is not False):raise ValueError('ncc_metric_audit_mismatch')
 partial=any(row['metrics_status']!='complete'for row in value)
 if (audit.get('coverage_status')!=('partial'if partial else'success')
     or audit.get('quality_status')!=('partial_metrics'if partial else'usable')
     or audit['status']!=('degraded_enrichment'if partial else'success')):raise ValueError('ncc_metric_quality_mismatch')
 stamp=_timestamp(audit)
 if stamp is None or not 0<=time.time()-stamp<1800:raise ValueError('ncc_metric_audit_expired')
 if not verified_candidates(value,ticker,today=today):raise ValueError('ncc_originals_expired_during_metric_validation')
 return usable


def guard_ncc_result(result,data,ticker):
 validate_ncc_refresh_context(data,ticker)
 try:
  if (result.source!='dynamic_peer_metrics'or result.provider!='FinMind/yfinance'
      or not isinstance(result.audit,dict)or result.status!=result.audit.get('status')):raise ValueError('ncc_result_identity_or_status')
  validate_ncc_payload(data,result.value,[result.audit],ticker)
 except(ValueError,TypeError,KeyError,OverflowError):
  audit=deepcopy(result.audit)if isinstance(result.audit,dict)else{}
  audit.update(source='dynamic_peer_metrics',status='error',record_count=0,usable_count=0,
   error_kind='ncc_peer_source_unverified',message='NCC 同業原件、指標或取得憑據未通過核對；保留未知及原快照。')
  return replace(result,status='error',value=[],audit=audit)
 return result


def merge_ncc_peer_source(old_data,old_audits,value,audits,ticker):
 from report_source_refresh import _reassess_original_freshness
 validate_ncc_refresh_context(old_data,ticker)
 try:validate_ncc_payload(old_data,value,audits,ticker)
 except(ValueError,TypeError,KeyError,OverflowError)as exc:
  raise HTTPException(status_code=502,detail='NCC 同業原件、指標或取得憑據未通過核對；原快照保持')from exc
 merged=deepcopy(old_data);merged['dynamic_peer_metrics']=deepcopy(value)
 merged['source_audit']=[deepcopy(row)for row in old_audits if row.get('source')!='dynamic_peer_metrics']+deepcopy(audits)
 _reassess_original_freshness(merged,ticker,'dynamic_peer_metrics',audits)
 return merged
