"""Actual native ledger must count two requests and exclude one workflow parent."""
from copy import deepcopy
from pathlib import Path
import json

import pytest

from provider_acquisition import project_acquisition_events
from data_fetch.earnings_call_fetcher import apply_earnings_call_audit

PROVIDER = 'Universal official conference presentation'


def test_saved_actual_ledger_excludes_parent_and_preserves_both_native_attempts():
    events = json.loads((Path(__file__).parent/'fixtures/source_acquisition/uk1325_formal_acquisition_events_20261012.json').read_text())
    before = deepcopy(events)
    row = project_acquisition_events(events, window='last_24h', now=max(e['created_at']for e in events)+1)['sources'][0]
    assert row['fetch_attempts'] == row['fetched_count'] == row['http_attempt_count'] == 2
    assert row['aggregate_count'] == 1 and row['nonempty_rate'] == 1.
    assert row['providers'][0]['fetch_attempts'] == 2 and events == before


@pytest.mark.parametrize('warm', [False, True])
def test_parent_never_claims_native_HTTP_even_when_workflow_requested_originals(warm):
    result = {'audit': {'status':'success','http_request_sent':True}, 'value': {'ticker':'1325.TW'}}
    apply_earnings_call_audit(result, {'actual_provider':PROVIDER,'uk_originals_verified':True,
        'http_request_sent':not warm,'http_request_count':0 if warm else 2})
    audit = result['audit']
    assert audit['http_request_sent'] is False
    assert audit['source_http_request_sent'] is (not warm) and audit['event_kind']=='aggregate'
    assert audit['status'] == ('skipped_fresh_cache' if warm else 'success')


def test_explicit_native_failures_and_untyped_legacy_observations_are_retained():
    def event(provider,status,count,details):
        return {'source':'earnings_call','provider':provider,'status':status,'record_count':count,
                'message':'','created_at':100.,'details_json':json.dumps(details)}
    events = [event(PROVIDER,'error',0,{'event_kind':'http_attempt','http_request_sent':True}),
              event(PROVIDER,'success',1,{'event_kind':'http_attempt','http_request_sent':True}),
              event('existing legacy provider','success',1,{'event_kind':'aggregate'})]
    row = project_acquisition_events(events,window='last_24h',now=101.)['sources'][0]
    assert row['fetch_attempts']==3 and row['fetched_count']==2 and row['failed_count']==1
    assert row['http_attempt_count']==2 and row['aggregate_count']==0
