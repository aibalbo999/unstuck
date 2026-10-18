"""Cancelled scheduler joins its producer and preserves undispatched intents."""
import asyncio
import threading
from contextvars import ContextVar
from types import SimpleNamespace

import pytest

import job_store
import watchlist_service as service
import watchlist_scheduler as scheduler
from test_watchlist_dispatch_recovery import environment,MemoryRedis,queue,noop,rows,jobs,NOW,tick,assert_complete


def dispatch(items,q,**extra):
    return service.enqueue_watchlist_items(items,create_job=job_store.create_job,
        find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop,**extra)


def test_stopped_batch_releases_all_undispatched_leases_and_recovers_same_job_ids(environment):
    redis=MemoryRedis();q=queue(redis);items=service.claim_due_watchlist_items(NOW)
    original={x['dispatch_id']:x['dispatch_job_id']for x in items}
    stop=threading.Event();stop.set()
    result=dispatch(items,q,stop_event=stop)
    assert result['interrupted']is True and result['success']is True and result['queued']==[]
    assert jobs()==[] and all(r['state']=='pending'and r['lease_token']is None for r in rows())
    assert {r['dispatch_id']:r['job_id']for r in rows()}==original
    assert len(tick(q)['queued'])==2;assert_complete(redis)
    assert {x['job_id']for x in jobs()}==set(original.values())


def test_stop_after_one_commit_keeps_receipt_and_releases_remaining_intent(environment,monkeypatch):
    redis=MemoryRedis();q=queue(redis);items=service.claim_due_watchlist_items(NOW);once=q.enqueue_once
    stop=threading.Event()
    def enqueue(*a,**k):
        receipt=once(*a,**k);stop.set();return receipt
    monkeypatch.setattr(q,'enqueue_once',enqueue)
    result=dispatch(items,q,stop_event=stop)
    assert result['interrupted']is True and len(result['queued'])==1 and not result['errors']
    assert [x['state']for x in rows()]==['acknowledged','pending']
    assert len(jobs())==1 and sum(len(v)for v in redis.lists.values())==1
    assert rows()[1]['job_id']==items[1]['dispatch_job_id']
    monkeypatch.setattr(q,'enqueue_once',once)
    assert len(tick(q)['queued'])==1;assert_complete(redis)
    assert {x['job_id']for x in jobs()}=={x['dispatch_job_id']for x in items}


def test_public_scheduler_cancellation_waits_for_background_producer_without_second_dispatch(environment,monkeypatch):
    redis=MemoryRedis();q=queue(redis);items=service.claim_due_watchlist_items(NOW)
    in_delay=threading.Event();release_legacy_delay=threading.Event();finished=threading.Event()
    original=service.enqueue_watchlist_items
    def producer(*a,**k):
        try:return original(*a,**k)
        finally:finished.set()
    def legacy_sleep(seconds):
        assert seconds==45;in_delay.set();release_legacy_delay.wait(2)
    class ObservedStop(threading.Event):
        def wait(self,timeout=None):
            if timeout==45:in_delay.set()
            return super().wait(timeout)
    monkeypatch.setattr(service,'enqueue_watchlist_items',producer)
    monkeypatch.setattr(service,'time',SimpleNamespace(sleep=legacy_sleep))
    monkeypatch.setattr(scheduler,'Event',ObservedStop,raising=False)
    monkeypatch.setattr(service,'claim_due_watchlist_items',lambda:items)
    monkeypatch.setattr(scheduler,'_run_daily_market_screener',lambda **k:pytest.fail('cancelled batch must not start screener'))
    async def monitor(**k):pytest.fail('cancelled batch must not start trigger work')
    monkeypatch.setattr(service,'monitor_watchlist_triggers',monitor)
    async def scenario():
        task=asyncio.create_task(scheduler.run_watchlist_scheduler(
            create_job=job_store.create_job,find_active_job=job_store.find_active_job,
            task_queue=q,run_stock_analysis_job=noop,data_service=object(),emit_log=lambda x:None))
        try:
            assert await asyncio.to_thread(in_delay.wait,2),'producer did not reach pacing boundary'
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await asyncio.wait_for(asyncio.shield(task),.75)
            assert finished.is_set(),'cancelled scheduler returned before its background producer exited'
            assert len(jobs())==1 and [x['state']for x in rows()]==['acknowledged','pending']
        finally:
            release_legacy_delay.set()
            if not task.done():task.cancel()
            await asyncio.to_thread(finished.wait,2)
    asyncio.run(scenario())


def test_cancelled_before_claim_does_not_acquire_more_leases(monkeypatch):
    stop=threading.Event();stop.set()
    monkeypatch.setattr(service,'claim_due_watchlist_items',lambda:pytest.fail('stop must be checked before claim'))
    result=scheduler._run_due_watchlist_batch(create_job=lambda *a:None,
        find_active_job=lambda *a:{},task_queue=object(),run_stock_analysis_job=noop,
        emit_log=lambda x:None,stop_event=stop)
    assert result['interrupted']is True and result['queued']==[]


def test_cancellation_during_claim_releases_just_acquired_leases(environment,monkeypatch):
    items=service.claim_due_watchlist_items(NOW);stop=threading.Event()
    def claim_then_stop():
        stop.set();return items
    monkeypatch.setattr(service,'claim_due_watchlist_items',claim_then_stop)
    result=scheduler._run_due_watchlist_batch(create_job=job_store.create_job,
        find_active_job=job_store.find_active_job,task_queue=queue(MemoryRedis()),
        run_stock_analysis_job=noop,emit_log=lambda x:None,stop_event=stop)
    assert result['interrupted']is True and jobs()==[]
    assert all(x['state']=='pending'for x in rows())


def test_trigger_pacing_can_be_cancelled_without_dispatching_the_next_stock(environment,monkeypatch):
    from data_fetch import FetchResult
    from datetime import datetime
    for ticker in ('2308.TW','3324.TWO'):
        service.upsert_watchlist_item({'ticker':ticker,'pipeline':'v1','enabled':True,
            'schedule_slots':['post_market'],'triggers':[{'type':'vix_above','threshold':30}]})
    dispatched=[]
    class TriggerQueue:
        def enqueue(self,key,function,*args,**kwargs):
            dispatched.append((key,args,kwargs))
    q=TriggerQueue()
    class Data:
        async def fetch_async(self,request):
            return FetchResult(request=request,data={'macro_indicators':{'indicators':{'vix':{'value':35}}}})
    async def scenario():
        in_wait=asyncio.Event();never=asyncio.Event()
        async def pacing(seconds):
            assert seconds==45;in_wait.set();await never.wait()
        monkeypatch.setattr(service,'asyncio',SimpleNamespace(sleep=pacing))
        task=asyncio.create_task(service.monitor_watchlist_triggers(data_service=Data(),
            create_job=job_store.create_job,find_active_job=job_store.find_active_job,
            task_queue=q,run_stock_analysis_job=noop,now=datetime(2026,10,7,16,0,tzinfo=service.TAIPEI)))
        try:
            await asyncio.wait_for(in_wait.wait(),1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):await task
            assert len(jobs())==1 and len(dispatched)==1
        finally:
            if not task.done():task.cancel()
            await asyncio.gather(task,return_exceptions=True)
    asyncio.run(scenario())


@pytest.mark.parametrize('cancel_other_tasks', [False, True])
def test_repeated_cancellation_joins_actual_producer_after_queue_commit(environment,monkeypatch,cancel_other_tasks):
    redis=MemoryRedis();q=queue(redis);items=service.claim_due_watchlist_items(NOW)
    original_claim=service.claim_due_watchlist_items
    committed=threading.Event();release_receipt=threading.Event();stop_seen=threading.Event()
    context=ContextVar('watchlist_test_context',default=None)
    once=q.enqueue_once
    def delayed_receipt(*args,**kwargs):
        assert context.get()=='scheduler_scope'
        receipt=once(*args,**kwargs)
        committed.set()
        assert release_receipt.wait(3),'test cleanup did not release queue receipt'
        return receipt
    class ObservedStop(threading.Event):
        def set(self):
            super().set();stop_seen.set()
    monkeypatch.setattr(q,'enqueue_once',delayed_receipt)
    monkeypatch.setattr(scheduler,'Event',ObservedStop)
    monkeypatch.setattr(service,'claim_due_watchlist_items',lambda:items)
    async def scenario():
        context.set('scheduler_scope')
        task=asyncio.create_task(scheduler.run_watchlist_scheduler(
            create_job=job_store.create_job,find_active_job=job_store.find_active_job,
            task_queue=q,run_stock_analysis_job=noop,data_service=object(),emit_log=lambda _:None))
        try:
            assert await asyncio.to_thread(committed.wait,1)
            task.cancel()
            assert await asyncio.to_thread(stop_seen.wait,1)
            assert not task.done()
            task.cancel()
            if cancel_other_tasks:
                for pending in asyncio.all_tasks():
                    if pending is not asyncio.current_task():pending.cancel()
            await asyncio.sleep(.03)
            assert not task.done(),'scheduler returned before actual producer finished'
            assert [r['state']for r in rows()]==['leased','leased']
            assert len(jobs())==1 and sum(len(v)for v in redis.lists.values())==1
        finally:
            release_receipt.set()
            await asyncio.gather(task,return_exceptions=True)
        assert task.cancelled()
        assert [r['state']for r in rows()]==['acknowledged','pending']
        assert {r['dispatch_id']:r['job_id']for r in rows()}=={
            item['dispatch_id']:item['dispatch_job_id']for item in items}
    asyncio.run(scenario())
    monkeypatch.setattr(q,'enqueue_once',once)
    monkeypatch.setattr(service,'claim_due_watchlist_items',original_claim)
    assert len(tick(q)['queued'])==1;assert_complete(redis)
    assert {j['job_id']for j in jobs()}=={item['dispatch_job_id']for item in items}
