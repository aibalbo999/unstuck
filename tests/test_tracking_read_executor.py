"""Isolated tracking must remain bounded, fresh, and honest about invalidation."""
import asyncio
from concurrent.futures import Future
import json
import os
from pathlib import Path
import pytest
import tracking_read_executor as module
from performance_read_executor import PerformanceReadExecutor, PerformanceReadUnavailable


class Executor:
    def __init__(self):self.calls=[];self.closed=[]
    def submit(self,fn,request):
        future=Future();self.calls.append((fn,request,future));return future
    def shutdown(self,**kw):self.closed.append(kw)


def test_same_revision_shares_running_work_changed_revision_is_not_queued():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor,compute_fn=module._compute_readonly_tracking,read_name='tracking')
        request=('saved','revision1')
        a=asyncio.create_task(reader.read(request));b=asyncio.create_task(reader.read(request));await asyncio.sleep(0)
        assert len(executor.calls)==1 and executor.calls[0][0] is module._compute_readonly_tracking
        with pytest.raises(PerformanceReadUnavailable,match='tracking_reader_busy'):await reader.read(('saved','revision2'))
        assert len(executor.calls)==1
        executor.calls[0][2].set_result({'items':[1]});assert await a==await b=={'items':[1]}
        c=asyncio.create_task(reader.read(('saved','revision2')));await asyncio.sleep(0);assert len(executor.calls)==2
        executor.calls[1][2].set_result({'items':[2]});assert await c=={'items':[2]};reader.close()
    asyncio.run(scenario())


def test_worker_detects_source_change_instead_of_serving_computed_old_items(monkeypatch):
    monkeypatch.setattr(module,'_install_readonly_boundary',lambda:None)
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:module._RULES_REVISION)
    revisions=iter(['before','after'])
    monkeypatch.setattr(module,'tracking_read_revision',lambda _:next(revisions))
    monkeypatch.setattr(module.service,'list_decision_tracking',lambda *a,**kw:{'items':['old']})
    with pytest.raises(PerformanceReadUnavailable,match='tracking_sources_changed'):
        module._compute_readonly_tracking(('saved','before'))


def test_rules_change_requires_reload_before_any_projection(monkeypatch):
    monkeypatch.setattr(module,'_install_readonly_boundary',lambda:None)
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:'changed')
    monkeypatch.setattr(module.service,'list_decision_tracking',lambda *a,**kw:pytest.fail('old runtime rules used'))
    with pytest.raises(PerformanceReadUnavailable,match='tracking_rules_require_reload'):
        module._compute_readonly_tracking(('saved','before'))
    with pytest.raises(PerformanceReadUnavailable,match='tracking_rules_require_reload'):
        module._prepare_tracking_read('saved')


def test_current_sources_and_rules_are_checked_each_completed_worker_read(monkeypatch):
    monkeypatch.setattr(module,'_install_readonly_boundary',lambda:None)
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:module._RULES_REVISION)
    state={'revision':'one','verdict':'passed'}
    monkeypatch.setattr(module,'tracking_read_revision',lambda _:state['revision'])
    calls=[]
    def compute(path,*,sync_metadata):
        calls.append(sync_metadata);return {'items':[{'verdict':state['verdict']} ]}
    monkeypatch.setattr(module.service,'list_decision_tracking',compute)
    assert module._compute_readonly_tracking(('saved','one'))['items'][0]['verdict']=='passed'
    state.update(revision='two',verdict='blocked')
    assert module._compute_readonly_tracking(('saved','two'))['items'][0]['verdict']=='blocked'
    assert calls==[False,False]


def test_source_hash_detects_same_length_change_even_with_restored_mtime(monkeypatch,tmp_path):
    filename='1301_TW_v4_report_20261002_090000.html';data=tmp_path/filename.replace('.html','.data.json');data.write_text('{"revision":1}')
    stat=data.stat();row={'filename':filename,'ticker':'1301.TW','pipeline_id':'v4','output_dir':str(tmp_path),'data_snapshot_filename':data.name}
    items=[{'ticker':'1301.TW','enabled':True}]
    monkeypatch.setattr(module.service.decision_tracking_store,'list_items',lambda:items)
    monkeypatch.setattr(module,'query_report_metadata',lambda **kw:([row],1))
    first=module.tracking_read_revision(str(tmp_path));data.write_text('{"revision":2}');os.utime(data,ns=(stat.st_atime_ns,stat.st_mtime_ns))
    second=module.tracking_read_revision(str(tmp_path));assert first!=second
    items[0]['enabled']=False;assert module.tracking_read_revision(str(tmp_path))!=second


def test_adapter_failure_returns_no_items_and_route_marks_it_503(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.decision_tracking import DecisionTrackingRouteDeps,create_decision_tracking_router
    monkeypatch.setattr(module,'_prepare_tracking_read',lambda path:(path,'revision'))
    async def fail(request):raise PerformanceReadUnavailable('tracking_read_timeout')
    monkeypatch.setattr(module.tracking_reads,'read',fail)
    payload=asyncio.run(module.read_tracking_items('saved'))
    assert payload['reason']=='tracking_read_timeout' and 'items' not in payload
    app=FastAPI();app.include_router(create_decision_tracking_router(DecisionTrackingRouteDeps(lambda:'saved',lambda:None,lambda _:None,module.read_tracking_items)))
    with TestClient(app) as client:
        response=client.get('/api/decision-tracking');assert response.status_code==503 and 'items' not in response.json()


def test_actual_tracking_route_uses_fresh_injected_reader_each_get(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.decision_tracking import DecisionTrackingRouteDeps,create_decision_tracking_router
    calls=[]
    async def read(path):calls.append(path);return {'items':[{'revision':len(calls)}]}
    monkeypatch.setattr(module.service,'list_decision_tracking',lambda *a,**kw:pytest.fail('projection in API threads'))
    app=FastAPI();app.include_router(create_decision_tracking_router(DecisionTrackingRouteDeps(lambda:'saved',lambda:None,lambda _:None,read)))
    with TestClient(app) as client:
        assert client.get('/api/decision-tracking').json()['items'][0]['revision']==1
        assert client.get('/api/decision-tracking').json()['items'][0]['revision']==2
    assert calls==['saved','saved']


def test_tracking_timeout_and_cancellation_keep_one_live_work_item():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor,timeout_seconds=.01,compute_fn=module._compute_readonly_tracking,read_name='tracking')
        for _ in range(2):
            with pytest.raises(PerformanceReadUnavailable,match='tracking_read_timeout'):await reader.read(('saved','same'))
        assert len(executor.calls)==1 and not executor.calls[0][2].cancelled()
        caller=asyncio.create_task(reader.read(('saved','same')));await asyncio.sleep(0);caller.cancel()
        with pytest.raises(asyncio.CancelledError):await caller
        assert not executor.calls[0][2].cancelled();reader.close()
        with pytest.raises(PerformanceReadUnavailable,match='finishing_previous'):reader.open()
        executor.calls[0][2].set_result({'items':[]});reader.open();reader.close()
    asyncio.run(scenario())


def test_preparation_syncs_raw_index_before_content_revision_without_quality_projection(monkeypatch):
    calls=[]
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:module._RULES_REVISION)
    monkeypatch.setattr(module,'sync_report_metadata',lambda path:calls.append(('index',path)))
    monkeypatch.setattr(module.service,'_sync_report_metadata_once',lambda _:pytest.fail('unused report quality projection'))
    def revision(path):
        assert calls==[('index',path)]
        return 'current-content'
    monkeypatch.setattr(module,'tracking_read_revision',revision)
    assert module._prepare_tracking_read('reports')==('reports','current-content')


def test_active_preparation_is_shared_but_completed_revision_is_recomputed():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor,compute_fn=module._prepare_tracking_read,read_name='tracking_preparation')
        a=asyncio.create_task(reader.read('reports'));b=asyncio.create_task(reader.read('reports'));await asyncio.sleep(0)
        assert len(executor.calls)==1
        executor.calls[0][2].set_result(('reports','current-one'))
        assert await a==await b==('reports','current-one')
        c=asyncio.create_task(reader.read('reports'));await asyncio.sleep(0)
        assert len(executor.calls)==2
        executor.calls[1][2].set_result(('reports','current-two'));assert await c==('reports','current-two');reader.close()
    asyncio.run(scenario())


def test_preparation_worker_denies_network_and_checks_parent_rules_before_and_after(monkeypatch):
    # Record original socket methods for automatic restoration in this process.
    for owner,name in [(module.socket.socket,'connect'),(module.socket.socket,'connect_ex'),(module.socket,'create_connection'),(module.socket,'getaddrinfo')]:
        monkeypatch.setattr(owner,name,getattr(owner,name))
    rules={'value':'parent-rules'}
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:rules['value'])
    monkeypatch.setattr(module,'_prepare_tracking_read',lambda path:(path,'content'))
    assert module._compute_tracking_preparation(('reports','parent-rules'))==('reports','content')
    with pytest.raises(OSError,match='does not permit network'):module.socket.create_connection(('example.invalid',80))
    rules['value']='changed'
    with pytest.raises(PerformanceReadUnavailable,match='tracking_rules_require_reload'):
        module._compute_tracking_preparation(('reports','parent-rules'))
    rules['value']='parent-rules'
    def change_during(path):rules['value']='changed';return (path,'content')
    monkeypatch.setattr(module,'_prepare_tracking_read',change_during)
    with pytest.raises(PerformanceReadUnavailable,match='tracking_rules_require_reload'):
        module._compute_tracking_preparation(('reports','parent-rules'))


@pytest.mark.parametrize("reason", ["tracking_reader_busy", "tracking_read_timeout", "quality_sources_changed"])
def test_quality_read_exposes_unavailable_without_a_previous_result(monkeypatch, reason):
    class Reader:
        async def read(self, request):
            raise PerformanceReadUnavailable(reason)
    monkeypatch.setattr(module, "tracking_preparations", Reader())
    value = asyncio.run(module.read_quality_audit("reports"))
    assert value["read_unavailable"] and value["status"] == "unavailable"
    assert value["reason"] == reason and "items" not in value


def test_quality_worker_invalidates_source_change_and_does_not_reuse_completed_cache(monkeypatch):
    monkeypatch.setattr(module, "_install_readonly_boundary", lambda: None)
    import report_quality_audit
    monkeypatch.setattr(module, "tracking_rules_revision", lambda: module._RULES_REVISION)
    versions = iter(["one", "two"])
    monkeypatch.setattr(module, "_quality_read_revision", lambda _: next(versions))
    report_quality_audit._REPORT_QUALITY_ROWS_CACHE[('old','old')] = (0, ['stale'])
    def compute(*a, **kw):
        assert not report_quality_audit._REPORT_QUALITY_ROWS_CACHE
        return {"items": ["fresh"]}
    monkeypatch.setattr(report_quality_audit, "build_indexed_report_quality_audit", compute)
    with pytest.raises(PerformanceReadUnavailable, match="quality_sources_changed"):
        module._compute_readonly_quality(("quality_audit", "reports", "one"))


def test_quality_projection_uses_its_own_lane_and_shares_tracking_preparation(monkeypatch):
    calls=[]
    class Preparation:
        async def read(self, request):
            calls.append(('preparation', request))
            return ('reports', 'current')
    class Quality:
        async def read(self, request):
            calls.append(('quality', request))
            return {'status':'complete','source_admission':'fresh'}
    class Tracking:
        async def read(self, request):
            pytest.fail('quality occupied tracking projection lane')
    monkeypatch.setattr(module,'tracking_preparations',Preparation())
    monkeypatch.setattr(module,'quality_reads',Quality())
    monkeypatch.setattr(module,'tracking_reads',Tracking())
    assert asyncio.run(module.read_quality_audit('reports'))['status']=='complete'
    assert calls==[('preparation',('reports',module._RULES_REVISION)),
                   ('quality',('quality_audit','reports',module._RULES_REVISION,'current'))]


@pytest.mark.parametrize('changed', [False, True])
def test_fresh_quality_request_hashes_sources_before_and_after_projection(monkeypatch, changed):
    import report_quality_audit
    monkeypatch.setattr(module,'_install_readonly_boundary',lambda:None)
    monkeypatch.setattr(module,'tracking_rules_revision',lambda:module._RULES_REVISION)
    versions=iter(['before','after' if changed else 'before'])
    calls=[]
    def fingerprint(_):
        calls.append('hash')
        return next(versions)
    def compute(*args, **kwargs):
        calls.append('project')
        return {'items':['fresh']}
    monkeypatch.setattr(module,'_quality_read_revision',fingerprint)
    monkeypatch.setattr(report_quality_audit,'build_indexed_report_quality_audit',compute)
    request=('quality_audit','reports',module._RULES_REVISION,'preparation-tracking-revision')
    if changed:
        with pytest.raises(PerformanceReadUnavailable,match='quality_sources_changed'):
            module._compute_readonly_quality(request)
    else:
        assert module._compute_readonly_quality(request)=={'items':['fresh']}
    assert calls==['hash','project','hash']
