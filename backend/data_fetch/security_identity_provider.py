"""Acquire only an explicit security classification for a saved unknown context."""
from copy import deepcopy
from datetime import datetime,timezone
from source_audit import audited_fetch
from .provider_base import DataProvider,provider_result_from_audited
from .market_sources.twse_security_identity import PROVIDER,fetch_security_identity,verified_security_identity

class SecurityIdentityProvider(DataProvider):
 source='taiwan_open_data'
 name=PROVIDER
 markets={'tw'}
 def fetch(self,request,context=None):
  diagnostics={}
  result=audited_fetch(self.source,self.name,lambda:fetch_security_identity(request.ticker,diagnostics=diagnostics),default=None,record_counter=lambda v:1 if verified_security_identity(v,request.ticker)else 0)
  audit=result['audit'];audit.update(deepcopy(diagnostics))
  if audit.get('status')=='success':
   epoch=result['value']['observed_at_epoch'];audit.update(fetched_at_epoch=epoch,fetched_at=datetime.fromtimestamp(epoch,timezone.utc).isoformat(),coverage_status='instrument_classification_only',source_url=result['value']['source_url'],response_sha256=result['value']['source_record_archive']['identity']['raw_response_sha256'],stale=False)
   identity_cached=diagnostics['components'][0].get('cache_hit')is True
   if identity_cached and audit['http_request_count']:
    audit.update(status='degraded_enrichment',cache_hit=True,coverage_status='partial_acquisition_with_cached_records',acquisition_status='partial_acquisition_with_cached_records',message='股別原文沿用原取得時間；只新增主檔觀測，不當成新股別取得。')
   elif identity_cached:audit.update(status='skipped_fresh_cache',cache_hit=True,event_kind='cache_hit')
  return provider_result_from_audited(result,self.source,self.name)
