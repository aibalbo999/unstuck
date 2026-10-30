import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
from pathlib import Path

import pytest
from api_routes import maintenance_verify as maintenance


@pytest.fixture
def root(tmp_path):
    for name in maintenance.IDENTITY_FILES:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(name)
    return tmp_path


@asynccontextmanager
async def running(app):
    incoming=asyncio.Queue();started=asyncio.Event();messages=[]
    async def send(event):
        messages.append(event)
        if event['type'].startswith('lifespan.startup'):started.set()
    task=asyncio.create_task(app({'type':'lifespan'},incoming.get,send))
    await incoming.put({'type':'lifespan.startup'});await asyncio.wait_for(started.wait(),1)
    try:
        yield incoming,messages,task
    finally:
        await incoming.put({'type':'lifespan.shutdown'});await asyncio.wait_for(task,1)


async def request(app,path='/healthz',method='GET',**changes):
    messages=[]
    async def send(message):messages.append(message)
    async def receive():raise AssertionError('No body or downstream work is required')
    scope={'type':'http','method':method,'path':path,'raw_path':path.encode(),'query_string':b'','root_path':''}
    scope.update(changes)
    await app(scope,receive,send)
    return messages[0]['status'],json.loads(messages[1]['body']),dict(messages[0]['headers'])


@pytest.mark.parametrize('path',sorted(maintenance.ALLOWED_PATHS))
def test_only_passive_health_and_frozen_source_identity_are_available(root,path):
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app):
            status,payload,headers=await request(app,path)
            assert status==200 and payload['mode']=='maintenance_verification'
            assert headers[b'cache-control']==b'no-store'
            if path=='/api/runtime-identity':
                assert payload['production_runtime_loaded'] is False
                assert payload['identity_basis']=='source_files_at_maintenance_startup'
                assert payload['files']['start_mac.command']['sha256']==hashlib.sha256(b'start_mac.command').hexdigest()
            else:assert payload['production_ready'] is False
            if path=='/readyz':assert payload['operational_checks_performed'] is False
    asyncio.run(scenario())


@pytest.mark.parametrize('method',['GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS','get'])
@pytest.mark.parametrize('path',['/','/static/index.html','/api/reports','/api/watchlist/daily-dashboard','/api/performance/stats','/api/stock/2330.TW','/api/analyze','/metrics','/docs','/openapi.json'])
def test_every_other_entry_is_closed_without_echo_or_dispatch(root,path,method):
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app):
            status,payload,_=await request(app,path,method)
            assert status==503 and payload['production_ready'] is False
            assert path not in str(payload)
    asyncio.run(scenario())


def test_startup_requests_and_shutdown_have_no_external_or_write_operations(root,monkeypatch):
    import builtins,os,socket,sqlite3,subprocess,threading
    import multiprocessing.process
    events=[];reads=[]
    original_open=Path.open;original_import=builtins.__import__
    def denied(*args,**kwargs):events.append('forbidden operation');raise AssertionError(events[-1])
    def read_only(path,mode='r',*args,**kwargs):
        assert mode=='rb' and str(path.relative_to(root)) in maintenance.IDENTITY_FILES
        reads.append(str(path.relative_to(root)))
        return original_open(path,mode,*args,**kwargs)
    def imports(name,*args,**kwargs):
        assert name not in {'api','config','settings','redis','sqlite3','subprocess'} and not name.startswith(('data_fetch','worker_'))
        return original_import(name,*args,**kwargs)
    async def scenario():
        with monkeypatch.context() as m:
            m.setattr(Path,'open',read_only)
            m.setattr(builtins,'__import__',imports)
            m.setattr(socket.socket,'connect',denied);m.setattr(socket.socket,'bind',denied)
            m.setattr(sqlite3,'connect',denied);m.setattr(subprocess,'Popen',denied)
            m.setattr(threading.Thread,'start',denied);m.setattr(multiprocessing.process.BaseProcess,'start',denied)
            m.setattr(os,'kill',denied);m.setattr(os,'mkdir',denied);m.setattr(os,'unlink',denied)
            app=maintenance.MaintenanceApplication(root)
            async with running(app):
                for path in [*maintenance.ALLOWED_PATHS,'/api/watchlist/daily-dashboard','/api/analyze','/static/index.html']:
                    await request(app,path)
            assert (await request(app))[0]==503
    asyncio.run(scenario())
    assert events==[] and sorted(reads)==sorted(maintenance.IDENTITY_FILES)


@pytest.mark.parametrize('path',sorted(maintenance.ALLOWED_PATHS))
@pytest.mark.parametrize('changes',[{'method':'POST'},{'method':'HEAD'},{'method':'OPTIONS'},{'query_string':b'x=secret'},{'root_path':'/other'},{'raw_path':b'/%68ealthz'},{'raw_path':None}])
def test_allowed_names_cannot_bypass_method_or_canonical_path_boundary(root,path,changes):
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app):assert (await request(app,path,**changes))[0]==503
    asyncio.run(scenario())


def test_websocket_is_never_accepted(root):
    async def scenario():
        app=maintenance.MaintenanceApplication(root);events=[]
        async def send(v):events.append(v)
        async def receive():raise AssertionError('No receive allowed')
        await app({'type':'websocket','path':'/healthz'},receive,send)
        assert events==[{'type':'websocket.close','code':1008}]
    asyncio.run(scenario())


def test_before_start_after_shutdown_and_repeated_start_remain_closed(root):
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        assert (await request(app))[0]==503
        async with running(app):assert (await request(app))[0]==200
        assert (await request(app))[0]==503
        async with running(app) as (_,messages,_):
            assert messages[0]['type']=='lifespan.startup.failed'
            assert (await request(app))[0]==503
    asyncio.run(scenario())


def test_duplicate_startup_fails_without_new_snapshot_or_cleanup(root,monkeypatch):
    calls=[];original=maintenance.capture_identity
    monkeypatch.setattr(maintenance,'capture_identity',lambda root:(calls.append(1),original(root))[1])
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app) as (incoming,messages,task):
            await incoming.put({'type':'lifespan.startup'});await task
            assert messages[-1]['type']=='lifespan.startup.failed'
            assert calls==[1] and (await request(app))[0]==503
    asyncio.run(scenario())


def test_identity_is_startup_snapshot_and_requests_do_not_reread(root,monkeypatch):
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app):
            original=(await request(app,'/api/runtime-identity'))[1]
            (root/'start_mac.command').write_text('subsequent change')
            monkeypatch.setattr(Path,'read_bytes',lambda self:(_ for _ in ()).throw(AssertionError('request file read')))
            assert (await request(app,'/api/runtime-identity'))[1]==original
    asyncio.run(scenario())


@pytest.mark.parametrize('kind',['missing','outside_symlink','file_symlink'])
def test_missing_or_unsafe_identity_never_claims_ready(root,tmp_path,kind):
    p=root/'start_mac.command';p.unlink()
    if kind!='missing':
        target=tmp_path/'other';target.write_text('never read')
        p.symlink_to(target if kind=='file_symlink' else '/not/read/production/database')
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app):
            status,payload,_=await request(app,'/readyz');assert status==503 and payload['status']=='not_ready'
            assert (await request(app,'/healthz'))[0]==200
            result=(await request(app,'/api/runtime-identity'))[1]['files']['start_mac.command']
            assert 'sha256' not in result
    asyncio.run(scenario())


def test_startup_error_is_closed_and_shutdown_does_not_recover_it(root,monkeypatch):
    def fail(root):raise RuntimeError('secret failure detail')
    monkeypatch.setattr(maintenance,'capture_identity',fail)
    async def scenario():
        app=maintenance.MaintenanceApplication(root)
        async with running(app) as (_,messages,_):
            assert messages[0]['type']=='lifespan.startup.failed'
            assert 'secret' not in str(messages)
            assert (await request(app))[0]==503
    asyncio.run(scenario())
