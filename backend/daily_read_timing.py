"""Payload-free request-local diagnostics; never cache, bound or alter reads."""
import asyncio
import logging
from time import monotonic
from uuid import uuid4

LOGGER = logging.getLogger('uvicorn.error')

class DailyReadTiming:
    def __init__(self):
        self.request_id = uuid4().hex
        self.started = monotonic()

    def mark(self, stage, event, **measurements):
        LOGGER.info('daily_read request_id=%s stage=%s event=%s elapsed_seconds=%.6f%s',
                    self.request_id, stage, event, monotonic()-self.started,
                    ''.join(' %s=%.6f' % (name, value) for name, value in measurements.items()))

    async def __aenter__(self):
        self.mark('request', 'start')
        return self

    async def __aexit__(self, kind, value, traceback):
        self.mark('request', 'cancelled' if kind and issubclass(kind, asyncio.CancelledError)
                  else 'error' if kind else 'response_ready')
        return False

    def sync_read(self, stage, fn, *args, **kwargs):
        start = monotonic()
        self.mark(stage, 'start')
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            self.mark(stage, 'error', run_seconds=monotonic()-start)
            raise
        self.mark(stage, 'end', run_seconds=monotonic()-start)
        return result

    async def thread_read(self, stage, fn, *args, **kwargs):
        queued = monotonic()
        self.mark(stage, 'queued')
        def run():
            self.mark(stage, 'worker_start', queue_seconds=monotonic()-queued)
            return self.sync_read(stage, fn, *args, **kwargs)
        try:
            return await asyncio.to_thread(run)
        except asyncio.CancelledError:
            # to_thread cancellation cannot stop its running callable; record it.
            self.mark(stage, 'await_cancelled')
            raise

    async def await_read(self, stage, fn, *args, **kwargs):
        start = monotonic()
        self.mark(stage, 'await_start')
        try:
            result = await fn(*args, **kwargs)
        except asyncio.CancelledError:
            self.mark(stage, 'await_cancelled', wait_seconds=monotonic()-start)
            raise
        except BaseException:
            self.mark(stage, 'error', wait_seconds=monotonic()-start)
            raise
        self.mark(stage, 'await_end', wait_seconds=monotonic()-start)
        return result
