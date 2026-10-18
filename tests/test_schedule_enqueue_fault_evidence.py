"""Diagnostic of current schedule contract; injected failure stays in isolated DB."""
from datetime import datetime
from types import SimpleNamespace
import pytest
import watchlist_service
import watchlist_scheduler

def test_enqueue_failure_keeps_unsubmitted_slots_retryable(monkeypatch,tmp_path):
    monkeypatch.setattr(watchlist_service,'WATCHLIST_PATH',tmp_path/'watchlist.json')
    watchlist_service.reset_watchlist_store_for_tests()
    for ticker in ('2308.TW','3324.TWO'):
        watchlist_service.upsert_watchlist_item({'ticker':ticker,'pipeline':'v4','enabled':True,'schedule_slots':['post_market']})
    now=datetime(2026,10,7,19,0,tzinfo=watchlist_service.TAIPEI)
    real_claim=watchlist_service.claim_due_watchlist_items
    monkeypatch.setattr(watchlist_service,'claim_due_watchlist_items',lambda:real_claim(now))
    def enqueue(*a,**kw):raise ConnectionError('isolated redis unavailable')
    created=[]
    result = watchlist_scheduler._run_due_watchlist_batch(create_job=lambda t,p,**kw:created.append((t,p)) or kw['job_id'],find_active_job=lambda t,p:{},task_queue=SimpleNamespace(enqueue_once=enqueue),run_stock_analysis_job=lambda *a:None,emit_log=lambda _:None)
    assert len(result['errors']) == 2 and result['success'] is False
    assert len(created)==2
    retryable = real_claim(now)
    assert {i['ticker'] for i in retryable} == {'2308.TW', '3324.TWO'}
