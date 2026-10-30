"""Exercise the real queued runner and checkpoint resume with frozen nightly input."""
import json
import pytest
import job_store
import nightly_analysis as nightly
import nightly_analysis_store as store
from test_analysis_job_checkpoint_input import harness
from agent_runtime.deferred import AgentDeferredError

@pytest.fixture
def bound(harness,monkeypatch,tmp_path):
    h=harness
    monkeypatch.setattr(store,'path',lambda:tmp_path/'nightly.sqlite3')
    job=h.new_job()
    data={'ticker':'TEST','current_price':123,'nightly_analysis':{'job_id':job,'session_date':'2026-10-30','policy':'nightly-analysis.v1'}}
    work={'job_id':job,'ticker':'TEST','pipeline':'v4','session_date':'2026-10-30','data_json':json.dumps(data),'data_sha256':store.digest(data)}
    monkeypatch.setattr(store,'get_work',lambda identity:work if identity==job else None)
    monkeypatch.setattr(nightly,'source_readiness',lambda *a:{'eligible':True,'reason_codes':[]})
    return h,job,work

def test_new_runner_and_resume_use_bound_input_without_refetch(bound):
    h,job,work=bound
    with pytest.raises(AgentDeferredError):h.run(job)
    h.control['available']=True
    assert h.run(job)
    assert h.counts['fetch']==0 and h.counts['quant']==1
    assert h.rendered[-1]['data']['current_price']==123
    assert h.rendered[-1]['data']['nightly_analysis']['job_id']==job
    before=h.counts.copy()
    assert h.run(job)
    assert h.counts==before

def test_source_invalidated_before_worker_stops_before_models(bound,monkeypatch):
    h,job,work=bound
    monkeypatch.setattr(nightly,'source_readiness',lambda *a:{'eligible':False,'reason_codes':['invalidated']})
    with pytest.raises(ValueError,match='not ready'):h.run(job)
    assert h.counts['fetch']==0 and h.counts['quant']==0 and not h.rendered
    assert job_store.get_job(job)['status']=='error'
