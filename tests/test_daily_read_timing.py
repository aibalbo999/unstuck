import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest
from daily_read_timing import DailyReadTiming

def test_passthrough_identity_without_payload(caplog):
    caplog.set_level(logging.INFO,logger='uvicorn.error');sentinel={'private':'SECRET'}
    async def run():
        async with DailyReadTiming() as t:
            assert await t.thread_read('reports',lambda:sentinel) is sentinel
            async def read():return sentinel
            assert await t.await_read('quality',read) is sentinel
            assert t.sync_read('builder',lambda:sentinel) is sentinel
            return t.request_id
    identifier=asyncio.run(run())
    assert all('request_id='+identifier in r.message for r in caplog.records)
    assert 'SECRET' not in caplog.text
    assert 'queue_seconds=' in caplog.text and 'response_ready' in caplog.text

def test_error_identity_without_payload(caplog):
    caplog.set_level(logging.INFO,logger='uvicorn.error');error=ValueError('SECRET')
    async def run():
        async with DailyReadTiming() as t:
            async def read():raise error
            await t.await_read('quality',read)
    with pytest.raises(ValueError) as exc:asyncio.run(run())
    assert exc.value is error
    assert 'event=error' in caplog.text and 'SECRET' not in caplog.text

def test_cancel_preserves_running_worker(caplog):
    caplog.set_level(logging.INFO,logger='uvicorn.error');release=threading.Event();started=threading.Event();finished=threading.Event()
    def worker():started.set();release.wait(2);finished.set();return 'ok'
    async def run():
        loop = asyncio.get_running_loop()
        previous_pool = loop._default_executor
        pool = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(pool)
        try:
            async with DailyReadTiming() as t:
                task=asyncio.create_task(t.thread_read('reports',worker))
                while not started.is_set():await asyncio.sleep(0)
                task.cancel()
                try:await task
                finally:release.set()
        finally:
            release.set()
            loop._default_executor = previous_pool
            pool.shutdown(wait=True)
    with pytest.raises(asyncio.CancelledError):asyncio.run(run())
    # The read uses a dedicated executor; explicitly join its completion.
    assert finished.wait(2), "cancelled await must not stop the running read"
    assert 'await_cancelled' in caplog.text and 'stage=request event=cancelled' in caplog.text
