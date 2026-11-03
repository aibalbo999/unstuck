"""Owned native RQ suspension and exact preservation of pending work.

No automatic resume or TTL: an uncertain controller outcome leaves RQ paused.
This is an operational deployment primitive, not canary/maintenance-arm authority.
"""
from __future__ import annotations
import os,re,time,uuid
from datetime import datetime,timezone,timedelta

KEY=b'rq:suspended'
_PREFIX=b'stock-agent:deployment:v1:'
_RESUME="if redis.call('GET',KEYS[1])==ARGV[1] then return redis.call('DEL',KEYS[1]) else return 0 end"

class PauseError(RuntimeError):pass

class OwnedRqPause:
    def __init__(self,client,token=None):
        self.client=client;self.pid=os.getpid()
        self.token=token or (_PREFIX+uuid.uuid4().hex.encode())
        if not isinstance(self.token,bytes)or not re.fullmatch(_PREFIX+rb'[0-9a-f]{32}',self.token):raise PauseError('Invalid pause identity')
    def check(self):
        if self.pid!=os.getpid()or self.client.get(KEY)!=self.token:raise PauseError('Pause ownership missing or changed')
        if self.client.pttl(KEY)!=-1:raise PauseError('Pause must not expire during deployment')
        return True
    def acquire(self):
        # Unknown result is never retried or compensated. Save token intent first.
        if self.client.set(KEY,self.token,nx=True)is not True:raise PauseError('Existing suspension preserved')
        self.check()
    def resume(self):
        self.check()
        if self.client.eval(_RESUME,1,KEY,self.token)!=1:raise PauseError('Resume ownership changed')
        if self.client.exists(KEY):raise PauseError('Resume result ambiguous')


def _kind(key):
    if key==b'rq:queues':return 'set'
    if key.startswith(b'rq:queue:'):return 'list'
    if key.startswith((b'rq:scheduled:',b'rq:wip:',b'rq:failed:',b'rq:finished:',b'rq:deferred:',b'rq:canceled:')):return 'zset'
    if key.startswith((b'rq:results:',))or key.startswith(b'rq:job:')and key.endswith(b':results'):return 'stream'
    if key.startswith(b'rq:job:'):return 'hash'
    return None


def _encoded(kind,value):
    if kind in ('list','set'):return [x.hex()for x in (sorted(value)if kind=='set'else value)]
    if kind=='hash':return {k.hex():v.hex()for k,v in sorted(value.items())}
    if kind=='zset':return [[k.hex(),score]for k,score in value]
    if kind=='stream':return [[k.hex(),{f.hex():v.hex()for f,v in sorted(row.items())}]for k,row in value]
    raise PauseError('Unknown durable RQ type')


def snapshot(client,pause):
    """Atomic reads of all discovered durable keys; reject key-set races."""
    pause.check();keys=sorted(k for k in client.scan_iter(b'rq:*')if _kind(k))
    with client.pipeline(transaction=True)as pipe:
        pipe.time();pipe.get(KEY);pipe.pttl(KEY)
        for key in keys:
            kind=_kind(key);pipe.type(key);pipe.pttl(key)
            {'list':lambda:pipe.lrange(key,0,-1),'set':lambda:pipe.smembers(key),
             'hash':lambda:pipe.hgetall(key),'zset':lambda:pipe.zrange(key,0,-1,withscores=True),
             'stream':lambda:pipe.xrange(key)}[kind]()
        values=pipe.execute()
    stamp=values[0][0]+values[0][1]/1e6
    if values[1]!=pause.token or values[2]!=-1:raise PauseError('Pause changed during snapshot')
    if keys!=sorted(k for k in client.scan_iter(b'rq:*')if _kind(k)):raise PauseError('RQ key set changed; snapshot not accepted')
    out={}
    for i,key in enumerate(keys):
        kind,ttl,value=values[3+3*i:6+3*i]
        if kind.decode()!=_kind(key)or ttl< -1:raise PauseError('RQ type changed during snapshot')
        out[key.decode()]={'type':kind.decode(),'pttl':ttl,'value':_encoded(kind.decode(),value)}
    from deployment_terminal_expiry import capture_application_states
    return {'schema':1,'server_time':stamp,'keys':out,'application_states':capture_application_states()}


def compare(before,after):
    """Only normal due scheduled->queued promotion may alter pending jobs.

    Exact payload/meta/retries/results retained. Successful terminal caches may
    expire only with complete original bytes, native TIME/PTTL/end/retention,
    finished registry and unchanged canonical SQL done witnesses. Pending work
    never qualifies; new jobs, execution or arbitrary differences still fail.
    """
    if before.get('schema')!=1 or after.get('schema')!=1:raise PauseError('Snapshot schema mismatch')
    elapsed=after['server_time']-before['server_time']
    if not 0<=elapsed<=86400:raise PauseError('Invalid snapshot time range')
    from deployment_terminal_expiry import scoped_comparison
    before,after,expired=scoped_comparison(before,after)
    b,a=before['keys'],after['keys'];promoted={};queue_additions={};checks=[]
    def value(rows,key,kind):
        if key not in rows:return {}if kind=='hash'else []
        if rows[key]['type']!=kind:raise PauseError('Durable RQ type changed')
        return rows[key]['value']
    for key in sorted(set(b)|set(a)):
        if key.startswith('rq:scheduled:'):
            old,new=dict(value(b,key,'zset')),dict(value(a,key,'zset'))
            if any(k not in old or old[k]!=v for k,v in new.items()):raise PauseError('Scheduled work changed')
            for job,eta in old.items():
                if job not in new:
                    if eta>after['server_time'] or job in promoted:raise PauseError('Premature or duplicate promotion')
                    promoted[job]=(key.removeprefix('rq:scheduled:'),eta)
    for key in sorted(set(b)|set(a)):
        if key.startswith('rq:queue:'):
            old,new=value(b,key,'list'),value(a,key,'list')
            if new[:len(old)]!=old:raise PauseError('Queued work consumed or reordered')
            added=new[len(old):]
            for job in added:
                if job in queue_additions:raise PauseError('Duplicate queued work')
                queue_additions[job]=key.removeprefix('rq:queue:')
    if set(promoted)!=set(queue_additions)or any(queue_additions[j]!=q for j,(q,_)in promoted.items()):raise PauseError('Scheduled/queued job identities differ')
    job_keys={k for k in set(b)|set(a)if k.startswith('rq:job:')and not k.endswith(':results')}
    for rows in (b,a):
        for key,row in rows.items():
            if key.startswith(('rq:queue:','rq:scheduled:')):
                ids=row['value'] if row['type']=='list' else [v[0]for v in row['value']]
                for job in ids:
                    payload=rows.get('rq:job:'+bytes.fromhex(job).decode())
                    if not payload or not payload['value'].get(b'data'.hex()):raise PauseError('Pending work lacks retained payload')
    for key in job_keys:
        if key not in b or key not in a:raise PauseError('Durable job appeared or disappeared')
        job=key.removeprefix('rq:job:').encode().hex();old=value(b,key,'hash');new=value(a,key,'hash')
        if job not in promoted:
            if old!=new:raise PauseError('Unpromoted job changed')
        else:
            status='status'.encode().hex();enqueued='enqueued_at'.encode().hex();origin='origin'.encode().hex()
            if old.get(status)!=b'scheduled'.hex()or new.get(status)!=b'queued'.hex():raise PauseError('Invalid promotion status')
            if old.get(origin)!=new.get(origin):raise PauseError('Queue origin changed')
            if new.get(origin)!=promoted[job][0].encode().hex():raise PauseError('Wrong promoted origin')
            if {k:v for k,v in old.items()if k not in(status,enqueued)}!={k:v for k,v in new.items()if k not in(status,enqueued)}:raise PauseError('Promoted payload or retry budget changed')
            try:
                dt=datetime.fromisoformat(bytes.fromhex(new[enqueued]).decode().replace('Z','+00:00'))
                if dt.utcoffset()!=timedelta(0):raise ValueError('Native RQ enqueue time must be UTC')
                t=dt.timestamp()
            except(Exception):raise PauseError('Invalid enqueued timestamp')from None
            if not max(before['server_time']-2,promoted[job][1]-2)<=t<=after['server_time']+2:raise PauseError('Unbound enqueue time')
    for key in sorted(set(b)|set(a)):
        if key.startswith(('rq:scheduled:','rq:queue:'))or key in job_keys:continue
        old,new=b.get(key),a.get(key)
        if key=='rq:queues':
            expected=set(value(b,key,'set'))|{('rq:queue:'+q).encode().hex()for q,_ in promoted.values()}
            if set(value(a,key,'set'))!=expected:raise PauseError('Queue registry changed')
        elif (old is None)!=(new is None)or old and(old['type']!=new['type']or old['value']!=new['value']):raise PauseError('Other durable state changed')
    if any(a[k]['pttl']!=-1 for k in set(a)-set(b)):raise PauseError('New queue metadata must not expire')
    for key in set(b)&set(a):
        old,new=b[key]['pttl'],a[key]['pttl']
        if old==-1:
            if new!=-1:raise PauseError('Persistent work received an expiry')
        elif not 0<=new<=old or abs((old-new)-elapsed*1000)>3000:raise PauseError('Durable TTL changed beyond natural passage')
    return {'passed':True,'promoted_job_ids':[bytes.fromhex(k).decode()for k in promoted],
            'exact_job_count':len(job_keys),'payloads_retries_results_preserved':True,
            'expired_terminal_caches':expired}


def deployment_pause_active(client):
    """Only this owned deployment namespace delays application background work."""
    if client is None:return False
    raw=client.get(KEY)
    if raw is None:return False
    if isinstance(raw,str):raw=raw.encode()
    if not isinstance(raw,bytes):raise PauseError('Invalid suspension state')
    if not raw.startswith(_PREFIX):return False
    if not re.fullmatch(_PREFIX+rb'[0-9a-f]{32}',raw)or client.pttl(KEY)!=-1:raise PauseError('Invalid owned deployment suspension')
    return True


async def wait_for_deployment_resume(client,*,poll_seconds=.5):
    import asyncio
    while deployment_pause_active(client):
        await asyncio.sleep(poll_seconds)
