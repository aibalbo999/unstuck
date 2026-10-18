"""Installed RQ + redis-py Redis/Pipeline state machine, transport-only fake.
No socket, live Redis, worker or model is involved.
"""
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import pytest
from redis import Redis
from redis.client import Pipeline
from redis.exceptions import ConnectionError, ResponseError, RedisError
from redis.backoff import NoBackoff
from redis.retry import Retry
from redis._parsers.encoders import Encoder
from rq import Queue
from rq.job import JobStatus
import job_store,watchlist_service,watchlist_store
from task_queue import RQTaskQueue

NOW=datetime(2026,10,8,15,30,tzinfo=watchlist_service.TAIPEI)
def noop(*args):return 'isolated transport test only'

class Server:
    def __init__(self):
        self.hashes={};self.lists={};self.sets={};self.zsets={};self.versions={}
        self.lock=threading.RLock();self.offline=False;self.fail_before_exec=False;self.lose_exec_reply=False
        self.trace=[];self.barrier=None;self.barrier_reads=0
    def apply(self,args):
        name=args[0].upper();a=args[1:];self.trace.append(name)
        if name==b'INFO':return b'redis_version:7.2.0\r\n'
        if name==b'PING':return b'PONG'
        key=a[0]
        if name==b'EXISTS':return int(key in self.hashes or key in self.lists or key in self.sets or key in self.zsets)
        if name==b'HGETALL':return [v for pair in self.hashes.get(key,{}).items() for v in pair]
        if name==b'HGET':return self.hashes.get(key,{}).get(a[1])
        if name==b'HSET':
            h=self.hashes.setdefault(key,{});n=0
            for f,v in zip(a[1::2],a[2::2]):n+=int(f not in h);h[f]=v
            self.versions[key]=self.versions.get(key,0)+1;return n
        if name==b'SADD':
            s=self.sets.setdefault(key,set());before=len(s);s.update(a[1:]);return len(s)-before
        if name==b'SMEMBERS':return list(self.sets.get(key,set()))
        if name==b'SISMEMBER':return int(a[1] in self.sets.get(key,set()))
        if name in (b'RPUSH',b'LPUSH'):
            l=self.lists.setdefault(key,[])
            if name==b'RPUSH':l.extend(a[1:])
            else:l[:0]=reversed(a[1:])
            return len(l)
        if name==b'LPOS':
            l=self.lists.get(key,[]);return l.index(a[1]) if a[1] in l else None
        if name==b'LLEN':return len(self.lists.get(key,[]))
        if name in (b'EXPIRE',b'PERSIST'):return 1
        if name==b'ZADD':
            z=self.zsets.setdefault(key,{});n=0
            for score,member in zip(a[1::2],a[2::2]):n+=int(member not in z);z[member]=float(score)
            return n
        if name==b'ZSCORE':
            score=self.zsets.get(key,{}).get(a[1]);return str(score).encode() if score is not None else None
        raise AssertionError('Unimplemented transport command: '+repr(args))

class WireConnection:
    def __init__(self,server):
        self.server=server;self.retry=Retry(NoBackoff(),0);self.encoder=Encoder('utf-8','strict',False)
        self.responses=deque();self.watched={};self.transaction=False;self.queued=[]
    def pack_commands(self,commands):return [tuple(self.encoder.encode(v) for v in command) for command in commands]
    def send_command(self,*args,**kwargs):self.send_packed_command(self.pack_commands([args]))
    def send_packed_command(self,commands,**kwargs):
        s=self.server
        if s.offline:raise ConnectionError('isolated unavailable transport')
        for args in commands:
            name=args[0].upper()
            with s.lock:
                if name==b'WATCH':
                    assert not self.transaction
                    self.watched.update({k:s.versions.get(k,0) for k in args[1:]});self.responses.append(b'OK')
                elif name==b'UNWATCH':self.watched.clear();self.responses.append(b'OK')
                elif name==b'MULTI':
                    assert not self.transaction;self.transaction=True;self.responses.append(b'OK')
                elif name==b'EXEC':
                    if s.fail_before_exec:raise ConnectionError('isolated transport loss before EXEC')
                    if any(s.versions.get(k,0)!=v for k,v in self.watched.items()):reply=None
                    else:reply=[s.apply(command) for command in self.queued]
                    self.watched.clear();self.queued.clear();self.transaction=False
                    self.responses.append(ConnectionError('isolated EXEC reply lost') if s.lose_exec_reply else reply)
                elif self.transaction:self.queued.append(args);self.responses.append(b'QUEUED')
                else:self.responses.append(s.apply(args))
            if name==b'EXISTS':
                with s.lock:
                    wait=s.barrier is not None and s.barrier_reads<2
                    if wait:s.barrier_reads+=1
                if wait:s.barrier.wait(timeout=5)
    def read_response(self,**kwargs):
        reply=self.responses.popleft()
        if isinstance(reply,Exception):raise reply
        return reply
    def disconnect(self):self.responses.clear();self.watched.clear();self.queued.clear();self.transaction=False

class TransportPool:
    def __init__(self,server):self.server=server;self.connection_kwargs={'protocol':2,'decode_responses':False,'db':15}
    def get_connection(self,*a,**kw):return WireConnection(self.server)
    def release(self,connection):connection.disconnect()
    def get_encoder(self):return Encoder('utf-8','strict',False)
    def disconnect(self,*a,**kw):pass

def make_queue(server,dependency=None):
    client=Redis(connection_pool=TransportPool(server))
    assert isinstance(client.pipeline(),Pipeline)
    if dependency is None:q=Queue('watchlist',connection=client)
    else:
        class DependencyQueue(Queue):
            def enqueue_call(self,**kwargs):return super().enqueue_call(depends_on=dependency,**kwargs)
        q=DependencyQueue('watchlist',connection=client)
    return RQTaskQueue(redis_client=client,queue=q)

@pytest.fixture
def environment(monkeypatch,tmp_path):
    monkeypatch.setattr(watchlist_service,'WATCHLIST_PATH',tmp_path/'watchlist.json');watchlist_service.reset_watchlist_store_for_tests()
    monkeypatch.setattr(job_store,'TASK_DB_PATH',str(tmp_path/'jobs.sqlite3'));job_store.reset_job_store_for_tests()
    monkeypatch.setattr(watchlist_service.time,'sleep',lambda _:None)
    for t in ('1101.TW','1216.TW'):watchlist_service.upsert_watchlist_item({'ticker':t,'pipeline':'v4','enabled':True,'schedule_slots':['post_market']})

def tick(q):return watchlist_service.enqueue_watchlist_items(watchlist_service.claim_due_watchlist_items(NOW),create_job=job_store.create_job,find_active_job=job_store.find_active_job,task_queue=q,run_stock_analysis_job=noop)
def records():
    with watchlist_store._connect() as c:return [dict(r) for r in c.execute('select * from watchlist_dispatches order by ticker')]

def test_native_pipeline_rejects_nested_multi_without_network():
    client=Redis(connection_pool=TransportPool(Server()));p=client.pipeline()
    with p:
        p.watch('isolated');p.multi()
        with pytest.raises(RedisError,match='nested calls to MULTI'):p.multi()

def test_no_dependency_real_client_transactions_and_duplicate_enqueue():
    s=Server();q=make_queue(s)
    first=q.enqueue_once('analysis:one',noop,'one','1101.TW','v4',queue_name='watchlist')
    second=q.enqueue_once('analysis:one',noop,'one','1101.TW','v4',queue_name='watchlist')
    assert first['created'] and not second['created']
    assert s.lists[b'rq:queue:watchlist']==[b'analysis:one']

@pytest.mark.parametrize('complete',[False,True])
def test_dependency_watches_before_native_multi_and_defers_or_enqueues(complete):
    s=Server();base=make_queue(s);parent=base.queue.enqueue_call(func=noop,args=('parent',),job_id='parent')
    if complete:parent.set_status(JobStatus.FINISHED)
    q=make_queue(s,parent);r=q.enqueue_once('child',noop,'child',queue_name='watchlist')
    assert r['created'];job=q.queue.fetch_job('child')
    assert job.get_status()==('queued' if complete else 'deferred')
    assert s.lists[b'rq:queue:watchlist'].count(b'child')==int(complete)
    assert not q.enqueue_once('child',noop,'child',queue_name='watchlist')['created']

@pytest.mark.parametrize('failure',['offline','fail_before_exec'])
def test_real_client_interruption_then_same_id_recovery(environment,failure):
    s=Server();q=make_queue(s);setattr(s,failure,True);a=tick(q)
    assert len(a['errors'])==2 and all(r['state']=='pending' for r in records())
    ids=[r['job_id'] for r in records()];setattr(s,failure,False);b=tick(q)
    assert b['success'];assert [r['job_id'] for r in records()]==ids
    assert all(r['state']=='acknowledged' for r in records())
    assert len(s.lists[b'rq:queue:watchlist'])==2 and tick(q)['queued']==[]

def test_native_exec_reply_loss_reconciles_committed_task_once(environment):
    s=Server();s.lose_exec_reply=True;q=make_queue(s);r=tick(q)
    assert r['success'],r
    assert all(d['state']=='acknowledged' for d in records())
    assert len(s.lists[b'rq:queue:watchlist'])==2
    assert all(d['receipt_kind']=='rq_existing' for d in records())

def test_partial_success_real_client_only_recovers_failed_item(environment,monkeypatch):
    s=Server();q=make_queue(s);once=q.enqueue_once
    def failure(task,fn,*args,**kwargs):
        if args[1]=='1216.TW':s.offline=True
        try:return once(task,fn,*args,**kwargs)
        finally:s.offline=False
    monkeypatch.setattr(q,'enqueue_once',failure);a=tick(q)
    assert len(a['queued'])==1 and len(a['errors'])==1
    monkeypatch.setattr(q,'enqueue_once',once);b=tick(q)
    assert len(b['queued'])==1 and len(s.lists[b'rq:queue:watchlist'])==2

def test_native_watch_conflict_two_producers_enqueue_one_task():
    s=Server();s.barrier=threading.Barrier(2);q=make_queue(s)
    def run(_):return q.enqueue_once('race',noop,'race',queue_name='watchlist')
    with ThreadPoolExecutor(max_workers=2) as pool:a,b=list(pool.map(run,range(2)))
    assert sorted([a['created'],b['created']])==[False,True]
    assert s.lists[b'rq:queue:watchlist']==[b'race']
