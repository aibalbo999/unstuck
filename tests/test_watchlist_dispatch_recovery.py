"""Real SQLite + installed RQ, Redis I/O simulated; no live analysis."""
from datetime import datetime,timedelta
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor
import threading
import pytest
from redis.exceptions import WatchError, RedisError
from rq import Queue
import job_store,watchlist_store,watchlist_service,watchlist_dispatch_store
from task_queue import RQTaskQueue
NOW=datetime(2026,10,7,16,0,tzinfo=watchlist_service.TAIPEI)
def noop(*args):return 'isolated test only'
def _bytes(v):return v if isinstance(v,bytes) else v.encode() if isinstance(v,str) else str(v).encode()
class MemoryRedis:
    def __init__(self):
        self.hashes={};self.lists={};self.sets={};self.versions={};self.lock=threading.RLock()
        self.offline=False;self.before=False;self.after=False;self.barrier=None;self.barrier_reads=0
    def pipeline(self):return MemoryPipeline(self)
    def hgetall(self,key):
        if self.offline:raise ConnectionError('isolated redis unavailable')
        with self.lock:return dict(self.hashes.get(key,{}))
    def hget(self,key,field):return self.hgetall(key).get(_bytes(field))
    def exists(self,key):return bool(self.hgetall(key))
    def info(self,*a,**kw):return {'redis_version':'7.2.0'}
    def lpos(self,key,value):
        with self.lock:
            values=self.lists.get(key,[])
            return values.index(_bytes(value)) if _bytes(value) in values else None
    def snapshot(self):return (self.hashes,self.lists,self.sets,self.versions)
    def load(self,snapshot):self.hashes,self.lists,self.sets,self.versions=snapshot
class MemoryPipeline:
    def __init__(self,redis):self.redis=redis;self.watched={};self.commands=[];self.transaction=False
    def __enter__(self):
        if self.redis.offline:raise ConnectionError('isolated redis unavailable')
        return self
    def __exit__(self,*args):self.commands.clear();return False
    def watch(self,key):
        with self.redis.lock:self.watched[key]=self.redis.versions.get(key,0)
    def exists(self,key):
        result=self.redis.exists(key)
        with self.redis.lock:
            barrier=self.redis.barrier is not None and self.redis.barrier_reads<2
            if barrier:self.redis.barrier_reads+=1
        if barrier:self.redis.barrier.wait(timeout=5)
        return result
    def hgetall(self,key):return self.redis.hgetall(key)
    def hget(self,key,field):return self.redis.hget(key,field)
    def multi(self):
        if self.transaction:raise RedisError("Cannot issue nested calls to MULTI")
        self.transaction=True
    def _command(self,name,*args,**kwargs):
        assert self.transaction
        self.commands.append((name,args,kwargs));return self
    def hset(self,*a,**kw):return self._command('hset',*a,**kw)
    def sadd(self,*a,**kw):return self._command('sadd',*a,**kw)
    def rpush(self,*a,**kw):return self._command('rpush',*a,**kw)
    def lpush(self,*a,**kw):return self._command('lpush',*a,**kw)
    def persist(self,*a,**kw):return self._command('persist',*a,**kw)
    def expire(self,*a,**kw):return self._command('expire',*a,**kw)
    def execute(self):
        r=self.redis
        with r.lock:
            if r.offline or r.before:raise ConnectionError('isolated failure before EXEC')
            if any(r.versions.get(k,0)!=v for k,v in self.watched.items()):raise WatchError('isolated watched key changed')
            for name,args,kw in self.commands:
                key=args[0]
                if name=='hset':
                    mapping=kw.get('mapping') or {args[1]:args[2]}
                    r.hashes.setdefault(key,{}).update({_bytes(k):_bytes(v) for k,v in mapping.items()});r.versions[key]=r.versions.get(key,0)+1
                elif name=='sadd':r.sets.setdefault(key,set()).update(_bytes(v) for v in args[1:])
                elif name in ('rpush','lpush'):
                    values=[_bytes(v) for v in args[1:]];lst=r.lists.setdefault(key,[])
                    if name=='rpush':lst.extend(values)
                    else:lst[:0]=list(reversed(values))
            self.commands.clear()
            if r.after:raise ConnectionError('isolated EXEC reply lost after commit')
            return []
def queue(redis):
    q=Queue('watchlist',connection=redis);q.get_redis_server_version=lambda:(7,2,0)
    return RQTaskQueue(redis_client=redis,queue=q)
@pytest.fixture
def environment(monkeypatch,tmp_path):
    monkeypatch.setattr(watchlist_service,'WATCHLIST_PATH',tmp_path/'watchlist.json');watchlist_service.reset_watchlist_store_for_tests()
    monkeypatch.setattr(job_store,'TASK_DB_PATH',str(tmp_path/'jobs.sqlite3'));job_store.reset_job_store_for_tests()
    monkeypatch.setattr(watchlist_service.time,'sleep',lambda _:None)
    for t in ('2308.TW','3324.TWO'):watchlist_service.upsert_watchlist_item({'ticker':t,'pipeline':'v4','enabled':True,'schedule_slots':['post_market']})
    return tmp_path
def tick(q,now=NOW):
    items=watchlist_service.claim_due_watchlist_items(now)
    return watchlist_service.enqueue_watchlist_items(items,create_job=job_store.create_job,find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop)
def rows():
    with watchlist_store._connect() as c:return [dict(r) for r in c.execute('select * from watchlist_dispatches order by ticker')]
def jobs():
    with job_store._connect() as c:return [dict(r) for r in c.execute('select * from analysis_jobs order by ticker')]
def assert_complete(redis,count=2):
    assert len(jobs())==count
    assert len(rows())==count and all(r['state']=='acknowledged' for r in rows())
    assert sum(len(v) for v in redis.lists.values())==count
    assert all(i['last_run_dates']['post_market']=='2026-10-07' for i in watchlist_service.list_watchlist()['items'])
@pytest.mark.parametrize('failure',['offline','before','after'])
def test_all_failures_then_recovery_and_duplicate_ticks(environment,failure):
    redis=MemoryRedis();q=queue(redis);setattr(redis,failure,True);first=tick(q)
    assert len(first['errors'])==2 and not first['success'] and not first['queued']
    assert len(jobs())==2 and all(r['state']=='pending' for r in rows())
    assert all(i['last_run_dates']=={} for i in watchlist_service.list_watchlist()['items'])
    ids={j['job_id'] for j in jobs()};setattr(redis,failure,False);second=tick(q)
    assert second['success'],second
    assert_complete(redis);assert {j['job_id'] for j in jobs()}==ids
    assert tick(q)['queued']==[];assert_complete(redis)
def test_partial_success_only_retries_failed_item(environment,monkeypatch):
    redis=MemoryRedis();q=queue(redis);once=q.enqueue_once
    def fail_one(task,fn,*args,**kw):
        if args[1]=='3324.TWO':raise ConnectionError('isolated one-item failure')
        return once(task,fn,*args,**kw)
    monkeypatch.setattr(q,'enqueue_once',fail_one);first=tick(q)
    assert len(first['queued'])==1 and len(first['errors'])==1,first
    assert [r['state'] for r in rows()]==['acknowledged','pending']
    monkeypatch.setattr(q,'enqueue_once',once);second=tick(q)
    assert len(second['queued'])==1 and second['queued'][0]['ticker']=='3324.TWO';assert_complete(redis)
def test_expired_owner_cannot_ack_or_release_new_owner(environment):
    old=watchlist_service.claim_due_watchlist_items(NOW);assert watchlist_service.claim_due_watchlist_items(NOW)==[]
    new=watchlist_service.claim_due_watchlist_items(NOW+timedelta(seconds=watchlist_dispatch_store.LEASE_SECONDS+1))
    assert [i['dispatch_id'] for i in new]==[i['dispatch_id'] for i in old]
    assert not watchlist_dispatch_store.renew(old[0]);assert not watchlist_dispatch_store.acknowledge(old[0],'old','invalid')
    watchlist_dispatch_store.release(old[0],'old');assert rows()[0]['lease_token']==new[0]['dispatch_token']
def test_two_workers_atomic_claim(environment):
    barrier=threading.Barrier(2)
    def claim(_):barrier.wait(timeout=5);return watchlist_service.claim_due_watchlist_items(NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:a,b=list(pool.map(claim,range(2)))
    assert sorted([len(a),len(b)])==[0,2]
    assert len({i['dispatch_id'] for i in a+b})==2
def test_two_producers_installed_rq_watch_transaction(environment):
    redis=MemoryRedis();redis.barrier=threading.Barrier(2);q=queue(redis)
    def enqueue(_):return q.enqueue_once('analysis:isolated-race',noop,'isolated-race','2308.TW','v4',queue_name='watchlist')
    with ThreadPoolExecutor(max_workers=2) as pool:a,b=list(pool.map(enqueue,range(2)))
    assert sorted([a['created'],b['created']])==[False,True]
    assert redis.lists['rq:queue:watchlist']==[b'analysis:isolated-race']
def test_job_creation_is_idempotent_and_identity_safe(environment):
    a=job_store.create_job('2308.TW','v4',job_id='isolated-stable')
    assert job_store.create_job('2308.TW','v4',job_id=a)==a and len(jobs())==1
    with pytest.raises(ValueError):job_store.create_job('3324.TWO','v4',job_id=a)
    assert len(jobs())==1 and len(job_store.get_events_since(a))==1
@pytest.mark.parametrize('status',['running','waiting_retry','done','error','cancelled'])
def test_sql_execution_receipt_never_requeues(environment,status):
    item=watchlist_service.claim_due_watchlist_items(NOW)[0]
    job_store.create_job(item['ticker'],item['pipeline'],job_id=item['dispatch_job_id']);job_store.update_job(item['dispatch_job_id'],status)
    redis=MemoryRedis();result=watchlist_service.enqueue_watchlist_items([item],create_job=job_store.create_job,find_active_job=job_store.find_active_job,task_queue=queue(redis),run_stock_analysis_job=noop)
    assert result['success'] and len(result['skipped'])==1 and redis.lists=={}
    assert rows()[0]['receipt_kind']=='sql_execution_or_terminal'
def test_completed_legacy_slot_not_replayed(environment):
    watchlist_service.mark_watchlist_run('2308.TW','v4','post_market',run_date=NOW.date().isoformat())
    assert [i['ticker'] for i in watchlist_service.claim_due_watchlist_items(NOW)]==['3324.TWO']
    assert [r['ticker'] for r in rows()]==['3324.TWO']
def test_reconciliation_preserves_pending_job(environment,monkeypatch):
    import worker_main
    item=watchlist_service.claim_due_watchlist_items(NOW)[0];jid=job_store.create_job(item['ticker'],item['pipeline'],job_id=item['dispatch_job_id'])
    monkeypatch.setattr(worker_main,'_rq_job_states',lambda _: {})
    assert worker_main.reconcile_abandoned_rq_jobs(SimpleNamespace(task_queue=SimpleNamespace(queues={'q':object()})))==0
    assert job_store.get_job(jid)['status']=='queued'
    monkeypatch.setattr(worker_main,'task_queue_has_task',lambda *a:False)
    assert worker_main.find_queue_backed_active_job(object(),item['ticker'],item['pipeline'])['job_id']==jid
def test_pending_api_attach_does_not_race(environment,monkeypatch):
    import analysis_job_service as service
    item=watchlist_service.claim_due_watchlist_items(NOW)[0];jid=job_store.create_job(item['ticker'],item['pipeline'],job_id=item['dispatch_job_id'])
    monkeypatch.setattr(service,'create_or_attach_active_job',lambda *a,**kw:{'job':job_store.get_job(jid),'created':False})
    def forbidden(*a,**kw):raise AssertionError('API must leave dispatch to scheduler')
    result=service.create_or_attach_analysis_job(ticker=item['ticker'],pipeline_id=item['pipeline'],task_queue=SimpleNamespace(enqueue=forbidden),run_stock_analysis_job=noop)
    assert result['job_id']==jid and job_store.get_job(jid)['status']=='queued'

@pytest.mark.parametrize("stage",["lease","job","queue"])
def test_process_exit_recovers_without_duplicate_jobs(environment,stage):
    import os,sys,subprocess,pickle
    from pathlib import Path
    probe=Path(__file__).with_name('dispatch_process_probe.py')
    first=subprocess.run([sys.executable,str(probe),'prepare',str(environment),stage],capture_output=True,text=True,timeout=20)
    assert first.returncode==17,first.stderr
    assert len(jobs())==(0 if stage=='lease' else 1) and all(r['state']=='leased' for r in rows())
    second=subprocess.run([sys.executable,str(probe),'recover',str(environment)],capture_output=True,text=True,timeout=20)
    assert second.returncode==0,second.stderr
    redis=MemoryRedis();redis.load(pickle.loads((environment/'redis-boundary.pickle').read_bytes()))
    assert_complete(redis)
    assert sorted(r['receipt_kind'] for r in rows())==(['rq_created','rq_existing'] if stage=='queue' else ['rq_created','rq_created'])

def test_pre_post_slots_attach_verified_active_task_without_second_model_job(environment):
    watchlist_service.upsert_watchlist_item({'ticker':'2308.TW','pipeline':'v4','enabled':True,'schedule_slots':['pre_market','post_market']})
    redis=MemoryRedis();result=tick(queue(redis))
    assert result['success'], result
    assert len(jobs())==2 and len(rows())==3
    assert sum(len(v) for v in redis.lists.values())==2
    assert sum(r['receipt_kind']=='attached_active' for r in rows())==1
    assert tick(queue(redis))['queued']==[]

def test_unknown_active_task_receipt_does_not_consume_slot(environment):
    redis=MemoryRedis();q=queue(redis);items=watchlist_service.claim_due_watchlist_items(NOW)
    result=watchlist_service.enqueue_watchlist_items(items,create_job=job_store.create_job,
        find_active_job=lambda t,p:{'job_id':'unverified-active'},task_queue=q,run_stock_analysis_job=noop)
    assert len(result['errors'])==2 and len(jobs())==0
    assert all(r['state']=='pending' for r in rows())
    assert all(i['last_run_dates']=={} for i in watchlist_service.list_watchlist()['items'])

def test_completed_identity_with_different_args_is_rejected(environment):
    redis=MemoryRedis();q=queue(redis)
    q.enqueue_once('analysis:identity',noop,'identity','2308.TW','v4',queue_name='watchlist')
    with pytest.raises(ValueError):q.enqueue_once('analysis:identity',noop,'identity','3324.TWO','v4',queue_name='watchlist')
    assert redis.lists['rq:queue:watchlist']==[b'analysis:identity']

def test_two_workers_dispatch_full_chain_once(environment):
    redis=MemoryRedis();q=queue(redis);barrier=threading.Barrier(2)
    def run(_):barrier.wait(timeout=5);return tick(q)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
    assert all(r['success'] for r in results)
    assert sum(len(r['queued']) for r in results)==2
    assert_complete(redis)

def test_expired_lease_after_queue_commit_is_reconciled_once(environment):
    redis=MemoryRedis();q=queue(redis);old=watchlist_service.claim_due_watchlist_items(NOW)
    first=old[0];jid=job_store.create_job(first['ticker'],first['pipeline'],job_id=first['dispatch_job_id'])
    q.enqueue_once('analysis:'+jid,noop,jid,first['ticker'],first['pipeline'],queue_name='watchlist')
    new=watchlist_service.claim_due_watchlist_items(NOW+timedelta(seconds=601))
    result=watchlist_service.enqueue_watchlist_items(new,create_job=job_store.create_job,find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop)
    assert result['success'];assert_complete(redis)
    assert not watchlist_dispatch_store.acknowledge(first,jid,'late_old_owner')
    watchlist_dispatch_store.release(first,'late_old_owner')
    assert_complete(redis)

def test_ack_database_failure_after_queue_success_reuses_receipt(environment,monkeypatch):
    redis=MemoryRedis();q=queue(redis);ack=watchlist_dispatch_store.acknowledge
    def fail_ack(*a,**kw):raise OSError('isolated ack commit failure')
    monkeypatch.setattr(watchlist_dispatch_store,'acknowledge',fail_ack);first=tick(q)
    assert len(first['errors'])==2 and sum(len(v) for v in redis.lists.values())==2
    monkeypatch.setattr(watchlist_dispatch_store,'acknowledge',ack)
    assert tick(q)['success'];assert_complete(redis)
    assert all(r['receipt_kind']=='rq_existing' for r in rows())

def test_hash_without_queue_receipt_is_not_acknowledged_or_requeued(environment):
    redis=MemoryRedis();q=queue(redis);item=watchlist_service.claim_due_watchlist_items(NOW)[0]
    jid=job_store.create_job(item['ticker'],item['pipeline'],job_id=item['dispatch_job_id'])
    q.enqueue_once('analysis:'+jid,noop,jid,item['ticker'],item['pipeline'],queue_name='watchlist')
    redis.lists['rq:queue:watchlist'].clear()
    result=watchlist_service.enqueue_watchlist_items([item],create_job=job_store.create_job,find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop)
    assert len(result['errors'])==1 and rows()[0]['state']=='pending'
    assert redis.lists['rq:queue:watchlist']==[] and len(jobs())==1
    assert watchlist_service.list_watchlist()['items'][0]['last_run_dates']=={}
