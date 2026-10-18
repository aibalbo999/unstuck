"""Isolation, bounded in-flight work and fresh reads after each completion."""
import asyncio
from concurrent.futures import Future
import sqlite3
import socket
import pytest
from performance_read_executor import PerformanceReadExecutor, _compute_readonly_performance

class Executor:
    def __init__(self):self.calls=[];self.closed=[]
    def submit(self, fn, path):
        future=Future();self.calls.append((fn,path,future));return future
    def shutdown(self, **kwargs):self.closed.append(kwargs)

def test_overlapping_reads_share_only_running_computation_then_read_fresh():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor)
        first=asyncio.create_task(reader.read('one'));second=asyncio.create_task(reader.read('one'))
        await asyncio.sleep(0);assert len(executor.calls)==1
        executor.calls[0][2].set_result({'revision':1})
        assert await first==await second=={'revision':1}
        third=asyncio.create_task(reader.read('one'));await asyncio.sleep(0);assert len(executor.calls)==2
        executor.calls[1][2].set_result({'revision':2});assert await third=={'revision':2}
        reader.close();assert executor.closed==[{'wait':False,'cancel_futures':False}]
    asyncio.run(scenario())

def test_cancelled_caller_does_not_cancel_or_duplicate_running_read():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor)
        first=asyncio.create_task(reader.read('one'));await asyncio.sleep(0);first.cancel()
        with pytest.raises(asyncio.CancelledError):await first
        assert not executor.calls[0][2].cancelled()
        second=asyncio.create_task(reader.read('one'));await asyncio.sleep(0);assert len(executor.calls)==1
        reader.close();assert not executor.calls[0][2].cancelled()
        executor.calls[0][2].set_result({'ok':True});assert await second=={'ok':True}
    asyncio.run(scenario())

def test_other_directory_cannot_queue_behind_active_read():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor)
        first=asyncio.create_task(reader.read('one'));await asyncio.sleep(0)
        with pytest.raises(RuntimeError,match='performance_reader_busy'):await reader.read('two')
        assert len(executor.calls)==1;executor.calls[0][2].set_result({});await first;reader.close()
    asyncio.run(scenario())

def test_worker_exception_is_visible_and_next_completed_read_is_not_cached():
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor)
        first=asyncio.create_task(reader.read('one'));await asyncio.sleep(0)
        executor.calls[0][2].set_exception(ValueError('invalid saved data'))
        with pytest.raises(ValueError,match='invalid saved data'):await first
        second=asyncio.create_task(reader.read('one'));await asyncio.sleep(0)
        executor.calls[1][2].set_result({'ok':True});assert await second=={'ok':True};reader.close()
    asyncio.run(scenario())

def test_child_boundary_reads_existing_db_and_denies_writes_network(monkeypatch,tmp_path):
    import decision_tracking_service
    import performance_read_executor as module
    monkeypatch.setattr(module, '_CHILD_BOUNDARY_INSTALLED', False)
    path=tmp_path/'existing.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE evidence(value INTEGER)');conn.execute('INSERT INTO evidence VALUES(76)')
    original_connect=sqlite3.connect
    original_network={key:getattr(socket,key) for key in ['create_connection','getaddrinfo']}
    original_methods={key:getattr(socket.socket,key) for key in ['connect','connect_ex']}
    def compute(output):
        assert output=='saved-output'
        with sqlite3.connect(path) as conn:
            assert conn.execute('SELECT value FROM evidence').fetchone()[0]==76
            with pytest.raises(sqlite3.OperationalError,match='readonly'):conn.execute('UPDATE evidence SET value=0')
        with pytest.raises(sqlite3.OperationalError):sqlite3.connect(tmp_path/'new.sqlite3')
        with pytest.raises(OSError,match='cannot contact'):socket.create_connection(('127.0.0.1',8080))
        return {'unchanged':76}
    monkeypatch.setattr(decision_tracking_service,'compute_tracking_performance_stats',compute)
    try:
        assert _compute_readonly_performance('saved-output')=={'unchanged':76}
        wrapped_connect=sqlite3.connect
        assert _compute_readonly_performance('saved-output')=={'unchanged':76}
        assert sqlite3.connect is wrapped_connect
    finally:
        sqlite3.connect=original_connect
        for key,value in original_network.items():setattr(socket,key,value)
        for key,value in original_methods.items():setattr(socket.socket,key,value)
    assert not (tmp_path/'new.sqlite3').exists()

def test_actual_route_uses_injected_reader_for_every_get():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.performance import PerformanceRouteDeps,create_performance_router
    calls=[]
    async def read(path):calls.append(path);return {'read_number':len(calls)}
    app=FastAPI();app.include_router(create_performance_router(PerformanceRouteDeps(lambda:'saved',read)))
    with TestClient(app) as client:
        assert client.get('/api/performance/stats').json()=={'read_number':1}
        assert client.get('/api/performance/stats').json()=={'read_number':2}
    assert calls==['saved','saved']

def test_daily_dashboard_uses_same_injected_reader(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api_routes.watchlist as route
    monkeypatch.setattr(route.report_history_service,'list_reports',lambda **kw:{})
    monkeypatch.setattr(route,'_build_quality_audit_or_unavailable',lambda *a:{})
    monkeypatch.setattr(route.watchlist_service,'list_watchlist_with_report_alerts',lambda *a,**kw:{})
    monkeypatch.setattr(route.market_screener,'list_auto_screener_watchlist',lambda *a,**kw:{})
    monkeypatch.setattr(route.job_observability,'build_ops_dashboard_snapshot',lambda **kw:{})
    monkeypatch.setattr(route,'get_delivery_audit_summary',lambda:{})
    monkeypatch.setattr(route,'build_free_mode_contract',lambda:{})
    monkeypatch.setattr(route,'build_daily_decision_dashboard',lambda **kw:{'performance':kw['performance']})
    monkeypatch.setattr(route.decision_tracking_service,'compute_tracking_performance_stats',lambda *a:pytest.fail('must use isolated adapter'))
    calls=[]
    async def read(path):calls.append(path);return {'fresh':76}
    deps=route.WatchlistRouteDeps(lambda:'saved',lambda:None,lambda *a:None,lambda *a:None,lambda *a:None,lambda *a:None,read)
    app=FastAPI();app.include_router(route.create_watchlist_router(deps))
    with TestClient(app) as client:assert client.get('/api/watchlist/daily-dashboard').json()=={'performance':{'fresh':76}}
    assert calls==['saved']

def test_broken_child_is_not_reused_for_next_request():
    from concurrent.futures.process import BrokenProcessPool
    async def scenario():
        executors=[Executor(),Executor()];reader=PerformanceReadExecutor(lambda:executors.pop(0))
        first=asyncio.create_task(reader.read('one'));await asyncio.sleep(0);failed=reader._executor
        failed.calls[0][2].set_exception(BrokenProcessPool('child unavailable'))
        with pytest.raises(BrokenProcessPool):await first
        assert failed.closed==[{'wait':False,'cancel_futures':False}]
        second=asyncio.create_task(reader.read('one'));await asyncio.sleep(0)
        assert reader._executor is not failed
        reader._executor.calls[0][2].set_result({'ok':True});assert await second=={'ok':True};reader.close()
    asyncio.run(scenario())

def test_timeout_keeps_one_running_read_and_repeated_calls_do_not_spawn():
    from performance_read_executor import PerformanceReadUnavailable
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor,timeout_seconds=.01)
        for _ in range(2):
            with pytest.raises(PerformanceReadUnavailable,match='performance_read_timeout'):await reader.read('one')
        assert len(executor.calls)==1 and not executor.calls[0][2].cancelled()
        executor.calls[0][2].set_result({'late_but_valid':True});reader.close()
    asyncio.run(scenario())

def test_close_rejects_new_reads_and_reopen_waits_for_natural_completion():
    from performance_read_executor import PerformanceReadUnavailable
    async def scenario():
        executor=Executor();reader=PerformanceReadExecutor(lambda:executor)
        first=asyncio.create_task(reader.read('one'));await asyncio.sleep(0);reader.close()
        with pytest.raises(PerformanceReadUnavailable,match='closed'):await reader.read('one')
        with pytest.raises(PerformanceReadUnavailable,match='finishing_previous'):reader.open()
        assert len(executor.calls)==1 and not executor.calls[0][2].cancelled()
        executor.calls[0][2].set_result({});await first;reader.open()
        assert reader._closed is False
    asyncio.run(scenario())

def test_route_returns_explicit_503_without_stale_stats():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api_routes.performance import PerformanceRouteDeps,create_performance_router
    async def read(path):return {'status':'unavailable','reason':'performance_read_timeout'}
    app=FastAPI();app.include_router(create_performance_router(PerformanceRouteDeps(lambda:'saved',read)))
    with TestClient(app) as client:
        response=client.get('/api/performance/stats')
        assert response.status_code==503
        assert response.json()=={'status':'unavailable','reason':'performance_read_timeout'}

def test_shared_adapter_does_not_replace_timeout_with_saved_numbers(monkeypatch):
    import performance_read_executor as module
    async def fail(path):raise module.PerformanceReadUnavailable('performance_read_timeout')
    monkeypatch.setattr(module.performance_reads,'read',fail)
    payload=asyncio.run(module.read_performance_stats('saved'))
    assert payload['population']['credible_strategy_performance'] is False
    assert payload['status']=='unavailable' and 'summary' not in payload
