from copy import deepcopy
from datetime import datetime,timezone
import pytest
from deployment_rq_pause import OwnedRqPause,PauseError,compare,KEY

def h(s):return s.encode().hex()

def pair():
    job={h('data'):h('immutable-pickle'),h('meta'):h('immutable-meta'),h('retries_left'):h('4'),h('origin'):h('watchlist'),h('status'):h('scheduled')}
    def item(kind,value):return {'type':kind,'value':value,'pttl':-1}
    b={'schema':1,'server_time':1000.,'keys':{'rq:job:x':item('hash',job),'rq:scheduled:watchlist':item('zset',[[h('x'),1001.]])}}
    a=deepcopy(b);a['server_time']=1002.;a['keys'].pop('rq:scheduled:watchlist');a['keys']['rq:queue:watchlist']=item('list',[h('x')]);a['keys']['rq:queues']=item('set',[h('rq:queue:watchlist')]);a['keys']['rq:job:x']['value'].update({h('status'):h('queued'),h('enqueued_at'):h(datetime.fromtimestamp(1001.5,timezone.utc).isoformat())})
    return b,a

def test_exact_pending_job_can_move_from_due_registry_to_queue():
    b,a=pair();v=compare(b,a)
    assert v['passed']and v['promoted_job_ids']==['x']and v['exact_job_count']==1
    assert compare(b,deepcopy(b))['passed']

@pytest.mark.parametrize('field',['data','meta','retries_left','origin','timeout','started_at'])
def test_promotion_cannot_change_payload_budget_or_execution_fields(field):
    b,a=pair();a['keys']['rq:job:x']['value'][h(field)]=h('changed')
    with pytest.raises(PauseError):compare(b,a)

@pytest.mark.parametrize('case',['lost_job','new_job','queue_lost','duplicate','wrong_queue','future','wrong_status','wrong_time','expiry','new_result','missing_payload','offset_time'])
def test_other_changes_never_excused_as_promotion(case):
    b,a=pair()
    if case=='lost_job':a['keys'].pop('rq:job:x')
    if case=='new_job':a['keys']['rq:job:y']=deepcopy(a['keys']['rq:job:x'])
    if case=='queue_lost':a['keys'].pop('rq:queue:watchlist')
    if case=='duplicate':a['keys']['rq:queue:watchlist']['value']*=2
    if case=='wrong_queue':a['keys']['rq:queue:other']=a['keys'].pop('rq:queue:watchlist')
    if case=='future':b['keys']['rq:scheduled:watchlist']['value'][0][1]=2000.
    if case=='wrong_status':a['keys']['rq:job:x']['value'][h('status')]=h('finished')
    if case=='wrong_time':a['keys']['rq:job:x']['value'][h('enqueued_at')]=h('2026-01-01T00:00:00Z')
    if case=='expiry':a['keys']['rq:job:x']['pttl']=100
    if case=='missing_payload':
        b['keys']['rq:job:x']['value'].pop(h('data'));a['keys']['rq:job:x']['value'].pop(h('data'))
    if case=='offset_time':a['keys']['rq:job:x']['value'][h('enqueued_at')]=h('1970-01-01T00:16:41.500000+01:00')
    if case=='new_result':a['keys']['rq:results:x']={'type':'stream','pttl':-1,'value':[]}
    with pytest.raises(PauseError):compare(b,a)

class Client:
    def __init__(self):self.values={};self.ttl=-1
    def get(self,k):return self.values.get(k)
    def pttl(self,k):return self.ttl
    def set(self,k,v,nx=False):
        if nx and k in self.values:return None
        self.values[k]=v;return True
    def eval(self,script,n,k,v):
        if self.get(k)!=v:return 0
        del self.values[k];return 1
    def exists(self,k):return k in self.values

def test_pause_owned_no_expiry_and_no_automatic_resume():
    c=Client();p=OwnedRqPause(c);p.acquire();assert p.check()
    with pytest.raises(PauseError):OwnedRqPause(c).acquire()
    assert c.get(KEY)==p.token
    p.resume();assert not c.exists(KEY)

def test_foreign_pause_or_ttl_cannot_be_resumed():
    c=Client();p=OwnedRqPause(c);p.acquire();c.values[KEY]=b'other'
    with pytest.raises(PauseError):p.resume()
    assert c.get(KEY)==b'other'
    c.values[KEY]=p.token;c.ttl=1
    with pytest.raises(PauseError):p.resume()


def test_owned_pause_delays_background_work_until_exact_key_removed():
    import asyncio
    from deployment_rq_pause import deployment_pause_active,wait_for_deployment_resume
    c=Client();p=OwnedRqPause(c);p.acquire()
    assert deployment_pause_active(c)
    async def exercise():
        task=asyncio.create_task(wait_for_deployment_resume(c,poll_seconds=.01))
        await asyncio.sleep(.02);assert not task.done()
        p.resume();await asyncio.wait_for(task,1)
    asyncio.run(exercise())
    c.values[KEY]=b'1'
    assert not deployment_pause_active(c)
    c.values[KEY]=b'stock-agent:deployment:v1:malformed'
    with pytest.raises(PauseError):deployment_pause_active(c)


def test_application_background_roles_do_not_start_work_while_owned_pause_exists():
    import asyncio
    from types import SimpleNamespace
    import worker_main,worker_maintenance
    c=Client();p=OwnedRqPause(c);p.acquire()
    # No other runtime dependencies: touching normal work before release fails.
    runtime=SimpleNamespace(task_queue=SimpleNamespace(redis=c))
    async def exercise():
        tasks=[asyncio.create_task(worker_main.run_scheduler_process(runtime)),
               asyncio.create_task(worker_maintenance.run_maintenance_process(runtime))]
        await asyncio.sleep(.02)
        assert all(not t.done()for t in tasks)
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
    asyncio.run(exercise())
