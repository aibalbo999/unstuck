"""Separate actual native observations, cached originals and typed summary."""
from copy import deepcopy
import json
import pytest
from data_fetch.earnings_call_fetcher import apply_earnings_call_audit
from provider_acquisition import project_acquisition_events
P='TXC official conference presentation'

@pytest.mark.parametrize('warm',[False,True])
def test_parent_never_claims_an_extra_native_request_or_fresh_success(warm):
    result={'value':{'ticker':'3042.TW'},'audit':{'status':'success','http_request_sent':True}}
    apply_earnings_call_audit(result,{'actual_provider':P,'txc_originals_verified':True,'http_request_sent':not warm,'http_request_count':0 if warm else 2})
    audit=result['audit'];assert audit['record_count']==1 and audit['event_kind']=='aggregate'
    assert audit['http_request_sent']is False and audit['source_http_request_sent']is(not warm)
    assert audit['status']==('skipped_fresh_cache'if warm else'success')

def test_two_native_rows_are_counted_once_parent_is_excluded_and_old_rows_not_rewritten():
    def row(status,count,event,sent):return {'source':'earnings_call','provider':P,'status':status,'record_count':count,'created_at':100.,'message':'','details_json':json.dumps({'event_kind':event,'http_request_sent':sent})}
    events=[row('success',1,'http_request',True),row('success',1,'http_request',True),row('success',1,'aggregate',False)];before=deepcopy(events)
    group=project_acquisition_events(events,window='last_24h',now=101.)['sources'][0]
    assert group['fetched_count']==group['fetch_attempts']==group['http_attempt_count']==2 and group['aggregate_count']==1 and events==before

def test_an_actual_native_failure_is_never_hidden_by_parent_or_cache():
    def row(provider,status,count,details):return {'source':'earnings_call','provider':provider,'status':status,'record_count':count,'created_at':100.,'message':'','details_json':json.dumps(details)}
    events=[row(P,'error',0,{'event_kind':'http_request','http_request_sent':True}),row(P,'success',1,{'event_kind':'aggregate','http_request_sent':False}),row('legacy issuer','success',1,{'event_kind':'aggregate'})]
    group=project_acquisition_events(events,window='last_24h',now=101.)['sources'][0]
    assert group['fetched_count']==1 and group['fetch_attempts']==2 and group['failed_count']==1 and group['aggregate_count']==1
