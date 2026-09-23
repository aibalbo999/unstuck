"""RQ backoff changes only after durable LangGraph progress, including cold resume."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest
import rq
from langgraph.graph import StateGraph, START, END

from agent_runtime.deferred import AgentDeferredError
from analysis_job_retry import prepare_analysis_retry
from workflow_checkpoints import execute_persistent_graph
from workflow_state import AgentGraphState


@pytest.fixture
def rig(monkeypatch, tmp_path):
    monkeypatch.setattr('analysis_job_retry.LLM_PROVIDER_QUOTA_AUTHORITATIVE', True)
    job = SimpleNamespace(id='analysis:progress-job', retries_left=0, retry_intervals=[60], meta={})
    job.save = lambda: None
    job.get_retry_interval = lambda: job.retry_intervals[0]
    monkeypatch.setattr(rq, 'get_current_job', lambda: job)
    return job, tmp_path / 'progress.sqlite3'


def fail(agent, wait=60):
    return AgentDeferredError(agent, [{'model_id': 'fixture-model', 'retry_wait_seconds': wait}])


def builder(control):
    graph = StateGraph(AgentGraphState)
    def prepare(state): return {'status': 'running'}
    def agent21(state):
        if control['fail'] == 'agent_21': raise fail(21, control.get('wait', 60))
        return {'analyses': {'21': 'completed initial analysis'}}
    def final_audit(state):
        if control['fail'] == 'final_audit': raise fail(17, control.get('wait', 60))
        return {'status': 'back' if control.get('back') else 'done'}
    graph.add_node('prepare', prepare);graph.add_node('agent_21', agent21);graph.add_node('final_audit', final_audit)
    graph.add_edge(START, 'prepare');graph.add_edge('prepare', 'agent_21');graph.add_edge('agent_21', 'final_audit')
    graph.add_conditional_edges('final_audit', lambda state: 'agent_21' if state['status']=='back' else END)
    return graph


def run_failure(path, control, *, thread='progress-job:v3', value=26):
    with pytest.raises(AgentDeferredError) as caught:
        asyncio.run(execute_persistent_graph(graph_builder=builder(control),
            initial_state={'pipeline_id': 'v3', 'ticker': 'TEST.TW',
                           'raw_financial_data': {'input': {'ticker': 'TEST.TW', 'current_price': value}}},
            thread_id=thread, checkpoint_path=path))
    return caught.value


def schedule(job, error):
    # RQ metadata is reloaded, not a shared Python object, on every worker run.
    job.meta = json.loads(json.dumps(job.meta))
    return prepare_analysis_retry('progress-job', error)


def test_cold_resume_progress_starts_new_stage_but_same_stage_keeps_backoff(rig):
    job,path=rig;waits=[]
    for phase in ['agent_21']*3 + ['final_audit']*4:
        result=schedule(job,run_failure(path,{'fail':phase}))
        waits.append(result['retry_after_seconds'])
        assert result['retry_scheduled'] and job.retries_left == 1
    assert waits == [300,600,1200,300,600,1200,1800]
    assert job.meta['availability_retry_count'] == 7
    assert job.meta['analysis_base_retry_intervals'] == [60]


def test_revisiting_old_node_does_not_reset_its_retained_count(rig):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    assert schedule(job,run_failure(path,{'fail':'final_audit'}))['retry_after_seconds']==300
    # final_audit completes, then a graph loop revisits previously failing Agent21.
    assert schedule(job,run_failure(path,{'fail':'agent_21','back':True}))['retry_after_seconds']==1800


def test_provider_deadline_overrides_new_stage_and_is_not_rewritten(rig):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    error=run_failure(path,{'fail':'final_audit','wait':7200})
    error.provider_quota_confirmed=True
    before=copy.deepcopy(error.routes)
    result=schedule(job,error)
    assert result['retry_after_seconds']==7200 and result['provider_quota_confirmed'] is True
    assert error.routes==before and error.key_cooldown_seconds==7200
    assert job.meta['availability_retry_count']==4


@pytest.mark.parametrize('meta', [None, {}, {'version': 1}, 'invalid', {'version': 1,'counts':{'agent_21':-1}}])
def test_legacy_or_malformed_progress_metadata_never_reduces_existing_wait(rig,meta):
    job,path=rig
    job.meta={'availability_retry_count':5, 'availability_stage_progress':meta}
    assert schedule(job,run_failure(path,{'fail':'agent_21'}))['retry_after_seconds']==1800


def test_missing_receipt_and_mismatched_job_never_reset(rig):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    assert schedule(job,fail(17))['retry_after_seconds']==1800
    error=run_failure(path.parent/'other.sqlite3',{'fail':'final_audit'},thread='another-job:v3')
    assert schedule(job,error)['retry_after_seconds']==1800


@pytest.mark.parametrize('field,value', [('node', []), ('node', {}), ('checkpoint', []),
                                         ('completion_token', 7), ('version', True)])
def test_full_scoped_but_malformed_ledger_falls_back_without_stopping_retry(rig,field,value):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    ledger=job.meta['availability_stage_progress']
    (ledger if field=='version' else ledger['last'])[field]=value
    result=schedule(job,run_failure(path,{'fail':'final_audit'}))
    assert result['retry_scheduled'] and 'retry_preparation_error' not in result
    assert result['retry_after_seconds']==1800


def test_unknown_receipt_gap_cannot_later_be_used_as_a_budget_reset(rig):
    job,path=rig
    schedule(job,run_failure(path,{'fail':'agent_21'}))
    schedule(job,fail(21));schedule(job,fail(21))
    assert schedule(job,run_failure(path,{'fail':'final_audit'}))['retry_after_seconds']==1800


def test_new_input_under_same_thread_cannot_borrow_old_completion(rig):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    error=run_failure(path.parent/'different-input.sqlite3',{'fail':'final_audit'},value=99)
    assert schedule(job,error)['retry_after_seconds']==1800


def test_changed_pending_label_without_committed_previous_node_cannot_reset(rig):
    from dataclasses import replace
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    error=run_failure(path,{'fail':'agent_21'})
    receipt=error._committed_retry_progress
    error._committed_retry_progress=replace(receipt,node='final_audit',checkpoint='different-timestamp-only')
    assert schedule(job,error)['retry_after_seconds']==1800


@pytest.mark.parametrize('field,value', [('thread', None), ('node', []), ('scope', []),
                                         ('completed', [('bad', [])]), ('checkpoint', None)])
def test_malformed_inprocess_receipt_does_not_break_retry(rig,field,value):
    from dataclasses import replace
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    error=run_failure(path,{'fail':'final_audit'})
    error._committed_retry_progress=replace(error._committed_retry_progress,**{field:value})
    result=schedule(job,error)
    assert result['retry_scheduled'] and 'retry_preparation_error' not in result
    assert result['retry_after_seconds']==1800


def test_reused_error_loses_old_receipt_when_checkpoint_read_fails(rig):
    from analysis_retry_progress import attach_committed_retry_progress
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    error=run_failure(path,{'fail':'final_audit'})
    class BrokenSaver:
        async def aget_tuple(self,config): raise OSError('fixture checkpoint unavailable')
    asyncio.run(attach_committed_retry_progress(error,BrokenSaver(),None,{}))
    result=schedule(job,error)
    assert result['retry_scheduled'] and result['retry_after_seconds']==1800


def test_saved_formal_checkpoint_headers_establish_stage_progress(rig):
    import os
    from pathlib import Path
    from analysis_retry_progress import attach_committed_retry_progress
    fixture=os.environ.get('RETRY_PROGRESS_CHECKPOINT_FIXTURE')
    if not fixture: pytest.skip('optional private committed checkpoint headers')
    rows=json.loads(Path(fixture).read_text());job,_=rig
    thread=rows[0]['config']['configurable']['thread_id'];job_id=thread.split(':',1)[0]
    job.id='analysis:'+job_id
    async def error_for(row):
        saved=SimpleNamespace(**{k:row[k] for k in ['config','metadata','checkpoint']})
        class Saved:
            async def aget_tuple(self,config): return saved
        class Graph:
            async def aget_state(self,config): return SimpleNamespace(next=(row['node'],))
        error=fail(21 if row['node']=='agent_21' else 17)
        await attach_committed_retry_progress(error,Saved(),Graph(),row['config'])
        return error
    waits=[]
    for row in [rows[0]]*3+[rows[1]]:
        error=asyncio.run(error_for(row))
        assert getattr(error,'_committed_retry_progress',None) is not None
        job.meta=json.loads(json.dumps(job.meta))
        waits.append(prepare_analysis_retry(job_id,error)['retry_after_seconds'])
    assert waits==[300,600,1200,300]


def test_missing_completion_token_is_not_explicit_no_prior_completion(rig):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    del job.meta['availability_stage_progress']['last']['completion_token']
    error=run_failure(path,{'fail':'final_audit'})
    from analysis_retry_progress import _valid_ledger
    assert not _valid_ledger(job.meta['availability_stage_progress'],error._committed_retry_progress,4)
    result=schedule(job,error)
    assert result['retry_scheduled'] and result['retry_after_seconds']==1800


@pytest.mark.parametrize('damage',['drop_old_stage','reduce_old_count','missing_counts','empty_counts'])
def test_lost_stage_accounting_cannot_treat_old_stage_as_fresh(rig,damage):
    job,path=rig
    for _ in range(3): schedule(job,run_failure(path,{'fail':'agent_21'}))
    assert schedule(job,run_failure(path,{'fail':'final_audit'}))['retry_after_seconds']==300
    ledger=job.meta['availability_stage_progress']
    if damage=='drop_old_stage': del ledger['counts']['agent_21']
    elif damage=='reduce_old_count': ledger['counts']['agent_21']=1
    elif damage=='missing_counts': del ledger['counts']
    else: ledger['counts']={}
    result=schedule(job,run_failure(path,{'fail':'agent_21','back':True}))
    assert result['retry_scheduled'] and result['retry_after_seconds']==1800
    assert job.meta['availability_retry_count']==5
