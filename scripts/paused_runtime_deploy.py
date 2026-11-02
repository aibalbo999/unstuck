"""Execute one reviewed deployment under owned native RQ suspension.

Default is read-only plan validation. --execute requires a dedicated canonical
Redis and a bound archive executor. Any uncertain failure retains suspension;
no automatic resume, deadline expiry, task deletion, or forced process kill.
"""
from pathlib import Path
import argparse,fcntl,hashlib,json,os,sqlite3,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from deployment_rq_pause import OwnedRqPause,PauseError,snapshot,compare


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w')as f:
        json.dump(value,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
    parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(parent)
    finally:os.close(parent)
def refresh(path,value):
    if path.exists():
        previous=path.read_bytes()
        history=path.with_name(path.name+'.previous-'+str(time.time_ns())+'.json')
        fd=os.open(history,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb')as stream:
            stream.write(previous);stream.flush();os.fsync(stream.fileno())
        temporary=path.with_name(path.name+'.next-'+str(time.time_ns()))
        write(temporary,value);os.replace(temporary,path)
        parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(parent)
        finally:os.close(parent)
    else:write(path,value)

def validate(plan_path):
    archive=ROOT.parent/'stock-agent-archives';plan_path=plan_path.resolve(strict=True)
    if not plan_path.is_relative_to(archive.resolve(strict=True)):raise PauseError('External archive plan required')
    p=json.loads(plan_path.read_text());case=Path(p['case']).resolve(strict=True)
    if case!=plan_path.parent or not case.is_relative_to(archive):raise PauseError('Plan/case identity mismatch')
    if p.get('schema')!='stock-agent.paused-deployment.v1':raise PauseError('Unqualified deployment plan')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if commit!=p['expected_commit']or subprocess.check_output(['git','rev-parse','origin/main'],cwd=ROOT,text=True).strip()!=commit:raise PauseError('Expected pushed revision missing')
    if subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).strip():raise PauseError('Tracked worktree changed')
    for name,digest in p['reviewed_scripts'].items():
        path=case/name
        if path.resolve(strict=True)!=path or path.parent!=case or sha(path)!=digest:raise PauseError('Reviewed script drift')
    if p['entrypoint']not in p['reviewed_scripts']or not p['entrypoint'].endswith('.py'):raise PauseError('Unreviewed executor')
    result=case/p['result_file']
    if result.parent!=case or result.name!=p['result_file']or not result.name.endswith('.json'):raise PauseError('Preservation result must remain in case')
    if not isinstance(p['queue_names'],list)or len(set(p['queue_names']))!=len(p['queue_names'])or not p['queue_names']:raise PauseError('Explicit queue scope required')
    return p,case

def workers(client,queues,*,drained=False,allow_absent=False):
    from rq import Worker
    rows=[]
    for w in Worker.all(connection=client):
        if not set(w.queue_names())<=set(queues):raise PauseError('Foreign RQ worker scope')
        if w.pid is None or subprocess.check_output(['lsof','-a','-p',str(w.pid),'-d','cwd','-Fn'],text=True).splitlines()[-1]!='n'+str(ROOT/'backend'):raise PauseError('Worker cwd identity unverified')
        row={'pid':w.pid,'state':w.get_state(),'job':w.get_current_job_id(),'queues':w.queue_names()}
        if drained and(row['state']!='suspended'or row['job']is not None):raise PauseError('Native worker not yet suspended')
        rows.append(row)
    if len(rows)!=1 and not(allow_absent and not rows):raise PauseError('Expected one canonical worker')
    return rows

def no_active_jobs():
    with sqlite3.connect((ROOT/'backend/cache/operational.sqlite3').as_uri()+'?mode=ro',uri=True)as db:
        rows=db.execute("SELECT job_id FROM analysis_jobs WHERE status NOT IN ('done','error','cancelled','waiting_retry','queued')").fetchall()
    if rows:raise PauseError('Running SQL jobs have not drained')

def stable_snapshot(client,pause):
    for attempt in range(3):
        try:return snapshot(client,pause)
        except PauseError as e:
            if 'key set changed'not in str(e)or attempt==2:raise
            time.sleep(.2)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--execute',action='store_true');ap.add_argument('--recover-paused',action='store_true');args=ap.parse_args();plan,case=validate(args.plan)
    if args.recover_paused and not args.execute:raise PauseError('Recovery also requires explicit --execute')
    if not args.execute:print(json.dumps({'plan':'validated','formal_actions':False,'commit':plan['expected_commit']}));return
    import redis,requests
    archive=ROOT.parent/'stock-agent-archives'
    with(archive/'shared-runtime-release.lock').open('a+')as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        client=redis.Redis.from_url('redis://127.0.0.1:6379/0',socket_timeout=3,socket_connect_timeout=3)
        info=client.info('server');config=client.config_get('dir')
        if Path(config['dir']).resolve()!=ROOT/'backend/cache/redis':raise PauseError('Redis storage not dedicated to this project')
        if subprocess.check_output(['ps','-p',str(info['process_id']),'-o','ppid='],text=True).strip()!='1':raise PauseError('Independent persistent Redis required')
        if not {k.decode().removeprefix('rq:queue:')for k in client.smembers('rq:queues')}<=set(plan['queue_names']):raise PauseError('Unexpected Redis queue scope')
        listener=subprocess.run(['lsof','-t','-iTCP:8080','-sTCP:LISTEN'],capture_output=True)
        recovery_absent=(args.recover_paused and(case/'shutdown-started.json').exists()
            and listener.returncode==1 and not listener.stdout.strip())
        before_workers=workers(client,plan['queue_names'],allow_absent=recovery_absent)
        previous=json.loads((case/'pause-intent.json').read_text())if args.recover_paused else None
        if previous and(previous['redis']!={k:info[k]for k in('run_id','process_id')}or previous['commit']!=plan['expected_commit']):raise PauseError('Recovery Redis/revision identity changed')
        pause=OwnedRqPause(client,bytes.fromhex(previous['token_hex'])if previous else None)
        intent={'at':time.time(),'pid':os.getpid(),'token_hex':pause.token.hex(),'redis':{k:info[k]for k in('run_id','process_id')},'workers':before_workers,'commit':plan['expected_commit'],'authorized':'Human explicitly requested execute reviewed pause/drain/deploy/verify/resume workflow'}
        write(case/('pause-recovery-'+str(time.time_ns())+'.json'if previous else'pause-intent.json'),intent)
        refresh(case/'lock-holder.json',{'pid':os.getpid(),'kernel_flock_held':True,'resource':str(archive/'shared-runtime-release.lock')})
        # Do not catch-and-resume. Once acquired, errors remain explicitly paused.
        if previous:pause.check()
        else:
            pause.acquire();write(case/'pause-acquired.json',{'at':time.time(),'owned':True,'no_expiry':True})
        print('Native RQ pause acquired; waiting for existing job to finish',flush=True)
        until=time.monotonic()+1800;last=0
        while True:
            pause.check()
            try:
                ws=workers(client,plan['queue_names'],drained=True,allow_absent=recovery_absent);no_active_jobs()
                if any(client.zcard(k)for k in client.scan_iter('rq:wip:*')):raise PauseError('Started work remains')
                break
            except PauseError:
                if time.monotonic()>=until:raise PauseError('Drain incomplete; pause retained')
                if time.monotonic()-last>30:print('Waiting for the same native job/worker drain',flush=True);last=time.monotonic()
                time.sleep(1)
        baseline=json.loads((case/'paused-rq-before.json').read_text())if previous and(case/'paused-rq-before.json').exists()else stable_snapshot(client,pause)
        if not(case/'paused-rq-before.json').exists():write(case/'paused-rq-before.json',baseline)
        compare(baseline,stable_snapshot(client,pause))
        refresh(case/'pause-drained.json',{'at':time.time(),'workers':ws})
        refresh(case/'pause-context.json',{'token_hex':pause.token.hex(),'controller_pid':os.getpid(),'redis_identity':intent['redis']})
        validate(args.plan)
        execution_env=dict(os.environ,STOCK_AGENT_DEPLOY_PLAN_PATH=str(args.plan.resolve()))
        subprocess.run([sys.executable,'-B',str(case/plan['entrypoint'])],cwd=ROOT,env=execution_env,check=True)
        pause.check();validate(args.plan)
        result=json.loads((case/plan['result_file']).read_text())
        if result.get('passed')is not True or result.get('merge_commit')!=plan['expected_commit']:raise PauseError('Full preservation not verified; pause retained')
        http=requests.Session();http.trust_env=False
        for route in('/healthz','/readyz'):
            if http.get('http://127.0.0.1:8080'+route,timeout=10).status_code!=200:raise PauseError('Runtime not healthy; pause retained')
        identity=http.get('http://127.0.0.1:8080/api/runtime-identity',timeout=10).json()
        if identity.get('commit')!=plan['expected_commit']:raise PauseError('Wrong runtime revision')
        no_active_jobs();ws=workers(client,plan['queue_names'],drained=True)
        after=stable_snapshot(client,pause);proof=compare(baseline,after);write(case/'paused-rq-after.json',after);write(case/'paused-rq-preservation.json',proof)
        write(case/'resume-verified.json',{'at':time.time(),'workers':ws,'runtime':identity,'full_preservation':True,'rq_preservation':proof})
        pause.resume();write(case/'resumed.json',{'at':time.time(),'owned_suspend_key_removed':True,'no_task_enqueued_or_deleted_by_controller':True})
        write(case/'lock-released.json',{'at':time.time(),'pid':os.getpid(),'kernel_flock_released_on_context_exit':True})
        print(json.dumps({'status':'deployed_verified_resumed','commit':plan['expected_commit'],'preservation':True}),flush=True)

if __name__=='__main__':main()
