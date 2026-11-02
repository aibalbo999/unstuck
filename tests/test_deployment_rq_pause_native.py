"""Opt-in real RQ/Redis proof, exclusively through the runner's private Unix socket."""
from datetime import datetime,timedelta,timezone
import os,shutil,subprocess,sys,time
from pathlib import Path
import pytest
from deployment_rq_pause import OwnedRqPause,snapshot,compare


def wait_for(predicate,seconds=10):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        if predicate():return
        time.sleep(.05)
    raise AssertionError('Owned isolated RQ condition did not occur')


def test_native_running_job_finishes_queued_retry_survives_restart_and_resumes_once():
    path=os.environ.get('STOCK_AGENT_TEST_REDIS_SOCKET')
    if not path:pytest.skip('Use --isolated-rq; TCP and formal Redis remain prohibited')
    server=shutil.which('redis-server')
    if not server:pytest.skip('Isolated native Redis binary unavailable')
    import redis
    from rq import Queue,Worker
    from rq.job import Job
    from rq.scheduler import RQScheduler
    from rq.suspension import is_suspended
    root=Path(path).parent;processes=[]
    env=dict(os.environ);env.pop('REDIS_URL',None)
    with (root/'redis.log').open('wb')as log:
        server_process=subprocess.Popen([server,'--port','0','--unixsocket','rq.sock','--unixsocketperm','700',
            '--save','','--appendonly','no','--dir',str(root)],stdout=log,stderr=subprocess.STDOUT,env=env,cwd=root)
    client=redis.Redis(unix_socket_path=path,socket_timeout=2)
    try:
        wait_for(lambda:Path(path).exists())
        assert client.ping()
        q=Queue('deployment-fixture',connection=client)
        q.enqueue(time.sleep,2.,job_id='deployment-first',result_ttl=600)
        q.enqueue_at(datetime.now(timezone.utc)+timedelta(seconds=5),time.sleep,.01,job_id='deployment-second',result_ttl=600)
        def worker(name,max_jobs=None):
            code='import redis; from rq import Queue,SimpleWorker; c=redis.Redis(unix_socket_path='+repr(path)+'); w=SimpleWorker([Queue("deployment-fixture",connection=c)],connection=c,name='+repr(name)+'); w.work(with_scheduler=False,max_idle_time=30,max_jobs='+repr(max_jobs)+',logging_level="ERROR")'
            with (root/(name+'.log')).open('wb')as log:p=subprocess.Popen([sys.executable,'-B','-c',code],stdout=log,stderr=subprocess.STDOUT,env=env)
            processes.append(p);return p
        first=worker('deployment-native-first')
        def state(name):
            w=Worker.find_by_key('rq:worker:'+name,connection=client)
            return w.get_state()if w else None
        wait_for(lambda:state('deployment-native-first')=='busy')
        pause=OwnedRqPause(client);pause.acquire();assert is_suspended(client)
        wait_for(lambda:state('deployment-native-first')=='suspended')
        assert Job.fetch('deployment-first',connection=client).get_status()=='finished'
        before=snapshot(client,pause)
        wait_for(lambda:time.time()>q.scheduled_job_registry.get_scheduled_time('deployment-second').timestamp())
        scheduler=RQScheduler([q],connection=client);scheduler.acquire_locks();scheduler.enqueue_scheduled_jobs();scheduler.release_locks()
        moved=snapshot(client,pause);proof=compare(before,moved)
        assert proof['promoted_job_ids']==['deployment-second']
        assert q.job_ids==['deployment-second']
        assert Job.fetch('deployment-second',connection=client).get_status()=='queued'
        first.terminate();assert first.wait(timeout=10)==0
        second=worker('deployment-native-second',1)
        wait_for(lambda:state('deployment-native-second')=='suspended')
        assert compare(moved,snapshot(client,pause))['passed']
        assert q.job_ids==['deployment-second']
        pause.resume();assert not is_suspended(client)
        assert second.wait(timeout=10)==0
        assert Job.fetch('deployment-second',connection=client).get_status()=='finished'
        assert q.job_ids==[] and q.finished_job_registry.count==2
    finally:
        for logpath in root.glob('deployment-native-*.log'):
            print(logpath.name, logpath.read_text()[-3000:])
        for p in processes:
            if p.poll()is None:p.terminate()
        for p in processes:
            if p.poll()is None:p.wait(timeout=10)
        if server_process.poll()is None:
            try:client.shutdown(nosave=True)
            except redis.exceptions.ConnectionError:pass
            server_process.wait(timeout=10)
