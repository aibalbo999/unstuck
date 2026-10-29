import json


def event(operation, *, model='gemini-a', status='observed', at=100, id=1, units=0, **metadata):
    return {'id':id, 'operation':operation, 'model_id':model, 'status':status,'units':units,
            'created_at':at,'metadata_json':json.dumps(metadata)}


def test_distinct_count_bases_unknown_tokens_and_parallel_wait_union():
    from llm_execution_observations import build_execution_observations
    rows=[
        event('llm_provider_request',units=1,job_id='job-a',attempt_id='a'),
        event('llm_transport_observation',status='attempt',job_id='job-a',attempt_id='a',transport_attempt_id='t'),
        event('llm_transport_observation',status='success',job_id='job-a',attempt_id='a',transport_attempt_id='t',usage={'input_tokens':12},elapsed_seconds=2),
        event('llm_model_response',status='success',job_id='job-a',attempt_id='a',response_diagnostics={'usage':{'input_tokens':12}}),
        event('llm_admission_decision',phase='model_circuit_open',observation_event_id='decision-a',job_id='job-a'),
        event('llm_wait_interval',job_id='job-a',wait_id='w1',started_at=100,elapsed_seconds=10,planned_seconds=390),
        event('llm_wait_interval',job_id='job-a',wait_id='w2',started_at=105,elapsed_seconds=10,planned_seconds=390),
    ]
    result=build_execution_observations(rows,[{'job_id':'job-a','status':'done','filename':'report.html','created_at':90,'started_at':95,'finished_at':120,'pipeline_id':'v4'}])
    assert result['totals']['agent_request_events']==1
    assert result['totals']['sdk_callback_attempts']==1
    assert result['totals']['local_preflight_events']==1
    report=result['reports'][0]
    assert report['known_input_tokens']==12
    assert report['observed_wait_union_seconds']==15
    assert report['quality_outcome']=='not_recorded'


def test_quota_companion_events_do_not_double_count_and_missing_details_stay_unknown():
    from llm_execution_observations import build_execution_observations
    observation={'detail_status':'partial','violations':[{'kind':'rpm','limit':None}]}
    rows=[
        event('llm_transport_observation',status='error',provider_status_code=429,attempt_id='a',transport_attempt_id='t',quota_observation=observation),
        event('llm_model_error',status='quota_error',attempt_id='a',provider_status_code=429,error_kind='ClientError'),
        event('llm_provider_quota_observation',attempt_id='a',provider_status_code=429,quota_observation=observation),
        event('llm_model_error',status='quota_error',id=2,error_kind='ClientError'),
    ]
    result=build_execution_observations(rows,[])
    assert result['quota']['events']==2
    assert result['quota']['kinds']=={'rpm':1,'unknown':1}
    assert result['quota']['classified_pct']==50


def test_evidence_requests_join_exact_quality_decision_not_job_done():
    from llm_execution_observations import build_execution_observations
    rows=[
        event('llm_provider_request',model='gemma-fixture',units=1,job_id='job-a',call_purpose='evidence_batch'),
        event('llm_evidence_progress',job_id='job-a',phase='gemma_evidence_appendix_prepared',evidence_appendix_attached=True),
        event('llm_report_quality_observation',status='gate_blocked',job_id='job-a',pipeline_id='v4',gates={'final_audit':'failed'}),
    ]
    result=build_execution_observations(rows,[{'job_id':'job-a','status':'error','filename':None,'created_at':90,'started_at':95,'finished_at':120,'pipeline_id':'v4'}])
    assert result['evidence']['request_events']==1
    assert result['evidence']['jobs_with_appendix']==1
    assert result['evidence']['jobs_with_appendix_gate_passed']==0
    assert result['reports'][0]['quality_outcome']=='gate_blocked'
    assert result['reports'][0]['known_input_tokens'] is None


def test_recorder_exposes_route_skips_and_quality_gate_without_model_calls():
    from api_usage_store import record_runtime_event_usage, summarize_llm_execution_observations
    from provider_correlation import correlation_scope
    from report_publication_gate import assert_report_publishable, ReportPublicationBlockedError
    import pytest
    record_runtime_event_usage('job-fixture',{'phase':'model_circuit_open','agent_num':22,'metadata':{'model_id':'gemini-fixture','reason_code':'model_cooldown'}})
    with correlation_scope(job_id='job-fixture'):
        with pytest.raises(ReportPublicationBlockedError):
            assert_report_publishable({'status':'blocked','pipeline_id':'v4'})
    result=summarize_llm_execution_observations(0)
    assert result['totals']['agent_request_events']==0
    assert result['totals']['local_preflight_events']>=1
    assert result['quality']['gate_blocked']>=1


def test_appendix_cannot_borrow_quality_from_another_mode_or_missing_pipeline():
    from llm_execution_observations import build_execution_observations
    rows=[event('llm_evidence_progress',job_id='job-a',pipeline_id='v4',phase='gemma_evidence_appendix_prepared',evidence_appendix_attached=True),
          event('llm_report_quality_observation',job_id='job-a',pipeline_id='v1',status='gate_passed'),
          event('llm_report_quality_observation',job_id='job-a',pipeline_id='v4',status='gate_blocked')]
    assert build_execution_observations(rows,[])['evidence']['jobs_with_appendix_gate_passed']==0


def test_bounded_reader_deduplicates_new_ledger_and_matching_analysis_event(tmp_path):
    import sqlite3
    from api_usage_store import record_runtime_event_usage,summarize_llm_execution_observations
    path=tmp_path/'observations.sqlite3'
    payload={'phase':'model_circuit_open','agent_num':22,'metadata':{'model_id':'gemini-a','observation_event_id':'exact-event'}}
    record_runtime_event_usage('job-a',payload,created_at=100,db_path=path)
    with sqlite3.connect(path) as conn:
        conn.execute('create table analysis_events (id integer,job_id text,phase text,payload text,created_at real)')
        conn.execute('insert into analysis_events values (1,?,?,?,100)',('job-a','model_circuit_open',json.dumps(payload)))
    result=summarize_llm_execution_observations(0,now=200,db_path=path)
    assert result['totals']['local_preflight_events']==1
    assert summarize_llm_execution_observations(150,now=200,db_path=path)['totals']['local_preflight_events']==0


def test_batch_success_is_not_role_success_or_a_role_retry():
    from llm_execution_observations import build_execution_observations
    rows=[event('llm_provider_request',units=1,logical_call_id='l',attempt_id='a',call_purpose='evidence_batch'),
          event('llm_provider_request',units=1,logical_call_id='l',attempt_id='b',call_purpose='evidence_batch'),
          event('llm_model_response',logical_call_id='l',call_purpose='evidence_batch')]
    result=build_execution_observations(rows,[])
    assert result['retry']['eventually_returned_role_response']==0
    assert result['retry']['logical_calls_with_multiple_attempts']==0


def test_missing_transport_terminal_does_not_hide_saved_provider_error():
    from llm_execution_observations import build_execution_observations
    rows=[event('llm_transport_observation',status='attempt',attempt_id='a',transport_attempt_id='t'),
          event('llm_model_error',status='quota_error',attempt_id='a',provider_status_code=429,error_kind='ClientError')]
    result=build_execution_observations(rows,[])
    assert result['quota']['events']==1


def test_quality_without_pipeline_cannot_qualify_pipeline_report():
    from llm_execution_observations import build_execution_observations
    result=build_execution_observations([event('llm_report_quality_observation',status='gate_passed',job_id='job-a')],
                                        [{'job_id':'job-a','pipeline_id':'v4','status':'done'}])
    assert result['reports'][0]['quality_outcome']=='not_recorded'


def test_two_missing_pipeline_ids_do_not_establish_appendix_quality_binding():
    from llm_execution_observations import build_execution_observations
    rows=[event('llm_evidence_progress',job_id='job-a',phase='gemma_evidence_appendix_prepared',evidence_appendix_attached=True),
          event('llm_report_quality_observation',job_id='job-a',status='gate_passed')]
    result=build_execution_observations(rows,[])
    assert result['evidence']['jobs_with_appendix']==1
    assert result['evidence']['jobs_with_appendix_gate_passed']==0


def test_native_observability_route_serves_real_isolated_observation(monkeypatch,tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.observability import create_observability_router,ObservabilityRouteDeps
    import api_usage_store as usage
    monkeypatch.setattr(usage,'API_USAGE_DB_PATH',str(tmp_path/'route.sqlite3'))
    usage.reset_api_usage_store_for_tests()
    usage.record_api_usage(service='Gemini / Google AI',provider='google_ai',operation='llm_provider_request',
                           model_id='gemma-4-26b-a4b-it',status='attempt',units=1)
    app=FastAPI()
    app.include_router(create_observability_router(ObservabilityRouteDeps(
        get_provider_sla_summary=lambda _:[],get_provider_sla_alerts=lambda _:[],get_task_queue=lambda:None)))
    with TestClient(app) as client:
        response=client.get('/api/observability/api-quotas')
    assert response.status_code==200
    observation=response.json()['services'][0]['usage']['execution_observation']
    assert observation['available'] is True
    assert observation['model_request_events']['gemma-4-26b-a4b-it']==1
