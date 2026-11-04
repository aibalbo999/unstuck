"""Choose one already qualified source on a later request, never a retry loop."""
import sqlite3
import time

import pytest

from test_shared_provider_cache import memory_cache


def observe(**changes):
    from provider_sla import record_source_audit_entries
    entry={'source':'earnings_call','provider':'MOPS published presentation','ticker':'3653.TW',
        'status':'error','record_count':0,'http_request_sent':True,'error_kind':'timeout',
        'component_statuses':[{'http_request_sent':False,'cache_hit':True},
            {'url':'https://mopsov.twse.com.tw/server-java/FileDownLoad','request_method':'POST',
             'http_request_sent':True,'http_status_observed':False,'response_complete':False,
             'error_kind':'timeout','response_bytes':0}]}
    entry.update(changes);record_source_audit_entries([entry])


def test_later_request_chooses_qualified_issuer_after_saved_transport_failure(memory_cache,monkeypatch):
    from test_report_refresh_acquisition_audit import init_db
    from data_fetch import earnings_call_fetcher as flow
    from data_fetch.market_sources import mops_presentation as m,jentech_conference as j
    init_db();observe();calls=[]
    monkeypatch.setattr(m,'fetch_presentation_context',lambda *a,**k:pytest.fail('No MOPS request on this invocation'))
    monkeypatch.setattr(j,'fetch_jentech_context',lambda *a,**k:calls.append((a,k))or{'issuer':True})
    diagnostic={}
    assert flow.fetch_free_earnings_call_context('3653.TW',diagnostics=diagnostic)=={'issuer':True}
    assert len(calls)==1 and calls[0][1]['force_refresh']is False
    assert diagnostic['selection_policy']=='qualified-issuer-after-prior-mops-transport:v1'


@pytest.mark.parametrize('changes',[
    {'error_kind':'parse_error'},{'error_kind':'context_unverified'},
    {'error_kind':'access_denied','http_status':403},{'error_kind':'rate_limited','http_status':429},
    {'component_statuses':[{'http_request_sent':True,'http_status':403,'error_kind':'timeout'}]},
    {'component_statuses':[{'http_request_sent':True,'error_kind':'timeout'}]},
    {'http_request_sent':False,'component_statuses':[]},
    {'status':'success','record_count':1},
])
def test_opaque_or_rejected_failure_never_authorizes_new_route(memory_cache,changes):
    from test_report_refresh_acquisition_audit import init_db
    from data_fetch.market_sources.jentech_source_routing import prior_mops_transport_failure
    init_db();observe(**changes)
    assert prior_mops_transport_failure('3653.TW')is None


def test_newer_native_success_restores_primary_and_old_failure_is_preserved(memory_cache):
    from test_report_refresh_acquisition_audit import init_db,events
    from data_fetch.market_sources.jentech_source_routing import prior_mops_transport_failure
    init_db();observe();original=events()[0]
    assert prior_mops_transport_failure('3653.TW')
    observe(status='success',record_count=1,error_kind='')
    assert prior_mops_transport_failure('3653.TW')is None and events()[0]==original


def test_old_failure_does_not_pin_a_route_indefinitely(memory_cache):
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import TASK_DB_PATH
    from data_fetch.market_sources.jentech_source_routing import prior_mops_transport_failure
    init_db();observe()
    with sqlite3.connect(TASK_DB_PATH)as c:c.execute('UPDATE provider_sla_events SET created_at=?',(time.time()-86401,))
    assert prior_mops_transport_failure('3653.TW')is None


def test_chosen_issuer_failure_does_not_retry_government_or_third_source(memory_cache,monkeypatch):
    from test_report_refresh_acquisition_audit import init_db
    from data_fetch import earnings_call_fetcher as flow
    from data_fetch.market_sources import mops_presentation as m,jentech_conference as j
    from search_provider_runtime import SourceResponseError
    init_db();observe()
    monkeypatch.setattr(m,'fetch_presentation_context',lambda *a,**k:pytest.fail('No second provider retry'))
    def blocked(*a,**k):raise SourceResponseError('access_denied',status_code=403)
    monkeypatch.setattr(j,'fetch_jentech_context',blocked)
    with pytest.raises(SourceResponseError)as e:flow.fetch_free_earnings_call_context('3653.TW')
    assert e.value.error_kind=='access_denied'


@pytest.mark.parametrize('mismatch',[None,'operation','time','component'])
def test_only_identical_native_operation_can_restore_wrapper_missing_hash(memory_cache,mismatch):
    import json
    from test_report_refresh_acquisition_audit import init_db
    from provider_sla import TASK_DB_PATH
    from data_fetch.market_sources.jentech_source_routing import prior_mops_transport_failure
    init_db();observe(fetch_id='a'*32,operation_id='b'*32)
    with sqlite3.connect(TASK_DB_PATH)as c:
        first=c.execute('SELECT id,created_at,details_json FROM provider_sla_events').fetchone()
    observe(fetch_id='a'*32,operation_id='b'*32)
    with sqlite3.connect(TASK_DB_PATH)as c:
        latest=c.execute('SELECT id,details_json FROM provider_sla_events ORDER BY id DESC LIMIT 1').fetchone()
        d=json.loads(latest[1]);d['component_statuses'][-1].pop('request_url_sha256')
        if mismatch=='operation':d['operation_id']='c'*32
        if mismatch=='component':d['component_statuses'][-1]['response_bytes']=1
        c.execute('UPDATE provider_sla_events SET created_at=?,details_json=? WHERE id=?',
            (first[1]+(1 if mismatch=='time'else 0),json.dumps(d),latest[0]))
    decision=prior_mops_transport_failure('3653.TW')
    if mismatch is None:
        assert decision['event_id']==first[0]and decision['correlated_wrapper_event_id']==latest[0]
    else:assert decision is None
