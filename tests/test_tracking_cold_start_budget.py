"""Measured cold and warm tracking reads must remain bounded and fresh."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

import tracking_read_executor as module
import pytest
from concurrent.futures import Future
from performance_read_executor import PerformanceReadExecutor, PerformanceReadUnavailable


def test_cold_tracking_read_covers_measured_startup_burst_and_shares_work(monkeypatch):
    reader = module.tracking_reads
    executor = ThreadPoolExecutor(max_workers=1)
    for name, value in {'_executor': None, '_inflight': None, '_output_dir': None,
                        '_closed': False}.items():
        monkeypatch.setattr(reader, name, value)
    monkeypatch.setattr(reader, '_factory', lambda: executor)
    calls = []
    state = {'revision': 'same', 'delay': .57}
    monkeypatch.setattr(module, '_install_readonly_boundary', lambda: None)
    monkeypatch.setattr(module, 'tracking_rules_revision', lambda: module._RULES_REVISION)
    monkeypatch.setattr(module, 'tracking_read_revision', lambda _: state['revision'])

    def compute(path, *, sync_metadata):
        calls.append(path)
        time.sleep(state['delay'])
        return {'items': [{'revision': state['revision']}], 'enabled_count': 1}

    monkeypatch.setattr(module.service, 'list_decision_tracking', compute)
    class Preparation:
        async def read(self, request):
            return ('reports', state['revision'])
    monkeypatch.setattr(module, 'tracking_preparations', Preparation())
    real_timeout = asyncio.timeout
    monkeypatch.setattr(module.asyncio, 'timeout', lambda seconds: real_timeout(seconds / 100))

    async def scenario():
        a, b = await asyncio.gather(module.read_tracking_items('reports'), module.read_tracking_items('reports'))
        assert a == b == {'items': [{'revision': 'same'}], 'enabled_count': 1}
        assert calls == ['reports']
        # A completed success is never substituted for a new current read.
        state.update(revision='new', delay=0)
        fresh = await module.read_tracking_items('reports')
        assert fresh['items'] == [{'revision': 'new'}]
        assert calls == ['reports', 'reports']

    try:
        asyncio.run(scenario())
    finally:
        reader.close()
        executor.shutdown(wait=True)


def test_tracking_total_deadline_covers_bounded_preparation_and_cold_read(monkeypatch):
    deadlines = []
    actual = asyncio.timeout
    def record(seconds):
        deadlines.append(seconds)
        return actual(seconds)
    class Preparation:
        async def read(self, request): return ('reports', 'current')
    class Tracking:
        async def read(self, request): return {'items': []}
    monkeypatch.setattr(module.asyncio, 'timeout', record)
    monkeypatch.setattr(module, 'tracking_preparations', Preparation())
    monkeypatch.setattr(module, 'tracking_reads', Tracking())
    assert asyncio.run(module.read_tracking_items('reports')) == {'items': []}
    assert 20 + 57 < deadlines[0] <= 100


def test_warm_tracking_read_can_finish_measured_34_second_projection(monkeypatch):
    """A valid warm projection must not time out before the observed workload."""
    reader = module.tracking_reads
    executor = ThreadPoolExecutor(max_workers=1)
    for name, value in {'_executor': None, '_inflight': None, '_output_dir': None,
                        '_closed': False}.items():
        monkeypatch.setattr(reader, name, value)
    monkeypatch.setattr(reader, '_factory', lambda: executor)
    monkeypatch.setattr(module, '_install_readonly_boundary', lambda: None)
    monkeypatch.setattr(module, 'tracking_rules_revision', lambda: module._RULES_REVISION)
    state = {'revision': 'cold', 'delay': 0}
    monkeypatch.setattr(module, 'tracking_read_revision', lambda _: state['revision'])
    calls = []

    def compute(path, *, sync_metadata):
        calls.append(state['revision'])
        time.sleep(state['delay'])
        return {'items': [{'revision': state['revision']}]}

    monkeypatch.setattr(module.service, 'list_decision_tracking', compute)
    class Preparation:
        async def read(self, request): return ('reports', state['revision'])
    monkeypatch.setattr(module, 'tracking_preparations', Preparation())
    real_timeout = asyncio.timeout
    monkeypatch.setattr(module.asyncio, 'timeout', lambda seconds: real_timeout(seconds / 100))

    async def scenario():
        assert await module.read_tracking_items('reports') == {'items': [{'revision': 'cold'}]}
        state.update(revision='warm-current', delay=.34)
        a, b = await asyncio.gather(module.read_tracking_items('reports'), module.read_tracking_items('reports'))
        assert a == b == {'items': [{'revision': 'warm-current'}]}
        assert calls == ['cold', 'warm-current']
        state.update(revision='new-current', delay=0)
        assert await module.read_tracking_items('reports') == {'items': [{'revision': 'new-current'}]}
        assert calls == ['cold', 'warm-current', 'new-current']

    try:
        asyncio.run(scenario())
    finally:
        reader.close()
        executor.shutdown(wait=True)


def test_cold_allowance_does_not_extend_warm_deadline_or_duplicate_timed_out_work():
    class Executor:
        def __init__(self): self.calls = []
        def submit(self, *args):
            future = Future()
            self.calls.append(future)
            return future
        def shutdown(self, **kwargs): pass
    async def scenario():
        executor = Executor()
        reader = PerformanceReadExecutor(lambda: executor, timeout_seconds=.01,
                                         cold_start_timeout_seconds=.1)
        first = asyncio.create_task(reader.read('same'))
        await asyncio.sleep(.025)  # Fits cold budget but exceeds warm budget.
        executor.calls[0].set_result({'first': True})
        assert await first == {'first': True}
        for _ in range(2):
            with pytest.raises(PerformanceReadUnavailable, match='read_timeout'):
                await reader.read('same')
        assert len(executor.calls) == 2
        assert not executor.calls[1].cancelled()
        executor.calls[1].set_result({'late': True})
        reader.close()
    asyncio.run(scenario())
