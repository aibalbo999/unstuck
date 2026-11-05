"""Native writer admission, with synthetic bytes and no external provider calls."""
import importlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SHARED = Path('/Volumes/X10 Pro Mac/project-system-tools/work')
sys.path.insert(0, str(SHARED))
import shared_capacity


@pytest.fixture
def low_space(monkeypatch):
    monkeypatch.setattr(shared_capacity, 'available_bytes', lambda: 0)


def test_report_refuses_before_artifact_or_sidecar_changes(tmp_path, low_space):
    from storage.report_storage import LocalFileStorage
    storage = LocalFileStorage(tmp_path/'reports')
    with pytest.raises(RuntimeError):
        storage.save_report('test.html', b'new report', content_type='text/html')
    assert list((tmp_path/'reports').iterdir()) == []


def test_report_reader_remains_available(tmp_path, monkeypatch):
    from storage.report_storage import LocalFileStorage
    storage = LocalFileStorage(tmp_path/'reports')
    storage.save_report('test.html', b'preserved report', content_type='text/html')
    monkeypatch.setattr(shared_capacity, 'available_bytes', lambda: 0)
    assert storage.get_report('test.html').content == b'preserved report'


def test_original_archive_refuses_before_directory_creation(tmp_path, monkeypatch, low_space):
    import runtime_paths
    from official_response_evidence import archive_response
    monkeypatch.setattr(runtime_paths, 'current_runtime_paths', lambda: SimpleNamespace(cache_dir=tmp_path/'cache'))
    result = archive_response(b'synthetic complete original', source_url='https://example.invalid/source', retrieved_at=1)
    assert result['status'] == 'unavailable'
    assert not (tmp_path/'cache').exists()


def test_existing_original_remains_readable_and_reusable(tmp_path, monkeypatch):
    import runtime_paths
    from official_response_evidence import archive_response, read_response
    monkeypatch.setattr(runtime_paths, 'current_runtime_paths', lambda: SimpleNamespace(cache_dir=tmp_path/'cache'))
    body=b'synthetic complete original'
    first=archive_response(body,source_url='https://example.invalid/source',retrieved_at=1)
    monkeypatch.setattr(shared_capacity, 'available_bytes', lambda: 0)
    second=archive_response(body,source_url='https://example.invalid/source',retrieved_at=1)
    assert first == second and read_response(first) == body


def test_cache_write_refuses_without_changing_prior_value_or_expiry(tmp_path, monkeypatch):
    from cache_backends import SqliteCacheBackend
    import sqlite3
    path=tmp_path/'provider.sqlite3';cache=SqliteCacheBackend(path)
    cache.set_json('same-key', {'state':'unknown'}, ttl_seconds=600)
    with sqlite3.connect(path) as connection:
        before=connection.execute('SELECT * FROM cache_entries').fetchall()
    monkeypatch.setattr(shared_capacity, 'available_bytes', lambda: 0)
    with pytest.raises(RuntimeError):cache.set_json('same-key', {'state':'passed'}, ttl_seconds=1000)
    assert cache.peek_json('same-key') == {'state':'unknown'}
    with sqlite3.connect(path) as connection:
        assert connection.execute('SELECT * FROM cache_entries').fetchall() == before


def test_bounded_source_refuses_before_creating_child(monkeypatch, low_space):
    import bounded_curl_process as source
    monkeypatch.setattr(shared_capacity, 'volume_guard', lambda: None)
    child=Mock(side_effect=AssertionError('No source process may start'))
    monkeypatch.setattr(source.subprocess, 'Popen', child)
    parts, code, error=source.collect_capped_process(['/usr/bin/false'],time.monotonic()+5,body_limit=4096)
    child.assert_not_called()
    assert parts['process_started'] is False and parts['body_bytes_read'] == 0
    assert error == 'storage_capacity_unavailable'


def test_bundle_refuses_before_any_artifact_or_index_change(tmp_path, low_space):
    from report_persistence import persist_report_bundle
    from storage.report_storage import LocalFileStorage
    storage=LocalFileStorage(tmp_path/'reports');repository=Mock()
    with pytest.raises(RuntimeError):
        persist_report_bundle(filename='2308_TW_v2_report_20260626_120000.html',
            html_content='<html>synthetic</html>',markdown_content='synthetic',
            data_snapshot={'ticker':'2308.TW','data_trust':{'status':'fresh'}},
            storage=storage,output_dir=str(storage._root),repository=repository)
    assert list(storage._root.iterdir()) == []
    assert repository.mock_calls == []


def test_backup_refuses_before_copy_vacuum_or_pruning(tmp_path, monkeypatch):
    import sqlite3,hashlib
    from database_maintenance import maintain_sqlite_databases
    source=tmp_path/'state.sqlite3'
    with sqlite3.connect(source) as connection:
        connection.execute('CREATE TABLE preserved (status TEXT)')
        connection.execute("INSERT INTO preserved VALUES ('unknown')")
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(shared_capacity,'available_bytes',lambda:0)
    with pytest.raises(RuntimeError):
        maintain_sqlite_databases({'cache_db':str(source)},backup_dir=str(tmp_path/'backup'),write=True)
    assert not (tmp_path/'backup').exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_cache_migration_refuses_before_any_destination(tmp_path, monkeypatch):
    import sqlite3,hashlib
    from cache_backends import SqliteCacheBackend
    from provider_json_cache_migration import copy_cache_entries
    source=tmp_path/'legacy.sqlite3';cache=SqliteCacheBackend(source)
    cache.set_json('cooldown',{'retry_after_epoch':time.time()+600},ttl_seconds=600);cache.close()
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    monkeypatch.setattr(shared_capacity,'available_bytes',lambda:0)
    with pytest.raises(RuntimeError):copy_cache_entries(source,tmp_path/'new'/'provider.sqlite3')
    assert not (tmp_path/'new').exists()
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_native_and_other_writer_share_ledger_and_release(tmp_path,monkeypatch):
    from storage.capacity import reserve_write,StorageCapacityUnavailable
    import threading
    original=shared_capacity.Reservation;registry=tmp_path/'claims'
    def reservation(peak,reserve,reason,**kwargs):
        return original(peak,0,reason,project_root=kwargs['project_root'],directory=registry,available_fn=lambda:100000)
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    with reserve_write(tmp_path,1,'native bounded writer') as lease:
        denied=[]
        def other_writer():
            try:
                with original(50000,0,'another project writer',project_root=tmp_path,directory=registry,available_fn=lambda:100000):pass
            except RuntimeError:denied.append(True)
        thread=threading.Thread(target=other_writer);thread.start();thread.join(timeout=5)
        assert not thread.is_alive() and denied == [True]
        with reserve_write(tmp_path,1,'nested same bounded bundle') as nested:
            assert nested.id == lease.id
        with pytest.raises(StorageCapacityUnavailable):
            with reserve_write(tmp_path,100000,'undeclared larger nested writer'):pass
        assert lease.receipt()['physical_bytes_reserved'] == 0
    assert list(registry.glob('*.json')) == []
    with original(100000,0,'released capacity',project_root=tmp_path,directory=registry,available_fn=lambda:100000):pass


def test_unknown_write_size_refuses_without_business_files(tmp_path):
    from storage.capacity import reserve_write
    with pytest.raises(ValueError):
        with reserve_write(tmp_path,None,'unknown batch'):pass
    assert list(tmp_path.iterdir()) == []


def test_create_only_bundle_uses_one_enclosing_claim_and_preserves_bytes(tmp_path,monkeypatch):
    from report_persistence import persist_report_bundle
    from storage.report_storage import LocalFileStorage
    from storage.create_only_reports import publication_is_pending
    storage=LocalFileStorage(tmp_path/'reports');repository=Mock()
    repository.exists.return_value=False;repository.insert.return_value={'indexed':True}
    name='2308_TW_v2_report_20260626_120000.html'
    calls=[];original=shared_capacity.Reservation
    def reservation(*args,**kwargs):
        lease=original(*args,**kwargs);calls.append(lease);return lease
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    result=persist_report_bundle(filename=name,html_content='<html>synthetic</html>',markdown_content='synthetic',
        data_snapshot={'ticker':'2308.TW','data_trust':{'status':'fresh'}},
        storage=storage,output_dir=str(storage._root),repository=repository,create_only=True)
    assert len(calls)==1 and calls[0].receipt()['state']=='completed'
    assert storage.get_report(result['html_key']).content==b'<html>synthetic</html>'
    assert not publication_is_pending(storage._root,name)


def test_create_only_low_capacity_does_not_leave_attempt_marker(tmp_path,low_space):
    from storage.report_storage import LocalFileStorage
    from storage.create_only_reports import create_only_bundle
    storage=LocalFileStorage(tmp_path/'reports')
    with pytest.raises(RuntimeError):
        with create_only_bundle(storage,output_dir=str(storage._root),filename='test.html',
                candidates=['test.html'],contents=[('test.html',b'new','text/html')]) as write:
            write()
    assert list(storage._root.iterdir())==[]


@pytest.mark.parametrize('asynchronous',[False,True])
def test_model_capacity_refuses_before_key_or_events(tmp_path,monkeypatch,low_space,asynchronous):
    import asyncio
    from agent_runtime import llm_calls
    from storage.capacity import StorageCapacityUnavailable
    acquire=Mock(side_effect=AssertionError('key admission must not run'))
    events=Mock(side_effect=AssertionError('business events must not run'))
    monkeypatch.setattr(llm_calls,'acquire_key',acquire)
    monkeypatch.setattr(llm_calls,'acquire_key_async',acquire)
    monkeypatch.setattr(llm_calls,'emit_context_event',events)
    monkeypatch.setattr(llm_calls,'emit_context_event_async',events)
    with pytest.raises(StorageCapacityUnavailable):
        if asynchronous:asyncio.run(llm_calls._run_agent_once_async(1,{},object(),'synthetic','prompt'))
        else:llm_calls._run_agent_once(1,{},object(),'synthetic','prompt')
    acquire.assert_not_called();events.assert_not_called()


def test_child_async_task_has_independent_capacity_claim(tmp_path,monkeypatch):
    import asyncio
    from storage.capacity import reserve_write,StorageCapacityUnavailable
    original=shared_capacity.Reservation;registry=tmp_path/'async-claims'
    def reservation(peak,reserve,reason,**kwargs):
        return original(peak,0,reason,project_root=kwargs['project_root'],directory=registry,available_fn=lambda:100000)
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    async def child():
        with reserve_write(tmp_path,1,'child must count independently'):pass
    async def parent():
        with reserve_write(tmp_path,1,'parent active'):
            with pytest.raises(StorageCapacityUnavailable):await asyncio.create_task(child())
    asyncio.run(parent())
    assert list(registry.glob('*.json'))==[]


def test_report_bundle_admits_index_wal_before_content(tmp_path,monkeypatch):
    from report_persistence import persist_report_bundle
    from report_repository import ReportRepository
    from storage.report_storage import LocalFileStorage
    import report_index
    root=tmp_path/'reports';storage=LocalFileStorage(root)
    db=tmp_path/'index.sqlite3';db.write_bytes(b'x'*(1024*1024))
    monkeypatch.setattr(report_index,'CACHE_DB_PATH',str(db))
    original=shared_capacity.Reservation
    def reservation(peak,reserve,reason,**kwargs):
        return original(peak,0,reason,project_root=kwargs['project_root'],directory=tmp_path/'claims',available_fn=lambda:500000)
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    with pytest.raises(RuntimeError):
        persist_report_bundle(filename='2308_TW_v2_report_20260626_120000.html',html_content='html',markdown_content='md',
            data_snapshot={'ticker':'2308.TW','data_trust':{'status':'fresh'}},storage=storage,output_dir=str(root),repository=ReportRepository())
    assert list(root.iterdir())==[]
    assert db.read_bytes()==b'x'*(1024*1024)



def test_model_forecast_claim_releases_on_async_cancel(tmp_path,monkeypatch):
    import asyncio
    from storage.capacity import reserve_model_phase
    original=shared_capacity.Reservation;registry=tmp_path/'model-claims'
    monkeypatch.setenv('STOCK_AGENT_MODEL_STORAGE_FORECAST_BYTES','1024')
    def reservation(peak,reserve,reason,**kwargs):
        return original(peak,0,reason,project_root=kwargs['project_root'],directory=registry,available_fn=lambda:1000000)
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    async def run():
        started=asyncio.Event()
        @reserve_model_phase
        async def waiting():
            started.set();await asyncio.Event().wait()
        task=asyncio.create_task(waiting());await started.wait()
        assert len(list(registry.glob('*.json')))==1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    asyncio.run(run())
    assert list(registry.glob('*.json'))==[]


def test_actual_artifact_larger_than_model_forecast_readmits_without_replay(tmp_path,monkeypatch):
    from storage.capacity import reserve_model_phase
    from storage.report_storage import LocalFileStorage
    monkeypatch.setenv('STOCK_AGENT_MODEL_STORAGE_FORECAST_BYTES','1')
    claims=[];original=shared_capacity.Reservation;calls=[]
    def reservation(*args,**kwargs):
        lease=original(*args,**kwargs);claims.append(lease);return lease
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    @reserve_model_phase
    def synthetic_result():
        calls.append(True);return b'x'*200000
    payload=synthetic_result()
    storage=LocalFileStorage(tmp_path/'reports');storage.save_report('test.html',payload,content_type='text/html')
    assert calls==[True] and len(claims)==2
    assert claims[1].peak>claims[0].peak
    assert all(c.receipt()['state']=='completed' for c in claims)
    assert storage.get_report('test.html').content==payload


def test_unknown_model_forecast_refuses_before_call(monkeypatch):
    from storage.capacity import reserve_model_phase,StorageCapacityUnavailable
    monkeypatch.setenv('STOCK_AGENT_MODEL_STORAGE_FORECAST_BYTES','unknown')
    called=[]
    @reserve_model_phase
    def synthetic_result():called.append(True)
    with pytest.raises(StorageCapacityUnavailable):synthetic_result()
    assert called==[]


def test_index_read_stays_available_when_sync_write_is_refused(tmp_path,monkeypatch):
    import report_index
    from storage.capacity import StorageCapacityUnavailable
    monkeypatch.setattr(report_index,'CACHE_DB_PATH',str(tmp_path/'index.sqlite3'))
    with report_index._connect() as conn:
        before=conn.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    def deny(*args,**kwargs):raise StorageCapacityUnavailable('synthetic low capacity')
    monkeypatch.setattr(report_index,'sync_report_metadata',deny)
    rows,total=report_index.query_report_metadata(1,10,output_dir=str(tmp_path))
    assert rows==[] and total==before==0



def test_synthetic_cache_write_overhead_sample(tmp_path,monkeypatch):
    from contextlib import nullcontext
    import cache_backends
    from storage.capacity import reserve_write,sqlite_write_bytes
    count=8;payload={'status':'unknown','data':'x'*2048};samples={}
    for mode in ('baseline','individual_claim','bounded_batch'):
        cache=cache_backends.SqliteCacheBackend(tmp_path/(mode+'.sqlite3'))
        with monkeypatch.context() as patch:
            if mode=='baseline':patch.setattr(cache_backends,'reserve_write',lambda *args,**kwargs:nullcontext())
            phase=(reserve_write(cache._peek_db_path,sqlite_write_bytes(cache._peek_db_path,count*8192),'Synthetic bounded cache batch')
                   if mode=='bounded_batch' else nullcontext())
            started=time.perf_counter()
            with phase:
                for i in range(count):cache.set_json(str(i),payload,ttl_seconds=60)
            elapsed=time.perf_counter()-started
            assert all(cache.get_json(str(i))==payload for i in range(count))
            samples[mode]={'writes':count,'elapsed_seconds':elapsed,'seconds_per_write':elapsed/count}
        cache.close()
    print('SYNTHETIC_CAPACITY_OVERHEAD='+json.dumps(samples,sort_keys=True))



def test_snapshot_and_calendar_low_capacity_make_no_destination(tmp_path,monkeypatch,low_space):
    import data_trust_snapshot,market_calendar_store
    monkeypatch.setattr(data_trust_snapshot,'build_data_snapshot',lambda *args,**kwargs:{'status':'unknown'})
    with pytest.raises(RuntimeError):data_trust_snapshot.write_data_snapshot(tmp_path/'snapshot'/'new.json',{})
    with pytest.raises(RuntimeError):market_calendar_store.write_market_calendar({'market':'tw','year':2026,'holidays':[]},calendar_dir=str(tmp_path/'calendar'))
    assert list(tmp_path.iterdir())==[]


def test_snapshot_repair_low_capacity_preserves_original(tmp_path,low_space):
    from snapshot_maintenance import verify_snapshots
    path=tmp_path/'test.data.json';original=b'{"status":"unknown"}';path.write_bytes(original)
    assert verify_snapshots(str(tmp_path),write=False)['missing_hash']==1
    with pytest.raises(RuntimeError):verify_snapshots(str(tmp_path),write=True)
    assert path.read_bytes()==original


def test_legacy_snapshot_low_capacity_leaves_originals_and_index_untouched(tmp_path,monkeypatch,low_space):
    from storage.legacy_reports import migrate_legacy_reports
    import report_index
    monkeypatch.setattr(report_index,'CACHE_DB_PATH',str(tmp_path/'index.sqlite3'))
    path=tmp_path/'2330_v2_report_20260606_010000.html';path.write_text('<html>synthetic</html>')
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(RuntimeError):migrate_legacy_reports(str(tmp_path),dry_run=False)
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before


def test_checkpoint_bulk_cleanup_low_capacity_keeps_rows(tmp_path,low_space):
    import hashlib
    from test_checkpoint_maintenance import _create_checkpoint_db,_create_task_db
    from checkpoint_maintenance import cleanup_terminal_checkpoints
    tasks=tmp_path/'task.sqlite3';checkpoints=tmp_path/'checkpoints.sqlite3'
    _create_task_db(tasks,[('done-job','done')]);_create_checkpoint_db(checkpoints,['done-job'])
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (tasks,checkpoints)}
    with pytest.raises(RuntimeError):cleanup_terminal_checkpoints(checkpoint_db_path=str(checkpoints),task_db_path=str(tasks),write=True)
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (tasks,checkpoints)}


@pytest.mark.parametrize('asynchronous',[False,True])
def test_evidence_model_capacity_refuses_before_key(tmp_path,monkeypatch,low_space,asynchronous):
    import asyncio
    from agent_runtime import gemma_evidence_runtime as evidence
    from storage.capacity import StorageCapacityUnavailable
    acquire=Mock(side_effect=AssertionError('evidence key admission must not run'))
    monkeypatch.setattr(evidence,'acquire_key',acquire);monkeypatch.setattr(evidence,'acquire_key_async',acquire)
    with pytest.raises(StorageCapacityUnavailable):
        if asynchronous:asyncio.run(evidence.call_batch_async({}, {}, object()))
        else:evidence.call_batch({}, {}, object())
    acquire.assert_not_called()


def test_larger_actual_write_inside_forecast_takes_additional_claim(tmp_path,monkeypatch):
    from storage.capacity import reserve_write
    from storage.report_storage import LocalFileStorage
    original=shared_capacity.Reservation;claims=[]
    def reservation(*args,**kwargs):
        lease=original(*args,**kwargs);claims.append(lease);return lease
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    storage=LocalFileStorage(tmp_path/'reports')
    with reserve_write(tmp_path,1,'forecast',allow_nested_readmission=True):
        storage.save_report('test.html',b'x'*200000,content_type='text/html')
    assert len(claims)==2 and all(c.receipt()['state']=='completed' for c in claims)
    assert claims[1].receipt()['observations'][0]['other_active_remaining_bytes'] >= claims[0].peak


def test_optional_native_capsule_capacity_denial_keeps_arrival_response_and_one_request(monkeypatch, low_space):
    import httpx
    import external_http_client as client
    from institutional_http_capsule import request_spec, observe_get
    from official_institutional_source import _url, TPEX_SOURCE
    from provider_correlation import correlation_scope, source_operation
    from finmind_transport_receipts import receipt_observation_scope
    from datetime import datetime
    for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
        monkeypatch.delenv(key,raising=False)
    url=_url('TPEX','2026-10-05');raw=b'[{"unknown_preserved":true}]';calls=[]
    arrived=datetime.fromisoformat('2026-10-05T14:29:59.999999+00:00').timestamp()
    monkeypatch.setattr(client,'time',SimpleNamespace(time=lambda:arrived))
    def get(u,**kw):
        calls.append(u)
        return httpx.Response(200,content=raw,request=httpx.Request('GET',u))
    monkeypatch.setattr(client.httpx,'get',get)
    spec=request_spec('TPEX','2026-10-05',url,TPEX_SOURCE)
    with correlation_scope(ticker='5314.TWO',fetch_id='capacity-offline-arrival'),source_operation('institutional_trading','FinMind'),receipt_observation_scope(True),observe_get(spec) as holder:
        response=client.sync_get(url,provider=TPEX_SOURCE)
    assert response.content==raw and calls==[url]
    assert holder['receipt'] is None
    assert holder['received_at_epoch']<=arrived<datetime.fromisoformat('2026-10-05T14:30:00+00:00').timestamp()


@pytest.mark.parametrize('fail_index',[False,True])
def test_exact_admission_balance_finishes_or_restores_entire_report_bundle(tmp_path,monkeypatch,fail_index):
    from storage.report_storage import LocalFileStorage
    from report_persistence import persist_report_bundle
    storage=LocalFileStorage(tmp_path/'reports')
    name='2308_TW_v2_report_20260626_120000.html'
    repository=Mock()
    persist_report_bundle(filename=name,html_content='old html',markdown_content='old md',
        data_snapshot={'ticker':'2308.TW','unknown':True},storage=storage,output_dir=str(storage._root),repository=repository)
    paths=lambda:list(storage._root.rglob('*'))
    before={str(p.relative_to(storage._root)):p.read_bytes() for p in paths() if p.is_file()}
    def allocated():return sum(max(p.stat().st_size,p.stat().st_blocks*512) for p in paths() if p.is_file())
    initial=allocated();registry=tmp_path/'isolated-claims';original=shared_capacity.Reservation;claims=[]
    def reservation(peak,reserve,reason,**kw):
        def available():
            ledger=sum(p.stat().st_blocks*512 for p in registry.glob('*.json'))
            return peak-max(0,allocated()-initial)-ledger
        value=original(peak,0,reason,**kw,directory=registry,available_fn=available)
        claims.append(value);return value
    monkeypatch.setattr(shared_capacity,'Reservation',reservation)
    if fail_index:repository.upsert.side_effect=ValueError('synthetic final index refusal')
    def write():
        return persist_report_bundle(filename=name,html_content='new html'*1500,markdown_content='new md'*1200,
            data_snapshot={'ticker':'2308.TW','unknown':True,'payload':'x'*3000},
            storage=storage,output_dir=str(storage._root),repository=repository)
    if fail_index:
        with pytest.raises(ValueError,match='synthetic final index refusal'):write()
        assert {str(p.relative_to(storage._root)):p.read_bytes() for p in paths() if p.is_file()}==before
    else:
        result=write();assert storage.get_report(result['html_key']).content==b'new html'*1500
    assert len(claims)==1 and claims[0].receipt()['state']==('failed' if fail_index else 'completed')
    assert list(registry.glob('*.json'))==[]


def test_backup_destination_refuses_before_backup_checkpoint_vacuum_or_prune(tmp_path,monkeypatch):
    import sqlite3,hashlib
    import database_maintenance as maintenance
    source=tmp_path/'state.sqlite3'
    with sqlite3.connect(source) as conn:conn.execute('CREATE TABLE preserved(status TEXT)')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    effects=Mock(side_effect=AssertionError('Unadmitted backup or maintenance effect'))
    monkeypatch.setattr(maintenance,'_create_backup_if_needed',effects)
    monkeypatch.setattr(maintenance,'_checkpoint_and_vacuum',effects)
    monkeypatch.setattr(maintenance,'prune_backup_files',effects)
    from storage.capacity import StorageCapacityUnavailable
    with pytest.raises(StorageCapacityUnavailable):
        maintenance.maintain_sqlite_databases({'cache_db':str(source)},
            backup_dir='/private/tmp/stock-capacity-forbidden-backup',write=True)
    effects.assert_not_called()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
