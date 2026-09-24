"""A durable parallel superstep is one availability stage until the whole join commits."""
import asyncio
import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from langgraph.graph import StateGraph, START, END

from analysis_job_retry import prepare_analysis_retry
from analysis_retry_progress import attach_committed_retry_progress
from agent_runtime.deferred import AgentDeferredError
from workflow_checkpoints import execute_persistent_graph, open_sqlite_checkpointer
from workflow_state import AgentGraphState
from test_retry_committed_progress import rig, schedule, fail


def parallel_builder(control, calls):
    graph=StateGraph(AgentGraphState)
    async def prepare(state):
        calls.append('prepare_analysis')
        if control['fail']=='prepare_analysis': raise fail(24)
        return {'status':'running'}
    def branch(name, agent):
        async def run(state):
            calls.append(name)
            if control['fail']==name:
                # Let the other task either finish its entire delta or remain cancellable.
                await asyncio.sleep(0.01)
                raise fail(agent,control.get('wait',60))
            if name not in control.get('succeed',[]):
                await asyncio.sleep(10)
            return {'analyses': {str(agent):'complete validated node output'}}
        return run
    async def join(state): return {'status':'joined'}
    async def final(state):
        calls.append('agent_24')
        if control['fail']=='agent_24': raise fail(24,control.get('wait',60))
        return {'status':'back' if control.get('back') else 'done'}
    graph.add_node('prepare_analysis',prepare)
    for name,agent in [('agent_22',22),('agent_23',23)]: graph.add_node(name,branch(name,agent))
    graph.add_node('join',join);graph.add_node('agent_24',final)
    graph.add_edge(START,'prepare_analysis')
    graph.add_edge('prepare_analysis','agent_22');graph.add_edge('prepare_analysis','agent_23')
    graph.add_edge(['agent_22','agent_23'],'join');graph.add_edge('join','agent_24')
    graph.add_conditional_edges('agent_24',lambda state: ['agent_22','agent_23'] if state['status']=='back' else END)
    return graph


def run_parallel(path, control, calls):
    with pytest.raises(AgentDeferredError) as caught:
        asyncio.run(execute_persistent_graph(graph_builder=parallel_builder(control,calls),
            initial_state={'ticker':'TEST.TW','pipeline_id':'v4',
                           'raw_financial_data':{'input':{'ticker':'TEST.TW','current_price':26}}},
            thread_id='progress-job:v4',checkpoint_path=path))
    return caught.value


def test_single_parallel_single_stage_progress_survives_cold_resume(rig):
    job,path=rig;calls=[];waits=[]
    for _ in range(3): waits.append(schedule(job,run_parallel(path,{'fail':'prepare_analysis'},calls))['retry_after_seconds'])
    for phase in ['agent_22','agent_23','agent_22']:
        waits.append(schedule(job,run_parallel(path,{'fail':phase},calls))['retry_after_seconds'])
    # One branch commits its complete pending delta; it must NOT reset the superstep.
    error=run_parallel(path,{'fail':'agent_22','succeed':['agent_23']},calls)
    receipt=error._committed_retry_progress
    waits.append(schedule(job,error)['retry_after_seconds'])
    stage=job.meta['availability_stage_progress']['last']['node']
    assert stage.startswith('parallel_')
    assert receipt.members == ('agent_22','agent_23')
    prior23=calls.count('agent_23')
    waits.append(schedule(job,run_parallel(path,{'fail':'agent_24','succeed':['agent_22','agent_23']},calls))['retry_after_seconds'])
    # LangGraph reuses the successful pending write: Agent23 is not repeated.
    assert calls.count('agent_23')==prior23
    assert waits == [300,600,1200,300,600,1200,1800,300]
    assert job.meta['availability_retry_count']==8
    assert job.meta['availability_stage_progress']['counts'][stage]==4


def test_return_to_parallel_stage_retains_count_and_provider_deadline(rig):
    job,path=rig;calls=[]
    for phase in ['agent_22','agent_23','agent_22']:
        schedule(job,run_parallel(path,{'fail':phase},calls))
    result=schedule(job,run_parallel(path,{'fail':'agent_24','succeed':['agent_22','agent_23']},calls))
    assert result['retry_after_seconds']==300
    error=run_parallel(path,{'fail':'agent_23','succeed':['agent_22'],'back':True,'wait':7200},calls)
    error.provider_quota_confirmed=True
    result=schedule(job,error)
    assert result['retry_after_seconds']==7200 and result['provider_quota_confirmed'] is True
    ledger=job.meta['availability_stage_progress']
    assert ledger['counts'][ledger['last']['node']]==4


def test_error_only_parallel_checkpoint_is_not_a_completed_group(rig):
    job,path=rig;calls=[]
    for _ in range(2): schedule(job,run_parallel(path,{'fail':'agent_22'},calls))
    async def inspect_saved():
        async with open_sqlite_checkpointer(path) as saver:
            return await saver.aget_tuple({'configurable':{'thread_id':'progress-job:v4','checkpoint_ns':''}})
    saved=asyncio.run(inspect_saved())
    assert not saved.checkpoint['channel_values'].get('analyses')
    assert {channel for _,channel,_ in saved.pending_writes}=={'__error__'}
    error=run_parallel(path,{'fail':'agent_23'},calls)
    receipt=error._committed_retry_progress
    assert not {'agent_22','agent_23'} & dict(receipt.completed).keys()
    assert schedule(job,error)['retry_after_seconds']==1200


def test_stale_legacy_parallel_history_stays_on_global_backoff(rig):
    job,path=rig;calls=[]
    schedule(job,run_parallel(path,{'fail':'prepare_analysis'},calls))
    # Exact shape of observed jobs: three prior parallel receipts were absent.
    job.meta['availability_retry_count']=5
    result=schedule(job,run_parallel(path,{'fail':'agent_22'},calls))
    assert result['retry_after_seconds']==1800
    assert job.meta['availability_retry_count']==6


@pytest.mark.parametrize('damage',['missing_members','missing_sibling','reordered_members','unknown_member'])
def test_malformed_parallel_ledger_members_never_reduce_wait(rig,damage):
    job,path=rig;calls=[]
    for _ in range(3): schedule(job,run_parallel(path,{'fail':'agent_22'},calls))
    last=job.meta['availability_stage_progress']['last']
    if damage=='missing_members': last.pop('members')
    elif damage=='missing_sibling': last['members']=['agent_22']
    elif damage=='reordered_members': last['members']=['agent_23','agent_22']
    else: last['members']=['agent_22','unknown_node']
    result=schedule(job,run_parallel(path,{'fail':'agent_24','succeed':['agent_22','agent_23']},calls))
    assert result['retry_scheduled'] and result['retry_after_seconds']==1800


@pytest.mark.parametrize('change',['missing_root_branches','different_next','empty_next','malformed_next'])
def test_unprovable_parallel_membership_cannot_issue_progress_receipt(rig,change):
    job,path=rig;calls=[]
    error=run_parallel(path,{'fail':'agent_22'},calls)
    async def replay():
        async with open_sqlite_checkpointer(path) as saver:
            config={'configurable':{'thread_id':'progress-job:v4','checkpoint_ns':''}}
            saved=await saver.aget_tuple(config)
            checkpoint=copy.deepcopy(saved.checkpoint)
            if change=='missing_root_branches':
                checkpoint['channel_values']={k:v for k,v in checkpoint['channel_values'].items() if not k.startswith('branch:to:')}
            snapshot=SimpleNamespace(next=('agent_22','agent_23'))
            if change=='different_next': snapshot.next=('unrelated',)
            elif change=='empty_next': snapshot.next=()
            elif change=='malformed_next': snapshot.next=(['agent_22'],)
            class Saved:
                async def aget_tuple(self,_): return SimpleNamespace(config=saved.config,metadata=saved.metadata,checkpoint=checkpoint)
            class Graph:
                async def aget_state(self,_): return snapshot
            await attach_committed_retry_progress(error,Saved(),Graph(),config)
    asyncio.run(replay())
    assert not hasattr(error,'_committed_retry_progress')


def test_private_v4_checkpoints_keep_parallel_identity_and_require_whole_commit(rig):
    fixture=os.environ.get('RETRY_PARALLEL_CHECKPOINT_FIXTURE')
    if not fixture: pytest.skip('optional private v4 checkpoint/pending-write replay')
    jobs=json.loads(Path(fixture).read_text());job,_=rig
    assert len(jobs)==5
    async def make_error(row, next_nodes=None):
        saved=SimpleNamespace(**{k:row[k] for k in ['config','metadata','checkpoint']})
        saved.pending_writes=[(w['task_id'],w['channel'],w['value']) for w in row['pending_writes']]
        class Saved:
            async def aget_tuple(self,_):return saved
        class Graph:
            async def aget_state(self,_):return SimpleNamespace(next=tuple(next_nodes or row['next']))
        error=fail(22)
        await attach_committed_retry_progress(error,Saved(),Graph(),row['config'])
        return error
    for case in jobs:
        prepare=next(r for r in case['records'] if r['next']==['prepare_analysis'])
        parallel=next(r for r in case['records'] if r['next']==['agent_22','agent_23'])
        final=next((r for r in case['records'] if r['next']==['agent_24']),None)
        jid=case['job_id'];job.id='analysis:'+jid;job.meta={};job.retry_intervals=[60]
        scopes=set();stages=[];waits=[]
        variants=[(prepare,None)]*3+[(parallel,None),(parallel,['agent_22']),(parallel,['agent_23'])]
        if final is not None: variants.append((final,None))
        for row,next_nodes in variants:
            error=asyncio.run(make_error(row,next_nodes));receipt=error._committed_retry_progress
            scopes.add(receipt.scope);stages.append(receipt.node)
            job.meta=json.loads(json.dumps(job.meta))
            waits.append(prepare_analysis_retry(jid,error)['retry_after_seconds'])
        assert len(scopes)==1 and len(set(stages[3:6]))==1
        assert waits==[300,600,1200,300,600,1200]+([300] if final is not None else [])
        # The actual old jobs have gaps in receipt history: never backfill/reset them.
        job.meta=copy.deepcopy(case['old_meta']);job.retry_intervals=[60]
        result=prepare_analysis_retry(jid,asyncio.run(make_error(parallel)))
        assert result['retry_after_seconds']==1800
        assert job.meta['availability_retry_count']==6
