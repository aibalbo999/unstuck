"""Fault injection uses isolated storage only, never production report files."""
from types import SimpleNamespace
import pytest
from report_persistence import persist_report_bundle, report_bundle_keys_for_filename
from storage.report_storage import InMemoryStorage, LocalFileStorage

@pytest.mark.parametrize('local',[False,True])
@pytest.mark.parametrize('fault',['second_write','write_then_raise','index'])
def test_failed_publication_preserves_preexisting_bundle(tmp_path, local, fault):
    storage=LocalFileStorage(tmp_path/'output') if local else InMemoryStorage()
    keys=report_bundle_keys_for_filename('TEST_v4_report_20261007_120000.html')
    entries=[(keys.html_key,b'old html','text/html'),(keys.md_key,b'old md','text/markdown'),(keys.data_key,b'{"old":true}','application/json')]
    for k,b,t in entries: storage.save_report(k,b,content_type=t)
    real_save=storage.save_report; calls=0
    def save(k,b,*,content_type):
        nonlocal calls
        calls+=1
        if calls==2 and fault=='second_write':raise OSError('injected write failure')
        result=real_save(k,b,content_type=content_type)
        if calls==2 and fault=='write_then_raise':raise OSError('injected late write failure')
        return result
    storage.save_report=save
    def index(*a,**kw):
        if fault=='index':raise OSError('injected index failure before commit')
        return {}
    with pytest.raises(OSError):
        persist_report_bundle(filename=keys.filename,html_content='new html',markdown_content='new md',data_snapshot={},storage=storage,repository=SimpleNamespace(upsert=index))
    assert [(storage.get_report(k).content if storage.get_report(k) else None) for k,b,t in entries]==[b for k,b,t in entries]
    assert [storage.get_report(k).metadata.content_type for k,b,t in entries]==[t for k,b,t in entries]

def test_failed_new_publication_removes_partial_bundle():
    storage=InMemoryStorage(); calls=0; real_save=storage.save_report
    def save(k,b,*,content_type):
        nonlocal calls
        calls+=1
        result=real_save(k,b,content_type=content_type)
        if calls==2:raise OSError('late write failure')
        return result
    storage.save_report=save
    with pytest.raises(OSError):
        persist_report_bundle(filename='TEST_v4_report_20261007_120000.html',html_content='new',markdown_content='new',data_snapshot={},storage=storage,repository=SimpleNamespace(upsert=lambda *a,**kw:{}))
    assert storage.list_reports()==[]

def test_recovery_failure_is_visible_instead_of_silently_swallowed():
    storage=InMemoryStorage(); keys=report_bundle_keys_for_filename('TEST_v4_report_20261007_120000.html')
    storage.save_report(keys.html_key,b'old',content_type='text/html')
    save=storage.save_report; calls=0
    def fail(k,b,*,content_type):
        nonlocal calls
        calls+=1
        if calls>=2:raise OSError('injected storage outage')
        return save(k,b,content_type=content_type)
    storage.save_report=fail
    with pytest.raises(ExceptionGroup,match='artifact recovery was incomplete') as exc:
        persist_report_bundle(filename=keys.filename,html_content='new',markdown_content='new',data_snapshot={},storage=storage,repository=SimpleNamespace(upsert=lambda *a,**kw:{}))
    assert len(exc.value.exceptions)==2

def test_sqlite_index_failure_rolls_back_index_and_artifacts(monkeypatch,tmp_path):
    import report_index
    from report_repository import DEFAULT_REPORT_REPOSITORY
    from report_repository import ReportListQuery
    filename='2308_TW_v4_report_20261007_120000.html'
    output=tmp_path/'output';storage=LocalFileStorage(output)
    kwargs=dict(filename=filename,storage=storage,output_dir=str(output),repository=DEFAULT_REPORT_REPOSITORY)
    persist_report_bundle(html_content='<html>old</html>',markdown_content='# old',data_snapshot={'ticker':'2308.TW'},**kwargs)
    query=ReportListQuery(page=1,limit=20,output_dir=str(output),sync_metadata=False)
    previous_index=DEFAULT_REPORT_REPOSITORY.query(query)
    keys=report_bundle_keys_for_filename(filename)
    previous_bytes={key:storage.get_report(key).content for key in (keys.html_key,keys.md_key,keys.data_key)}
    connect=report_index._connect
    class FaultConnection:
        def __enter__(self):
            self.context=connect();self.conn=self.context.__enter__();return self
        def execute(self,sql,*args):
            result=self.conn.execute(sql,*args)
            if 'INSERT INTO reports' in sql:raise OSError('injected failure after SQL before commit')
            return result
        def __exit__(self,*args):return self.context.__exit__(*args)
    with monkeypatch.context() as patch:
        patch.setattr(report_index,'_connect',FaultConnection)
        with pytest.raises(OSError):
            persist_report_bundle(html_content='<html>new</html>',markdown_content='# new',data_snapshot={'ticker':'2308.TW'},**kwargs)
    assert DEFAULT_REPORT_REPOSITORY.query(query)==previous_index
    assert {key:storage.get_report(key).content for key in previous_bytes}==previous_bytes
