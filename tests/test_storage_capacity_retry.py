"""Native terminal capacity classification; no live model/source or RQ writes."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from test_analysis_retry_scheduling import retry_job, rerun_retry_job
from storage.capacity import StorageCapacityUnavailable, _shared


@pytest.mark.parametrize('asynchronous',[False,True])
def test_gemma_existing_retry_entry_refuses_once_before_key_provider_or_observation(monkeypatch, asynchronous):
    from agent_runtime import gemma_evidence_runtime as calls
    from workflow_graph import is_retryable_workflow_error
    count=[]
    def unavailable():count.append(True);return 0
    monkeypatch.setattr(_shared(),'available_bytes',unavailable)
    key=Mock(side_effect=AssertionError('No key/provider admission'))
    monkeypatch.setattr(calls,'acquire_key',key)
    monkeypatch.setattr(calls,'acquire_key_async',key)
    with pytest.raises(StorageCapacityUnavailable) as caught:
        if asynchronous:asyncio.run(calls.call_batch_with_retry_async(object(),{},object()))
        else:calls.call_batch_with_retry(object(),{},object())
    key.assert_not_called()
    assert len(count)==1 and not is_retryable_workflow_error(caught.value)


def test_report_capacity_denial_is_terminal_after_one_completed_pipeline(retry_job,monkeypatch,tmp_path):
    import analysis_jobs as jobs
    from storage.report_storage import LocalFileStorage
    from report_persistence import persist_report_bundle
    job,events,updates,saved=retry_job
    storage=LocalFileStorage(tmp_path/'reports');runs=[];persists=[]
    async def completed(request):
        runs.append(True)
        return SimpleNamespace(context={'data':request.data})
    async def persist(**kwargs):
        persists.append(True)
        return persist_report_bundle(filename='2308_TW_v2_report_20260626_120000.html',
            html_content='<html>completed synthetic output</html>',markdown_content='complete',
            data_snapshot={'ticker':'2308.TW','quality':'unknown'},storage=storage,
            output_dir=str(storage._root),repository=Mock())
    monkeypatch.setattr(jobs,'PIPELINE_RUNNER',SimpleNamespace(run_async=completed))
    monkeypatch.setattr(jobs,'attach_model_executions',lambda *a:None)
    monkeypatch.setattr(jobs,'build_operator_audit_notice',lambda *a:{'status':'passed'})
    monkeypatch.setattr(jobs,'render_and_persist_report',persist)
    monkeypatch.setattr(_shared(),'available_bytes',lambda:0)
    assert asyncio.run(jobs.run_stock_analysis_job_async('job-deferred','TEST','v4'))==''
    assert runs==[True] and persists==[True] and saved==[]
    assert job.retries_left==3 and job.retry_intervals==[60,300,900]
    assert updates[-1][0]=='error' and events[-1]['phase']=='storage_capacity_refused'
    assert events[-1]['retry_scheduled'] is False
    assert list(storage._root.iterdir())==[]


def test_report_rerun_capacity_denial_returns_terminal_result_without_queue_retry(rerun_retry_job,monkeypatch,tmp_path):
    import report_rerun_jobs as jobs
    job,events,updates=rerun_retry_job;calls=[]
    async def denied(*args,**kwargs):
        calls.append(True);raise StorageCapacityUnavailable('synthetic actual-write capacity refusal')
    monkeypatch.setattr(jobs.report_rerun_service,'rerun_report_analysis',denied)
    assert asyncio.run(jobs.run_report_rerun_job_async('rerun-deferred','sample.html',output_dir=str(tmp_path),storage=object()))==''
    assert calls==[True] and job.retries_left==2 and job.retry_intervals==[60,300]
    assert updates[-1][0]=='error' and events[-1]['phase']=='storage_capacity_refused'
    assert events[-1]['retry_scheduled'] is False


def test_optional_payload_cache_denial_preserves_same_observation_without_refetch(monkeypatch):
    from data_fetch import yfinance_payload as payload
    calls=[]
    def denied(*args):
        calls.append(args);raise StorageCapacityUnavailable('synthetic cache capacity refusal')
    monkeypatch.setattr(payload,'set_cache_json',denied)
    data={'ticker':'AAPL','current_price':123,'data_source_notes':[],
          'capacity_fixture_unknown':None,'source_audit':[]}
    result=payload.finalize_and_cache_legacy_payload(data=data,ticker='AAPL',original_cache_key='test:financial',
        provider=SimpleNamespace(name='explicit offline fixture'),fetch_started_epoch=1,
        skip_optional_http=True,enrichment_audit=[],fmp_quote_audit=None,
        monthly_revenue_audit=None,finmind_financial_fallback_audit=None)
    assert result is data and result['current_price']==123
    assert result['capacity_fixture_unknown'] is None and len(calls)==1
    assert not result.get('error')
