"""DB status stays compatible while observed execution and retry evidence are explicit."""
import time
import pytest
from analysis_job_payloads import serialize_analysis_job


def test_waiting_retry_is_visible_without_changing_legacy_status():
    value=serialize_analysis_job({'job_id':'j','status':'waiting_retry','error':'provider temporarily unavailable'})
    assert value['status']=='running'
    assert value['execution_state']=='waiting_retry'
    assert value['registry']['state']=='unknown'
    assert value['retry_at'] is None


def test_terminal_quality_never_reuses_a_previous_retry():
    value=serialize_analysis_job({'job_id':'j','status':'error','error':'報告品質檢查未通過'})
    assert value['status']=='failed'
    assert value['execution_state']=='terminal_quality'
    assert value['retry_at'] is None


def test_unknown_db_status_is_not_assumed_running():
    value=serialize_analysis_job({'job_id':'j','status':'unexpected'})
    assert value['execution_state']=='unknown'


@pytest.mark.parametrize('state,due,reason,health', [
    ('scheduled',2000,'cooldown','normal'), ('scheduled',900,'retry_due','normal'),
    ('missing',None,'registry_missing','needs_check'), ('unknown',None,'registry_unknown','unknown'),
    ('queued',None,'retry_queued','normal'), ('started',None,'registry_conflict','needs_check'),
])
def test_retry_deadline_does_not_change_or_resubmit_job(state,due,reason,health):
    from analysis_job_execution_state import execution_projection
    job={'job_id':'j','status':'waiting_retry','updated_at':1}
    registry={'state':state,'scheduled_at':due}
    view=execution_projection(job, registry=registry, now=1000)
    assert job=={'job_id':'j','status':'waiting_retry','updated_at':1}
    assert view['execution_state']=='waiting_retry'
    assert view['execution_reason_code']==reason
    assert view['execution_health']==health


def test_terminal_quality_clears_old_retry_and_reports_sampled_attempts():
    from analysis_job_execution_state import execution_projection
    events=[{'id':1,'created_at':10,'payload':{'phase':'workflow_retry','retry_scheduled':True,'retry_at':'2030-01-01T00:00:00Z'}},
            {'id':2,'created_at':11,'payload':{'phase':'llm_provider_request'}},
            {'id':3,'created_at':12,'payload':{'type':'progress','current':2,'total':3,'name':'Stage'}},
            {'id':4,'created_at':13,'payload':{'type':'error','phase':'report_quality_blocked'}}]
    view=execution_projection({'status':'error'}, events=events, registry={'state':'finished'})
    assert view['execution_state']=='terminal_quality'
    assert view['retry_at'] is None
    assert view['last_progress']['current']==2
    assert view['attempts']=={'basis':'bounded_event_sample','events_sampled':4,'provider_requests_sampled':1,'workflow_retries_sampled':1}


def test_stale_worker_heartbeat_is_attention_not_terminal_or_resubmission():
    from analysis_job_execution_state import execution_projection
    view=execution_projection({'status':'running'},registry={'state':'started','heartbeat_at':100},now=2000)
    assert view['execution_state']=='running'
    assert view['execution_reason_code']=='worker_heartbeat_stale'
    assert view['execution_health']=='needs_check'


class ReadOnlyRedis:
    def __init__(self): self.calls=[];self.executions=0
    def pipeline(self,**kwargs): return self
    def __enter__(self): self.batch=[];return self
    def __exit__(self,*args): pass
    def hmget(self,*args): self.calls.append(('hmget',args));self.batch.append(('hmget',args));return self
    def zscore(self,*args): self.calls.append(('zscore',args));self.batch.append(('zscore',args));return self
    def lpos(self,*args): self.calls.append(('lpos',args));self.batch.append(('lpos',args));return self
    def execute(self):
        self.executions+=1
        return [[b'scheduled',b'analysis.high',b'2026-09-22T12:00:00.000000Z'] if op=='hmget'
                else 2000 if op=='zscore' and args[0]=='rq:scheduled:analysis.high' else None
                for op,args in self.batch]


def test_registry_uses_two_batched_read_only_pipelines_and_rerun_task_identity():
    from types import SimpleNamespace
    from analysis_job_registry import inspect_job_registries
    redis=ReadOnlyRedis()
    rows=inspect_job_registries(SimpleNamespace(redis=redis),[
        {'job_id':'a','pipeline_id':'v4'}, {'job_id':'b','pipeline_id':'rerun:full_report'}])
    assert redis.executions==2
    assert all(row['state']=='scheduled' for row in rows.values())
    assert rows['a']['job_status']=='scheduled'
    assert ('hmget',(b'rq:job:report-rerun:b','status','origin','last_heartbeat')) in redis.calls
    assert all(op in {'hmget','zscore','lpos'} for op,args in redis.calls)


def test_registry_failure_is_unknown_and_does_not_expose_exception():
    from types import SimpleNamespace
    from analysis_job_registry import inspect_job_registries
    class Broken:
        def pipeline(self,**kwargs): raise RuntimeError('redis://secret@example')
    result=inspect_job_registries(SimpleNamespace(redis=Broken()),[{'job_id':'a'}])
    assert result['a']['state']=='unknown'
    assert 'secret' not in str(result)


def test_status_api_and_active_jobs_share_db_retry_projection(monkeypatch):
    import api,job_store
    from fastapi.testclient import TestClient
    monkeypatch.setattr(api,'analysis_task_queue',None)
    job=job_store.create_job('STATUS.TW','v4')
    job_store.update_job(job,'waiting_retry',error='temporary provider unavailability')
    job_store.append_event(job,{'type':'status','phase':'workflow_retry','retry_at':'2030-01-01T00:00:00Z','retry_scheduled':True})
    client=TestClient(api.app)
    detail=client.get(f'/api/analysis-jobs/{job}').json()
    active=next(row for row in client.get('/api/observability/active-jobs').json()['jobs'] if row['job_id']==job)
    assert detail['status']=='running' and active['status']=='waiting_retry'
    for key in ('execution_state','retry_at','execution_reason_code','attempts'):
        assert detail[key]==active[key]
    assert detail['registry']['state']=='unknown'
    assert job_store.get_job(job)['status']=='waiting_retry'
